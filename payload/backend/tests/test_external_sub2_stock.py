import json

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2, external_sub2_stock as stock

CFG = {'base_url': 'http://localhost:8080', 'admin_token': 'admin-private', 'platform': 'adobe'}


@pytest.fixture
def inventory(monkeypatch):
    monkeypatch.setattr(stock, '_cache', {})
    monkeypatch.setattr(external_sub2, 'config', lambda db: dict(CFG))
    accounts, calls = [], []
    def request(cfg, method, path, body=None):
        assert method == 'GET' and body is None
        calls.append(path)
        return {'items': accounts[:], 'total': len(accounts)}
    monkeypatch.setattr(external_sub2, '_request', request)
    return accounts, calls


def account(aid, email, **values):
    return {'id': aid, 'name': 'Display Name', 'platform': 'adobe', 'type': 'oauth',
            'credentials': {'email': email, 'cookie': 'remote-private'}, **values}


def member(db, email='one@example.com', **values):
    row = ExternalMember(email=email, login_status='ok', cookie='local-private', **values)
    db.add(row)
    db.commit()
    return row


def test_other_entry_import_appears_without_linking_or_changing_login(client, db, inventory):
    accounts, calls = inventory
    row = member(db, 'One@Example.com')
    accounts.append(account(3, 'one@example.com'))
    result = client.get('/api/external/members/sub2-stock').json()
    assert result['ok']
    assert result['items'][str(row.id)]['account_ids'] == [3]
    assert result['items'][str(row.id)]['in_stock'] is True
    assert 'private' not in json.dumps(result)
    db.refresh(row)
    assert row.sub2_links is None and row.cookie == 'local-private' and row.login_status == 'ok'
    assert calls and len(calls) == 1


def test_added_deleted_readded_and_failed_snapshots(client, db, inventory, monkeypatch):
    accounts, _ = inventory
    row = member(db, sub2_links={'http://127.0.0.1:8080/api/v1': {'status': 'synced', 'account_id': 3}})
    def state():
        return client.get('/api/external/members/sub2-stock?refresh=true').json()
    assert state()['items'][str(row.id)]['in_stock'] is False
    accounts.append(account(3, row.email))
    assert state()['items'][str(row.id)]['in_stock'] is True
    accounts.clear()
    assert state()['items'][str(row.id)]['in_stock'] is False
    accounts.append(account(5, row.email))
    assert state()['items'][str(row.id)]['account_ids'] == [5]
    def fail(*args, **kwargs):
        raise RuntimeError('private-cookie-and-admin-key')
    monkeypatch.setattr(external_sub2, '_request', fail)
    failed = state()
    assert failed['ok'] is False and failed['items'] == {}
    assert 'private' not in json.dumps(failed)
    db.refresh(row)
    assert row.sub2_links['http://127.0.0.1:8080/api/v1']['status'] == 'synced'


def test_strict_identity_platform_and_name_fallback(client, db, inventory):
    accounts, _ = inventory
    emails = ['one@example.com', 'two@example.com', 'three@example.com', 'four@example.com', 'five@example.com']
    members = [member(db, email) for email in emails]
    accounts.extend([
        account(1, emails[1], name=emails[0]),  # explicit email wins over display name
        account(2, emails[2], platform='openai'),
        account(3, emails[3], extra={'adobeteam_external_email': 'different@example.com'}),
        account(4, '', name=emails[4]),
        account(5, emails[0], type='apikey'),
    ])
    result = client.get('/api/external/members/sub2-stock').json()
    assert [result['items'][str(row.id)]['in_stock'] for row in members] == [False, True, False, False, True]


def test_cache_expires_and_config_changes_cannot_reuse_inventory(db, inventory, monkeypatch):
    accounts, calls = inventory
    row = member(db)
    clock = [0]
    monkeypatch.setattr(stock, 'monotonic', lambda: clock[0])
    stock.membership(db)
    accounts.append(account(3, row.email))
    assert stock.membership(db)['items'][row.id]['in_stock'] is False
    clock[0] = stock.TTL + 1
    assert stock.membership(db)['items'][row.id]['in_stock'] is True
    assert len(calls) == 2
    accounts.clear()
    monkeypatch.setattr(external_sub2, 'config', lambda db: {**CFG, 'base_url': 'https://other.example'})
    assert stock.membership(db)['items'][row.id]['in_stock'] is False
    assert len(calls) == 3
    accounts.append(account(5, row.email))
    monkeypatch.setattr(external_sub2, 'config', lambda db: {**CFG, 'base_url': 'https://other.example', 'admin_token': 'changed'})
    assert stock.membership(db)['items'][row.id]['account_ids'] == [5]
    assert len(calls) == 4


def test_unconfigured_does_not_call_remote(client, inventory, monkeypatch):
    _, calls = inventory
    monkeypatch.setattr(external_sub2, 'config', lambda db: {**CFG, 'admin_token': ''})
    result = client.get('/api/external/members/sub2-stock').json()
    assert result['configured'] is False and result['ok'] is False and not calls


@pytest.mark.parametrize('pages', [
    [{'items': [], 'total': 1}],
    [{'items': [account(3, 'one@example.com')], 'total': 2}, {'items': [], 'total': 2}],
    [{'items': []}],
    [{'items': ['invalid'], 'total': 1}],
])
def test_incomplete_or_malformed_inventory_never_means_absent(db, inventory, monkeypatch, pages):
    member(db)
    queue = iter(pages)
    monkeypatch.setattr(external_sub2, '_request', lambda *a, **k: next(queue))
    result = stock.membership(db)
    assert result['ok'] is False and result['items'] == {}


def test_multiple_pages_and_duplicate_accounts(db, inventory, monkeypatch):
    row = member(db)
    pages = iter([{'items': [account(3, row.email)], 'total': 2},
                  {'items': [account(4, row.email)], 'total': 2}])
    monkeypatch.setattr(external_sub2, '_request', lambda *a, **k: next(pages))
    assert stock.membership(db)['items'][row.id]['account_ids'] == [3, 4]
