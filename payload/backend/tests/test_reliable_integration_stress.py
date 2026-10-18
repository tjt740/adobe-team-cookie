"""File SQLite concurrency regressions; no live mail or Adobe requests."""
import time, threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.external_member import ExternalMember
from app.models.integration import CredentialState,CredentialDelivery,RecoveryJob
from app.services import reliable_integration as link,login_coordinator,external_login
CFG={'enabled':True,'integration_key':'fake','site_id':'test-site','issuer':'fixture',
     'base_url':'http://127.0.0.1:19999','admin_token':'fake','platform':'adobe','group_ids':[1]}

@pytest.fixture
def storage(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'concurrent.db'),connect_args={'check_same_thread':False,'timeout':10})
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine,autoflush=False)
    monkeypatch.setattr(link,'SessionLocal',factory);monkeypatch.setattr(external_login,'SessionLocal',factory)
    monkeypatch.setattr(link,'settings',lambda db:dict(CFG))
    with factory() as db:
        row=ExternalMember(email='one@fixture.invalid',cookie='fixture-cookie',mail_url='http://127.0.0.1/mail')
        db.add(row);db.commit();mid=row.id
    yield factory,mid
    engine.dispose()


def test_24_simultaneous_sync_requests_have_one_version(storage):
    factory,mid=storage;barrier=threading.Barrier(24)
    def submit(_):
        with factory() as db:
            barrier.wait(timeout=10)
            link.queue_source(db,'external:'+str(mid))
    with ThreadPoolExecutor(max_workers=24) as executor:list(executor.map(submit,range(24)))
    with factory() as db:
        assert len(list(db.scalars(select(CredentialState))))==1
        assert db.get(CredentialState,'external:'+str(mid)).version==1
        assert len(list(db.scalars(select(CredentialDelivery))))==1


def test_queued_duplicate_recovery_jobs_do_not_login_again(storage,monkeypatch):
    factory,mid=storage;calls=[]
    def login(*args,**kwargs):
        calls.append(1);time.sleep(.25)
        return {'ok':True,'code':'','cookie':'fixture-cookie'}
    monkeypatch.setattr(external_login,'_login_and_store',login)
    with factory() as db:
        for i in range(24):link.submit_recovery(db,f'request-{i}','one@fixture.invalid',f'external:{mid}')
    with ThreadPoolExecutor(max_workers=3) as executor:list(executor.map(link.run_recovery,[f'request-{i}' for i in range(24)]))
    with factory() as db:assert all(j.state=='done' for j in db.scalars(select(RecoveryJob)))
    assert len(calls)==1


def test_source_listing_is_read_only_when_pool_mail_credentials_need_fallback(db,monkeypatch):
    from app.models.adobe_member import AdobeMember
    from app.models.email import Email
    from app.api.routes.integration import sources
    monkeypatch.setattr(link,'settings',lambda db:dict(CFG))
    row=AdobeMember(admin_id=0,email='fallback@fixture.invalid',refresh_token='',client_id='')
    db.add(row);db.add(Email(email=row.email,refresh_token='fake-rt',client_id='fake-client'));db.commit()
    result=sources(page=1,db=db)
    assert result['items'][0]['auto_recovery']
    db.refresh(row)
    assert not row.refresh_token and not row.client_id


def test_dashboard_counts_include_deliveries_outside_recent_window(db,monkeypatch):
    from app.api.routes.integration import status
    monkeypatch.setattr(link,'settings',lambda db:dict(CFG))
    for i in range(650):
        db.add(CredentialDelivery(key=f'test-site/external:{i}',source_key=f'external:{i}',site_id='test-site',target='http://127.0.0.1',version=1,state='ready',updated_at=time.time()))
    db.commit();result=status(db=db)
    assert result['counts']['ready']==650 and len(result['deliveries'])==100


