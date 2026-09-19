"""Shared helpers for same-session Arkose (ported from adAuto internal/captcha)."""

from __future__ import annotations

from urllib.parse import quote, urlparse


def clip(s: str | bytes | None, n: int = 180) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        s = s.decode("utf-8", "replace")
    s = s or ""
    return s if len(s) <= n else s[:n]


def ark_quote(s: str) -> str:
    """RFC 3986 unreserved only. Slashes in base64 guess/tguess/bio must be %2F."""
    return quote(str(s), safe="-_.~")


def form_encode(*pairs: str) -> str:
    if len(pairs) % 2 != 0:
        return ""
    parts: list[str] = []
    for i in range(0, len(pairs), 2):
        parts.append(ark_quote(pairs[i]) + "=" + ark_quote(pairs[i + 1]))
    return "&".join(parts)


def first_non_empty(*vals: str) -> str:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return ""


def worker_proxy(proxy_url: str) -> str:
    proxy_url = (proxy_url or "").strip()
    if not proxy_url:
        return ""
    try:
        u = urlparse(proxy_url)
    except Exception:
        return proxy_url
    host = (u.hostname or "").lower()
    if host in ("localhost", "localhost."):
        return ""
    if host.startswith("127.") or host == "::1":
        return ""
    return proxy_url


def chrome_major(ua: str) -> str:
    import re

    m = re.search(r"Chrome/(\d+)", ua or "")
    return m.group(1) if m else ""
