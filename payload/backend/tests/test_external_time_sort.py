"""Second boundaries and stable timestamp ordering across filtered actions."""
from datetime import datetime, timedelta
import pytest
from app.models.external_member import ExternalMember
from app.services.job_manager import JOBS


@pytest.fixture
def timed_members(db):
    base = datetime(2026, 10, 29, 4, 34, 56)
    imported = [3, 1, 2, 2.999999, 2, 4, 2.5]
    logged = [1, 3, 2, None, 2, 4, 2.999999]
    rows = [ExternalMember(email=f'time{i}@example.test', cookie=f'cookie={i}',
                           created_at=base + timedelta(seconds=value),
                           last_login_at=base + timedelta(seconds=logged[i]) if logged[i] is not None else None)
            for i, value in enumerate(imported)]
    db.add_all(rows); db.commit()
    return rows


def assert_scopes(client, monkeypatch, filters, expected):
    for page in range(1, max(1, (len(expected) + 1) // 2) + 1):
        response = client.get('/api/external/members', params=dict(filters, page=page, size=2))
        assert response.status_code == 200, response.text
        assert response.json()['total'] == len(expected)
        assert [r['id'] for r in response.json()['items']] == [r.id for r in expected[(page-1)*2:page*2]]
    response = client.get('/api/external/members/export', params=filters)
    assert response.status_code == 200, response.text
    assert response.json() == [{'cookie': r.cookie} for r in expected]
    started = []
    class Job:
        def to_dict(self):
            return dict(id=999, type='external_login', status='running', target=len(expected), success=0, fail=0, logs=[])
    def start(kind, worker, *, meta):
        started.extend(meta['member_ids']); return Job()
    monkeypatch.setattr(JOBS, 'start', start)
    response = client.post('/api/external/members/batch-login-filter', json=filters)
    assert response.status_code == 200, response.text
    assert response.json()['total'] == response.json()['queued'] == len(expected)
    assert started == [r.id for r in expected]


@pytest.mark.parametrize('sort_by', ['id', 'created_at', 'last_login_at'])
@pytest.mark.parametrize('sort_order', ['asc', 'desc'])
def test_sort_before_pagination_and_shared_scope(client, timed_members, monkeypatch, sort_by, sort_order):
    reverse = sort_order == 'desc'
    known = [r for r in timed_members if getattr(r, sort_by) is not None]
    expected = sorted(known, key=lambda r: (getattr(r, sort_by), r.id), reverse=reverse)
    expected += sorted([r for r in timed_members if getattr(r, sort_by) is None], key=lambda r: r.id, reverse=reverse)
    assert_scopes(client, monkeypatch, dict(sort_by=sort_by, sort_order=sort_order), expected)


@pytest.mark.parametrize('field,prefix,indexes', [
    ('created_at', 'imported', [2, 3, 4, 6]),
    ('last_login_at', 'last_login', [2, 4, 6]),
])
@pytest.mark.parametrize('sort_order', ['asc', 'desc'])
def test_same_second_includes_microseconds_but_excludes_next_second(client, timed_members, monkeypatch, field, prefix, indexes, sort_order):
    # UI 12:34:58 to 12:34:58 inclusive becomes [58, 59) in UTC+8.
    filters = {prefix+'_from': '2026-10-29T12:34:58+08:00',
               prefix+'_before': '2026-10-29T12:34:59+08:00',
               'sort_by': field, 'sort_order': sort_order}
    expected = sorted([timed_members[i] for i in indexes], key=lambda r: (getattr(r, field), r.id), reverse=sort_order=='desc')
    assert_scopes(client, monkeypatch, filters, expected)


def test_both_time_ranges_and_keyword_intersect(client, timed_members, monkeypatch):
    filters = dict(imported_from='2026-10-29T12:34:58+08:00', imported_before='2026-10-29T12:34:59+08:00',
                   last_login_from='2026-10-29T12:34:58+08:00', last_login_before='2026-10-29T12:34:59+08:00',
                   keyword='time4', sort_by='created_at', sort_order='asc')
    assert_scopes(client, monkeypatch, filters, [timed_members[4]])


@pytest.mark.parametrize('filters', [
    {'sort_by': 'cookie'}, {'sort_by': 'created_at desc; drop table external_members'},
    {'sort_order': 'sideways'}, {'sort_order': 'ASC'},
])
def test_sort_validation_for_all_actions(client, monkeypatch, filters):
    monkeypatch.setattr(JOBS, 'start', lambda *a, **kw: pytest.fail('Invalid sort must not start jobs'))
    for path in ['/api/external/members', '/api/external/members/export']:
        assert client.get(path, params=filters).status_code == 422
    assert client.post('/api/external/members/batch-login-filter', json=filters).status_code == 422
