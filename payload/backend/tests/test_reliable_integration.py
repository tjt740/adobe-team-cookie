import hashlib
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember
from app.models.integration import CredentialState, CredentialDelivery, RecoveryJob, LoginLease
from app.services import reliable_integration as link, login_coordinator

CFG={'enabled':True,'integration_key':'test-key','site_id':'test-site','issuer':'test-okad',
     'base_url':'http://127.0.0.1:12345','admin_token':'test-admin','platform':'adobe','group_ids':[1]}

@pytest.fixture
def setup(monkeypatch,SessionLocal):
    monkeypatch.setattr(link,'SessionLocal',SessionLocal)
    monkeypatch.setattr(link,'settings',lambda db:dict(CFG))


def test_cookie_and_delivery_rollback_together(db,setup):
    row=ExternalMember(email='one@test.example',cookie='old',login_status='ok',mail_url='http://mail.test')
    db.add(row);db.commit()
    row.cookie='new'
    link.record_cookie(db,'external:'+str(row.id),row.email,row.cookie)
    db.rollback();db.refresh(row)
    assert row.cookie=='old'
    assert db.get(CredentialState,'external:'+str(row.id)) is None
    assert not list(db.scalars(select(CredentialDelivery)))
    row.cookie='new';link.record_cookie(db,'external:'+str(row.id),row.email,row.cookie);db.commit()
    assert db.get(CredentialState,'external:'+str(row.id)).version==1
    assert len(list(db.scalars(select(CredentialDelivery))))==1


def test_recovery_source_disambiguation_and_manual_gate(db,setup):
    external=ExternalMember(email='same@test.example',otp_mode='manual',cookie='cookie')
    pool=AdobeMember(admin_id=0,email='same@test.example',refresh_token='rt',client_id='cid')
    db.add_all([external,pool]);db.commit()
    with pytest.raises(link.IntegrationError,match='多个来源'):link.resolve(db,external.email)
    with pytest.raises(link.IntegrationError) as error:link.capability(db,external.email,'external:'+str(external.id))
    assert error.value.code=='needs_manual'
    key,row=link.capability(db,pool.email,'pool:'+str(pool.id))
    assert key.startswith('pool:') and row.id==pool.id


def test_recovery_request_id_is_durable(db,setup):
    row=ExternalMember(email='one@test.example',mail_url='http://mail.test')
    db.add(row);db.commit()
    one=link.submit_recovery(db,'incident-1',row.email)
    one.state='done';db.commit()
    two=link.submit_recovery(db,'incident-1',row.email)
    assert two.id==one.id and two.state=='done'
    with pytest.raises(link.IntegrationError):link.submit_recovery(db,'incident-1','other@test.example')
    assert len(list(db.scalars(select(RecoveryJob))))==1


def test_delivery_failure_retries_cookie_without_login(db,setup,monkeypatch):
    row=ExternalMember(email='one@test.example',cookie='secret-cookie',login_status='ok')
    db.add(row);db.commit();key='external:'+str(row.id)
    link.queue_source(db,key)
    monkeypatch.setattr(link,'request',lambda *a,**k:(_ for _ in ()).throw(link.IntegrationError('transport','network',True)))
    monkeypatch.setattr(link,'login_pool',lambda *a,**k:pytest.fail('delivery must not login'))
    link.deliver('test-site/'+key)
    db.expire_all();d=db.get(CredentialDelivery,'test-site/'+key)
    assert d.state=='retry' and d.next_at>time.time() and d.lease_until==0
    assert row.cookie=='secret-cookie' and not list(db.scalars(select(RecoveryJob)))
    from app.services.external_sub2 import summary
    assert summary(row,link.target(CFG))['sub2_status']=='pending'
    assert summary(row,link.target(CFG))['sub2_message']=='network'


@pytest.mark.parametrize('failure,message', [
    ('not_found','Sub2 没有该账号，请先手动推送入库'),
    ('configuration','联动密钥无效或无权操作，请检查配置'),
])
def test_failure_before_remote_id_updates_external_status(db,setup,monkeypatch,failure,message):
    from app.services.external_sub2 import summary
    row=ExternalMember(email='unlinked@test.example',cookie='saved-cookie',login_status='ok')
    db.add(row);db.commit();key='external:'+str(row.id)
    link.queue_source(db,key)
    def request(cfg,method,path,body=None):
        if failure=='not_found':
            return {'site_id':CFG['site_id']} if path=='/capabilities' else {'items':[],'next_cursor':0}
        raise link.IntegrationError(failure,message)
    monkeypatch.setattr(link,'request',request)
    link.deliver('test-site/'+key)
    db.expire_all();delivery=db.get(CredentialDelivery,'test-site/'+key)
    assert delivery.state=='blocked' and delivery.account_id is None
    shown=summary(row,link.target(CFG))
    assert shown['sub2_status']=='failed' and shown['sub2_message']==message
    assert shown['sub2_account_id'] is None and shown['sub2_synced_at'] is None
    assert row.cookie=='saved-cookie'


