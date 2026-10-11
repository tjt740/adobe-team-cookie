"""Exercise legacy entry points and the durable flow against isolated SQLite."""
import hashlib
import time
import pytest
from sqlalchemy import create_engine, select
from app.db.session import Base
from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember
from app.models.integration import CredentialDelivery, RecoveryJob
from app.crud import setting as settings_crud
from app.schemas.setting import SettingsUpdate
from app.services import reliable_integration as link, external_login, external_sub2, external_sub2_stock

CFG = {'enabled': True, 'base_url': 'http://127.0.0.1:19999', 'site_id': 'fixture-site',
       'integration_key': 'fixture-key', 'issuer': 'fixture-okad', 'admin_token': 'fixture-admin',
       'platform': 'adobe', 'group_ids': [1], 'concurrency': 3}

@pytest.fixture
def engine(tmp_path):
    value = create_engine('sqlite:///' + str(tmp_path/'foundation.db'), connect_args={'check_same_thread':False})
    Base.metadata.create_all(value)
    yield value
    value.dispose()

@pytest.fixture
def wired(db, SessionLocal, monkeypatch):
    for module in (link, external_login, external_sub2):
        monkeypatch.setattr(module, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(link, 'settings', lambda db: dict(CFG))
    monkeypatch.setattr(external_sub2, 'config', lambda db: dict(CFG))
    settings_crud.update_settings(db, SettingsUpdate(external_api_key='callback-key'))
    member = ExternalMember(email='one@fixture.invalid', cookie='old-cookie', mail_url='http://127.0.0.1/mail')
    db.add(member); db.commit()
    return member.id

@pytest.mark.parametrize('enabled', [False, True])
def test_legacy_callback_still_returns_saved_cookie_and_uses_configured_proxy(client, db, wired, monkeypatch, enabled):
    monkeypatch.setattr(link, 'settings', lambda db: {**CFG, 'enabled':enabled})
    settings_crud.update_settings(db, SettingsUpdate(proxy_enabled=True, proxy_url='http://127.0.0.1:23111'))
    seen=[]
    def login(**options):
        seen.append(options['proxy_url'])
        return {'cookie':'fresh-cookie','access_token':'fake-token','credits':4000,'credits_total':4000}
    monkeypatch.setattr(external_login.firefly, 'register_account', login)
    monkeypatch.setattr(external_sub2, 'after_login', lambda *a,**kw:None)
    response=client.post('/api/v1/adobe/cookie/refresh',headers={'X-API-Key':'callback-key'},json={'email':'one@fixture.invalid'})
    assert response.status_code==200 and response.json()['ok']
    assert response.json()['cookie']=='fresh-cookie'
    db.expire_all();assert db.get(ExternalMember,wired).cookie=='fresh-cookie'
    assert seen==['http://127.0.0.1:23111']

@pytest.mark.parametrize('manual', [False, True])
def test_new_saved_cookie_syncs_even_if_relogin_needs_human(client, db, wired, monkeypatch, manual):
    row=db.get(ExternalMember,wired);row.otp_mode='manual' if manual else 'auto';row.mail_url='';db.commit()
    monkeypatch.setattr(external_login,'login_and_store',lambda *a,**k:pytest.fail('preflight must never login'))
    result=client.get('/api/v1/adobe/cookie/capability',headers={'X-API-Key':'callback-key'},params={
        'email':row.email,'cookie_hash':hashlib.sha256(b'older-sub2-cookie').hexdigest()}).json()
    assert result['code']=='awaiting_sync'
    db.expire_all();assert db.get(CredentialDelivery,f'fixture-site/external:{wired}').state=='pending'

def test_managed_rejection_keeps_request_identity(client, db, wired):
    row=db.get(ExternalMember,wired);row.otp_mode='manual';db.commit()
    response=client.post('/api/v1/adobe/cookie/refresh',headers={'X-API-Key':'callback-key'},json={
        'email':row.email,'request_id':'manual-request','source_key':f'external:{wired}'})
    result=response.json()
    assert result['code']=='needs_manual' and result['email']==row.email
    assert result['job_id']=='manual-request' and result['state']=='failed'

def test_switching_to_v2_resumes_legacy_pending_cookie(db, wired, monkeypatch):
    row=db.get(ExternalMember,wired)
    target=external_sub2.destination(CFG)
    row.sub2_links={target:{'status':'syncing','account_id':91}};db.commit()
    external_sub2.resume_pending()
    db.expire_all();delivery=db.get(CredentialDelivery,f'fixture-site/external:{wired}')
    assert delivery is not None and delivery.account_id==91 and delivery.state=='pending'

def test_v2_inventory_does_not_depend_on_admin_session(db,wired,monkeypatch):
    monkeypatch.setattr(external_sub2,'config',lambda db:{**CFG,'admin_token':''})
    monkeypatch.setattr(external_sub2_stock,'_cache',{})
    monkeypatch.setattr(link,'inventory',lambda cfg:[{'id':91,'email':'one@fixture.invalid'}])
    monkeypatch.setattr(external_sub2,'_request',lambda *a,**k:pytest.fail('v2 inventory must use scoped key'))
    result=external_sub2_stock.membership(db,refresh=True)
    assert result['ok'] and result['items'][wired]['in_stock']

def test_pool_delivery_updates_legacy_push_marker(db,wired,monkeypatch):
    row=AdobeMember(admin_id=0,email='pool@fixture.invalid',cookie='pool-cookie',registered=True,credits=4000)
    db.add(row);db.commit();key=f'pool:{row.id}'
    link.queue_source(db,key,account_id=91)
    def request(cfg,method,path,body=None):
        if path=='/capabilities':return {'site_id':'fixture-site'}
        if path.startswith('/accounts?'):return {'items':[{'id':91,'email':row.email}],'next_cursor':0}
        return {'id':91,'status':'active','schedulable':True,'integration':{'verification':'verified'}}
    monkeypatch.setattr(link,'request',request)
    link.deliver('fixture-site/'+key)
    db.refresh(row);assert row.sub2_pushed_at is not None

def test_disabling_integration_still_finalizes_interrupted_login(db,wired,monkeypatch):
    job=link.submit_recovery(db,'interrupted','one@fixture.invalid')
    job.state='running';job.updated_at=time.time()-300;db.commit()
    monkeypatch.setattr(link,'settings',lambda db:{**CFG,'enabled':False})
    link.tick()
    db.refresh(job);assert job.state=='failed' and job.code=='outcome_unknown'

def test_terminal_job_never_keeps_login_items_running(client,monkeypatch):
    from app.services.job_manager import JOBS
    def crash(job):
        job.record_item(1,status='running',message='正在登录')
        raise RuntimeError('fixture worker failed')
    job=JOBS.start('external_login',crash,meta={'member_ids':[1]})
    deadline=time.monotonic()+3
    while job.finished_at is None and time.monotonic()<deadline:time.sleep(.01)
    assert job.status=='error' and job.finished_at
    assert job.extra['items'][0]['status']=='failed'

def test_dashboard_uses_same_v2_site_and_scoped_inventory(db,wired,monkeypatch):
    from app.api.routes.dashboard import overview
    monkeypatch.setattr(external_sub2,'config',lambda db:{**CFG,'admin_token':''})
    monkeypatch.setattr(external_sub2_stock,'_cache',{})
    monkeypatch.setattr(link,'inventory',lambda cfg:[
        {'id':91,'email':'one@fixture.invalid','status':'active','schedulable':True},
        {'id':92,'email':'paused@fixture.invalid','status':'active','schedulable':False},
        {'id':93,'email':'failed@fixture.invalid','status':'error','schedulable':True}])
    result=overview(db)
    assert result['sub2']['enabled'] and result['sub2']['ok'] and result['sub2']['live']==1
    stock=external_sub2_stock._snapshot(external_sub2.config(db))
    assert len(stock['by_email'])==3, 'paused/error accounts remain in inventory for deduplication'

def test_native_create_keeps_group_concurrency_and_rate(db,wired,monkeypatch):
    cfg={**CFG,'rate_multiplier':2.5,'concurrency':7,'group_ids':[3,4]}
    monkeypatch.setattr(link,'settings',lambda db:dict(cfg))
    monkeypatch.setattr(link,'inventory',lambda cfg:[])
    calls=[]
    def admin_request(cfg,method,path,body=None):
        if method=='GET':return [{'id':n,'platform':'adobe','status':'active'} for n in [3,4]]
        calls.append(body);return {'id':91}
    monkeypatch.setattr(external_sub2,'_request',admin_request)
    link.queue_source(db,f'external:{wired}',allow_create=True)
    delivery=db.get(CredentialDelivery,f'fixture-site/external:{wired}')
    assert link._locate(cfg,delivery,'one@fixture.invalid')==91
    assert calls[0]['group_ids']==[3,4] and calls[0]['concurrency']==7 and calls[0]['rate_multiplier']==2.5
    assert 'proxy_id' not in calls[0]

def test_v2_http_delivery_retries_without_relogin_and_finishes_status(client,db,wired,monkeypatch):
    import json,threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    remote={'cookie':'old','proxy_id':72,'group_ids':[8],'priority':5,'verify_calls':0}
    class Remote(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            data={'site_id':'fixture-site'} if self.path.endswith('/capabilities') else {
                'items':[{'id':91,'email':'one@fixture.invalid'}],'next_cursor':0}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'data':data}).encode())
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            assert self.headers.get('X-Integration-Key')=='fixture-key'
            if self.path.endswith('/credentials'):
                assert set(body)=={'email','issuer','source_key','version','cookie'}
                remote['cookie']=body['cookie']
            else:
                remote['verify_calls']+=1
                if remote['verify_calls']==1:
                    self.send_response(503);self.end_headers();return
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'data':{
                'id':91,'status':'active','schedulable':True,'integration':{'verification':'verified'}}}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Remote)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(link,'settings',lambda db:{**CFG,'base_url':f'http://127.0.0.1:{server.server_port}'})
    logins=[]
    def login(**kwargs):
        logins.append(1);return {'cookie':'fresh-cookie','credits':4000,'credits_total':4000}
    monkeypatch.setattr(external_login.firefly,'register_account',login)
    try:
        submitted=client.post('/api/v1/adobe/cookie/refresh',headers={'X-API-Key':'callback-key'},json={
            'email':'one@fixture.invalid','request_id':'http-recovery'})
        assert submitted.status_code==202
        link.run_recovery('http-recovery')
        state=client.get('/api/v1/adobe/cookie/jobs/http-recovery',headers={'X-API-Key':'callback-key'}).json()
        assert state['state']=='done' and state['ok']
        key=f'fixture-site/external:{wired}'
        link.deliver(key)
        db.expire_all();assert db.get(CredentialDelivery,key).state=='retry' and remote['cookie']=='fresh-cookie'
        link.deliver(key)
        db.expire_all();assert db.get(CredentialDelivery,key).state=='ready'
        assert len(logins)==1 and remote['verify_calls']==2
        assert remote['proxy_id']==72 and remote['group_ids']==[8] and remote['priority']==5
        dest=external_sub2.destination(link.settings(db))
        assert db.get(ExternalMember,wired).sub2_links[dest]['status']=='synced'
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)

