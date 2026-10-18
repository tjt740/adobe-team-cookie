import asyncio
import time

import pytest

from app.services import server_monitor as sm


def write(root, name, content):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)


@pytest.fixture
def linux(tmp_path, monkeypatch):
    proc, group = tmp_path / 'proc', tmp_path / 'cgroup'
    group.mkdir()
    write(proc, 'self/cgroup', '0::/app')
    write(proc, 'self/mountinfo', f'1 0 0:1 / {group} rw - cgroup2 cgroup rw')
    write(proc, 'stat', 'cpu 10 0 10 80 0 0 0 0 99 0\ncpu0 0')
    write(proc, 'meminfo', 'MemTotal: 1024000 kB\nMemAvailable: 614400 kB\nSwapTotal: 100 kB\nSwapFree: 80 kB')
    write(proc, 'uptime', '3600 7200')
    write(proc, 'self/status', 'VmRSS: 1024 kB\nThreads: 4')
    write(proc, 'net/dev', 'eth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0\nlo: 9999 0 0 0 0 0 0 0 9999 0 0 0 0 0 0 0')
    write(group, 'app/cpu.stat', 'usage_usec 1000000')
    write(group, 'app/cpu.max', '100000 100000')
    write(group, 'app/memory.current', '268435456')
    write(group, 'app/memory.max', '536870912')
    write(group, 'app/memory.events', 'oom_kill 2')
    monkeypatch.setattr(sm.os, 'cpu_count', lambda: 8)
    monkeypatch.setattr(sm.os, 'getloadavg', lambda: (2., 1., .5))
    return proc, group


def test_host_and_container_are_separate_with_counter_deltas(linux, tmp_path):
    proc, group = linux
    sampler = sm.Resources(proc, tmp_path)
    first = sampler.sample(100)
    assert first['host']['cpu_percent'] is None
    assert first['network']['receive_bps'] is None
    assert first['host']['memory_percent'] == 40
    assert first['application']['memory_percent'] == 50
    assert first['application']['memory_limit'] == 512 * 1024**2
    write(proc, 'stat', 'cpu 40 0 20 130 10 0 0 0 200 0')
    write(proc, 'net/dev', 'eth0: 6000 0 0 0 0 0 0 0 12000 0 0 0 0 0 0 0')
    write(group, 'app/cpu.stat', 'usage_usec 3500000')
    second = sampler.sample(105)
    assert second['host']['cpu_percent'] == 40  # guest counters are already in user/nice
    assert second['host']['io_wait_percent'] == 10
    assert second['application']['cpu_percent'] == 50
    assert second['application']['oom_kills'] == 2
    assert second['network'] == {'receive_bps': 1000, 'transmit_bps': 2000}
    assert second['process'] == {'memory_rss': 1024**2, 'threads': 4}
    assert second['disk']['total'] > 0


def test_parent_limits_and_unlimited_cgroup(linux, monkeypatch):
    proc, group = linux
    monkeypatch.setattr(sm.os, 'sched_getaffinity', lambda _: {0, 1}, raising=False)
    write(group, 'app/memory.max', 'max')
    write(group, 'memory.max', '536870912')
    write(group, 'app/cpu.max', 'max 100000')
    write(group, 'cpu.max', '50000 100000')
    data = sm._group_stats(sm._group_paths(proc), 8)
    assert data['memory_percent'] == 50
    assert data['cpu_capacity'] == .5
    write(group, 'memory.max', 'max')
    write(group, 'cpu.max', 'max 100000')
    data = sm._group_stats(sm._group_paths(proc), 8)
    assert data['memory_percent'] is None and data['memory_limit'] is None
    assert data['cpu_capacity'] == 2


def test_namespace_mount_and_v1_limits(tmp_path):
    proc, group = tmp_path / 'proc', tmp_path / 'group'
    write(proc, 'self/cgroup', '1:cpu,cpuacct:/\n2:memory:/')
    write(proc, 'self/mountinfo', f'1 0 0:1 /docker/id {group}/cpu rw - cgroup cgroup rw,cpu,cpuacct\n2 0 0:2 /docker/id {group}/memory rw - cgroup cgroup rw,memory')
    write(group, 'cpu/cpuacct.usage', '2000000000')
    write(group, 'cpu/cpu.cfs_quota_us', '50000')
    write(group, 'cpu/cpu.cfs_period_us', '100000')
    write(group, 'memory/memory.usage_in_bytes', '50')
    write(group, 'memory/memory.limit_in_bytes', '100')
    result = sm._group_stats(sm._group_paths(proc), 4)
    assert result['cpu_seconds'] == 2 and result['cpu_capacity'] == .5
    assert result['memory_percent'] == 50
    write(group, 'memory/memory.limit_in_bytes', str(2**63 - 4096))
    assert sm._group_stats(sm._group_paths(proc), 4)['memory_limit'] is None


