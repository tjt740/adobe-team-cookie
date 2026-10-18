import json

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2, external_sub2_stock as stock, reliable_integration, sub2_account_health
from app.services.job_manager import JOBS


def health(code=None, state='error'):
    return {'state': state, 'errors': [] if code is None else [
        {'code': code, 'reason': 'timeout' if code == 408 else 'upstream', 'source': 'business'}]}


@pytest.fixture
def inventory(db, monkeypatch):
    monkeypatch.setattr(stock, '_cache', {})
    monkeypatch.setattr(external_sub2, 'config', lambda db: {
        'base_url': 'http://localhost:8080', 'enabled': True,
        'integration_key': 'private-key', 'site_id': 'primary', 'platform': 'adobe'})
    rows = [ExternalMember(email=f'health{i}@example.test', login_status='ok', cookie=f'local-{i}',
                           subscription_ok=True) for i in range(245)]
    db.add_all(rows)
    db.commit()
    remote = [{'id': r.id, 'email': r.email, 'account_health': health(401 if i < 220 else 408)}
              for i, r in enumerate(rows)]
    monkeypatch.setattr(reliable_integration, 'inventory', lambda cfg: remote)
    return rows, remote


def test_health_filters_before_pagination_and_share_export_batch_scope(client, db, inventory, monkeypatch):
    rows, remote = inventory
    for page, expected in [(1, 200), (2, 20)]:
        response = client.get('/api/external/members', params={'sub2_health': '401', 'page': page, 'size': 200})
        assert response.status_code == 200
        assert response.json()['total'] == 220
        assert len(response.json()['items']) == expected
    assert len(client.get('/api/external/members/export?sub2_health=408').json()) == 25
    assert client.get('/api/external/members?sub2_health=408&in_stock=false').json()['total'] == 0
    captured = []

    class Job:
        def to_dict(self):
            return dict(id=900, type='external_login', status='running', target=25, success=0, fail=0, logs=[])

    def start(kind, worker, *, meta):
        captured.extend(meta['member_ids'])
        return Job()

    monkeypatch.setattr(JOBS, 'start', start)
    response = client.post('/api/external/members/batch-login-filter', json={'sub2_health': '408'})
    assert response.status_code == 200
    assert set(captured) == {r.id for r in rows[220:]}
    db.refresh(rows[0])
    assert rows[0].login_status == 'ok' and rows[0].cookie == 'local-0'
    assert rows[0].sub2_links is None


def test_duplicate_accounts_recovery_unknown_and_identity(client, db, inventory, monkeypatch):
    rows, remote = inventory
    remote[:] = [remote[0], {'id': 9999, 'email': rows[0].email, 'account_health': health(408)},
                 {'id': rows[1].id, 'email': rows[1].email, 'account_health': health(state='recovered')},
                 {'id': rows[2].id, 'email': rows[2].email},
                 {'id': rows[3].id, 'email': rows[3].email, 'imported_email': 'wrong@example.test', 'account_health': health(401)}]
    result = client.get('/api/external/members/sub2-stock?refresh=true').json()
    assert result['items'][str(rows[0].id)]['account_health']['codes'] == [401, 408]
    assert not result['items'][str(rows[3].id)]['in_stock']
    assert client.get('/api/external/members?sub2_health=recovered').json()['total'] == 1
    assert client.get('/api/external/members?sub2_health=unknown').json()['total'] == 1
    # A success in one duplicate does not clear the other's unresolved failure.
    remote[0]['account_health'] = health(state='recovered')
    result = client.get('/api/external/members/sub2-stock?refresh=true').json()
    assert result['items'][str(rows[0].id)]['account_health']['codes'] == [408]
    remote[1]['account_health'] = health(state='recovered')
    result = client.get('/api/external/members/sub2-stock?refresh=true').json()
    assert result['items'][str(rows[0].id)]['account_health']['state'] == 'recovered'
    assert 'private' not in json.dumps(result)
    # Connection failure must not leave a successful-looking old status.
    def fail(cfg):
        raise RuntimeError('private-key')
    monkeypatch.setattr(reliable_integration, 'inventory', fail)
    result = client.get('/api/external/members/sub2-stock?refresh=true').json()
    assert result['ok'] is False and result['items'] == {}
    assert 'private' not in json.dumps(result)
    assert client.get('/api/external/members?sub2_health=401').status_code == 503
    assert client.get('/api/external/members').status_code == 200


@pytest.mark.parametrize('code', [400, 403, 429, 500, 502, 503, 504, 529, 599, 0])
def test_other_errors_and_allowlisted_payload(code):
    data = health(code)
    data['errors'][0].update(message='secret-cookie', reason='secret-token', stage='private')
    projected = sub2_account_health.project({'account_health': data})
    assert sub2_account_health.matches(projected, 'other')
    assert sub2_account_health.matches(projected, 'error')
    if code:
        assert sub2_account_health.matches(projected, str(code))
    assert 'secret' not in json.dumps(projected) and 'private' not in json.dumps(projected)


@pytest.mark.parametrize('value', ['200', '600', 'bad', '401 OR 1=1'])
def test_invalid_filter_rejected_everywhere(client, value):
    for path in ['/api/external/members', '/api/external/members/export']:
        assert client.get(path, params={'sub2_health': value}).status_code == 422
    assert client.post('/api/external/members/batch-login-filter', json={'sub2_health': value}).status_code == 422
