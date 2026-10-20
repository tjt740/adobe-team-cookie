"""Release orchestration tests: synthetic Git, Docker and HTTP; no production writes."""
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
import tarfile
import time
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE/filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


client = load('release_client', 'release.py')
remote = load('release_remote', 'incremental_remote.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(['git', '-c', 'user.name=Release Test', '-c',
            'user.email=release@example.test', *args], cwd=tmp_path).decode().strip()
    git('init', '-q')
    (tmp_path/'payload/frontend-v2').mkdir(parents=True)
    (tmp_path/'payload/frontend-v2/a.js').write_text('old')
    git('add', '.'); git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')
    monkeypatch.setattr(client, 'ROOT', tmp_path)
    return tmp_path, git, base


def test_collect_committed_sources_and_small_archive(repo):
    root, git, base = repo
    (root/'payload/frontend-v2/a.js').write_text('new')
    (root/'payload/frontend-v2/tests').mkdir()
    (root/'payload/frontend-v2/tests/test_ui.py').write_text('test only')
    (root/'README.md').write_text('documentation')
    git('add', '.'); git('commit', '-qm', 'source')
    meta, contents = client.collect(base, 'HEAD')
    assert list(meta['files']) == ['frontend-v2/a.js']
    assert meta['files']['frontend-v2/a.js'] == {'before':digest(b'old'), 'after':digest(b'new')}
    assert len(meta['ignored']) == 2
    with tarfile.open(fileobj=io.BytesIO(client.package(meta, contents, {'incremental_remote.py':b'helper'}))) as tar:
        assert set(tar.getnames()) == {'manifest.json','incremental_remote.py','payload/frontend-v2/a.js'}
        assert tar.extractfile('payload/frontend-v2/a.js').read() == b'new'
    assert remote.validate(meta) == 'frontend'


@pytest.mark.parametrize('path', ['payload/backend/requirements.txt','payload/backend/app/db/init_db.py',
    'payload/backend/app/models/account.py','payload/backend/run_local.py','Dockerfile','compose.yml'])
def test_special_releases_are_not_silently_omitted(repo, path):
    root, git, base = repo
    file = root/path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('special change')
    git('add', '.'); git('commit', '-qm', 'special')
    with pytest.raises(ValueError): client.collect(base, 'HEAD')


def test_delete_and_symlink_rejected(repo):
    root, git, base = repo
    (root/'payload/frontend-v2/a.js').unlink()
    git('add', '.'); git('commit', '-qm', 'delete')
    with pytest.raises(ValueError, match='deletion'): client.collect(base, 'HEAD')
    git('reset', '--hard', base)
    (root/'payload/frontend-v2/b.js').symlink_to('/etc/passwd')
    git('add', '.'); git('commit', '-qm', 'link')
    with pytest.raises(ValueError, match='regular file'): client.collect(base, 'HEAD')


@pytest.mark.parametrize('name', ['../escape.js','frontend-v2/../../escape.js','/frontend-v2/a.js',
    'frontend-v2/a b.js','frontend-v2/.env.js','frontend-v2/a\nCOPY.js','backend/app/db/new.py'])
def test_client_and_server_reject_unsafe_paths(name):
    with pytest.raises(ValueError): client.source_path(name)
    with pytest.raises(AssertionError): remote.validate(dict(base='a'*40, commit='b'*40,
        files={name:dict(before=None, after='a'*64)}))