def test_missing_metrics_and_network_reset_are_not_fake_zero(linux, tmp_path):
    proc, _ = linux
    sampler = sm.Resources(proc, tmp_path)
    sampler.sample(1)
    write(proc, 'net/dev', 'eth0: 10 0 0 0 0 0 0 0 20 0 0 0 0 0 0 0')
    assert sampler.sample(6)['network']['receive_bps'] is None
    missing = sm.Resources(tmp_path / 'unavailable', tmp_path / 'missing-disk').sample(1)
    assert missing['host']['cpu_percent'] is None
    assert missing['host']['memory_percent'] is None
    assert missing['disk']['percent'] is None
    assert missing['application']['available'] is False


def test_requests_rates_errors_latency_cap_and_expiry():
    requests = sm.Requests()
    for i in range(10001):
        requests.begin()
        requests.finish(500 if i == 0 else 404 if i == 1 else 200, .1, now=100)
    result = requests.snapshot(101)
    assert result['count'] == 10001 and result['latency_samples'] == 10000
    assert result['server_errors'] == 1 and result['client_errors'] == 1
    assert result['p95_ms'] == 100 and result['active'] == 0
    assert result['rps'] == round(10001 / 60, 2)
    requests.begin()
    expired = requests.snapshot(161)
    assert expired['count'] == 0 and expired['p95_ms'] is None and expired['active'] == 1


def test_middleware_measures_errors_and_excludes_monitor():
    monitor = sm.Monitor()
    async def downstream(scope, receive, send):
        assert monitor.requests.active == (0 if scope['path'] in ('/api/monitor/snapshot', '/api/health', '/assets/a.js') else 1)
        if scope['path'] == '/api/broken':
            raise RuntimeError('private exception')
        await send({'type':'http.response.start', 'status':201})
        await send({'type':'http.response.body', 'body':b'ok'})
    async def run():
        async def noop(*args):
            pass
        middleware = sm.RequestMetricsMiddleware(downstream, monitor)
        for path in ('/api/monitor/snapshot', '/api/health', '/assets/a.js', '/api/accounts'):
            await middleware({'type':'http', 'path':path}, noop, noop)
        with pytest.raises(RuntimeError):
            await middleware({'type':'http', 'path':'/api/broken'}, noop, noop)
    asyncio.run(run())
    result = monitor.requests.snapshot(time.monotonic())
    assert result['active'] == 0 and result['count'] == 2 and result['server_errors'] == 1


def test_history_bounded_stale_and_thresholds(linux, tmp_path, monkeypatch):
    from app.services.job_manager import JOBS
    monkeypatch.setattr(JOBS, '_jobs', {})
    monitor = sm.Monitor()
    monitor.resources = sm.Resources(linux[0], tmp_path)
    monitor.sample()
    sample = monitor.history[0]
    sample['host']['cpu_percent'] = 90
    assert sm.pressure(sample)[0]['level'] == 'critical'
    for i in range(sm.HISTORY_POINTS + 10):
        monitor.history.append(dict(sample, ts=time.time() - i * 5))
    assert len(monitor.history) == sm.HISTORY_POINTS
    monitor.history.append(dict(sample, ts=time.time() - 20))
    assert monitor.snapshot(5)['stale'] is True
    monitor.history.append(dict(sample, ts=time.time()))
    output = monitor.snapshot(5)
    assert output['stale'] is False
    assert all(row['ts'] >= time.time() - 301 for row in output['history'])
    assert 'jobs' not in output['history'][-1]


def test_endpoint_auth_cache_and_range(client, monkeypatch):
    from app.api.deps import get_current_user
    from app.api.routes import monitor
    from app.main import app
    monkeypatch.setattr(monitor, 'MONITOR', sm.Monitor())
    response = client.get('/api/monitor/snapshot')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['current'] is None and response.json()['stale'] is True
    assert client.get('/api/monitor/snapshot?minutes=61').status_code == 422
    assert client.get('/api/monitor/snapshot?minutes=0').status_code == 422
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/monitor/snapshot').status_code == 401


def test_job_summary_does_not_read_database(monkeypatch):
    from app.services.job_manager import Job, JobManager
    manager = JobManager()
    for index, status in enumerate(['running', 'paused', 'pausing', 'cancelling', 'done', 'error']):
        job = Job(index, 'example', {'password':'private'})
        job.status = status
        manager._jobs[index] = job
    monkeypatch.setattr(manager, '_ensure_storage', lambda: pytest.fail('monitor must not read DB'))
    assert manager.monitor_summary() == {'running':1, 'paused':1, 'pausing':1, 'cancelling':1}
