"""Publish the last-login filter as an overlay using the primary release guards."""
import importlib.util
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('guarded_release',Path(__file__).with_name('profile-invitation-release.py'))
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
release.FILES=('backend/app/schemas/external_member.py', 'backend/app/crud/external_member.py', 'backend/app/api/routes/external_member.py', 'frontend-v2/index.html', 'frontend-v2/index-okad.html', 'frontend-v2/external-members-patch.js', 'frontend-v2/external-members-view.js')
original_summary=release.database_summary
def summary():
    value = original_summary()
    # The hourly monitor is expected to persist its own result during startup.
    value["settings_hashes"] = {k:v for k,v in value["settings_hashes"].items()
                                if not k.startswith(("supply_mail_health", "supply_mail_binding:"))}
    import sqlite3, hashlib, json
    baseline_path = release.STAGE / "backup/cutover.db"
    with sqlite3.connect("file:" + str(release.APP / "data/app.db") + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        if baseline_path.exists():
            with sqlite3.connect("file:" + str(baseline_path) + "?mode=ro", uri=True) as baseline:
                old = {r[0]: r for r in baseline.execute("SELECT id,email,cookie,sub2_links FROM external_members")}
                stable = []
                for mid,email,cookie,raw in db.execute("SELECT id,email,cookie,sub2_links FROM external_members"):
                    if mid not in old: continue
                    prior = old[mid]
                    assert email == prior[1], "Account email changed"
                    links = json.loads(raw or "{}")
                    for target, previous in json.loads(prior[3] or "{}").items():
                        account_id = previous.get("account_id")
                        if account_id is not None:
                            assert links.get(target, {}).get("account_id") == account_id, "Existing Sub2 association changed"
                            stable.append((mid,email,target,account_id))
                    if cookie != prior[2]:
                        current = db.execute("SELECT version,cookie_hash FROM integration_credentials WHERE source_key=?", ("external:"+str(mid),)).fetchone()
                        previous = baseline.execute("SELECT version FROM integration_credentials WHERE source_key=?", ("external:"+str(mid),)).fetchone()
                        assert cookie and current and current[1] == hashlib.sha256(cookie.encode()).hexdigest(), "Cookie changed without version ownership"
                        assert not previous or current[0] > previous[0], "Cookie version did not advance"
                value["existing_sub2_links_sha"] = hashlib.sha256(json.dumps(stable).encode()).hexdigest()
                value["cookie_version_integrity"] = True
    return value
release.database_summary=summary
original_idle=release.require_idle
def wait_idle():
    import time
    deadline = time.monotonic() + 1200
    previous = None
    while True:
        try:
            original_idle()
            return
        except AssertionError as error:
            if not str(error).startswith('Active work;') or time.monotonic() >= deadline:
                raise
            if str(error) != previous:
                print('WAITING_FOR_EXISTING_WORK', str(error), flush=True)
                previous = str(error)
            time.sleep(10)
release.require_idle=wait_idle
original_hashes=release.hashes
SMOKE="from datetime import datetime\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session\nfrom app.main import app\nfrom app.db.session import Base\nfrom app.models.external_member import ExternalMember\nfrom app.crud.external_member import list_members, export_cookies\nfrom app.api.routes.external_member import _member_filters\nfrom app.schemas.external_member import ExternalLoginFilter\nengine=create_engine('sqlite://'); Base.metadata.create_all(engine)\nwith Session(engine) as db:\n for i,stamp in enumerate([None,datetime(2026,10,27,15,59,59),datetime(2026,10,27,16),datetime(2026,10,28,15,59,59),datetime(2026,10,28,16)]):\n  db.add(ExternalMember(email=f'synthetic{i}@example.test',cookie=f'cookie={i}',last_login_at=stamp))\n db.commit()\n payload=ExternalLoginFilter(last_login_from='2026-10-28T00:00:00+08:00',last_login_before='2026-10-29T00:00:00+08:00')\n filters=_member_filters(db,last_login_from=payload.last_login_from,last_login_before=payload.last_login_before)\n rows,total=list_members(db,size=1,**filters); assert total==2 and rows[0].email=='synthetic3@example.test'\n assert export_cookies(db,**filters)==[{'cookie':'cookie=3'},{'cookie':'cookie=2'}]\n assert list_members(db)[1]==5\nschema=app.openapi()\nfor path in ['/api/external/members','/api/external/members/export']:\n fields={p['name'] for p in schema['paths'][path]['get']['parameters']}\n assert {'last_login_from','last_login_before'}<=fields\nassert {'last_login_from','last_login_before'}<=schema['components']['schemas']['ExternalLoginFilter']['properties'].keys()\nprint('CANDIDATE_LAST_LOGIN_FILTER_BOUNDARIES_AND_SCOPES_OK')\n"
def hashes(image=None):
 value=original_hashes(image)
 if image:
  release.run(['docker','run','--rm','--network','none','--entrypoint','python',image,'-c',SMOKE])
 return value
release.hashes=hashes
LIVE_CHECK="import json,sqlite3,urllib.parse,urllib.request\nfrom datetime import datetime,timedelta,timezone\nfrom app.core.security import create_access_token\nc=sqlite3.connect('file:/app/data/app.db?mode=ro',uri=True)\nassert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'\nuid,version=c.execute('SELECT id,token_version FROM users WHERE is_active=1 AND is_superuser=1 LIMIT 1').fetchone()\ntoken=create_access_token(uid,expires_minutes=5,token_version=version)\ndef get(path):\n with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9500'+path,headers={'Authorization':'Bearer '+token}),timeout=30) as response:return json.load(response)\nlatest=c.execute('SELECT max(last_login_at) FROM external_members').fetchone()[0]\nday=(datetime.fromisoformat(latest).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))) if latest else datetime.now(timezone(timedelta(hours=8)))).replace(hour=0,minute=0,second=0,microsecond=0)\nstart=day.astimezone(timezone.utc).replace(tzinfo=None);end=start+timedelta(days=1)\nparams=urllib.parse.urlencode({'last_login_from':day.isoformat(),'last_login_before':(day+timedelta(days=1)).isoformat()})\nexpected=c.execute('SELECT id,cookie FROM external_members WHERE last_login_at>=? AND last_login_at<? ORDER BY id DESC',(str(start),str(end))).fetchall()\nresponse=get('/api/external/members?size=1&'+params)\nassert response['total']==len(expected)\nassert [r['id'] for r in response['items']]==[r[0] for r in expected[:1]]\nassert get('/api/external/members/export?'+params)==[{'cookie':cookie} for _,cookie in expected if cookie and cookie.strip()]\ntry:get('/api/external/members?last_login_from=2026-10-29T00:00:00Z&last_login_before=2026-10-28T00:00:00Z')\nexcept urllib.error.HTTPError as error:assert error.code==422\nelse:raise AssertionError('Invalid range accepted')\nprint(json.dumps({'last_login_list':'ok','export_scope':'ok','invalid_range':'rejected','matching_accounts':len(expected)}))\n"
original_switch=release.switch
def switch(image):
 original_switch(image)
 import json
 meta=json.loads((release.STAGE/'manifest.json').read_text())
 if image=='adobe-team-cookie:'+meta['commit']:
  result=release.out(['docker','exec',release.CONTAINER,'python','-c',LIVE_CHECK])
  (release.STAGE/'last-login-verification.json').write_text(result)
  print('LIVE_LAST_LOGIN_FILTER_CHECK_OK',result,flush=True)
release.switch=switch
if __name__=='__main__':
 action=sys.argv[1] if len(sys.argv)==2 else ''
 if action not in ('deploy','check-rollback','rollback'):
  raise SystemExit('Usage: last-login-filter-release.py deploy|check-rollback|rollback')
 release.main(action)
