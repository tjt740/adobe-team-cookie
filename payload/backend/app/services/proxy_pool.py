from __future__ import annotations

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

_lock = threading.Lock()
_cursor: dict[str, itertools.count] = {}
_health: dict[str, dict[str, object]] = {}
_split_cache: dict[str, list[str]] = {}

_PROXY_ERROR_MARKERS = (
    "proxy",
    "socks",
    "connection reset",
    "connection refused",
    "connection aborted",
    "connect timeout",
    "read timeout",
    "timed out",
    "timeout",
    "ssl",
    "tls",
    "wrong_version_number",
    "tunnel",
    "407",
    "502 bad gateway",
    "503",
    "network error",
    "curl:",
)


def _split(raw: str) -> list[str]:
    cached = _split_cache.get(raw)
    if cached is not None:
        return cached
    items: list[str] = []
    for line in (raw or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for part in line.replace(",", " ").replace(";", " ").split():
            part = part.strip()
            if part:
                items.append(_normalize(part))
    # 防止无界增长:缓存条目上限
    if len(_split_cache) > 32:
        _split_cache.clear()
    _split_cache[raw] = items
    return items


def _normalize(proxy: str) -> str:
    proxy = (proxy or "").strip()
    if not proxy:
        return ""
    if "://" in proxy:
        return proxy
    if "@" in proxy:
        return f"http://{proxy}"
    parts = proxy.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{proxy}"
    return proxy


def _healthy(proxy: str) -> bool:
    rec = _health.get(proxy) or {}
    return float(rec.get("cool_until") or 0) <= time.time()


def proxy_count(raw: str) -> int:
    return len(_split(raw))


def next_proxy(raw: str) -> str:
    proxies = _split(raw)
    if not proxies:
        return ""

    key = "\n".join(proxies)
    with _lock:
        counter = _cursor.setdefault(key, itertools.count())
        start = next(counter)

    for offset in range(len(proxies)):
        proxy = proxies[(start + offset) % len(proxies)]
        if _healthy(proxy):
            return proxy
    return proxies[start % len(proxies)]


def random_proxy(raw: str, exclude: str = "") -> str:
    """随机取一个健康代理;raw 空返回 ''。优先健康的,全不健康则随机回退。

    ``exclude`` 是刚失败的出口(换 IP 重试用),优先避开;池里只剩它时仍返回它。
    """
    import random

    proxies = _split(raw)
    if not proxies:
        return ""
    healthy = [p for p in proxies if _healthy(p)]
    pool = healthy or proxies
    skip = _normalize(exclude)
    if skip:
        others = [p for p in pool if p != skip]
        if others:
            pool = others
    return random.choice(pool)


def pick(settings) -> str:
    if not getattr(settings, "proxy_enabled", False):
        return ""
    return next_proxy(getattr(settings, "proxy_url", "") or "")


def report_success(proxy: str) -> None:
    proxy = _normalize(proxy)
    if not proxy:
        return
    with _lock:
        rec = _health.setdefault(proxy, {})
        rec["ok"] = int(rec.get("ok") or 0) + 1
        rec["fail"] = 0
        rec["cool_until"] = 0.0
        rec["last_message"] = ""
        rec["last_at"] = int(time.time())


def report_failure(proxy: str, message: str = "") -> None:
    proxy = _normalize(proxy)
    if not proxy:
        return
    with _lock:
        rec = _health.setdefault(proxy, {})
        fail = int(rec.get("fail") or 0) + 1
        rec["fail"] = fail
        rec["last_message"] = (message or "")[:300]
        rec["last_at"] = int(time.time())
        rec["cool_until"] = time.time() + min(300, 15 * fail)


def is_proxy_error(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _PROXY_ERROR_MARKERS)


def _requests_proxies(proxy: str) -> dict[str, str] | None:
    proxy = _normalize(proxy)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _test_one(proxy: str) -> dict:
    started = time.perf_counter()
    try:
        resp = requests.get(
            "https://api.ipify.org?format=json",
            proxies=_requests_proxies(proxy),
            timeout=12,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        resp.raise_for_status()
        data = resp.json()
        report_success(proxy)
        return {
            "proxy": proxy,
            "ok": True,
            "ip": str(data.get("ip") or ""),
            "latency_ms": latency_ms,
            "message": "OK",
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        message = str(exc)[:300]
        report_failure(proxy, message)
        return {
            "proxy": proxy,
            "ok": False,
            "ip": "",
            "latency_ms": latency_ms,
            "message": message,
        }


def test_all(raw: str) -> list[dict]:
    proxies = _split(raw)
    if not proxies:
        return []
    workers = min(20, len(proxies))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(_test_one, proxy): proxy for proxy in proxies}
        for future in as_completed(future_map):
            results.append(future.result())
    order = {proxy: idx for idx, proxy in enumerate(proxies)}
    results.sort(key=lambda item: order.get(item["proxy"], 0))
    return results


def health_snapshot(raw: str) -> list[dict]:
    items = []
    now = time.time()
    for proxy in _split(raw):
        rec = _health.get(proxy) or {}
        cool_until = float(rec.get("cool_until") or 0)
        items.append(
            {
                "proxy": proxy,
                "healthy": cool_until <= now,
                "ok": int(rec.get("ok") or 0),
                "fail": int(rec.get("fail") or 0),
                "cooldown_sec": max(0, int(cool_until - now)),
                "last_message": rec.get("last_message") or "",
                "last_at": rec.get("last_at") or 0,
            }
        )
    return items
