import threading
from datetime import datetime
from time import time

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2_stock
from app.services.job_manager import JOBS, Job


@pytest.fixture
def members(db, monkeypatch):
    rows = [ExternalMember(email=f'state{i}@example.test', login_status='ok' if i < 3 else 'never',
                           cookie=f'cookie-{i}' if i < 3 else '', adobe_password='private' if i == 0 else '',
                           created_at=datetime(2026, 10, 1)) for i in range(5)]
    db.add_all(rows)
    db.commit()
    inventory = {r.id: {'in_stock': i != 4, 'account_health': {
        'state': 'error' if i < 2 else 'recovered',
        'codes': [408] if i == 0 else [401] if i == 1 else [],
        'errors': [{'code': 408 if i == 0 else 401}] if i < 2 else []}}
        for i, r in enumerate(rows)}
    monkeypatch.setattr(external_sub2_stock, 'membership', lambda db: {'ok': True, 'items': inventory})
    return rows


def test_or_before_pagination_export_and_batch(client, members, monkeypatch):
    chosen = ['sub2_401', 'sub2_408']
    for page, member in [(1, members[1]), (2, members[0])]:
        response = client.get('/api/external/members', params={'account_states': chosen, 'size': 1, 'page': page})
        assert response.status_code == 200, response.text
        assert response.json()['total'] == 2
        assert [r['id'] for r in response.json()['items']] == [member.id]
    assert len(client.get('/api/external/members/export', params={'account_states': chosen}).json()) == 2
    data = client.get('/api/external/members', params={
        'account_states': ['sub2_408', 'no_cookie'], 'keyword': 'state3'}).json()
    assert [r['id'] for r in data['items']] == [members[3].id]
    captured = []
    def start(kind, worker, *, meta):
        captured.extend(meta['member_ids'])
        return Job(999, kind, meta)
    monkeypatch.setattr(JOBS, 'start', start)
    response = client.post('/api/external/members/batch-login-filter', json={'account_states': chosen})
    assert response.status_code == 200, response.text
    assert set(captured) == {members[0].id, members[1].id}


def test_credentials_login_validation_and_inventory_failure(client, members, monkeypatch):
    for selected, indexes in [(['has_password'], [0]), (['no_password'], [4, 3, 2, 1]),
                              (['no_cookie', 'has_password'], [4, 3, 0]), (['ok'], [2, 1, 0])]:
        data = client.get('/api/external/members', params={'account_states': selected}).json()
        assert [r['id'] for r in data['items']] == [members[i].id for i in indexes]
    monkeypatch.setattr(external_sub2_stock, 'membership', lambda db: {'ok': False, 'message': '库存暂不可用'})
    for path in ['/api/external/members', '/api/external/members/export']:
        assert client.get(path, params={'account_states': ['sub2_408', 'has_cookie']}).status_code == 503
        assert client.get(path, params={'account_states': ['has_cookie']}).status_code == 200
    for invalid in [['unknown-value'], ['sub2_200'], ['ok'] * 33]:
        assert client.get('/api/external/members', params={'account_states': invalid}).status_code == 422
        assert client.post('/api/external/members/batch-login-filter', json={'account_states': invalid}).status_code == 422


def save_job(jid, members, *, status='running', phases=None, kind='external_login', memory=True):
    JOBS._ensure_storage()
    j = Job(jid, kind, {'member_ids': [m.id for m in members], 'target': len(members),
                       'member_emails': {str(m.id): m.email for m in members}}, persist_cb=JOBS._persist_job)
    j.status, j.created_at = status, int(time())
    j.extra = {'items': [{'id': m.id, 'status': phase} for m, phase in zip(members, phases or ['pending'] * len(members))]}
    j.persist()
    if memory:
        JOBS._jobs[jid] = j
    return j


def test_task_states_latest_and_identity(client, db, members):
    save_job(1, members[:3], phases=['done', 'running', 'pending'])
    save_job(2, [members[3]], status='paused')
    save_job(3, [members[4]], status='cancelled')
    for value, indexes in [('task_done', [0]), ('task_running', [1]), ('task_pending', [2]),
                           ('task_paused', [3]), ('task_cancelled', [4])]:
        response = client.get('/api/external/members', params={'account_states': [value]})
        assert response.status_code == 200, response.text
        assert [m['id'] for m in response.json()['items']] == [members[i].id for i in indexes]
    save_job(4, [members[1]], status='done', phases=['pending'])
    assert client.get('/api/external/members', params={'account_states': ['task_interrupted']}).json()['total'] == 1
    members[1].email = 'renamed@example.test'
    db.commit()
    assert client.get('/api/external/members', params={'account_states': ['task_interrupted']}).json()['total'] == 0


def test_stop_all_including_paused_and_orphan_preserves_other_jobs(client, members):
    running = save_job(1, members[:2], phases=['done', 'running'])
    running.success, running.logs = 1, ['已完成结果']
    running.persist()
    paused = save_job(2, [members[2]], status='paused')
    paused._pause_requested = True
    orphan = save_job(3, [members[3]], memory=False)
    completed = save_job(4, [members[4]], status='done', phases=['done'])
    unrelated = save_job(5, [members[4]], kind='pool_login')
    already = save_job(6, [members[4]])
    already.cancel()
    entered, result = threading.Event(), []
    def wait():
        entered.set()
        result.append(paused.begin_item())
    waiter = threading.Thread(target=wait)
    waiter.start()
    assert entered.wait(1)
    response = client.post('/api/external/members/cancel-all-jobs')
    waiter.join(2)
    assert response.status_code == 200, response.text
    assert response.json()['requested'] == 3 and response.json()['already_stopping'] == 1
    assert running.cancelled and paused.cancelled and result == [False] and not waiter.is_alive()
    assert JOBS.get(orphan.id).status == 'cancelled'
    assert not unrelated.cancelled and completed.status == 'done'
    assert running.success == 1 and running.logs[0] == '已完成结果'
    again = client.post('/api/external/members/cancel-all-jobs').json()
    assert again['requested'] == 0 and again['already_stopping'] == 3


def test_stop_all_requires_session(client):
    from app.api.deps import get_current_user
    from app.main import app
    override = app.dependency_overrides.pop(get_current_user)
    try:
        assert client.post('/api/external/members/cancel-all-jobs').status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = override


def test_stop_all_does_not_stop_at_recent_list_limit_or_first_error(client, members, monkeypatch):
    jobs = [save_job(i, [members[0]], memory=i < 10) for i in range(1, 65)]
    cancel = JOBS.cancel
    def sometimes_fails(jid):
        if jid == 2:
            raise RuntimeError('temporary write contention')
        return cancel(jid)
    monkeypatch.setattr(JOBS, 'cancel', sometimes_fails)
    result = client.post('/api/external/members/cancel-all-jobs').json()
    assert result['requested'] == 63 and result['failed'] == 1
    assert '请重试' in result['message']
    assert JOBS.get(64).status == 'cancelled'
    assert not jobs[1].cancelled
