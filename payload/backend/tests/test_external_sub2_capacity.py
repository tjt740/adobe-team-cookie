import json

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2, external_sub2_stock


@pytest.fixture
def capacity_case(db, monkeypatch):
    cfg = {'base_url': 'https://sub2.example', 'admin_token': 'admin-private'}
    row = ExternalMember(email='one@example.test', cookie='local-private', login_status='ok',
        sub2_links={external_sub2.destination(cfg): {'status': 'pending', 'account_id': 999}})
    db.add(row)
    db.commit()
    account = {'id': 999, 'platform': 'adobe', 'type': 'oauth', 'proxy_id': None,
               'credentials': {'email': row.email, 'cookie': 'remote-private'},
               'extra': {'okad': {'verification': 'proxy_pending'}}}
    allocation = {'enabled': True, 'accounts_per_proxy': 3, 'accounts': 7,
                  'available_slots': 0, 'nodes': [{'id': 1}, {'id': 2}]}
    calls = []
    def request(config, method, path, body=None):
        assert method == 'GET' and body is None
        calls.append(path)
        return allocation if path.endswith('/proxy-allocation') else account
    monkeypatch.setattr(external_sub2, 'config', lambda db: cfg)
    monkeypatch.setattr(external_sub2, '_request', request)
    return row, account, allocation, calls, cfg


def test_capacity_confirmation_is_read_only_and_redacted(client, db, capacity_case):
    row, account, allocation, calls, _ = capacity_case
    before = dict(row.sub2_links)
    response = client.get(f'/api/external/members/{row.id}/sub2-capacity')
    data = response.json()
    assert data['confirmed'] is True and data['capacity'] == 6
    assert data['account_id'] == 999 and data['accounts'] == 7
    assert response.headers['cache-control'] == 'no-store'
    assert 'private' not in json.dumps(data) and len(calls) == 2
    db.refresh(row)
    assert row.sub2_links == before and row.cookie == 'local-private'


@pytest.mark.parametrize('change', [
    'healthy_capacity', 'disabled', 'free_slot', 'assigned', 'wrong_identity',
    'already_verified', 'missing_proxy', 'malformed', 'duplicate_nodes', 'missing_key',
])
def test_other_waiting_reasons_never_confirm_capacity(db, capacity_case, change):
    row, account, allocation, calls, cfg = capacity_case
    if change == 'healthy_capacity':
        allocation.update(accounts=6, nodes=[{'id': 1, 'status': 'unhealthy'}, {'id': 2}])
    elif change == 'disabled': allocation['enabled'] = False
    elif change == 'free_slot': allocation['available_slots'] = 1
    elif change == 'assigned': account['proxy_id'] = 2
    elif change == 'wrong_identity': account['credentials']['email'] = 'another@example.test'
    elif change == 'already_verified': account['extra']['okad']['verification'] = 'verified'
    elif change == 'missing_proxy': del account['proxy_id']
    elif change == 'malformed': allocation['accounts_per_proxy'] = '3'
    elif change == 'duplicate_nodes': allocation['nodes'] = [{'id': 1}, {'id': 1}]
    elif change == 'missing_key': cfg['admin_token'] = ''
    assert external_sub2_stock.capacity_detail(db, row) == {'confirmed': False}


def test_failed_capacity_read_never_exposes_error(db, capacity_case, monkeypatch):
    row, *_ = capacity_case
    def fail(*args, **kwargs):
        raise RuntimeError('private-cookie-and-admin-key')
    monkeypatch.setattr(external_sub2, '_request', fail)
    assert external_sub2_stock.capacity_detail(db, row) == {'confirmed': False}


def test_missing_member(client):
    assert client.get('/api/external/members/999/sub2-capacity').status_code == 404