def test_master_detached_without_capture_pipe(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if '-M' in args:
            assert '-f' in args and '-N' in args
            assert kwargs['stdout'] == subprocess.DEVNULL
            assert kwargs['stderr'] != subprocess.PIPE
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(client.subprocess, 'run', run)
    with client.SSHSession('/synthetic/key') as session:
        assert len(session.socket) < 100
        assert '-M' not in session.command('print("quoted value")')
        assert 'ControlMaster=no' in session.command('pass')
    assert any('-O' in args and 'exit' in args for args in calls)


@pytest.fixture
def production(tmp_path, monkeypatch):
    app, stage = tmp_path/'app', tmp_path/'release'
    app.mkdir(); stage.mkdir()
    monkeypatch.setattr(remote, 'STAGE', stage)
    monkeypatch.setattr(remote, 'lock_release', lambda core: [])
    contents = {'frontend-v2/a.js':b'old', 'backend/app/main.py':b'unchanged backend'}
    for name, data in contents.items():
        file = app/'payload'/name; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(data)
    (app/'compose.yml').write_text('services:\n  app:\n    image: adobe-team-cookie:old\n')
    runtime, images, calls = dict(contents), {}, []
    container = {'Id':'container', 'Image':'image-old', 'State':{'StartedAt':'same', 'Health':{'Status':'healthy'}},
        'Config':{'Image':'adobe-team-cookie:old', 'Labels':{'com.docker.compose.project.config_files':str(app/'compose.yml')}}}
    def inspect(name):
        return json.loads(json.dumps(container)) if name == 'app-container' else {'Id':'id-'+name}
    def hashes(image=None):
        return {n:digest(v) for n,v in (images[image] if image else runtime).items() if Path(n).suffix in ('.js','.css','.html','.py')}
    def run(args, **kwargs):
        calls.append(args)
        if args[:2] == ['docker','commit']: images[args[-1]] = dict(runtime)
        elif args[:2] == ['docker','build']:
            image = args[args.index('-t')+1]
            images[image] = runtime | {n: (stage/'payload'/n).read_bytes() for n in meta['files']}
        elif args[:2] == ['docker','cp']:
            runtime[args[3].split(':/app/')[1]] = Path(args[2]).read_bytes()
        elif args[:4] == ['docker','exec','app-container','python']:
            values = {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(args[-1]).body if isinstance(n,ast.Assign)}
            for source, target in values['pairs']:
                runtime[target.removeprefix('/app/')] = runtime.pop(source.removeprefix('/app/'))
            for target in values['remove']: runtime.pop(target.removeprefix('/app/'), None)
        else:
            assert args[:4] == ['docker','exec','app-container','mkdir'], args
    def save(name, value): (stage/name).write_text(json.dumps(value))
    def backup(path): calls.append(['backup']); path.write_bytes(b'synthetic database backup')
    core = SimpleNamespace(APP=app, CONTAINER='app-container', inspect=inspect, hashes=hashes, run=run,
        save=save, backup_db=backup, digest=lambda p:digest(p.read_bytes()) if p.exists() else None,
        configs=lambda:{str(app/'compose.yml'):digest((app/'compose.yml').read_bytes()), '.env':'same'},
        other_containers=lambda:{'database':'same','sub2':'same'}, http_health=lambda:None)
    meta = dict(base='a'*40, commit='b'*40, release='test-source', container='container', source_image_id='image-old',
                files={'frontend-v2/a.js':dict(before=digest(b'old'), after=digest(b'new'))})
    (stage/'payload/frontend-v2').mkdir(parents=True)
    (stage/'payload/frontend-v2/a.js').write_bytes(b'new')
    monkeypatch.setattr(remote.urllib.request, 'urlopen', lambda url, **kw:io.BytesIO(runtime['frontend-v2/'+url.rsplit('/',1)[1]]))
    return SimpleNamespace(core=core, meta=meta, runtime=runtime, images=images, calls=calls, app=app, stage=stage)


def test_probe_is_read_only_and_detects_current_and_divergence(production):
    p = production
    report = remote.probe(p.core, p.meta)
    assert report['status'] == 'ready' and not p.calls and not list(p.stage.glob('*.json'))
    p.meta['files']['frontend-v2/a.js']['after'] = digest(b'old')
    assert remote.probe(p.core, p.meta)['status'] == 'current'
    p.meta['files']['frontend-v2/a.js']['before'] = digest(b'other')
    p.meta['files']['frontend-v2/a.js']['after'] = digest(b'new')
    with pytest.raises(AssertionError, match='diverged'): remote.probe(p.core, p.meta)
    assert not p.calls


def test_partial_release_requires_inspection(production):
    p = production
    p.meta['files']['backend/app/main.py'] = dict(before=digest(b'older'), after=digest(b'unchanged backend'))
    with pytest.raises(AssertionError, match='Partially applied'): remote.probe(p.core, p.meta)


def test_frontend_hot_release_is_durable_and_keeps_backend_and_container(production):
    p = production
    timings = {}
    remote.frontend(p.core, p.meta, timings, 'deploy')
    assert p.runtime == {'frontend-v2/a.js':b'new', 'backend/app/main.py':b'unchanged backend'}
    assert p.images['adobe-team-cookie:'+'b'*40] == p.runtime
    assert 'adobe-team-cookie:'+'b'*40 in (p.app/'compose.yml').read_text()
    after = json.loads((p.stage/'after.json').read_text())
    assert after['restarted'] is False and after['container'] == 'container'
    assert set(timings) == {'backup','build','publish_and_verify'}
    assert not any('compose' in c for c in p.calls)
    remote.frontend(p.core, p.meta, {}, 'check-rollback')
    remote.frontend(p.core, p.meta, {}, 'rollback')
    assert p.runtime['frontend-v2/a.js'] == b'old'
    assert 'adobe-team-cookie:old' in (p.app/'compose.yml').read_text()
    assert p.calls.count(['backup']) == 1


def test_frontend_verification_failure_restores_code_only(production, monkeypatch):
    p = production
    monkeypatch.setattr(remote.urllib.request, 'urlopen', lambda *a,**kw:io.BytesIO(b'cached old file'))
    with pytest.raises(AssertionError, match='Served file mismatch'):
        remote.frontend(p.core, p.meta, {}, 'deploy')
    assert p.runtime == {'frontend-v2/a.js':b'old', 'backend/app/main.py':b'unchanged backend'}
    assert (p.app/'payload/frontend-v2/a.js').read_bytes() == b'old'
    assert 'adobe-team-cookie:old' in (p.app/'compose.yml').read_text()
    assert (p.stage/'automatic-rollback.json').is_file()
    assert p.calls.count(['backup']) == 1  # No database restore.


def test_rollback_refuses_later_changes(production):
    p = production
    remote.frontend(p.core, p.meta, {}, 'deploy')
    (p.app/'compose.yml').write_text('a subsequent configuration change')
    with pytest.raises(AssertionError, match='Later release'):
        remote.frontend(p.core, p.meta, {}, 'rollback')
    assert p.runtime['frontend-v2/a.js'] == b'new'


def test_backend_retains_core_guards_and_uses_generic_smoke():
    calls = []
    core = SimpleNamespace(backup_db=lambda *a:None, switch=lambda *a:None, hashes=lambda *a:{}, run=lambda *a,**kw:None)
    core.main = lambda action:calls.append(action)
    remote.backend(core, dict(files={'backend/app/services/example.py':{}}), {}, 'deploy')
    assert calls == ['deploy'] and core.FILES == ('backend/app/services/example.py',)
    assert 'ast.parse' in core.CANDIDATE_CHECK and 'import app.main' in core.CANDIDATE_CHECK
    assert 'PRAGMA integrity_check' in core.LIVE_CHECK and 'Authorization' in core.LIVE_CHECK
    original = load('legacy_release', 'profile-invitation-release.py')
    assert 'CANDIDATE_PROFILE_SCHEMA_AND_IMPORT_OK' in original.CANDIDATE_CHECK
    assert 'profile_schema' in original.LIVE_CHECK


def test_current_release_exits_before_backup_build_or_restart(production, monkeypatch):
    p = production
    (p.stage/'profile-invitation-release.py').write_bytes((HERE/'profile-invitation-release.py').read_bytes())
    (p.stage/'manifest.json').write_text(json.dumps(p.meta))
    monkeypatch.setattr(remote, 'probe', lambda *a:dict(status='current', mode='frontend'))
    monkeypatch.setattr(remote, 'frontend', lambda *a:pytest.fail('current release must not publish'))
    monkeypatch.setattr(remote, 'backend', lambda *a:pytest.fail('current release must not restart'))
    remote.main('deploy')
    report = json.loads((p.stage/'result.json').read_text())
    assert report['status'] == 'already_current' and report['restarted'] is False
    assert 'preflight' in report['phases'] and not (p.stage/'backup').exists()
    assert not p.calls


def test_record_guard_detects_content_changes_without_exposing_credentials(tmp_path):
    core = load('protected_records_release', 'profile-invitation-release.py')
    core.APP = tmp_path
    (tmp_path/'data').mkdir()
    with sqlite3.connect(tmp_path/'data/app.db') as db:
        db.execute('CREATE TABLE settings (key TEXT, value TEXT)')
        db.execute("INSERT INTO settings VALUES ('example','synthetic-secret')")
        for name in ('users','adobe_accounts','adobe_members','external_members','emails'):
            db.execute('CREATE TABLE '+name+' (id INTEGER, value TEXT)')
            db.execute('INSERT INTO '+name+' VALUES (1,?)', ('synthetic-secret',))
    before = core.database_summary()
    assert 'synthetic-secret' not in json.dumps(before)
    with sqlite3.connect(tmp_path/'data/app.db') as db:
        db.execute("UPDATE external_members SET value='modified'")
    after = core.database_summary()
    assert before['external_member_ids'] == after['external_member_ids']
    assert before['protected_records'] != after['protected_records']


def bootstrap_fixture(tmp_path, code):
    meta = dict(release='transport-test', base='a'*40, commit='b'*40, files={})
    bundle = client.package(meta, {}, {'incremental_remote.py':code.encode(), 'profile-invitation-release.py':b''})
    bootstrap = client.BOOTSTRAP.replace('/opt/adobe-team-cookie', str(tmp_path/'app'))
    stage = tmp_path/'app/.local/releases/transport-test'
    return bundle, bootstrap, stage


def test_single_upload_runs_worker_and_streams_result(tmp_path):
    bundle, code, stage = bootstrap_fixture(tmp_path, "print('RELEASE_RESULT {\"status\":\"synthetic-ok\"}',flush=True)")
    result = subprocess.run([sys.executable,'-c',code],input=bundle,capture_output=True,timeout=10)
    assert result.returncode == 0, result.stderr.decode()
    assert 'synthetic-ok' in result.stdout.decode()
    assert (stage/'exit-code').read_text() == '0'
    assert 'synthetic-ok' in (stage/'deploy.log').read_text()
    assert '!payload/**' in (stage/'.dockerignore').read_text()


def test_transport_disconnect_does_not_kill_release_worker(tmp_path):
    bundle, code, stage = bootstrap_fixture(tmp_path, """import pathlib,time
print('RELEASE_PHASE synthetic-start',flush=True)
time.sleep(.5)
pathlib.Path(__file__).with_name('finished').write_text('code switch finished')
print('RELEASE_RESULT {"status":"synthetic-ok"}',flush=True)
""")
    proc = subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        proc.stdin.write(bundle); proc.stdin.close()
        assert proc.stdout.readline().startswith(b'RELEASE_PHASE synthetic-start')
        proc.terminate(); proc.wait(timeout=3)
        deadline = time.monotonic()+5
        while not (stage/'exit-code').exists() and time.monotonic()<deadline: time.sleep(.02)
        assert (stage/'exit-code').read_text() == '0'
        assert (stage/'finished').read_text() == 'code switch finished'
    finally:
        if proc.poll() is None: proc.kill(); proc.wait(timeout=3)
        proc.stdout.close(); proc.stderr.close()


def test_worker_failure_is_audited_and_not_retried(tmp_path):
    bundle, code, stage = bootstrap_fixture(tmp_path, "raise RuntimeError('synthetic failure')")
    result = subprocess.run([sys.executable,'-c',code],input=bundle,capture_output=True,timeout=10)
    assert result.returncode == 1 and b'synthetic failure' in result.stdout
    assert (stage/'exit-code').read_text() == '1'
