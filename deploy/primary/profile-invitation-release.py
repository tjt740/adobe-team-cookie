"""Guarded organization-invitation login release for the primary host; no business-data restore.

Upload beside manifest.json and payload/, then run deploy.
check-rollback is read-only; rollback restores code only after all guards pass.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

APP = Path('/opt/adobe-team-cookie')
STAGE = Path(__file__).resolve().parent
CONTAINER = 'adobe-team-cookie-app-1'
FILES = ('backend/app/schemas/account_profile.py', 'backend/app/services/account_profile.py', 'backend/app/services/adobe_admin.py', 'backend/app/services/firefly.py', 'frontend-v2/external-members-patch.js', 'frontend-v2/external-members-view.css', 'frontend-v2/index.html', 'frontend-v2/index-okad.html')
HASH_CODE = """import pathlib,hashlib,json
r=pathlib.Path('/app')
print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['backend/app','frontend-v2'] for p in (r/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.js','.css','.html']}))
"""


def run(args, **kwargs):
    return subprocess.run(args, cwd=APP, check=True, **kwargs)


def out(args):
    return subprocess.check_output(args, cwd=APP, text=True).strip()


def inspect(name):
    return json.loads(out(['docker', 'inspect', name]))[0]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def save(name, value):
    (STAGE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def hashes(image=None):
    command = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python', image] if image else ['docker', 'exec', CONTAINER, 'python']
    return json.loads(out(command + ['-c', HASH_CODE]))


def configs():
    paths = [APP / name for name in ('.env', 'compose.yml', 'compose.override.yml')]
    paths += [Path('/opt/adobe-relay/shared') / name for name in ('.env', 'compose.yml', 'clash.yml', 'resources.yml', 'data/config.yaml')]
    return {str(path): digest(path) for path in paths}


def other_containers():
    rows = json.loads(out(['docker', 'inspect'] + out(['docker', 'ps', '-q']).split()))
    return {r['Name']: {'id':r['Id'], 'image':r['Image']} for r in rows if r['Name'] != '/' + CONTAINER}


def database_summary():
    with sqlite3.connect('file:' + str(APP / 'data/app.db') + '?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        settings = {k: hashlib.sha256((v or '').encode()).hexdigest() for k, v in db.execute('SELECT key,value FROM settings')}
        ids = [r[0] for r in db.execute('SELECT id FROM external_members ORDER BY id')]
        return {'settings_hashes':settings, 'external_member_ids':ids}


def require_idle():
    with sqlite3.connect('file:' + str(APP / 'data/app.db') + '?mode=ro', uri=True) as db:
        now = time.time()
        queries = {
            'jobs': "SELECT count(*) FROM job_records WHERE deleted=0 AND status IN ('running','pausing','paused','cancelling')",
            'recovery': "SELECT count(*) FROM integration_recovery_jobs WHERE state IN ('queued','running')",
            'login_leases': "SELECT count(*) FROM integration_login_leases WHERE (result IS NULL OR result='null') AND expires_at>?",
            'deliveries': "SELECT count(*) FROM integration_deliveries WHERE lease_until>? OR (state='pending' AND next_at<=?) OR (state='retry' AND next_at<=?)",
        }
        state = {}
        for key, query in queries.items():
            params = (now, now + 60, now) if key == 'deliveries' else (now,) if '?' in query else ()
            state[key] = db.execute(query, params).fetchone()[0]
        durable = {(s,t) for s,t in db.execute('SELECT source_key,target FROM integration_deliveries')}
        state['legacy_pending'] = 0
        for mid, raw in db.execute('SELECT id,sub2_links FROM external_members'):
            for target, link in json.loads(raw or '{}').items():
                if link.get('status') in ('pending','syncing') and ('external:' + str(mid), target) not in durable:
                    state['legacy_pending'] += 1
        assert not any(state.values()), 'Active work; wait before deployment: ' + repr(state)


def backup_db(path):
    with sqlite3.connect('file:' + str(APP / 'data/app.db') + '?mode=ro', uri=True) as src, sqlite3.connect(path) as dst:
        src.backup(dst)
        assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def http_health():
    with urllib.request.urlopen('http://127.0.0.1:9500/api/health', timeout=15) as response:
        assert json.load(response)['status'] == 'ok'


def switch(image):
    path = APP / 'compose.yml'
    content, count = re.subn(r'(?m)^(    image:)\s*adobe-team-cookie:[^\s]+[ \t]*$', lambda m:m[1] + ' ' + image, path.read_text())
    assert count == 1, 'Unexpected compose image declaration'
    path.write_text(content)
    run(['docker', 'compose', '-f', str(path), 'up', '-d', '--no-build', '--no-deps', '--timeout', '300', '--wait', '--wait-timeout', '180', 'app'])
    assert inspect(CONTAINER)['Config']['Image'] == image
    http_health()


def restore_host(backup):
    for name in FILES:
        path = APP / 'payload' / name
        if (backup / 'payload' / name).exists():
            shutil.copy2(backup / 'payload' / name, path)
        else:
            path.unlink(missing_ok=True)


def main(mode):
    os.umask(0o077)
    locks = []
    for path in [Path('/opt/adobe-relay/.release.lock')] + [APP/n for n in ('.release.lock', '.incremental-release.lock', '.local/deploy-login-batches.lock', '.local/monitor-release.lock')]:
        handle = path.open('a'); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(handle)
    meta = json.loads((STAGE / 'manifest.json').read_text())
    assert set(meta['files']) == set(FILES)
    assert re.fullmatch(r'[a-f0-9]{40}', meta['commit'])
    assert re.fullmatch(r'[a-z0-9-]+', meta['release'])
    backup = STAGE / 'backup'
    if mode != 'deploy':
        before = json.loads((STAGE / 'before.json').read_text())
        after = json.loads((STAGE / 'after.json').read_text())
        current = inspect(CONTAINER)
        assert current['Image'] == after['image_id'] and current['Config']['Image'] == after['image'], 'Later application release; inspect before rollback'
        assert hashes() == after['source_hashes'], 'Later runtime changes'
        assert configs() == after['config_hashes'], 'Later configuration changes'
        assert database_summary()['settings_hashes'] == after['database']['settings_hashes'], 'Later Okad settings changes'
        for name in FILES:
            assert digest(APP / 'payload' / name) == meta['files'][name]['after'], 'Later host source changes'
        assert inspect(before['rollback'])['Id'] == before['rollback_image_id'], 'Rollback image changed'
        if mode == 'check-rollback':
            print('Rollback guards passed; no application or data changed')
            return
        require_idle()
        switch(before['rollback'])
        restore_host(backup)
        assert hashes() == before['source_hashes']
        save('rolled-back.json', {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image':before['rollback']})
        print('Restored previous code; current business data and settings retained')
        return
    assert not (STAGE / 'before.json').exists(), 'Release already prepared; inspect audit before retrying'
    current = inspect(CONTAINER)
    assert current['Id'] == meta['container'] and current['Image'] == meta['source_image_id'], 'Concurrent deployment detected'
    assert current['State']['Health']['Status'] == 'healthy'
    assert current['Config']['Labels']['com.docker.compose.project.config_files'] == str(APP / 'compose.yml')
    source = hashes()
    private = configs()
    others = other_containers()
    for name in FILES:
        item = meta['files'][name]
        assert source.get(name) == item['before'], 'Runtime changed: ' + name
        assert digest(APP / 'payload' / name) == item['host_before'], 'Host changed: ' + name
        assert digest(STAGE / 'payload' / name) == item['after'], 'Upload mismatch: ' + name
    require_idle()
    backup.mkdir(mode=0o700)
    for name in FILES:
        target = backup / 'payload' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if (APP / 'payload' / name).is_file():
            shutil.copy2(APP / 'payload' / name, target)
    for name in ('.env', 'compose.yml', 'compose.override.yml'):
        if (APP / name).is_file(): shutil.copy2(APP / name, backup / name)
    backup_db(backup / 'pre-release.db')
    print('DATABASE_AND_SOURCE_BACKUP_READY', flush=True)
    rollback = 'adobe-team-cookie:before-' + meta['release']
    image = 'adobe-team-cookie:' + meta['commit']
    # Preserve runtime overlays even when an old image tag does not describe them.
    print('CAPTURING_ROLLBACK_IMAGE', flush=True)
    run(['docker', 'commit', '--pause=false', CONTAINER, rollback], stdout=subprocess.DEVNULL)
    before = {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'container':current['Id'], 'source_image_id':current['Image'],
              'source_hashes':source, 'config_hashes':private, 'other_containers':others, 'rollback':rollback,
              'rollback_image_id':inspect(rollback)['Id']}
    save('before.json', before)
    (STAGE / 'Dockerfile').write_text('FROM ' + rollback + '\n' + ''.join('COPY payload/' + n + ' /app/' + n + '\n' for n in FILES) + 'LABEL org.opencontainers.image.revision="' + meta['commit'] + '"\n')
    run(['docker', 'build', '--network', 'none', '--pull=false', '-t', image, str(STAGE)])
    expected = source | {n:meta['files'][n]['after'] for n in FILES}
    assert hashes(image) == expected, 'Candidate changes unrelated source files'
    run(['docker','run','--rm','--network','none','--entrypoint','python',image,'-c',"import inspect;import app.main;from app.services.adobe_admin import complete_sub_account;from app.services.firefly import _prefer_organization_profile;from app.services.account_profile import build_profile_snapshot;assert 'activate_profiles' in inspect.signature(complete_sub_account).parameters;p=build_profile_snapshot({'check_account_type':'type1','check_user_id':'synthetic@AdobeID','profile_preference':'organization','profile_fallback_reason':'synthetic fallback'},'synthetic@AdobeID');assert p['fallback_reason']=='synthetic fallback' and p['requested_preference']=='organization';print('CANDIDATE_PROFILE_SCHEMA_AND_IMPORT_OK')"])
    assert inspect(CONTAINER)['Id'] == current['Id'] and hashes() == source and configs() == private
    assert other_containers() == others, 'Another service changed while preparing'
    require_idle()
    backup_db(backup / 'cutover.db')
    before['database'] = database_summary()
    save('before.json', before)
    changed = False
    try:
        require_idle()
        changed = True
        switch(image)
        assert hashes() == expected, 'Unexpected runtime source changes'
        verification=json.loads(out(['docker','exec',CONTAINER,'python','-c',"import json,sqlite3,urllib.request\nfrom app.core.security import create_access_token\nc=sqlite3.connect('file:/app/data/app.db?mode=ro',uri=True)\nassert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'\nuid,version=c.execute('SELECT id,token_version FROM users WHERE is_active=1 AND is_superuser=1 LIMIT 1').fetchone()\ntoken=create_access_token(uid,expires_minutes=5,token_version=version)\ndef get(path):\n with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9500'+path,headers={'Authorization':'Bearer '+token}),timeout=30) as r:return json.load(r)\nassert get('/api/health')['status']=='ok'\nschema=get('/openapi.json')['components']['schemas']['AccountProfile']['properties']\nassert 'fallback_reason' in schema and 'requested_preference' in schema\nmembers=get('/api/external/members?size=1')\nassert members['total']==c.execute('SELECT count(*) FROM external_members').fetchone()[0]\nfor member in members['items']:\n assert 'cookie' not in member and 'access_token' not in member and 'adobe_password' not in member\n profile=member.get('account_profile')\n if profile: assert 'fallback_reason' in profile and 'requested_preference' in profile\nprint(json.dumps({'api':'ok','database':'ok','members':members['total'],'profile_schema':'ok'}))\n"]))
        print('LIVE_READ_ONLY_PROFILE_CHECK_OK',json.dumps(verification),flush=True)
        for name in FILES:
            shutil.copy2(STAGE / 'payload' / name, APP / 'payload' / name)
        config_after = configs()
        assert {k:v for k,v in config_after.items() if k != str(APP/'compose.yml')} == {k:v for k,v in private.items() if k != str(APP/'compose.yml')}
        assert other_containers() == others, 'Another service changed during release'
        db_after = database_summary()
        assert db_after == before['database'], 'Existing account identities or settings changed during release'
        after = {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image':image, 'image_id':inspect(CONTAINER)['Image'],
                 'container':inspect(CONTAINER)['Id'], 'config_hashes':config_after, 'source_hashes':expected, 'other_containers':others,
                 'database':db_after, 'changed_setting_keys':[k for k in set(before['database']['settings_hashes'])|set(db_after['settings_hashes']) if before['database']['settings_hashes'].get(k) != db_after['settings_hashes'].get(k)]}
        after['verification'] = verification
        save('after.json', after)
        print(json.dumps({'deployed':image, 'health':'healthy', 'changed_source_files':list(FILES), 'changed_setting_keys':after['changed_setting_keys']}, ensure_ascii=False))
    except BaseException:
        if changed:
            switch(rollback)
            restore_host(backup)
            save('automatic-rollback.json', {'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action not in ('deploy', 'check-rollback', 'rollback'):
        raise SystemExit('Usage: profile-invitation-release.py deploy|check-rollback|rollback')
    main(action)
