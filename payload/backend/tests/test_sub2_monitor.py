import json
from datetime import datetime, timezone

import pytest

from app.services import sub2_monitor as sm


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def response(now, total=12):
    return dict(overview=dict(request_count_total=total, success_count=total-9,
        error_count_total=9, business_limited_count=7,
        system_metrics=dict(created_at=iso(now-10), memory_used_mb=256, memory_total_mb=8192),
        token_consumed=999999, secret='must-not-leak'),
        throughput_trend=dict(bucket='1m', points=[dict(bucket_start=iso(now-60), request_count=total, token_consumed=999999)]))


def setup_monitor():
    clock, calls, source = [1800000000], [], [('https://gateway/api/', 'private-token')]
    def fetch(config, endpoint, start, end):
        calls.append((config, endpoint, start, end))
        data = response(clock[0])
        return data['overview'] if endpoint == 'overview' else data
    monitor = sm.Sub2Monitor(lambda: source[0], fetch, lambda: clock[0])
    return monitor, clock, calls, source


def test_real_counts_include_limits_and_only_whitelisted_data():
    monitor, clock, calls, _ = setup_monitor()
    data = monitor.snapshot(5)
    assert data['status'] == 'ok'
    assert data['requests']['counts'] == dict(request_count_total=12, success_count=3, error_count_total=9, business_limited_count=7)
    assert calls[0][2:] == (clock[0]-300, clock[0])
    assert data['memory']['current']['used'] == 256*1024**2
    assert data['memory']['samples'] == 1 and data['memory']['change'] is None
    assert all(word not in json.dumps(data) for word in ('private-token', 'gateway', 'secret', 'token_consumed'))


def test_zero_is_valid_missing_is_not_zero():
    raw = response(1000)
    raw['overview'].update(request_count_total=0, success_count=0, error_count_total=0, business_limited_count=0)
    assert sm.request_data(raw, 700, 1000)['counts']['request_count_total'] == 0
    for value in (None, -1, True, 1.5):
        raw['overview']['success_count'] = value
        with pytest.raises(ValueError):
            sm.request_data(raw, 700, 1000)


def test_cache_windows_source_change_and_failure_backoff():
    monitor, clock, calls, source = setup_monitor()
    for _ in range(20):
        monitor.snapshot(15)
    assert len(calls) == 1
    monitor.snapshot(5)
    assert len(calls) == 2
    source[0] = ('https://another/api/', 'new-private-token')
    monitor.snapshot(15)
    assert len(calls) == 3 and list(monitor.cache) == [15]
    clock[0] += 31
    def failure(*args):
        calls.append(args)
        raise RuntimeError('private-token')
    monitor.fetcher = failure
    for _ in range(20):
        data = monitor.snapshot(15)
    assert len(calls) == 4
    assert data['status'] == 'unavailable' and data['requests'] is None
    assert 'private-token' not in json.dumps(data)
    source[0] = None
    assert monitor.snapshot(15)['status'] == 'unconfigured'
    assert monitor.snapshot(15)['memory']['current'] is None


def test_busy_upstream_does_not_queue_readers_or_show_old_window():
    monitor, _, _, _ = setup_monitor()
    monitor.snapshot(5)
    with monitor.fetch_lock:
        assert monitor.snapshot(15)['status'] == 'loading'
        assert monitor.snapshot(5)['status'] == 'ok'


def test_memory_dedup_bounds_stale_and_no_backfill():
    monitor, clock, _, _ = setup_monitor()
    monitor.sample()
    monitor.sample()
    assert monitor.snapshot(15)['memory']['samples'] == 1
    clock[0] += 60
    monitor._record(dict(created_at=iso(clock[0]-10), memory_used_mb=200, memory_total_mb=8192))
    data = monitor._memory(5, clock[0])
    assert data['peak'] == 256*1024**2 and data['change'] == -56*1024**2
    assert data['average'] == 228*1024**2 and data['samples'] == 2
    assert monitor._memory(5, clock[0], clock[0]-60)['samples'] == 1
    for invalid in (None, float('nan'), -1, True):
        monitor._record(dict(created_at=iso(clock[0]), memory_used_mb=invalid, memory_total_mb=8192))
    monitor._record(dict(created_at=iso(clock[0]+60), memory_used_mb=3, memory_total_mb=8192))
    assert len(monitor.history) == 2
    clock[0] += 151
    assert monitor._memory(5, clock[0])['stale']
    clock[0] += 3600
    assert monitor._memory(60, clock[0])['samples'] == 0


def test_memory_sampler_does_not_ask_for_business_logs():
    monitor, _, calls, _ = setup_monitor()
    monitor.sample()
    assert calls[0][1] == 'overview'
    assert len(calls) == 1


def test_endpoint_admin_auth_and_supported_windows(client, monkeypatch):
    from app.api.deps import get_current_user
    from app.api.routes import monitor as route
    from app.main import app
    from app.models.user import User
    monitor, _, calls, _ = setup_monitor()
    monkeypatch.setattr(route, 'SUB2_MONITOR', monitor)
    for minutes in (5, 15, 30, 60):
        result = client.get('/api/monitor/user-requests', params={'minutes':minutes})
        assert result.status_code == 200
        assert result.headers['cache-control'] == 'no-store'
        assert result.json()['minutes'] == minutes
    assert client.get('/api/monitor/user-requests?minutes=6').status_code == 422
    assert len(calls) == 4
    app.dependency_overrides[get_current_user] = lambda: User(id=2, is_active=True, is_superuser=False)
    assert client.get('/api/monitor/user-requests').status_code == 403
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/monitor/user-requests').status_code == 401
    assert len(calls) == 4


def test_http_get_is_bounded_no_redirect_or_proxy_and_no_remote_error_body(monkeypatch):
    calls = []
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield json.dumps({'code':0, 'data':{'ok':True}}).encode()
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            calls.append((url, kwargs, self.trust_env))
            return Response()
    monkeypatch.setattr(sm.requests, 'Session', Session)
    assert sm.fetch(('https://gateway/', 'admin-private'), 'overview', 100, 200) == {'ok':True}
    url, kwargs, proxy = calls[0]
    assert url == 'https://gateway/overview' and proxy is False
    assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (3,8)
    assert kwargs['headers'] == {'x-api-key':'admin-private'}
    assert kwargs['params']['mode'] == 'raw'
    Response.status_code = 302
    with pytest.raises(ValueError, match='Monitoring unavailable'):
        sm.fetch(('https://gateway/', 'private'), 'overview', 100, 200)
