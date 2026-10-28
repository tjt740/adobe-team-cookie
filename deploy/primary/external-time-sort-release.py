"""Publish second-precision ranges and timestamp ordering using the primary release guards."""
import importlib.util
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('guarded_release',Path(__file__).with_name('profile-invitation-release.py'))
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
release.FILES=('backend/app/api/routes/external_member.py', 'backend/app/crud/external_member.py', 'backend/app/schemas/external_member.py', 'frontend-v2/external-members-patch.js', 'frontend-v2/external-members-view.js', 'frontend-v2/external-members-view.css', 'frontend-v2/index.html', 'frontend-v2/index-okad.html')
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
SMOKE="from datetime import datetime,timedelta,timezone\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session\nfrom app.main import app\nfrom app.db.session import Base\nfrom app.models.external_member import ExternalMember\nfrom app.crud.external_member import list_members,export_cookies\nfrom app.api.routes.external_member import _member_filters\nengine=create_engine('sqlite://');Base.metadata.create_all(engine)\nwith Session(engine) as db:\n base=datetime(2026,10,29,4,34,56)\n for i,(seconds,logged) in enumerate([(2,2),(1,None),(2.999999,2.999999),(3,3)]):\n  db.add(ExternalMember(email=f'synthetic{i}@example.test',cookie=f'cookie={i}',created_at=base+timedelta(seconds=seconds),last_login_at=base+timedelta(seconds=logged) if logged is not None else None))\n db.commit()\n filters=_member_filters(db,imported_from=datetime.fromisoformat('2026-10-29T12:34:58+08:00'),imported_before=datetime.fromisoformat('2026-10-29T12:34:59+08:00'))\n rows,total=list_members(db,size=1,sort_by='created_at',sort_order='asc',**filters)\n assert total==2 and rows[0].email=='synthetic0@example.test'\n assert export_cookies(db,sort_by='created_at',sort_order='desc',**filters)==[{'cookie':'cookie=2'},{'cookie':'cookie=0'}]\n for order in ['asc','desc']:\n  rows,total=list_members(db,size=None,sort_by='last_login_at',sort_order=order)\n  assert total==4 and rows[-1].last_login_at is None\nschema=app.openapi()\nfor path in ['/api/external/members','/api/external/members/export']:\n assert {'sort_by','sort_order'}<={p['name'] for p in schema['paths'][path]['get']['parameters']}\nassert {'sort_by','sort_order'}<=schema['components']['schemas']['ExternalLoginFilter']['properties'].keys()\nprint('CANDIDATE_SECOND_PRECISION_AND_GLOBAL_TIMESTAMP_ORDER_OK')\n"
def hashes(image=None):
 value=original_hashes(image)
 if image:
  release.run(['docker','run','--rm','--network','none','--entrypoint','python',image,'-c',SMOKE])
 return value
release.hashes=hashes
LIVE_CHECK="import json,sqlite3,urllib.parse,urllib.request,urllib.error\nfrom datetime import datetime,timedelta,timezone\nfrom app.core.security import create_access_token\nc=sqlite3.connect('file:/app/data/app.db?mode=ro',uri=True)\nassert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'\nuid,version=c.execute('SELECT id,token_version FROM users WHERE is_active=1 AND is_superuser=1 LIMIT 1').fetchone()\ntoken=create_access_token(uid,expires_minutes=5,token_version=version)\ndef get(path):\n with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9500'+path,headers={'Authorization':'Bearer '+token}),timeout=30) as response:return json.load(response)\nfor field in ['created_at','last_login_at']:\n for order in ['asc','desc']:\n  rows=get('/api/external/members?size=10&'+urllib.parse.urlencode({'sort_by':field,'sort_order':order}))['items']\n  known=[r for r in rows if r[field] is not None];missing=[r for r in rows if r[field] is None]\n  expected=sorted(known,key=lambda r:(r[field],r['id']),reverse=order=='desc')+sorted(missing,key=lambda r:r['id'],reverse=order=='desc')\n  assert [r['id'] for r in rows]==[r['id'] for r in expected]\nlatest=c.execute('SELECT max(created_at) FROM external_members').fetchone()[0]\nmatching=0\nif latest:\n start=datetime.fromisoformat(latest).replace(microsecond=0);end=start+timedelta(seconds=1)\n params=urllib.parse.urlencode({'imported_from':start.replace(tzinfo=timezone.utc).isoformat(),'imported_before':end.replace(tzinfo=timezone.utc).isoformat(),'sort_by':'created_at','sort_order':'asc'})\n matching=c.execute('SELECT count(*) FROM external_members WHERE created_at>=? AND created_at<?',(str(start),str(end))).fetchone()[0]\n assert get('/api/external/members?size=1&'+params)['total']==matching\n expected=sum(1 for row in c.execute('SELECT cookie FROM external_members WHERE created_at>=? AND created_at<?',(str(start),str(end))) if row[0] and row[0].strip())\n assert len(get('/api/external/members/export?'+params))==expected\nassert get('/api/external/members?size=1&last_login_from=2099-01-01T00:00:00Z')['total']==0\nfor path in ['/api/external/members?sort_by=cookie','/api/external/members/export?sort_order=invalid']:\n try:get(path)\n except urllib.error.HTTPError as error:assert error.code==422\n else:raise AssertionError('Invalid sort accepted')\nprint(json.dumps({'timestamp_order':'ok','import_second_scope':'ok','export_scope':'ok','invalid_sort':'rejected','matching_import_second':matching}))\n"
original_switch=release.switch
def switch(image):
 original_switch(image)
 import json
 meta=json.loads((release.STAGE/'manifest.json').read_text())
 if image=='adobe-team-cookie:'+meta['commit']:
  result=release.out(['docker','exec',release.CONTAINER,'python','-c',LIVE_CHECK])
  (release.STAGE/'time-sort-verification.json').write_text(result)
  print('LIVE_TIME_SORT_CHECK_OK',result,flush=True)
release.switch=switch
if __name__=='__main__':
 action=sys.argv[1] if len(sys.argv)==2 else ''
 if action not in ('deploy','check-rollback','rollback'):
  raise SystemExit('Usage: external-time-sort-release.py deploy|check-rollback|rollback')
 release.main(action)
