"""Bounded, read-only telemetry for the default single-process deployment.

Linux /proc reports host resources; cgroups report the application's resource
group. Never substitute one for the other when a counter is unavailable.
"""
from __future__ import annotations

import math
import os
import platform
import shutil
import threading
import time
from collections import deque
from pathlib import Path, PurePosixPath

from sqlalchemy.engine import make_url

INTERVAL = 5
HISTORY_POINTS = 721


def _read(file: Path) -> str:
    try:
        return file.read_text().strip()
    except (OSError, UnicodeError):
        return ""


def _number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _pairs(value: str) -> dict:
    result = {}
    for line in value.splitlines():
        fields = line.replace(":", " ").split()
        if len(fields) >= 2:
            result[fields[0]] = _number(fields[1])
    return result


def _percent(used, total):
    return round(max(0, min(100, used / total * 100)), 1) if used is not None and total else None


def _rate(current, previous, elapsed):
    if current is None or previous is None or elapsed <= 0 or current < previous:
        return None
    return (current - previous) / elapsed


def _group_paths(proc: Path) -> dict:
    """Resolve membership against mount roots, including cgroup namespaces."""
    memberships = {}
    for line in _read(proc / "self/cgroup").splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3:
            for controller in parts[1].split(","):
                memberships[controller] = parts[2]
    groups = {}
    for line in _read(proc / "self/mountinfo").splitlines():
        before, sep, after = line.partition(" - ")
        left, right = before.split(), after.split()
        if not sep or len(left) < 5 or len(right) < 3 or right[0] not in ("cgroup", "cgroup2"):
            continue
        controllers = [""] if right[0] == "cgroup2" else right[2].split(",")
        for controller in controllers:
            member = memberships.get(controller)
            if member is None:
                continue
            root = PurePosixPath(left[3])
            try:
                relative = PurePosixPath(member).relative_to(root)
            except ValueError:
                if member != "/":
                    continue
                relative = PurePosixPath(".")
            mount = Path(left[4].replace("\\040", " "))
            groups[controller or "v2"] = (mount / str(relative), mount)
    return groups


def _ancestors(group):
    current, mount = group
    while True:
        yield current
        if current == mount:
            break
        current = current.parent


def _group_stats(groups: dict, cores: int) -> dict:
    result = dict(cpu_seconds=None, cpu_capacity=None, memory_used=None, memory_limit=None,
                  memory_percent=None, oom_kills=None, available=False)
    limits, cpu_limits = [], [float(cores)]
    try:
        cpu_limits.append(float(len(os.sched_getaffinity(0))))
    except (AttributeError, OSError):
        pass
    if "v2" in groups:
        current, _ = groups["v2"]
        cpu = _pairs(_read(current / "cpu.stat"))
        usage = cpu.get("usage_usec")
        result["cpu_seconds"] = usage / 1e6 if usage is not None else None
        result["memory_used"] = _number(_read(current / "memory.current"))
        result["oom_kills"] = _pairs(_read(current / "memory.events")).get("oom_kill")
        for directory in _ancestors(groups["v2"]):
            limit = _number(_read(directory / "memory.max"))
            if limit is not None and limit > 0:
                limits.append(limit)
            fields = _read(directory / "cpu.max").split()
            if len(fields) == 2:
                quota, period = map(_number, fields)
                if quota is not None and quota > 0 and period and period > 0:
                    cpu_limits.append(quota / period)
    else:
        if "memory" in groups:
            current, _ = groups["memory"]
            result["memory_used"] = _number(_read(current / "memory.usage_in_bytes"))
            for directory in _ancestors(groups["memory"]):
                limit = _number(_read(directory / "memory.limit_in_bytes"))
                if limit is not None and 0 < limit < 2**60:
                    limits.append(limit)
        if "cpuacct" in groups:
            usage = _number(_read(groups["cpuacct"][0] / "cpuacct.usage"))
            result["cpu_seconds"] = usage / 1e9 if usage is not None else None
        if "cpu" in groups:
            for directory in _ancestors(groups["cpu"]):
                quota = _number(_read(directory / "cpu.cfs_quota_us"))
                period = _number(_read(directory / "cpu.cfs_period_us"))
                if quota is not None and quota > 0 and period and period > 0:
                    cpu_limits.append(quota / period)
    result["available"] = result["memory_used"] is not None or result["cpu_seconds"] is not None
    result["cpu_capacity"] = min(cpu_limits) if result["cpu_seconds"] is not None else None
    result["memory_limit"] = min(limits) if limits else None
    result["memory_percent"] = _percent(result["memory_used"], result["memory_limit"])
    return result


