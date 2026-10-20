"""Server-side source release. Loaded in memory for a read-only plan/probe."""
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import urllib.request

STAGE = Path(__file__).resolve().parent
LIVE_CHECK = """import json,sqlite3,urllib.request
from app.core.security import create_access_token
with sqlite3.connect('file:/app/data/app.db?mode=ro',uri=True) as db:
 assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 uid,version=db.execute('SELECT id,token_version FROM users WHERE is_active=1 AND is_superuser=1 LIMIT 1').fetchone()
 token=create_access_token(uid,expires_minutes=5,token_version=version)
 count=db.execute('SELECT count(*) FROM external_members').fetchone()[0]
def get(path):
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9500'+path,headers={'Authorization':'Bearer '+token}),timeout=30) as r:return json.load(r)
assert get('/api/health')['status']=='ok'
members=get('/api/external/members?size=1')
assert members['total']==count
for row in members['items']:assert not {'cookie','access_token','adobe_password'} & row.keys()
print(json.dumps({'api':'ok','database':'ok','members':count}))
"""


def validate(meta):
    assert re.fullmatch(r'[a-f0-9]{40}', meta['commit'])
    assert re.fullmatch(r'[a-f0-9]{40}', meta['base'])
    if 'release' in meta: assert re.fullmatch(r'[a-z0-9-]{1,100}', meta['release'])
    kinds = set()
    for name, info in meta['files'].items():
        path = PurePosixPath(name)
        assert re.fullmatch(r'[A-Za-z0-9_./@-]+', name) and path.as_posix() == name
        assert not path.is_absolute() and all(not p.startswith('.') for p in path.parts)
        assert info['before'] is None or re.fullmatch(r'[a-f0-9]{64}', info['before'])
        assert re.fullmatch(r'[a-f0-9]{64}', info['after'])
        if name.startswith('frontend-v2/') and path.suffix in ('.js', '.css', '.html') and '/tests/' not in name:
            kinds.add('frontend')
        else:
            assert name.startswith('backend/app/') and path.suffix == '.py'
            assert not name.startswith(('backend/app/db/', 'backend/app/models/'))
            kinds.add('backend')
    return 'backend' if 'backend' in kinds else 'frontend'


def probe(core, manifest=None):
    started = time.monotonic()
    current = core.inspect(core.CONTAINER)
    assert current['State']['Health']['Status'] == 'healthy'
    core.http_health()
    source = core.hashes() if manifest else {}
    state, files, mode = 'healthy', {}, None
    if manifest:
        mode = validate(manifest)
        for name, info in manifest['files'].items():
            runtime, host = source.get(name), core.digest(core.APP/'payload'/name)
            assert runtime == host, 'Host/runtime source mismatch: ' + name
            assert runtime in (info['before'], info['after']), 'Production diverged from --base: ' + name
            files[name] = 'current' if runtime == info['after'] else 'update'
        # Partial application after a disconnected release needs its original audit.
        assert len(set(files.values())) <= 1, 'Partially applied release; inspect prior audit before continuing'
        state = 'current' if all(v == 'current' for v in files.values()) else 'ready'
    return {'status': state, 'mode': mode, 'container': current['Id'], 'image': current['Config']['Image'],
            'files': files, 'server_seconds': round(time.monotonic()-started, 3)}


@contextlib.contextmanager
def phase(timings, name):
    start = time.monotonic()
    print('RELEASE_PHASE ' + name, flush=True)
    try:
        yield
    finally:
        timings[name] = round(timings.get(name, 0) + time.monotonic()-start, 3)


def lock_release(core):
    locks = []
    try:
        paths = [Path('/opt/adobe-relay/.release.lock')] + [core.APP/n for n in
            ('.release.lock', '.incremental-release.lock', '.local/deploy-login-batches.lock', '.local/monitor-release.lock')]
        for path in paths:
            handle = path.open('a')
            locks.append(handle)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return locks
    except BaseException:
        for handle in locks: handle.close()
        raise


