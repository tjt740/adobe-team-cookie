import json

import pytest
from sqlalchemy import func, select

from app.api.routes import sub2
from app.models.adobe_member import AdobeMember
from app.models.external_member import ExternalMember
from app.services import pool_sub2 as service
from app.services.job_manager import Job, JobCancelled


@pytest.fixture
def flow(db, SessionLocal, monkeypatch):
    for key, value in {'sub2_base_url': 'http://sub2.test', 'sub2_admin_token': 'admin-secret',
                       'sub2_platform': 'adobe', 'sub2_group_ids': '2'}.items():
        sub2._set(db, key, value)
    db.commit()
    monkeypatch.setattr(service, 'SessionLocal', SessionLocal)
    accounts, logins, writes = [], [], []
    state = {'fail_create': False, 'lost_response': False, 'unavailable': False}

    def request(method, url, token, body=None, **kwargs):
        if state['unavailable']:
            return 401, '{}'
        if url.endswith('/admin/groups/all'):
            return 200, json.dumps({'data': [{'id': 2, 'platform': 'adobe'}]})
        if method == 'GET':
            return 200, json.dumps({'data': {'items': accounts, 'total': len(accounts)}})
        writes.append(body)
        if state['fail_create']:
            return 400, '{}'
        account = {**body, 'id': len(accounts) + 1}
        accounts.append(account)
        if state['lost_response']:
            raise TimeoutError('secret-response')
        return 201, json.dumps({'data': account})

    def login(**kwargs):
        logins.append(kwargs['email'])
        kwargs['on_credentials'](refresh_token='rotated-secret')
        return {'cookie': 'ims_sid=cookie-secret', 'access_token': 'web-token',
                'credits': 4000, 'rotated_refresh_token': 'rotated-secret'}

    monkeypatch.setattr(service.sub2_client, '_request', request)
    monkeypatch.setattr(service.firefly, 'register_account', login)
    members = [AdobeMember(admin_id=0, email=f'pool{i}@example.com', is_imported=True,
                           registered=True, access_token='ios-token', device_token='device-secret',
                           device_id='device-id', credits=4000, refresh_token='mail-secret', client_id='cid')
               for i in range(3)]
    db.add_all(members)
    db.commit()

    def run(ids=None):
        job = Job(1, 'pool_cookie_sub2', {'member_ids': ids or [members[0].id], 'target': len(ids or [1])})
        service.worker(job, service.configuration(db))
        db.expire_all()
        return job

    return members, accounts, logins, writes, state, run


def test_selected_pool_accounts_get_cookie_and_create_without_external_records(db, flow):
    members, accounts, logins, writes, _, run = flow
    job = run([members[0].id, members[1].id])
    assert job.success == 2 and job.fail == 0
    assert logins == [m.email for m in members[:2]]
    assert len(accounts) == 2
    for member in members[:2]:
        assert member.cookie == 'ims_sid=cookie-secret' and member.sub2_pushed_at
        assert member.access_token == 'ios-token' and member.device_token == 'device-secret'
        assert member.refresh_token == 'rotated-secret'
    assert not members[2].cookie and not members[2].sub2_pushed_at
    assert db.scalar(select(func.count()).select_from(ExternalMember)) == 0
    assert all(b['credentials']['cookie'] and 'access_token' not in b['credentials'] for b in writes)
    assert all(b['group_ids'] == [2] for b in writes)
    assert all(secret not in json.dumps(job.to_dict()) for secret in
               ('cookie-secret', 'ios-token', 'mail-secret', 'admin-secret', 'rotated-secret'))


def test_existing_account_skips_login_and_write(db, flow):
    members, accounts, logins, writes, _, run = flow
    accounts.append({'id': 42, 'platform': 'adobe', 'name': members[0].email,
                     'credentials': {'email': members[0].email}})
    job = run()
    assert job.result['existing'] == 1 and not writes and not logins


def test_failed_push_keeps_cookie_and_retry_uses_it(db, flow):
    members, accounts, logins, writes, state, run = flow
    state['fail_create'] = True
    first = run()
    assert first.fail == 1 and not members[0].sub2_pushed_at
    assert members[0].cookie and len(logins) == 1
    state['fail_create'] = False
    second = run()
    assert second.success == 1 and len(logins) == 1 and len(accounts) == 1


def test_lost_create_response_retry_checks_remote_before_login(db, flow):
    members, accounts, logins, writes, state, run = flow
    state['lost_response'] = True
    assert run().fail == 1
    assert run().result['existing'] == 1
    assert len(accounts) == len(writes) == len(logins) == 1