class Resources:
    def __init__(self, proc=Path("/proc"), disk_path=None):
        self.proc = proc
        self.disk_path = disk_path or Path.cwd()
        self.previous = None
        self.cores = os.cpu_count() or 1
        self.groups = _group_paths(proc)

    def sample(self, now):
        stat = _read(self.proc / "stat").splitlines()
        cpu = []
        if stat and stat[0].startswith("cpu "):
            cpu = [_number(x) for x in stat[0].split()[1:9]]
        if len(cpu) < 5 or any(x is None for x in cpu):
            cpu = None
        memory = _pairs(_read(self.proc / "meminfo"))
        total, available = memory.get("MemTotal"), memory.get("MemAvailable")
        used = max(0, total - available) * 1024 if total is not None and available is not None else None
        swap_total, swap_free = memory.get("SwapTotal"), memory.get("SwapFree")
        net = {}
        for line in _read(self.proc / "net/dev").splitlines():
            name, sep, counters = line.partition(":")
            fields = counters.split()
            if sep and name.strip() != "lo" and len(fields) >= 16:
                rx, tx = _number(fields[0]), _number(fields[8])
                if rx is not None and tx is not None:
                    net[name.strip()] = (rx, tx)
        group = _group_stats(self.groups, self.cores)
        previous = self.previous
        elapsed = now - previous["time"] if previous else 0
        cpu_percent = io_wait = rx_rate = tx_rate = group_cpu = None
        if previous and elapsed > 0:
            old_cpu = previous["cpu"]
            if cpu and old_cpu:
                delta = sum(cpu) - sum(old_cpu)
                idle = cpu[3] + cpu[4] - old_cpu[3] - old_cpu[4]
                if delta > 0 and idle >= 0:
                    cpu_percent = _percent(delta - idle, delta)
                    io_wait = _percent(max(0, cpu[4] - old_cpu[4]), delta)
            # A renamed, reset, or disappearing interface cannot produce a spike.
            if net and net.keys() == previous["net"].keys():
                rates = [(_rate(values[0], previous["net"][name][0], elapsed),
                          _rate(values[1], previous["net"][name][1], elapsed)) for name, values in net.items()]
                if all(rx is not None and tx is not None for rx, tx in rates):
                    rx_rate, tx_rate = round(sum(x[0] for x in rates), 2), round(sum(x[1] for x in rates), 2)
            seconds = _rate(group["cpu_seconds"], previous["group_cpu"], elapsed)
            if seconds is not None and group["cpu_capacity"]:
                group_cpu = _percent(seconds, group["cpu_capacity"])
        self.previous = dict(time=now, cpu=cpu, net=net, group_cpu=group["cpu_seconds"])
        group.pop("cpu_seconds")
        group["cpu_percent"] = group_cpu
        try:
            disk = shutil.disk_usage(self.disk_path)
            disk_data = dict(total=disk.total, used=disk.used, free=disk.free,
                             percent=_percent(disk.used, disk.total))
        except OSError:
            disk_data = dict(total=None, used=None, free=None, percent=None)
        uptime = _read(self.proc / "uptime").split()
        process = _pairs(_read(self.proc / "self/status"))
        try:
            load = list(os.getloadavg())
        except (AttributeError, OSError):
            load = None
        return dict(
            host=dict(cpu_percent=cpu_percent, io_wait_percent=io_wait, cores=self.cores,
                      memory_total=total * 1024 if total is not None else None, memory_used=used,
                      memory_percent=_percent(used, total * 1024 if total is not None else None),
                      swap_used=(swap_total - swap_free) * 1024 if swap_total is not None and swap_free is not None else None,
                      swap_total=swap_total * 1024 if swap_total is not None else None,
                      load=load, uptime_seconds=_number(uptime[0]) if uptime else None),
            application=group, disk=disk_data,
            network=dict(receive_bps=rx_rate, transmit_bps=tx_rate),
            process=dict(memory_rss=process["VmRSS"] * 1024 if process.get("VmRSS") is not None else None,
                         threads=process.get("Threads")),
        )


