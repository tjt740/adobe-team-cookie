import json

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2 as sync

CFG = {'base_url': 'http://localhost:8080/', 'admin_token': 'admin-secret', 'platform': 'adobe',
       'group_ids': [2], 'concurrency': 10, 'rate_multiplier': '1'}
TARGET = 'http://127.0.0.1:8080/api/v1'


@pytest.fixture
def setup_sync(monkeypatch, SessionLocal):
    monkeypatch.setattr(sync, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(sync, 'config', lambda db: dict(CFG))
    monkeypatch.setattr(sync, '_queued', set())


def member(db, **kwargs):
    row = ExternalMember(email=kwargs.pop('email', 'one@example.com'), login_status='ok', cookie='ims_sid=fresh', **kwargs)
    db.add(row)
    db.commit()
    return row


class Remote:
    def __init__(self):
        self.accounts = {}
        self.calls = []
        self.fail = False

    def request(self, cfg, method, path, body=None):
        self.calls.append((method, path, body))
        if self.fail:
            raise sync.SyncError('Sub2 请求失败（HTTP 503）')
        if method == 'GET' and path.startswith('/admin/accounts?'):
            return {'items': list(self.accounts.values()), 'total': len(self.accounts)}
        if method == 'GET' and path == '/admin/groups/all':
            return [{'id': 2, 'platform': 'adobe', 'status': 'active'}]
        if method == 'GET':
            aid = int(path.rsplit('/', 1)[1])
            if aid not in self.accounts:
                raise sync.SyncError('Sub2 账号或接口不存在（HTTP 404）')
            return self.accounts[aid]
        if path == '/admin/accounts':
            account = {'id': len(self.accounts) + 10, **body}
            self.accounts[account['id']] = account
            return account
        assert path.endswith('/apply-oauth-credentials')
        account = self.accounts[int(path.split('/')[3])]
        # Match native Sub2: omitted non-sensitive keys are removed. Only
        # omitted sensitive keys survive (GET responses redact those keys).
        sensitive = {key: value for key, value in account['credentials'].items()
                     if key in ('cookie', 'access_token', 'arp_session_id')}
        account['credentials'] = {**sensitive, **body['credentials']}
        account['extra'].update(body['extra'])
        return account


@pytest.fixture
def remote(monkeypatch):
    result = Remote()
    monkeypatch.setattr(sync, '_request', result.request)
    return result


def test_explicit_push_then_relogin_updates_same_remote_account(db, setup_sync, remote, monkeypatch, SessionLocal):
    row = member(db)
    target, ids, skipped = sync.prepare(db, [row.id, row.id, 999])
    assert target == TARGET and ids == [row.id] and skipped == [999]
    sync._run(row.id, target)
    db.refresh(row)
    link = row.sub2_links[target]
    assert link['status'] == 'synced' and link['account_id'] == 10
    assert row.cookie not in json.dumps(row.sub2_links)
    account = remote.accounts[10]
    assert account['group_ids'] == [2] and account['credentials']['access_token'] == ''
    # Change runtime settings remotely; re-login must preserve them.
    account['proxy_id'] = 91
    account['concurrency'] = 6
    account['group_ids'] = [7]
    account['credentials']['model_mapping'] = {'model': 'target'}
    row.cookie = 'ims_sid=newest'
    db.commit()
    monkeypatch.setattr(sync, 'submit', lambda ids, target: [sync._run(mid, target) for mid in ids])
    sync.after_login(row.id, session_factory=SessionLocal)
    db.refresh(row)
    assert len(remote.accounts) == 1
    assert account['credentials']['cookie'] == row.cookie
    assert account['proxy_id'] == 91 and account['concurrency'] == 6 and account['group_ids'] == [7]
    assert account['credentials']['model_mapping'] == {'model': 'target'}
    assert sync.summary(row, target)['sub2_status'] == 'synced'


def test_unlinked_accounts_never_auto_push(db, setup_sync, remote, monkeypatch, SessionLocal):
    row = member(db)
    calls = []
    monkeypatch.setattr(sync, 'submit', lambda ids, target: calls.extend(ids))
    sync.after_login(row.id, session_factory=SessionLocal)
    assert calls == [] and remote.calls == []


def test_no_automatic_transfer_to_a_different_destination(db, setup_sync, remote, monkeypatch, SessionLocal):
    row = member(db, sub2_links={TARGET: {'status': 'synced', 'account_id': 10}})
    monkeypatch.setattr(sync, 'config', lambda db: {**CFG, 'base_url': 'https://other.example'})
    sync.after_login(row.id, session_factory=SessionLocal)
    assert remote.calls == []
    assert sync.summary(row, 'https://other.example/api/v1')['sub2_status'] == 'not_pushed'


def test_failure_is_separate_from_login_and_retry_does_not_duplicate(db, setup_sync, remote):
    row = member(db)
    target, _, _ = sync.prepare(db, [row.id])
    remote.fail = True
    sync._run(row.id, target)
    db.refresh(row)
    assert row.login_status == 'ok' and row.cookie == 'ims_sid=fresh'
    assert row.sub2_links[target]['status'] == 'failed'
    remote.fail = False
    # Simulate a create that succeeded remotely but whose response was lost.
    remote.accounts[10] = {'id': 10, 'name': row.email, 'platform': 'adobe', 'type': 'oauth',
                           'credentials': {'email': row.email}, 'extra': {}, 'group_ids': [2]}
    sync.prepare(db, [row.id])
    sync._run(row.id, target)
    db.refresh(row)
    assert row.sub2_links[target]['account_id'] == 10
    assert not any(method == 'POST' and path == '/admin/accounts' for method, path, _ in remote.calls)


def test_changed_remote_identity_is_not_overwritten(db, setup_sync, remote):
    row = member(db, sub2_links={TARGET: {'account_id': 10, 'status': 'synced'}})
    remote.accounts[10] = {'id': 10, 'name': row.email, 'platform': 'adobe', 'type': 'oauth',
                           'credentials': {'email': 'someone-else@example.com'}}
    sync.prepare(db, [row.id])
    sync._run(row.id, TARGET)
    db.refresh(row)
    assert row.sub2_links[TARGET]['status'] == 'failed'
    assert not any(method == 'POST' for method, _, _ in remote.calls)


def test_deleted_linked_remote_is_not_recreated(db, setup_sync, remote):
    row = member(db, sub2_links={TARGET: {'account_id': 10, 'status': 'synced'}})
    sync.prepare(db, [row.id])
    sync._run(row.id, TARGET)
    db.refresh(row)
    assert row.sub2_links[TARGET]['status'] == 'failed'
    assert not remote.accounts


def test_new_cookie_arriving_during_sync_is_sent_last(db, setup_sync, remote, monkeypatch, SessionLocal):
    row = member(db)
    sync.prepare(db, [row.id])
    original = sync._sync
    count = 0
    def racing(cfg, email, cookie, link):
        nonlocal count
        aid = original(cfg, email, cookie, link)
        count += 1
        if count == 1:
            with SessionLocal() as session:
                account = session.get(ExternalMember, row.id)
                account.cookie = 'ims_sid=rotated-during-sync'
                session.commit()
        return aid
    monkeypatch.setattr(sync, '_sync', racing)
    sync._run(row.id, TARGET)
    assert len(remote.accounts) == 1 and count == 2
    assert remote.accounts[10]['credentials']['cookie'] == 'ims_sid=rotated-during-sync'


def test_restart_resumes_only_current_pending_destination(db, setup_sync, monkeypatch):
    row = member(db, sub2_links={TARGET: {'status': 'syncing'}})
    member(db, email='other@example.com', sub2_links={'https://other/api/v1': {'status': 'pending'}})
    calls = []
    monkeypatch.setattr(sync, 'submit', lambda ids, target: calls.append((ids, target)))
    sync.resume_pending()
    assert calls == [([row.id], TARGET)]


def test_endpoint_selection_validation_and_public_status(client, db, setup_sync, monkeypatch):
    row = member(db)
    bad = member(db, email='no-cookie@example.com')
    bad.cookie = ''
    db.commit()
    calls = []
    monkeypatch.setattr(sync, 'submit', lambda ids, target: calls.append((ids, target)))
    assert client.post('/api/external/members/push-sub2', json={'ids': []}).status_code == 400
    response = client.post('/api/external/members/push-sub2', json={'ids': [row.id, bad.id]})
    assert response.json()['queued'] == 1 and response.json()['skipped'] == 1
    assert calls == [([row.id], TARGET)]
    listing = client.get('/api/external/members').json()['items']
    assert next(item for item in listing if item['id'] == row.id)['sub2_status'] == 'pending'
    assert 'cookie_hash' not in json.dumps(listing) and 'ims_sid=fresh' not in json.dumps(listing)
    monkeypatch.setattr(sync, 'config', lambda db: {**CFG, 'admin_token': ''})
    assert client.post('/api/external/members/push-sub2', json={'ids': [row.id]}).status_code == 400


def test_request_errors_do_not_echo_credentials(monkeypatch):
    monkeypatch.setattr(sync.sub2_client, '_request', lambda *a, **kw: (400, '{"message":"secret-cookie"}'))
    with pytest.raises(sync.SyncError) as exc:
        sync._request(CFG, 'POST', '/admin/accounts', {'credentials': {'cookie': 'secret-cookie'}})
    assert 'secret' not in str(exc.value)