def publish(core, base, files, release):
    """Stage all replacements, then dependencies before either HTML entrypoint."""
    pairs, remove = [], []
    for name in sorted(files, key=lambda n: (n.endswith('.html'), n)):
        source, target = base/'payload'/name, core.APP/'payload'/name
        remote = '/app/' + name
        if not source.is_file():
            target.unlink(missing_ok=True)
            remove.append(remote)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + target.name + '.' + release)
        shutil.copy2(source, temporary); os.replace(temporary, target)
        staged = remote + '.' + release
        core.run(['docker', 'exec', core.CONTAINER, 'mkdir', '-p', str(PurePosixPath(remote).parent)], stdout=subprocess.DEVNULL)
        core.run(['docker', 'cp', str(source), core.CONTAINER + ':' + staged], stdout=subprocess.DEVNULL)
        pairs.append((staged, remote))
    code = 'import os\npairs=' + repr(pairs) + '\nremove=' + repr(remove) + \
           '\nfor source,target in pairs:os.replace(source,target)\nfor path in remove:\n if os.path.exists(path):os.unlink(path)'
    core.run(['docker', 'exec', core.CONTAINER, 'python', '-c', code], stdout=subprocess.DEVNULL)


def compose_image(core, image):
    path = core.APP/'compose.yml'
    content, count = re.subn(r'(?m)^(    image:)\s*adobe-team-cookie:[^\s]+[ \t]*$',
                            lambda m: m[1]+' '+image, path.read_text())
    assert count == 1, 'Unexpected compose image declaration'
    temporary = path.with_suffix('.release')
    temporary.write_text(content); shutil.copymode(path, temporary); os.replace(temporary, path)


