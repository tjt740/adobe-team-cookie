"""Guarded mailbox batches and complete credential-format release. Preserve other runtime overlays and current business data.
Upload beside manifest.json and payload/. Run deploy, check-rollback, or rollback."""
import datetime,fcntl,hashlib,json,os,re,shutil,sqlite3,subprocess,sys,time,urllib.request
from pathlib import Path
os.umask(0o077)
APP=Path('/opt/adobe-team-cookie');STAGE=Path(__file__).resolve().parent
META=json.loads((STAGE/'manifest.json').read_text());BEFORE=META['before'];FILES=META['files']
NAME='adobe-team-cookie-app-1';RELEASE=META['release'];BACKUP=APP/'backups'/RELEASE
assert re.fullmatch(r'[a-f0-9]{40}',META['commit'])
assert re.fullmatch(r'[a-z0-9-]+',RELEASE)
locks=[]
for p in [Path('/opt/adobe-relay/.release.lock')]+[APP/n for n in ['.release.lock','.incremental-release.lock','.local/deploy-login-batches.lock','.local/monitor-release.lock']]:
 h=p.open('a');fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(h)
def out(args):return subprocess.check_output(args,cwd=APP,text=True).strip()
def run(args,**kw):return subprocess.run(args,cwd=APP,check=True,**kw)
def inspect(name=NAME):return json.loads(out(['docker','inspect',name]))[0]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def record(name,value):(STAGE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
def hashes(image=None):
 cmd=['docker','run','--rm','--network','none','--entrypoint','python',image] if image else ['docker','exec',NAME,'python']
 return json.loads(out(cmd+['-c',BEFORE['hash_code']]))
def configs():
 paths=[APP/n for n in ['.env','compose.yml','compose.override.yml']]+[Path('/opt/adobe-relay/shared')/n for n in ['.env','compose.yml','clash.yml','resources.yml','data/config.yaml']]
 return {str(p):digest(p) for p in paths}
def others():
 rows=json.loads(out(['docker','inspect']+out(['docker','ps','-q']).split()))
 return {r['Name']:{'id':r['Id'],'image':r['Image']} for r in rows if r['Name']!='/'+NAME}
def idle():
 now=time.time()
 with sqlite3.connect('file:'+str(APP/'data/app.db')+'?mode=ro',uri=True) as c:
  queries={'jobs':("SELECT count(*) FROM job_records WHERE deleted=0 AND status IN ('running','pausing','paused','cancelling')",()),
   'recovery':("SELECT count(*) FROM integration_recovery_jobs WHERE state IN ('queued','running')",()),
   'leases':("SELECT count(*) FROM integration_login_leases WHERE (result IS NULL OR result='null') AND expires_at>?",(now,)),
   'deliveries':("SELECT count(*) FROM integration_deliveries WHERE lease_until>? OR (state='pending' AND next_at<=?) OR (state='retry' AND next_at<=?)",(now,now+60,now))}
  state={k:c.execute(sql,params).fetchone()[0] for k,(sql,params) in queries.items()}
 assert not any(state.values()),'Active work: '+repr(state)
def backup_db(path):
 with sqlite3.connect('file:'+str(APP/'data/app.db')+'?mode=ro',uri=True) as src,sqlite3.connect(path) as dst:
  src.backup(dst);assert dst.execute('pragma integrity_check').fetchone()[0]=='ok'
def health():
 with urllib.request.urlopen('http://127.0.0.1:9500/api/health',timeout=15) as r:assert json.load(r)['status']=='ok'
def switch(image):
 p=APP/'compose.yml';s,n=re.subn(r'(?m)^(    image:)\s*adobe-team-cookie:[^\s]+[ \t]*$',lambda m:m[1]+' '+image,p.read_text());assert n==1
 p.write_text(s)
 run(['docker','compose','-f',str(p),'up','-d','--no-build','--no-deps','--timeout','300','--wait','--wait-timeout','180','app'])
 assert inspect()['Config']['Image']==image;health()

mode=sys.argv[1] if len(sys.argv)>1 else 'deploy'
assert mode in ('deploy','check-rollback','rollback')
if mode!='deploy':
 before=json.loads((STAGE/'before.json').read_text());after=json.loads((STAGE/'after.json').read_text())
 expected=BEFORE['source_hashes']|{n:m['after'] for n,m in FILES.items()}
 assert inspect()['Id']==after['container'] and inspect()['Config']['Image']==after['image'],'A later release exists'
 assert hashes()==expected and configs()==after['configs'] and others()==BEFORE['other_containers'],'Later source, config or service changes'
 for n,m in FILES.items():assert digest(APP/'payload'/n)==m['after'],'Host changed: '+n
 assert inspect(before['rollback'])['Id']==before['rollback_image_id'],'Rollback image changed'
 if mode=='check-rollback':print('ROLLBACK_GUARDS_PASSED_NO_CHANGES',flush=True);sys.exit(0)
 idle();switch(before['rollback'])
 for n,m in FILES.items():
  dst=APP/'payload'/n
  if m['before'] is not None:shutil.copy2(BACKUP/'payload'/n,dst)
  else:dst.unlink(missing_ok=True)
 assert hashes()==BEFORE['source_hashes']
 record('rolled-back.json',{'current_database_preserved':True,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 print('PREVIOUS_CODE_RESTORED_CURRENT_DATABASE_RETAINED',flush=True);sys.exit(0)
assert not (STAGE/'before.json').exists(),'Already prepared; inspect outcome before retrying'

current=inspect()
assert current['Id']==BEFORE['container']['id'] and current['Image']==BEFORE['container']['image_id'],'Concurrent deployment'
assert current['State']['Health']['Status']=='healthy'
assert hashes()==BEFORE['source_hashes'],'Runtime changed since capture'
assert others()==BEFORE['other_containers'],'Another service changed since capture'
for n,m in FILES.items():
 assert digest(APP/'payload'/n)==m['before'],'Host changed: '+n
 assert digest(STAGE/'payload'/n)==m['after'],'Upload mismatch: '+n
idle();private=configs();BACKUP.mkdir(mode=0o700)
for n in FILES:
 p=APP/'payload'/n
 if p.is_file():
  dst=BACKUP/'payload'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
shutil.copy2(APP/'compose.yml',BACKUP/'compose.yml');backup_db(BACKUP/'before.db')
rollback='adobe-team-cookie:before-'+RELEASE;candidate='adobe-team-cookie:'+RELEASE
run(['docker','commit','--pause=false',NAME,rollback],stdout=subprocess.DEVNULL)
record('before.json',{'backup':str(BACKUP),'rollback':rollback,'rollback_image_id':inspect(rollback)['Id'],'container':current['Id'],'configs':private})
(STAGE/'Dockerfile').write_text('FROM '+rollback+'\n'+''.join('COPY payload/'+n+' /app/'+n+'\n' for n in FILES)+'LABEL org.opencontainers.image.revision='+META['commit']+'\n')
print('BACKUP_COMPLETE_BUILDING_PATCH_IMAGE',flush=True)
run(['docker','build','--network','none','--pull=false','-t',candidate,str(STAGE)])
expected=BEFORE['source_hashes']|{n:m['after'] for n,m in FILES.items()}
assert hashes(candidate)==expected,'Unrelated candidate source changes'
assert inspect(candidate)['Config']['Labels']['org.opencontainers.image.revision']==META['commit']
trial=STAGE/'migration-trial';trial.mkdir(mode=0o700);shutil.copy2(BACKUP/'before.db',trial/'app.db')
rehearsal=r'''
import hashlib,json,sqlite3
from app.db.init_db import _run_migrations
from app.main import app
from app.crud.email import email_formats
from app.schemas.email import EmailFormatsRequest
from app.db.session import SessionLocal
path='/app/data/app.db'
def snapshot():
 result={}
 with sqlite3.connect(path) as c:
  for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
   cols=[r[1] for r in c.execute('PRAGMA table_info("'+table+'")')]
   values=c.execute('SELECT '+','.join('"'+n+'"' for n in cols)+' FROM "'+table+'" ORDER BY rowid').fetchall()
   result[table]=(cols,hashlib.sha256(json.dumps(values,default=str).encode()).hexdigest())
 return result
before=snapshot()
_run_migrations();_run_migrations()
with sqlite3.connect(path) as c:
 assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 for table,(cols,digest) in before.items():
  values=c.execute('SELECT '+','.join('"'+n+'"' for n in cols)+' FROM "'+table+'" ORDER BY rowid').fetchall()
  assert hashlib.sha256(json.dumps(values,default=str).encode()).hexdigest()==digest,table+' changed'
 assert c.execute('SELECT count(*) FROM emails WHERE import_batch IS NOT NULL OR imported_at IS NOT created_at').fetchone()[0]==0
 count=c.execute('SELECT count(*) FROM emails').fetchone()[0]
with SessionLocal() as db:
 result=email_formats(db,EmailFormatsRequest())
 assert result.total==count
 assert email_formats(db,EmailFormatsRequest(ids=[])).total==0
print(json.dumps({'migration':'ok','repeatable':True,'old_tables_unchanged':len(before),'legacy_emails':count,'complete_formats':'ok'}))
'''
run(['docker','run','--rm','--network','none','--entrypoint','python','-e','DATABASE_URL=sqlite:////app/data/app.db','-v',str(trial)+':/app/data',candidate,'-c',rehearsal])
print('ISOLATED_MIGRATION_REHEARSAL_PASSED',flush=True)
assert hashes()==BEFORE['source_hashes'] and inspect()['Id']==current['Id']
assert configs()==private and others()==BEFORE['other_containers']
idle();backup_db(BACKUP/'cutover.db')
changed=False
try:
 changed=True;switch(candidate)
 assert hashes()==expected and others()==BEFORE['other_containers']
 for n in FILES:
  dst=APP/'payload'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(STAGE/'payload'/n,dst)
 after_configs=configs()
 assert {k:v for k,v in after_configs.items() if k!=str(APP/'compose.yml')}=={k:v for k,v in private.items() if k!=str(APP/'compose.yml')}
 verification=r'''
import hashlib,json,sqlite3,urllib.error,urllib.request
from app.core.security import create_access_token
c=sqlite3.connect('file:/app/data/app.db?mode=ro',uri=True)
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
uid,version=c.execute('SELECT id,token_version FROM users WHERE is_active=1 AND is_superuser=1 LIMIT 1').fetchone()
token=create_access_token(uid,expires_minutes=5,token_version=version)
def request(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:9500'+path,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},data=json.dumps(data).encode() if data is not None else None)
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
page=request('/api/emails?size=1');count=c.execute('SELECT count(*) FROM emails').fetchone()[0]
assert page['total']==count
assert all(k in page['items'][0] for k in ['import_batch','imported_at']) if count else True
assert isinstance(request('/api/emails/import-batches'),list)
assert request('/api/emails/formats',{'ids':[]})=={'content':'','total':0}
if count:
 row=page['items'][0]
 for style,keys,sep in [('standard',['email','password','client_id','refresh_token'],'----'),('pipe',['email','password','refresh_token','client_id'],'|')]:
  result=request('/api/emails/formats',{'ids':[row['id']],'format':style})
  fields=[row[k] or '' for k in keys]+([row['mail_url']] if row['mail_url'] else [])
  assert result=={'total':1,'content':sep.join(fields)}
try:request('/api/emails/batch-import',{'content':''})
except urllib.error.HTTPError as error:assert error.code==422
else:raise AssertionError('Missing import fields were accepted')
try:request('/api/emails',{'email':'validation-only@example.invalid'})
except urllib.error.HTTPError as error:assert error.code==422
else:raise AssertionError('Missing single-import fields were accepted')
schema=request('/openapi.json')['components']['schemas']
assert {'import_batch','on_duplicate'}<=set(schema['EmailBatchImportRequest']['required'])
assert {'import_batch','on_duplicate'}<=set(schema['EmailCreate']['required'])
print(json.dumps({'api':'ok','database':'ok','emails':count,'complete_formats':'ok','required_fields':'ok'}))
'''
 verified=json.loads(out(['docker','exec',NAME,'python','-c',verification]))
 # Compare every original mailbox field with the cutover backup, without printing credentials.
 with sqlite3.connect('file:'+str(BACKUP/'cutover.db')+'?mode=ro',uri=True) as old,sqlite3.connect('file:'+str(APP/'data/app.db')+'?mode=ro',uri=True) as new:
  cols=[r[1] for r in old.execute('PRAGMA table_info(emails)')]
  query='SELECT '+','.join('"'+n+'"' for n in cols)+' FROM emails ORDER BY id'
  assert old.execute(query).fetchall()==new.execute(query).fetchall(),'Existing mailbox fields changed'
  assert old.execute('SELECT key,value FROM settings ORDER BY key').fetchall()==new.execute('SELECT key,value FROM settings ORDER BY key').fetchall(),'Settings changed'
 result={'status':'deployed','release':RELEASE,'commit':META['commit'],'image':candidate,'container':inspect()['Id'],'health':'healthy','backup':str(BACKUP),'configs':after_configs,'verification':verified,'other_services_unchanged':True,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 record('after.json',result);(BACKUP/'manifest.json').write_text(json.dumps(META,indent=2));print(json.dumps(result),flush=True)
except BaseException:
 if changed:
  switch(rollback)
  for n,m in FILES.items():
   dst=APP/'payload'/n
   if m['before'] is not None:shutil.copy2(BACKUP/'payload'/n,dst)
   elif dst.exists():dst.unlink()
  record('automatic-rollback.json',{'restored_code':True,'current_database_preserved':True})
 raise
finally:
 shutil.rmtree(trial,ignore_errors=True)