def test_late_delivery_cannot_ack_new_cookie(db,setup,monkeypatch,SessionLocal):
    row=ExternalMember(email='one@test.example',cookie='first',login_status='ok')
    db.add(row);db.commit();key='external:'+str(row.id);mid=row.id
    link.queue_source(db,key)
    def request(cfg,method,path,body=None):
        if path=='/capabilities':return {'protocol':2,'site_id':'test-site'}
        if path.startswith('/accounts?'):return {'items':[{'id':10,'email':'one@test.example'}],'next_cursor':0}
        if path.endswith('/credentials'):
            with SessionLocal() as session:
                member=session.get(ExternalMember,mid);member.cookie='second'
                link.record_cookie(session,key,member.email,member.cookie);session.commit()
        return {'id':10,'status':'active','schedulable':True,'integration':{'verification':'verified'}}
    monkeypatch.setattr(link,'request',request)
    link.deliver('test-site/'+key)
    db.expire_all();d=db.get(CredentialDelivery,'test-site/'+key)
    assert d.version==2 and d.state=='pending' and d.lease_until==0


def test_deleted_link_not_recreated(db,setup,monkeypatch):
    row=ExternalMember(email='one@test.example',cookie='cookie');db.add(row);db.commit()
    key='external:'+str(row.id);link.queue_source(db,key,True,99)
    calls=[]
    def request(cfg,method,path,body=None):
        calls.append((method,path))
        return {'protocol':2,'site_id':'test-site'} if path=='/capabilities' else {'items':[],'next_cursor':0}
    monkeypatch.setattr(link,'request',request)
    link.deliver('test-site/'+key)
    db.expire_all();assert db.get(CredentialDelivery,'test-site/'+key).state=='blocked'
    assert all(method=='GET' for method,_ in calls)


def test_manual_and_automatic_logins_join_one_lease(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'lease.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    started=threading.Event();release=threading.Event();calls=[]
    def action():
        calls.append(1);started.set();assert release.wait(5)
        with factory() as db:login_coordinator.assert_owner(db)
        return {'ok':True,'cookie':'private-cookie','code':''}
    with ThreadPoolExecutor(max_workers=2) as executor:
        one=executor.submit(login_coordinator.run,'external:1','ONE@test.example',action,factory,lambda db:{'cookie':'private-cookie'})
        assert started.wait(3)
        two=executor.submit(login_coordinator.run,'external:1','one@test.example',action,factory,lambda db:{'cookie':'private-cookie'})
        time.sleep(.3);release.set()
        assert one.result()['ok'] and two.result()['cookie']=='private-cookie'
    assert calls==[1]
    with factory() as db:
        lease=db.get(LoginLease,'one@test.example');assert 'cookie' not in lease.result
    engine.dispose()


def test_stale_login_owner_cannot_commit(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'fence.db'));Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    def action():
        with factory() as db:
            lease=db.get(LoginLease,'one@test.example');lease.owner='new-owner';db.commit()
        with factory() as db:
            with pytest.raises(RuntimeError):login_coordinator.assert_owner(db)
        return {'ok':False,'code':'outcome_unknown'}
    assert not login_coordinator.run('external:1','one@test.example',action,factory,lambda db:{})['ok']
    engine.dispose()


def test_login_destination_is_frozen_when_settings_change(db,setup,monkeypatch):
    row=ExternalMember(email='one@test.example',cookie='new');db.add(row);db.commit()
    key='external:'+str(row.id)
    with link.login_destination(CFG):
        monkeypatch.setattr(link,'settings',lambda db:{**CFG,'site_id':'other-site','base_url':'http://localhost:9999'})
        link.record_cookie(db,key,row.email,row.cookie);db.commit()
    delivery=db.get(CredentialDelivery,'test-site/'+key)
    assert delivery and delivery.target==link.target(CFG)
    assert db.get(CredentialDelivery,'other-site/'+key) is None
    monkeypatch.setattr(link,'request',lambda *a,**k:pytest.fail('changed destination must not receive cookie'))
    link.deliver(delivery.key)
    db.expire_all();assert db.get(CredentialDelivery,delivery.key).state=='blocked'


def test_stale_delivery_cannot_release_successor_lease(db,setup,monkeypatch,SessionLocal):
    row=ExternalMember(email='one@test.example',cookie='cookie');db.add(row);db.commit()
    key='external:'+str(row.id);link.queue_source(db,key)
    successor=time.time()+900
    def request(*args,**kwargs):
        with SessionLocal() as session:
            delivery=session.get(CredentialDelivery,'test-site/'+key)
            delivery.lease_until=successor;delivery.message='new worker';session.commit()
        raise link.IntegrationError('transport','old failure',True)
    monkeypatch.setattr(link,'request',request)
    link.deliver('test-site/'+key)
    db.expire_all();delivery=db.get(CredentialDelivery,'test-site/'+key)
    assert delivery.lease_until==successor and delivery.message=='new worker'


def test_deleted_source_stops_delivery_and_releases_lease(db,setup,monkeypatch):
    row=ExternalMember(email='one@test.example',cookie='cookie');db.add(row);db.commit()
    key='external:'+str(row.id);link.queue_source(db,key)
    db.delete(row);db.commit()
    monkeypatch.setattr(link,'request',lambda *a,**k:pytest.fail('deleted source must not send'))
    link.deliver('test-site/'+key)
    db.expire_all();delivery=db.get(CredentialDelivery,'test-site/'+key)
    assert delivery.state=='blocked' and delivery.lease_until==0
