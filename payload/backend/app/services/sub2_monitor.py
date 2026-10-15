"""Read-only, bounded Sub2 telemetry. Credentials and raw logs never leave here.

Business counts come from persisted usage/error records, not Okad middleware or
estimated token usage. Memory is sampled independently; it is not attribution.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import math
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests

WINDOWS = (5, 15, 30, 60)
CACHE_SECONDS = 30
MEMORY_INTERVAL = 60
MEMORY_MAX_AGE = 150


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (AttributeError, ValueError, TypeError, OverflowError):
        return None


def configuration():
    # Avoid importing API routes (and their unrelated job services) in the sampler.
    from cryptography.fernet import Fernet
    from sqlalchemy import select
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.setting import Setting
    with SessionLocal() as db:
        values = dict(db.execute(select(Setting.key, Setting.value).where(
            Setting.key.in_(['sub2_base_url', 'sub2_admin_token']))).all())
    base, token = values.get('sub2_base_url') or '', values.get('sub2_admin_token') or ''
    if token.startswith('enc:v1:'):
        key = base64.urlsafe_b64encode(hashlib.sha256((settings.SECRET_KEY or 'adobeteam').encode()).digest())
        token = Fernet(key).decrypt(token[7:].encode()).decode()
    if not base or not token:
        return None
    url = urlsplit(base)
    private = url.hostname in ('localhost', 'host.docker.internal')
    try:
        private = private or ipaddress.ip_address(url.hostname).is_private
    except ValueError:
        pass
    if not url.hostname or url.username or url.password or url.query or url.fragment or not (
        url.scheme == 'https' or url.scheme == 'http' and private
    ):
        raise ValueError('Invalid monitor origin')
    path = url.path.rstrip('/')
    for suffix in ('/api/v1', '/api', '/v1'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    return urlunsplit((url.scheme, url.netloc, path + '/api/v1/admin/ops/dashboard/', '', '')), token


def fetch(config, endpoint, start, end):
    assert endpoint in ('overview', 'snapshot-v2')
    base, token = config
    headers = {'x-api-key': token} if token.startswith('admin-') else {'Authorization': 'Bearer ' + token}
    params = {k: datetime.fromtimestamp(v, timezone.utc).isoformat() for k, v in (
        ('start_time', start), ('end_time', end))}
    params['mode'] = 'raw'
    with requests.Session() as client:
        client.trust_env = False
        with client.get(base + endpoint, params=params, headers=headers, timeout=(3, 8),
                        allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError('Monitoring unavailable')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 1024 * 1024:
                    raise ValueError('Monitoring response too large')
            data = json.loads(body)
            if data.get('code') != 0 or not isinstance(data.get('data'), dict):
                raise ValueError('Invalid monitoring response')
            return data['data']


def request_data(data, start, end):
    overview = data['overview']
    counts = {key: overview.get(key) for key in (
        'request_count_total', 'success_count', 'error_count_total', 'business_limited_count')}
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in counts.values()):
        raise ValueError('Missing request counters')
    if counts['request_count_total'] != counts['success_count'] + counts['error_count_total'] or counts['business_limited_count'] > counts['error_count_total']:
        raise ValueError('Inconsistent request counters')
    trend = data.get('throughput_trend') or {}
    bucket = {'1m': 60, '5m': 300, '1h': 3600}.get(trend.get('bucket'))
    points = []
    for row in (trend.get('points') or [])[:121]:
        ts, count = timestamp(row.get('bucket_start')), row.get('request_count')
        if bucket and ts is not None and start - bucket < ts < end and finite(count):
            points.append({'ts': max(start, ts), 'count': count})
    return dict(start=start, end=end, counts=counts, history=points,
                bucket_seconds=bucket, average_rps=round(counts['request_count_total'] / (end - start), 2))


class Sub2Monitor:
    def __init__(self, config_loader=configuration, fetcher=fetch, clock=time.time):
        self.config_loader, self.fetcher, self.clock = config_loader, fetcher, clock
        self.lock = threading.RLock()
        self.fetch_lock = threading.Lock()
        self.history = deque(maxlen=121)
        self.cache = {}
        self.source = None
        self.stop_event = threading.Event()
        self.thread = None

    def _configuration(self):
        config = self.config_loader()
        fingerprint = hashlib.sha256(repr(config).encode()).digest()
        with self.lock:
            if fingerprint != self.source:
                self.cache.clear()
                self.history.clear()
                self.source = fingerprint
        return config

    def _record(self, metrics):
        if not isinstance(metrics, dict):
            return
        ts = timestamp(metrics.get('created_at'))
        used, total = metrics.get('memory_used_mb'), metrics.get('memory_total_mb')
        if ts is None or not finite(used) or not finite(total) or total <= 0 or not 0 <= self.clock() - ts <= MEMORY_MAX_AGE:
            return
        row = dict(ts=ts, used=used * 1024**2, total=total * 1024**2,
                   percent=round(used / total * 100, 1))
        with self.lock:
            if not self.history or ts > self.history[-1]['ts']:
                self.history.append(row)

    def _memory(self, minutes, now, end=None):
        end = now if end is None else end
        with self.lock:
            rows = [dict(row) for row in self.history if end - minutes * 60 <= row['ts'] <= end]
            latest = dict(self.history[-1]) if self.history else None
        values = [row['used'] for row in rows]
        return dict(current=latest, stale=not latest or now - latest['ts'] > MEMORY_MAX_AGE,
                    history=rows, samples=len(rows), observed_from=rows[0]['ts'] if rows else None,
                    observed_to=rows[-1]['ts'] if rows else None,
                    peak=max(values) if values else None, minimum=min(values) if values else None,
                    average=round(sum(values) / len(values)) if values else None,
                    change=values[-1] - values[0] if len(values) > 1 else None,
                    interval_seconds=MEMORY_INTERVAL, stale_after_seconds=MEMORY_MAX_AGE)

    def snapshot(self, minutes):
        if minutes not in WINDOWS:
            raise ValueError('Unsupported window')
        now = int(self.clock())
        # A busy upstream never queues every browser poll behind network I/O.
        if self.fetch_lock.acquire(blocking=False):
            try:
                config = self._configuration()
                with self.lock:
                    cached = self.cache.get(minutes)
                if not cached or now - cached['checked_at'] >= CACHE_SECONDS:
                    entry = dict(checked_at=now, status='unconfigured' if not config else 'unavailable', requests=None)
                    if config:
                        try:
                            data = self.fetcher(config, 'snapshot-v2', now - minutes * 60, now)
                            entry.update(status='ok', requests=request_data(data, now - minutes * 60, now))
                            self._record(data['overview'].get('system_metrics'))
                        except Exception:
                            # No exception strings, remote body, URL, or credentials in output/logs.
                            pass
                    with self.lock:
                        self.cache[minutes] = entry
            except Exception:
                with self.lock:
                    self.cache.clear()
                    self.history.clear()
                    self.cache[minutes] = dict(status='unavailable', requests=None, checked_at=now)
            finally:
                self.fetch_lock.release()
        with self.lock:
            result = dict(self.cache.get(minutes) or dict(status='loading', requests=None, checked_at=None))
        now = self.clock()
        end = result['requests']['end'] if result['requests'] else now
        result.update(minutes=minutes, memory=self._memory(minutes, now, end), refresh_seconds=CACHE_SECONDS)
        if result['checked_at'] is not None and now - result['checked_at'] > CACHE_SECONDS * 2:
            result['status'] = 'stale'
        return result

    def sample(self):
        if not self.fetch_lock.acquire(blocking=False):
            return
        try:
            config = self._configuration()
            if config:
                now = int(self.clock())
                self._record(self.fetcher(config, 'overview', now - 60, now).get('system_metrics'))
        except Exception:
            pass
        finally:
            self.fetch_lock.release()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name='sub2-monitor', daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            self.sample()
            self.stop_event.wait(MEMORY_INTERVAL)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)


SUB2_MONITOR = Sub2Monitor()