def test_remote_pause_resume_delete_update_local_status_without_writes(db,wired,monkeypatch):
    key=f'fixture-site/external:{wired}'
    link.queue_source(db,f'external:{wired}',account_id=91)
    d=db.get(CredentialDelivery,key);d.state='ready';db.commit()
    remote={'id':91,'email':'one@fixture.invalid','status':'active','schedulable':False,
            'integration':{'issuer':'fixture-okad','source_key':f'external:{wired}','version':1,'verification':'verified'}}
    def request(cfg,method,path,body=None):
        assert method=='GET' and body is None
        return {'site_id':'fixture-site'} if path=='/capabilities' else {'items':[remote] if remote else [],'next_cursor':0}
    monkeypatch.setattr(link,'request',request)
    link.reconcile_inventory();db.refresh(d);assert d.state=='paused'
    remote['schedulable']=True
    link.reconcile_inventory();db.refresh(d);assert d.state=='ready'
    remote.clear()
    link.reconcile_inventory();db.refresh(d);assert d.state=='blocked' and '删除' in d.message

def test_late_inventory_cannot_replace_new_pending_cookie(db,wired,monkeypatch):
    key=f'fixture-site/external:{wired}'
    link.queue_source(db,f'external:{wired}',account_id=91)
    d=db.get(CredentialDelivery,key);d.state='ready';db.commit()
    def request(cfg,method,path,body=None):
        if path=='/capabilities':return {'site_id':'fixture-site'}
        row=db.get(ExternalMember,wired);row.cookie='new-cookie'
        link.record_cookie(db,f'external:{wired}',row.email,row.cookie);db.commit()
        return {'items':[],'next_cursor':0}
    monkeypatch.setattr(link,'request',request)
    link.reconcile_inventory();db.refresh(d)
    assert d.version==2 and d.state=='pending'