class Requests:
    """All requests contribute to counts; latency keeps at most 10,000 samples."""
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.buckets = deque(maxlen=61)
        self.latencies = deque(maxlen=10000)

    def begin(self):
        with self.lock:
            self.active += 1

    def finish(self, status, elapsed, now=None):
        with self.lock:
            now = time.monotonic() if now is None else now
            second = int(now)
            self.active = max(0, self.active - 1)
            if not self.buckets or self.buckets[-1][0] != second:
                self.buckets.append([second, 0, 0, 0, 0.0])
            bucket = self.buckets[-1]
            bucket[1] += 1
            bucket[2] += int(400 <= status < 500)
            bucket[3] += int(status >= 500)
            bucket[4] += elapsed * 1000
            self.latencies.append((now, elapsed * 1000))

    def snapshot(self, now):
        with self.lock:
            # Whole-second buckets, plus at most one partial boundary second.
            while self.buckets and self.buckets[0][0] <= int(now) - 60:
                self.buckets.popleft()
            while self.latencies and self.latencies[0][0] <= now - 60:
                self.latencies.popleft()
            count = sum(b[1] for b in self.buckets)
            client_errors = sum(b[2] for b in self.buckets)
            errors = sum(b[3] for b in self.buckets)
            total_ms = sum(b[4] for b in self.buckets)
            durations = sorted(x[1] for x in self.latencies)
            return dict(active=self.active, count=count, rps=round(count / 60, 2),
                        client_errors=client_errors, server_errors=errors,
                        error_percent=round(errors / count * 100, 1) if count else None,
                        average_ms=round(total_ms / count, 1) if count else None,
                        p95_ms=round(durations[math.ceil(len(durations) * .95) - 1], 1) if durations else None,
                        latency_samples=len(durations))


def pressure(sample):
    alerts = []
    for label, value in (("整机 CPU", sample["host"]["cpu_percent"]),
                         ("应用 CPU 额度", sample["application"]["cpu_percent"]),
                         ("整机内存", sample["host"]["memory_percent"]),
                         ("应用内存额度", sample["application"]["memory_percent"]),
                         ("数据盘", sample["disk"]["percent"])):
        if value is not None and value >= 80:
            alerts.append(dict(level="critical" if value >= 90 else "warning",
                               message=f"{label}使用率 {value:.1f}%，请结合趋势检查"))
    http = sample["http"]
    if http["server_errors"]:
        alerts.append(dict(level="warning", message=f"最近 60 秒出现 {http['server_errors']} 次服务端错误，请查看日志"))
    return alerts


class Monitor:
    def __init__(self):
        self.requests = Requests()
        self.lock = threading.Lock()
        self.history = deque(maxlen=HISTORY_POINTS)
        self.stop_event = threading.Event()
        self.thread = None
        self.started = time.monotonic()
        self.failed = False

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        from app.core.config import settings
        url = make_url(settings.DATABASE_URL)
        directory = Path(url.database).resolve().parent if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:" else Path.cwd()
        self.resources = Resources(disk_path=directory)
        self.started = time.monotonic()
        self.stop_event.clear()
        with self.lock:
            self.history.clear()
        self.thread = threading.Thread(target=self._run, name="server-monitor", daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.sample()
            except Exception:
                # Do not expose paths or exceptions; mark old data as stale.
                with self.lock:
                    self.failed = True
            self.stop_event.wait(INTERVAL)

    def sample(self):
        from app.services.job_manager import JOBS
        now = time.monotonic()
        sample = self.resources.sample(now)
        sample.update(ts=time.time(), service_uptime_seconds=round(now - self.started),
                      http=self.requests.snapshot(now), jobs=JOBS.monitor_summary())
        sample["alerts"] = pressure(sample)
        with self.lock:
            self.history.append(sample)
            self.failed = False

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def snapshot(self, minutes):
        with self.lock:
            samples = list(self.history)
            failed = self.failed
        latest = samples[-1] if samples else None
        age = max(0, time.time() - latest["ts"]) if latest else None
        history = [dict(ts=row["ts"], cpu=row["host"]["cpu_percent"], memory=row["host"]["memory_percent"],
                        app_cpu=row["application"]["cpu_percent"], app_memory=row["application"]["memory_percent"],
                        rx=row["network"]["receive_bps"], tx=row["network"]["transmit_bps"],
                        rps=row["http"]["rps"], p95=row["http"]["p95_ms"])
                   for row in samples if row["ts"] >= time.time() - minutes * 60]
        return dict(current=latest, history=history,
                    interval_seconds=INTERVAL, retention_minutes=60,
                    stale=failed or age is None or age > INTERVAL * 3,
                    age_seconds=round(age, 1) if age is not None else None,
                    platform=platform.system(), container=Path("/.dockerenv").exists() or Path("/run/.containerenv").exists())


MONITOR = Monitor()


class RequestMetricsMiddleware:
    def __init__(self, app, monitor=MONITOR, api_prefix="/api"):
        self.app, self.monitor, self.api_prefix = app, monitor, api_prefix

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith(self.api_prefix + "/") or path.startswith(self.api_prefix + "/monitor") or path == self.api_prefix + "/health":
            return await self.app(scope, receive, send)
        started, status = time.monotonic(), 500
        self.monitor.requests.begin()

        async def observe(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observe)
        except BaseException:
            status = 500
            raise
        finally:
            self.monitor.requests.finish(status, time.monotonic() - started)
