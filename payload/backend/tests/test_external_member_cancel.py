import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.external_member import ExternalMember
from app.services import external_login as login, manual_otp
from app.services.job_manager import JOBS, Job, JobCancelled


def wait_until(predicate, timeout=3):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.01)
    assert predicate(), 'worker did not reach expected state'


@pytest.fixture
def members(db):
    rows = [ExternalMember(email=f'cancel{i}@example.test', created_at=datetime(2026, 1, 1),
                           cookie='saved-cookie', login_status='ok') for i in range(1, 4)]
    db.add_all(rows); db.commit()
    return rows


def start(monkeypatch, SessionLocal, members, callback, concurrency=1, **meta):
    monkeypatch.setattr(login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(login.setting_crud, 'get_settings', lambda db: SimpleNamespace(concurrency=concurrency))
    monkeypatch.setattr(login, 'login_and_store', callback)
    return JOBS.start('external_login', login.batch_login_worker, meta={
        'member_ids': [m.id for m in members],
        'member_emails': {str(m.id): m.email for m in members}, **meta})


def stop(client, job, member):
    return client.post(f'/api/external/members/{member.id}/cancel-job', json={'job_id': job.id})


def phases(job):
    return {i['id']: i['status'] for i in job.to_dict()['extra']['items']}


def test_queued_member_is_skipped_without_stopping_batch(client, db, members, monkeypatch, SessionLocal):
    entered, release = threading.Event(), threading.Event()
    calls, pushes = [], []
    def fake(mid, **kwargs):
        calls.append(mid)
        if mid == members[0].id:
            entered.set(); assert release.wait(4)
        return {'ok': True}
    from app.services import external_sub2
    monkeypatch.setattr(external_sub2, 'queue_login_push', lambda mid, *a, **kw: pushes.append(mid) or {'message':'已提交'})
    job = start(monkeypatch, SessionLocal, members, fake, push_to_sub2=True)
    try:
        assert entered.wait(3)
        response = stop(client, job, members[1])
        assert response.status_code == 200 and response.json()['requested']
        assert not stop(client, job, members[1]).json()['requested']
        assert phases(job)[members[1].id] == 'cancelled' and job.status == 'running' and not job.cancelled
        from app.api.routes.external_member import _active_jobs
        assert members[1].id not in _active_jobs([m.id for m in members])
        release.set(); wait_until(lambda: job.finished_at is not None)
        assert calls == pushes == [members[0].id, members[2].id]
        assert job.success == 2 and job.fail == 0 and job.to_dict()['cancelled_count'] == 1
        assert job.result == {'total':3, 'success':2, 'fail':0, 'cancelled':1}
        assert phases(job)[members[0].id] == phases(job)[members[2].id] == 'done'
        summary = client.get('/api/external/members').json()['items']
        assert next(m for m in summary if m['id']==members[1].id)['latest_job']['cancelled_count'] == 1
        db.refresh(members[1]); assert members[1].cookie == 'saved-cookie'
    finally:
        release.set(); job.cancel()


def test_running_cancel_does_not_count_as_failure_or_push(client, members, monkeypatch, SessionLocal):
    entered, release = threading.Event(), threading.Event()
    calls, pushed = [], []
    def fake(mid, **kwargs):
        calls.append(mid)
        if mid == members[0].id:
            entered.set(); assert release.wait(4)
        # Simulate an HTTP call that returns successfully without a cancel check.
        return {'ok':True}
    from app.services import external_sub2
    monkeypatch.setattr(external_sub2,'queue_login_push',lambda mid,*a,**kw:pushed.append(mid) or {'message':'已提交'})
    job = start(monkeypatch,SessionLocal,members,fake,concurrency=2,push_to_sub2=True)
    try:
        assert entered.wait(3)
        assert stop(client,job,members[0]).json()['requested']
        assert phases(job)[members[0].id]=='cancelling'
        release.set();wait_until(lambda:job.finished_at is not None)
        assert job.status=='done' and job.success==2 and job.fail==0
        assert members[0].id not in pushed and set(pushed)=={members[1].id,members[2].id}
        assert phases(job)[members[0].id]=='cancelled' and not job.cancelled
    finally:
        release.set();job.cancel()


def test_paused_queue_can_cancel_one_then_all_remaining(client, members, monkeypatch, SessionLocal):
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def fake(mid,**kwargs):
        calls.append(mid);entered.set();assert release.wait(4)
        return {'ok':True}
    job=start(monkeypatch,SessionLocal,members,fake)
    try:
        assert entered.wait(3);assert job.pause();release.set()
        wait_until(lambda:job.status=='paused')
        assert stop(client,job,members[1]).json()['requested']
        assert job.status=='paused' and calls==[members[0].id]
        assert stop(client,job,members[2]).json()['requested']
        wait_until(lambda:job.finished_at is not None)
        assert job.success==1 and job.fail==0 and job.to_dict()['cancelled_count']==2
    finally:
        release.set();job.cancel()


def test_manual_otp_wait_only_cancels_target(client, members, monkeypatch, SessionLocal):
    broker=manual_otp.ManualOtpBroker()
    def fake(mid,*,log,check_cancelled,**kwargs):
        broker.request(mid,f'{mid}@example.test',timeout=4,check_cancelled=check_cancelled)
        return {'ok':True}
    job=start(monkeypatch,SessionLocal,members[:2],fake,concurrency=2)
    try:
        wait_until(lambda:all(broker.status(m.id) for m in members[:2]))
        assert stop(client,job,members[0]).json()['requested']
        wait_until(lambda:phases(job)[members[0].id]=='cancelled')
        assert broker.status(members[0].id) is None
        challenge=broker.status(members[1].id);assert challenge
        broker.submit(members[1].id,challenge['request_id'],'123456')
        wait_until(lambda:job.finished_at is not None)
        assert job.success==1 and job.fail==0 and not job.cancelled
    finally:
        job.cancel()


def test_cancel_before_initialization_and_completion_race(monkeypatch, SessionLocal):
    monkeypatch.setattr(login,'SessionLocal',SessionLocal)
    monkeypatch.setattr(login.setting_crud,'get_settings',lambda db:SimpleNamespace(concurrency=1))
    calls=[]
    monkeypatch.setattr(login,'login_and_store',lambda mid,**kw:calls.append(mid) or {'ok':True})
    job=Job(1,'external_login',{'member_ids':[1,2]})
    assert job.cancel_item(2)=='requested'
    login.batch_login_worker(job)
    assert calls==[1] and phases(job)=={1:'done',2:'cancelled'}
    assert job.cancel_item(1)=='finished' and job.success==1 and job.fail==0
    assert job.cancel_item(2)=='cancelled'


def test_cancel_queued_member_in_later_batch(monkeypatch, SessionLocal):
    monkeypatch.setattr(login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(login.setting_crud, 'get_settings', lambda db: SimpleNamespace(concurrency=1))
    calls = []
    job = Job(1, 'external_login', {'member_ids': list(range(1, 53))})
    def fake(mid, **kwargs):
        calls.append(mid)
        if mid == 1:
            assert job.cancel_item(51) == 'requested'
        return {'ok': True}
    monkeypatch.setattr(login, 'login_and_store', fake)
    login.batch_login_worker(job)
    assert calls == list(range(1, 51)) + [52]
    assert job.success == 51 and job.fail == 0 and phases(job)[51] == 'cancelled'
    assert job.extra['batch']['index'] == 2


def test_api_identity_auth_and_completed_protection(client, db, members):
    JOBS._ensure_storage()
    def save(jid,member,kind='external_login',phase='pending'):
        job=Job(jid,kind,{'member_ids':[member.id],'member_emails':{str(member.id):member.email}},persist_cb=JOBS._persist_job)
        job.initialize_items([{'id':member.id,'status':phase}]);JOBS._jobs[jid]=job
        return job
    old=save(1,members[0]);new=save(2,members[0])
    assert stop(client,old,members[0]).status_code==409
    assert not new._cancelled_item_ids and not old._cancelled_item_ids
    assert stop(client,new,members[1]).status_code==409
    finished=save(3,members[1],phase='done');finished.success=1;finished.persist()
    assert not stop(client,finished,members[1]).json()['requested']
    assert phases(finished)[members[1].id]=='done' and finished.success==1
    members[0].email='renamed@example.test';db.commit()
    assert stop(client,new,members[0]).status_code==409
    assert client.post('/api/external/members/999999/cancel-job',json={'job_id':2}).status_code==404
    assert client.post(f'/api/external/members/{members[0].id}/cancel-job',json={'job_id':0}).status_code==422
    from app.main import app
    from app.api.deps import get_current_user
    override=app.dependency_overrides.pop(get_current_user)
    try:
        assert stop(client,new,members[0]).status_code==401
    finally:app.dependency_overrides[get_current_user]=override
    assert JOBS.cancel_external_member(save(4,members[2],kind='pool_login').id,members[2].id)=='not_found'


def test_orphan_and_restart_preserve_individual_stop(client,members):
    JOBS._ensure_storage()
    job=Job(1,'external_login',{'member_ids':[m.id for m in members],
        'member_emails':{str(m.id):m.email for m in members}},persist_cb=JOBS._persist_job)
    job.initialize_items([{'id':m.id,'status':'pending'} for m in members])
    assert stop(client,job,members[1]).json()['requested']
    saved=JOBS.get(1)
    assert phases(saved)=={members[0].id:'pending',members[1].id:'cancelled',members[2].id:'pending'}
    assert saved._cancelled_item_ids=={members[1].id}
    saved.extra['items'][1]['status']='cancelling';saved._persist_cb=JOBS._persist_job;saved.persist()
    JOBS.recover_interrupted('external_login')
    assert phases(JOBS.get(1))=={members[0].id:'interrupted',members[1].id:'cancelled',members[2].id:'interrupted'}


def test_scoped_cancellation_preserves_saved_credentials(db,members,monkeypatch,SessionLocal):
    member=members[0]
    monkeypatch.setattr(login,'SessionLocal',SessionLocal)
    job=Job(1,'external_login',{'member_ids':[member.id]})
    job.initialize_items([{'id':member.id,'status':'pending'}]);assert job.begin_item(member.id)
    def protocol(**kwargs):
        assert job.cancel_item(member.id)=='requested'
        kwargs['on_credentials'](adobe_password='must-not-be-saved')
        return {'cookie':'must-not-be-saved','credits':4000,'credits_total':4000}
    monkeypatch.setattr(login.firefly,'register_account',protocol)
    with pytest.raises(JobCancelled):
        login.login_and_store(member.id,check_cancelled=lambda:job.check_cancelled(member.id))
    db.refresh(member)
    assert member.cookie=='saved-cookie' and member.adobe_password!='must-not-be-saved' and member.login_status=='ok'