def test_one_login_failure_does_not_block_other_selected_account(db, flow, monkeypatch):
    members, _, _, writes, _, run = flow
    good = service.firefly.register_account
    def login(**kwargs):
        if kwargs['email'] == members[0].email:
            kwargs['on_credentials'](refresh_token='rotated-even-on-failure')
            raise RuntimeError('OTP timeout cookie-secret admin-secret')
        return good(**kwargs)
    monkeypatch.setattr(service.firefly, 'register_account', login)
    job = run([members[0].id, members[1].id])
    assert job.fail == job.success == 1 and len(writes) == 1
    assert members[0].refresh_token == 'rotated-even-on-failure' and not members[0].cookie
    assert '验证码' in job.result['items'][0]['message']
    assert 'cookie-secret' not in json.dumps(job.to_dict())


def test_remote_unavailable_does_not_login(db, flow):
    _, _, logins, writes, state, run = flow
    state['unavailable'] = True
    with pytest.raises(ValueError):
        run()
    assert not logins and not writes


def test_cookie_saved_but_low_credits_not_pushed(db, flow, monkeypatch):
    members, _, _, writes, _, run = flow
    monkeypatch.setattr(service.firefly, 'register_account', lambda **_: {'cookie': 'new', 'credits': 20})
    job = run()
    assert job.fail == 1 and members[0].cookie == 'new' and not writes
    assert '4000' in job.result['items'][0]['message']


def test_target_change_during_login_stops_push(db, flow, monkeypatch):
    members, _, _, writes, _, run = flow
    def login(**kwargs):
        sub2._set(db, 'sub2_group_ids', '3')
        db.commit()
        return {'cookie': 'new', 'credits': 4000}
    monkeypatch.setattr(service.firefly, 'register_account', login)
    assert run().fail == 1
    assert members[0].cookie == 'new' and not writes


def test_cancel_after_login_preserves_cookie_but_does_not_push(db, flow, monkeypatch):
    members, _, _, writes, _, _ = flow
    job = Job(1, 'pool_cookie_sub2', {'member_ids': [members[0].id]})
    def login(**kwargs):
        job.cancel()
        return {'cookie': 'new', 'credits': 4000}
    monkeypatch.setattr(service.firefly, 'register_account', login)
    with pytest.raises(JobCancelled):
        service.worker(job, service.configuration(db))
    db.expire_all()
    assert members[0].cookie == 'new' and not writes


def test_route_validates_selection_config_and_duplicate_running_job(client, db, flow, monkeypatch):
    members, _, _, _, _, _ = flow
    created = []
    def start(kind, worker, meta):
        job = Job(12, kind, meta)
        created.append(job)
        return job
    monkeypatch.setattr(service.JOBS, 'start', start)
    monkeypatch.setattr(service.JOBS, 'list_recent', lambda _: created)
    endpoint = '/api/pool/login-push-sub2'
    assert client.post(endpoint, json={'ids': []}).status_code == 400
    assert client.post(endpoint, json={'ids': [999]}).status_code == 400
    members[2].is_admin = True
    db.commit()
    assert client.post(endpoint, json={'ids': [members[2].id]}).status_code == 400
    response = client.post(endpoint, json={'ids': [members[0].id, members[0].id]})
    assert response.status_code == 200
    assert created[0].meta['member_ids'] == [members[0].id]
    assert 'admin-secret' not in response.text
    assert client.post(endpoint, json={'ids': [members[0].id]}).status_code == 400
    sub2._set(db, 'sub2_group_ids', '')
    db.commit()
    assert client.post(endpoint, json={'ids': [members[1].id]}).status_code == 400


def test_restart_marks_only_pool_push_tasks_interrupted(client):
    from app.services.job_manager import JOBS
    for jid, kind in ((10, 'pool_cookie_sub2'), (11, 'external_login')):
        job = Job(jid, kind, {'member_ids': [1]})
        JOBS._persist_job(job)
    JOBS.recover_interrupted('pool_cookie_sub2')
    assert JOBS.get(10).status == 'error' and JOBS.get(10).finished_at
    assert JOBS.get(11).status == 'running'


def test_missing_sub2_key_rejects_import_before_starting_any_task(client, db, flow, monkeypatch):
    members, _, logins, writes, _, _ = flow
    sub2._set(db, 'sub2_admin_token', '')
    db.commit()
    monkeypatch.setattr(service.JOBS, 'start', lambda *a, **k: pytest.fail('must not start without admin key'))
    response = client.post('/api/pool/login-push-sub2', json={'ids': [members[0].id]})
    assert response.status_code == 400 and '管理员密钥' in response.json()['detail']
    assert not logins and not writes
    config = client.get('/api/sub2/config').json()
    assert config['admin_token_set'] is False and 'admin_token' not in config
