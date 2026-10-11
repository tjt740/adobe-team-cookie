import asyncio
import threading
import time
from types import SimpleNamespace

from app.models.external_member import ExternalMember
from app.services import external_login as login, external_sub2 as sync
from app.services.job_manager import JOBS, Job


def wait_until(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        time.sleep(.01)
    assert predicate()


def test_next_batch_waits_for_twenty_and_successes_push_immediately(monkeypatch, SessionLocal):
    monkeypatch.setattr(login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(login.setting_crud, 'get_settings', lambda db: SimpleNamespace(concurrency=5))
    release = threading.Event()
    started, pushed, failures = [], [], []
    active = maximum = 0
    lock = threading.Lock()

    def fake(mid, **kw):
        nonlocal active, maximum
        assert kw['sync_to_sub2'] is False
        with lock:
            started.append(mid)
            active += 1
            maximum = max(maximum, active)
        try:
            if mid == 1:
                assert release.wait(5)
            return {'ok': mid != 7}
        finally:
            with lock:
                active -= 1

    def push(mid, target, **kw):
        assert target == 'https://sub2.example/api/v1'
        pushed.append(mid)
        return {'status': 'pending', 'message': '已提交 Sub2 推送'}

    monkeypatch.setattr(login, 'login_and_store', fake)
    monkeypatch.setattr(sync, 'queue_login_push', push)
    job = Job(1, 'external_login', {'member_ids': list(range(1, 46)), 'push_to_sub2': True,
                                  'sub2_target': 'https://sub2.example/api/v1'})
    def run():
        try:
            login.batch_login_worker(job)
        except BaseException as exc:
            failures.append(exc)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        wait_until(lambda: len(started) == 20 and len(pushed) == 18)
        assert 21 not in started and 1 not in pushed and 7 not in pushed
        assert job.extra['batch'] == {'index': 1, 'total': 3, 'size': 20}
        release.set()
        worker.join(5)
        assert not worker.is_alive() and not failures
        assert maximum <= 5
        assert set(started) == set(range(1, 46))
        assert set(pushed) == set(range(1, 46)) - {7}
        assert job.success == 44 and job.fail == 1
        assert job.extra['batch'] == {'index': 3, 'total': 3, 'size': 20}
    finally:
        release.set()
        worker.join(5)


def test_sync_failure_does_not_turn_successful_login_into_failure(monkeypatch, SessionLocal):
    monkeypatch.setattr(login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(login.setting_crud, 'get_settings', lambda db: SimpleNamespace(concurrency=1))
    monkeypatch.setattr(login, 'login_and_store', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(sync, 'queue_login_push', lambda *a, **kw: {'status': 'failed', 'message': 'Sub2 暂不可用'})
    job = Job(1, 'external_login', {'member_ids': [1, 2], 'push_to_sub2': True})
    login.batch_login_worker(job)
    assert job.success == 2 and job.fail == 0
    assert all(i['status'] == 'done' and 'Sub2 暂不可用' in i['message'] for i in job.extra['items'])


def test_startup_recovers_external_tasks_and_preserves_completed_results(client, db, monkeypatch):
    from app import main
    rows = [ExternalMember(email=f'restart{i}@example.test', login_status='ok', cookie='saved') for i in range(4)]
    db.add_all(rows)
    db.commit()
    job = Job(1, 'external_login', {'member_ids': [m.id for m in rows]})
    job.success, job.fail, job.target = 1, 1, 4
    job.created_at += 1  # Recorded after these accounts were created.
    job.extra['items'] = [{'id': m.id, 'status': phase, 'message': phase}
                          for m, phase in zip(rows, ['done', 'failed', 'running', 'pending'])]
    JOBS._persist_job(job)
    monkeypatch.setattr(main, 'init_db', lambda: None)
    monkeypatch.setattr(sync, 'resume_pending', lambda: None)
    async def startup():
        async with main.lifespan(main.app):
            pass
    asyncio.run(startup())
    recovered = JOBS.get(1)
    assert recovered.status == 'error' and recovered.finished_at
    assert (recovered.success, recovered.fail) == (1, 1)
    assert [i['status'] for i in recovered.extra['items']] == ['done', 'failed', 'interrupted', 'interrupted']
    assert all(m.cookie == 'saved' for m in rows)
    listing = client.get('/api/external/members').json()['items']
    states = {r['id']: r['latest_job']['item_status'] for r in listing}
    assert [states[m.id] for m in rows] == ['done', 'failed', 'interrupted', 'interrupted']
    assert 'saved' not in str([r['latest_job'] for r in listing])
