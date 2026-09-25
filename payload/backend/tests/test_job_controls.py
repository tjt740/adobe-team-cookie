import threading
import time
from types import SimpleNamespace

from app.services.job_manager import JOBS, Job, JobCancelled
from app.services import external_login as login


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    assert predicate(), 'worker did not reach expected state'


def setup_worker(monkeypatch, SessionLocal, callback):
    monkeypatch.setattr(login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(login.setting_crud, 'get_settings', lambda db: SimpleNamespace(concurrency=1))
    monkeypatch.setattr(login, 'login_and_store', callback)


def test_pause_drains_current_account_then_resume_queue(client, monkeypatch, SessionLocal):
    entered, release = threading.Event(), threading.Event()
    started = []
    def fake(mid, *, log=None, check_cancelled=None):
        started.append(mid)
        if mid == 1:
            entered.set(); assert release.wait(3)
        return {'ok': True}
    setup_worker(monkeypatch, SessionLocal, fake)
    job = JOBS.start('external_login', login.batch_login_worker, meta={'member_ids':[1,2,3]})
    try:
        assert entered.wait(3)
        assert client.post(f'/api/adobe-accounts/jobs/{job.id}/pause').json()['success']
        assert job.status == 'pausing'
        release.set()
        wait_until(lambda: job.status == 'paused')
        assert started == [1] and job.success == 1 and job.finished_at is None
        assert JOBS.delete_many([job.id]) == (0,[job.id])
        assert client.post(f'/api/adobe-accounts/jobs/{job.id}/resume').json()['success']
        wait_until(lambda: job.finished_at is not None)
        assert job.status == 'done' and started == [1,2,3] and job.success == 3
    finally:
        release.set();job.cancel()


def test_cancel_waits_for_request_exit_and_skips_queue(client, monkeypatch, SessionLocal):
    entered, release = threading.Event(), threading.Event()
    started = []
    def fake(mid, *, log=None, check_cancelled=None):
        started.append(mid);entered.set();assert release.wait(3)
        check_cancelled()
        raise AssertionError('cancelled login must not store a result')
    setup_worker(monkeypatch, SessionLocal, fake)
    job = JOBS.start('external_login', login.batch_login_worker, meta={'member_ids':[1,2,3]})
    try:
        assert entered.wait(3)
        assert client.post(f'/api/adobe-accounts/jobs/{job.id}/cancel').json()['success']
        assert job.status == 'cancelling' and job.finished_at is None
        assert JOBS.delete_many([job.id]) == (0,[job.id])
        release.set()
        wait_until(lambda: job.finished_at is not None)
        assert job.status == 'cancelled' and started == [1]
        assert job.fail == 0 and job.success == 0 and not job.error
        assert not client.post(f'/api/adobe-accounts/jobs/{job.id}/resume').json()['success']
    finally:
        release.set();job.cancel()


def test_cancel_wakes_paused_workers(client, monkeypatch, SessionLocal):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def fake(mid, *, log=None, check_cancelled=None):
        calls.append(mid);entered.set();assert release.wait(3)
        return {'ok':True}
    setup_worker(monkeypatch, SessionLocal, fake)
    job = JOBS.start('external_login',login.batch_login_worker,meta={'member_ids':[1,2]})
    try:
        assert entered.wait(3);assert job.pause();release.set()
        wait_until(lambda:job.status=='paused')
        assert job.cancel()
        wait_until(lambda:job.finished_at is not None)
        assert job.status=='cancelled' and calls==[1] and job.success==1
    finally:
        release.set();job.cancel()


def test_pause_cannot_lose_last_completed_result(client, monkeypatch, SessionLocal):
    def fake(mid, *, log=None, check_cancelled=None):
        job = next(iter(JOBS._jobs.values()))
        job.pause()
        return {'ok':True}
    setup_worker(monkeypatch, SessionLocal, fake)
    job=JOBS.start('external_login',login.batch_login_worker,meta={'member_ids':[1]})
    wait_until(lambda:job.finished_at is not None)
    assert job.status=='done' and job.success==1


def test_other_jobs_do_not_offer_fake_pause():
    job=Job(1,'pool_login',{})
    assert not job.pause()


def test_protocol_cancellation_is_not_saved_as_login_failure(db, monkeypatch, SessionLocal):
    from app.models.external_member import ExternalMember
    member=ExternalMember(email='cancel@example.test',cookie='existing',login_status='ok')
    db.add(member);db.commit()
    monkeypatch.setattr(login,'SessionLocal',SessionLocal)
    job=Job(1,'external_login',{})
    def protocol(**kw):
        job.cancel()
        kw['log']('request returned')
    monkeypatch.setattr(login.firefly,'register_account',protocol)
    try:
        login.login_and_store(member.id,log=job.log,check_cancelled=job.check_cancelled)
    except JobCancelled:
        pass
    else:
        raise AssertionError('cancellation swallowed')
    db.refresh(member)
    assert member.cookie=='existing' and member.login_status=='ok'


def test_pause_waits_for_all_inflight_accounts(client, monkeypatch, SessionLocal):
    releases = {1:threading.Event(), 2:threading.Event()}
    entered = {1:threading.Event(), 2:threading.Event()}
    started=[]
    def fake(mid, *, log=None, check_cancelled=None):
        started.append(mid)
        if mid in releases:
            entered[mid].set();assert releases[mid].wait(3)
        return {'ok':True}
    setup_worker(monkeypatch,SessionLocal,fake)
    monkeypatch.setattr(login.setting_crud,'get_settings',lambda db:SimpleNamespace(concurrency=2))
    job=JOBS.start('external_login',login.batch_login_worker,meta={'member_ids':[1,2,3]})
    try:
        assert entered[1].wait(3) and entered[2].wait(3)
        assert job.pause();releases[1].set()
        wait_until(lambda:job.success==1)
        assert job.status=='pausing' and sorted(started)==[1,2]
        releases[2].set();wait_until(lambda:job.status=='paused')
        assert job.resume();wait_until(lambda:job.finished_at is not None)
        assert job.status=='done' and job.success==3
    finally:
        [event.set() for event in releases.values()];job.cancel()
