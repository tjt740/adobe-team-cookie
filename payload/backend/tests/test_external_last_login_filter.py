"""Last-login filtering uses the displayed timestamp across every filtered action."""
from datetime import datetime

import pytest

from app.models.external_member import ExternalMember
from app.services.job_manager import JOBS


@pytest.fixture
def login_members(db):
    # Beijing Oct 28 includes [Oct 27 16:00 UTC, Oct 28 16:00 UTC).
    times = [None, '2026-10-27T15:59:59.999999', '2026-10-27T16:00:00',
             '2026-10-28T15:59:59.999999', '2026-10-28T16:00:00']
    rows = [ExternalMember(email=f'lastlogin{i}@example.test', cookie=f'cookie={i}',
                           login_status='ok' if timestamp else 'never',
                           created_at=datetime(2026, 10, 20),
                           last_login_at=datetime.fromisoformat(timestamp) if timestamp else None)
            for i, timestamp in enumerate(times)]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.mark.parametrize('filters,indexes', [
    ({}, [4, 3, 2, 1, 0]),
    ({'last_login_from': '2026-10-28T00:00:00+08:00',
      'last_login_before': '2026-10-29T00:00:00+08:00'}, [3, 2]),
    ({'last_login_from': '2026-10-28T00:00:00+08:00'}, [4, 3, 2]),
    ({'last_login_before': '2026-10-29T00:00:00+08:00'}, [3, 2, 1]),
    ({'last_login_from': '2026-10-27T16:00:00Z',
      'last_login_before': '2026-10-28T16:00:00'}, [3, 2]),
    ({'last_login_from': '2026-10-28T00:00:00+08:00', 'login_status': 'never'}, []),
    ({'last_login_from': '2026-10-28T00:00:00+08:00',
      'imported_before': '2026-10-20T00:00:00Z'}, []),
    ({'last_login_before': '2026-10-29T00:00:00+08:00', 'keyword': 'lastlogin2'}, [2]),
])
def test_last_login_scope(client, login_members, monkeypatch, filters, indexes):
    expected = [login_members[i] for i in indexes]
    for page in range(1, max(1, len(expected)) + 1):
        response = client.get('/api/external/members', params=dict(filters, page=page, size=1))
        assert response.status_code == 200, response.text
        assert response.json()['total'] == len(expected)
        assert [r['id'] for r in response.json()['items']] == [r.id for r in expected[page-1:page]]
    response = client.get('/api/external/members/export', params=filters)
    assert response.status_code == 200, response.text
    assert response.json() == [{'cookie': r.cookie} for r in expected]
    started = []

    class Job:
        def to_dict(self):
            return dict(id=999, type='external_login', status='running', target=len(expected),
                        success=0, fail=0, logs=[])

    def start(kind, worker, *, meta):
        started.extend(meta['member_ids'])
        return Job()

    monkeypatch.setattr(JOBS, 'start', start)
    response = client.post('/api/external/members/batch-login-filter', json=filters)
    assert response.status_code == 200, response.text
    assert response.json()['total'] == response.json()['queued'] == len(expected)
    assert started == [r.id for r in expected]


@pytest.mark.parametrize('filters', [
    {'last_login_from': '2026-10-28T00:00:00+08:00', 'last_login_before': '2026-10-27T16:00:00Z'},
    {'last_login_from': '2026-10-29T00:00:00Z', 'last_login_before': '2026-10-28T00:00:00Z'},
    {'last_login_from': 'invalid'}, {'last_login_before': 'invalid'},
])
def test_invalid_last_login_range(client, monkeypatch, filters):
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid dates must not start a login job')

    monkeypatch.setattr(JOBS, 'start', unexpected)
    for path in ('/api/external/members', '/api/external/members/export'):
        assert client.get(path, params=filters).status_code == 422
    assert client.post('/api/external/members/batch-login-filter', json=filters).status_code == 422