def frontend(core, meta, timings, action):
    locks = lock_release(core)
    try:
        files = tuple(meta['files'])
        backup = STAGE/'backup'
        if action != 'deploy':
            before, after = (json.loads((STAGE/n).read_text()) for n in ('before.json', 'after.json'))
            current = core.inspect(core.CONTAINER)
            assert current['Id'] == after['container'] and current['Image'] == after['runtime_image']
            assert core.hashes() == after['source_hashes'] and core.configs() == after['config_hashes'], 'Later release/configuration changes'
            assert core.other_containers() == after['other_containers']
            assert all(core.digest(core.APP/'payload'/n) == meta['files'][n]['after'] for n in files)
            assert core.inspect(before['rollback'])['Id'] == before['rollback_image_id']
            if action == 'check-rollback':
                print('Rollback guards passed; no application or data changed')
                return
            publish(core, backup, files, meta['release'])
            shutil.copy2(backup/'compose.yml', core.APP/'compose.yml')
            assert core.hashes() == before['source_hashes']
            core.http_health()
            core.save('rolled-back.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
            return
        assert not (STAGE/'before.json').exists(), 'Inspect the existing release audit before retrying'
        current = core.inspect(core.CONTAINER)
        assert current['Id'] == meta['container'] and current['Image'] == meta['source_image_id']
        assert current['State']['Health']['Status'] == 'healthy'
        assert current['Config']['Labels']['com.docker.compose.project.config_files'] == str(core.APP/'compose.yml')
        source, private, others = core.hashes(), core.configs(), core.other_containers()
        for name, info in meta['files'].items():
            assert source.get(name) == info['before'] and core.digest(core.APP/'payload'/name) == info['before'], 'Source changed after preflight'
            assert core.digest(STAGE/'payload'/name) == info['after'], 'Upload mismatch: '+name
        with phase(timings, 'backup'):
            backup.mkdir(mode=0o700)
            for name in files:
                target = backup/'payload'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                if (core.APP/'payload'/name).is_file(): shutil.copy2(core.APP/'payload'/name, target)
            shutil.copy2(core.APP/'compose.yml', backup/'compose.yml')
            core.backup_db(backup/'app.db')
            rollback = 'adobe-team-cookie:before-' + meta['release']
            core.run(['docker', 'commit', '--pause=false', core.CONTAINER, rollback], stdout=subprocess.DEVNULL)
            core.save('before.json', {'container': current['Id'], 'rollback': rollback,
                'rollback_image_id': core.inspect(rollback)['Id'], 'source_hashes': source, 'config_hashes': private})
        image = 'adobe-team-cookie:' + meta['commit']
        with phase(timings, 'build'):
            (STAGE/'Dockerfile').write_text('FROM '+rollback+'\n'+''.join(
                'COPY '+json.dumps(['payload/'+n, '/app/'+n])+'\n' for n in files)+
                'LABEL org.opencontainers.image.revision="'+meta['commit']+'"\n')
            core.run(['docker', 'build', '--network', 'none', '--pull=false', '-t', image, str(STAGE)])
            expected = source | {n:meta['files'][n]['after'] for n in files}
            assert core.hashes(image) == expected, 'Candidate changed unrelated files'
        assert core.hashes() == source and core.configs() == private and core.other_containers() == others
        changed = False
        try:
            with phase(timings, 'publish_and_verify'):
                changed = True
                publish(core, STAGE, files, meta['release'])
                compose_image(core, image)
                assert core.hashes() == expected
                for name in files:
                    assert core.digest(core.APP/'payload'/name) == meta['files'][name]['after']
                    url = 'http://127.0.0.1:9500/' + name.removeprefix('frontend-v2/')
                    with urllib.request.urlopen(url, timeout=15) as response:
                        assert hashlib.sha256(response.read()).hexdigest() == meta['files'][name]['after'], 'Served file mismatch: '+name
                now = core.inspect(core.CONTAINER)
                assert now['Id'] == current['Id'] and now['State']['StartedAt'] == current['State']['StartedAt']
                assert now['State']['Health']['Status'] == 'healthy' and core.other_containers() == others
                config_after = core.configs()
                assert {k:v for k,v in config_after.items() if k!=str(core.APP/'compose.yml')} == {k:v for k,v in private.items() if k!=str(core.APP/'compose.yml')}
                core.http_health()
                core.save('after.json', {'status':'deployed', 'mode':'frontend', 'commit':meta['commit'],
                    'image':image, 'image_id':core.inspect(image)['Id'], 'container':now['Id'], 'runtime_image':now['Image'],
                    'restarted':False, 'source_hashes':expected, 'config_hashes':config_after, 'other_containers':others})
        except BaseException:
            if changed:
                publish(core, backup, files, meta['release'])
                shutil.copy2(backup/'compose.yml', core.APP/'compose.yml')
                assert core.hashes() == source
                core.http_health()
                core.save('automatic-rollback.json', {'restored':True})
            raise
    finally:
        for handle in locks: handle.close()


def backend(core, meta, timings, action):
    core.FILES = tuple(meta['files'])
    core.CANDIDATE_CHECK = 'import ast,pathlib\n' + ''.join(
        'ast.parse(pathlib.Path('+repr('/app/'+n)+').read_text())\n' for n in core.FILES if n.endswith('.py')) + \
        "import app.main\nprint('CANDIDATE_SOURCE_IMPORT_OK')"
    core.LIVE_CHECK = LIVE_CHECK
    # Retain the existing rollback/idle/configuration/data guards and expose timings.
    for attribute, label in (('backup_db','database_backup'), ('switch','switch_and_health'), ('hashes','source_checks')):
        original = getattr(core, attribute)
        def timed(*args, _fn=original, _label=label, **kwargs):
            with phase(timings, _label): return _fn(*args, **kwargs)
        setattr(core, attribute, timed)
    original_run = core.run
    def run(args, **kwargs):
        label = {('docker','commit'):'snapshot', ('docker','build'):'build',
                 ('docker','compose'):'compose_update'}.get(tuple(args[:2]), 'candidate_check')
        with phase(timings, label): return original_run(args, **kwargs)
    core.run = run
    core.main(action)


def main(action):
    os.umask(0o077)
    started, timings = time.monotonic(), {}
    spec = importlib.util.spec_from_file_location('guarded_core', STAGE/'profile-invitation-release.py')
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    core.STAGE = STAGE
    meta = json.loads((STAGE/'manifest.json').read_text())
    mode = validate(meta)
    if action == 'deploy':
        with phase(timings, 'preflight'):
            report = probe(core, meta)
        if report['status'] == 'current':
            locks = lock_release(core)
            try:
                assert probe(core, meta)['status'] == 'current', 'Source changed after preflight'
                result = dict(report, restarted=False, status='already_current', commit=meta['commit'],
                              release=meta['release'], audit=str(STAGE), phases=timings)
                core.save('result.json', result)
                print('RELEASE_RESULT '+json.dumps(result), flush=True)
            finally:
                for handle in locks: handle.close()
            return
        else:
            meta['container'] = report['container']
            meta['source_image_id'] = core.inspect(core.CONTAINER)['Image']
            for name in meta['files']: meta['files'][name]['host_before'] = meta['files'][name]['before']
            core.save('manifest.json', meta)
    if mode == 'frontend': frontend(core, meta, timings, action)
    else: backend(core, meta, timings, action)
    if action == 'deploy':
        result = {'status':'deployed', 'mode':mode, 'commit':meta['commit'], 'release':meta['release'],
            'restarted':mode=='backend', 'server_seconds':round(time.monotonic()-started, 3), 'phases':timings,
            'audit':str(STAGE)}
        core.save('result.json', result)
        print('RELEASE_RESULT '+json.dumps(result), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('deploy','check-rollback','rollback'):
        raise SystemExit('Usage: incremental_remote.py deploy|check-rollback|rollback')
    main(sys.argv[1])