def test_source_pagination_crosses_external_pool_boundary_without_duplicates(db,monkeypatch):
    from app.models.adobe_member import AdobeMember
    from app.api.routes.integration import sources
    monkeypatch.setattr(link,'settings',lambda db:dict(CFG))
    for i in range(105):
        db.add(ExternalMember(email=f'external-{i}@fixture.invalid',cookie='fake' if i%2 else '',mail_url='http://127.0.0.1/mail'))
    for i in range(102):
        db.add(AdobeMember(admin_id=0,email=f'pool-{i}@fixture.invalid',refresh_token='fake',client_id='fake'))
    db.add(AdobeMember(admin_id=0,email='admin@fixture.invalid',is_admin=True))
    db.commit()
    pages=[sources(page=i,db=db) for i in (1,2,3)]
    assert [len(p['items']) for p in pages]==[100,100,7]
    assert all(p['total']==207 for p in pages)
    rows=[row for p in pages for row in p['items']]
    assert len({row['source_key'] for row in rows})==207
    assert rows[104]['source']=='外部子号' and rows[105]['source']=='号池'
    assert sum(row['has_cookie'] for row in rows)==52
    assert not sources(page=4,db=db)['items']
    assert sources(page=0,db=db)['page']==1


def test_reliable_pool_preserves_existing_account_skip_and_credit_threshold(storage,monkeypatch):
    from app.models.adobe_member import AdobeMember
    from app.services import pool_sub2
    from app.services.job_manager import Job
    factory,_=storage
    monkeypatch.setattr(pool_sub2,'SessionLocal',factory)
    monkeypatch.setattr(pool_sub2,'_check_target',lambda cfg:None)
    monkeypatch.setattr(link,'login_pool',lambda *a,**k:pytest.fail('existing account must not trigger login'))
    with factory() as db:
        row=AdobeMember(admin_id=0,email='pool@fixture.invalid',credits=10,cookie='')
        db.add(row);db.commit();mid=row.id
    monkeypatch.setattr(link,'inventory',lambda *a,**k:[{'id':99,'email':'pool@fixture.invalid'}])
    assert pool_sub2._one_reliable(Job(1,'pool_cookie_sub2',{}),mid,CFG,lambda *a:None)[0]=='existing'
    monkeypatch.setattr(link,'inventory',lambda *a,**k:[])
    with factory() as db:
        row=db.get(AdobeMember,mid);row.cookie='fixture-cookie';db.commit()
    with pytest.raises(ValueError,match='4000'):
        pool_sub2._one_reliable(Job(2,'pool_cookie_sub2',{}),mid,CFG,lambda *a:None)


def test_pending_delivery_survives_reopened_database_without_relogin(storage,monkeypatch):
    factory,mid=storage
    key=f'external:{mid}'
    with factory() as db:
        link.queue_source(db,key,account_id=99)
    original_engine=factory.kw['bind']
    url=original_engine.url
    original_engine.dispose()
    reopened=create_engine(url,connect_args={'check_same_thread':False})
    monkeypatch.setattr(link,'SessionLocal',sessionmaker(bind=reopened,autoflush=False))
    monkeypatch.setattr(external_login,'login_and_store',lambda *a,**k:pytest.fail('delivery restart must not login'))
    calls=[]
    def request(cfg,method,path,body=None):
        calls.append((method,path))
        if path=='/capabilities':return {'site_id':'test-site','protocol':2}
        if path.startswith('/accounts?'):return {'items':[{'id':99,'email':'one@fixture.invalid'}],'next_cursor':0}
        return {'id':99,'status':'active','schedulable':True,'integration':{'verification':'verified'}}
    monkeypatch.setattr(link,'request',request)
    try:
        link.deliver('test-site/'+key)
        with link.SessionLocal() as db:
            delivery=db.get(CredentialDelivery,'test-site/'+key)
            assert delivery.state=='ready' and delivery.attempts==1 and delivery.version==1
            assert db.get(ExternalMember,mid).cookie=='fixture-cookie'
            assert not list(db.scalars(select(RecoveryJob)))
        assert ('POST','/accounts/99/credentials') in calls
        assert ('POST','/accounts/99/verify') in calls
    finally:reopened.dispose()


def test_interrupted_login_is_not_replayed_and_request_id_remains_durable(storage,monkeypatch):
    factory,mid=storage
    with factory() as db:
        job=link.submit_recovery(db,'interrupted','one@fixture.invalid',f'external:{mid}')
        job.state='running';job.updated_at=time.time()-300;db.commit()
    factory.kw['bind'].dispose()
    monkeypatch.setattr(link._login_executor,'submit',lambda *a,**k:pytest.fail('interrupted login must not replay'))
    link.tick()
    with factory() as db:
        same=link.submit_recovery(db,'interrupted','one@fixture.invalid',f'external:{mid}')
        assert same.state=='failed' and same.code=='outcome_unknown'
        assert len(list(db.scalars(select(RecoveryJob))))==1
