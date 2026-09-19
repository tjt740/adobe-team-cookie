"""Adobe IMS Arkose (FunCaptcha) for invited-account completion.

IMS now refuses PUT /signin/v2/accounts with:
  403 {"errorCode":"forbidden","errorMessage":"Use /v4/accounts when Arkose captcha is enabled"}

The working protocol (same as adAuto guest CompleteInvite / signup) is:

  1. PUT /signin/v4/accounts on the same incompleteAccount session
     with header x-ims-arkose-captcha-token (empty on the first try).
  2. If 400 captcha_required, read x-ims-captcha-encrypted (the blob)
     and echo x-ims-authentication-state-encrypted /
     x-identity-verification-token from that response.
  3. Harvest THIS blob's /fc/gt2/ in a real page (same proxy), then
     classify tiles with YesCaptcha FunCaptchaClassification and POST
     /fc/ca/ on that same Arkose session.
  4. PUT /signin/v4/accounts again on the SAME IMS client with
     x-ims-arkose-captcha-token = that session's token.

Do not send X-IMS-EntCaptcha-Response here — that header is for
POST /signin/v2/accounts signup, not v4 complete.

YesCaptcha's FunCaptcha widget API is offline. FunCaptchaTask opens a
second widget on the solver worker; Adobe's signup key refuses that token.
Cloak harvest pool is not wired in this backend yet (Playwright one-shot).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

from app.services.arkose_session import (
    is_navigation_failed,
    is_unknown_question,
    not_retryable,
    solve_session,
)

LogFn = Callable[[str], None]

SIGNUP_PUBLIC_KEY = "436DD567-5435-4B14-89A6-2F1188E11334"
SIGNUP_SURL = "https://arks-client.adobe.com"
DEFAULT_WEBSITE_URL = "https://auth.services.adobe.com/en_US/index.html"

# Arkose grades a whole session; one bad tile burns the token. Retry a few times.
ARKOSE_TRIES = 3

_SESSION_IDENTITY_COOKIES = frozenset(
    {"relay", "gds", "bfp", "ftrset", "idg_token"}
)

_PROVIDERS = {
    "2captcha": "https://api.2captcha.com",
    "capsolver": "https://api.capsolver.com",
    "ez": "https://api.ez-captcha.com",
    "ezcaptcha": "https://api.ez-captcha.com",
}


class ArkoseError(RuntimeError):
    pass


@dataclass
class ArkoseResult:
    token: str
    cookies: list[dict[str, str]] = field(default_factory=list)
    suppressed: bool = False
    via: str = ""


def echo_auth_state(auth: Any, resp: Any) -> None:
    """Copy IMS session headers the retry must echo.

    captcha_required 400 returns a fresh authentication state. A retry that
    keeps the pre-PUT state is a different session to IMS (adAuto job 225).
    """
    if auth is None or resp is None:
        return
    headers = getattr(resp, "headers", None) or {}
    ast = _header(headers, "x-ims-authentication-state-encrypted")
    ivt = _header(headers, "x-identity-verification-token")
    if ast:
        auth.auth_state_encrypted = ast
    if ivt:
        auth.identity_verification_token = ivt


def complete_headers(auth: Any, arkose_token: str = "") -> dict[str, str]:
    """Headers for PUT /signin/v4/accounts.

    Always set x-ims-arkose-captcha-token (empty on the first probe).
    Never set X-IMS-EntCaptcha-Response on this path.
    """
    h = dict(auth.headers()) if auth is not None else {}
    h.pop("X-IMS-EntCaptcha-Response", None)
    h.pop("x-ims-entcaptcha-response", None)
    h["x-ims-arkose-captcha-token"] = arkose_token or ""
    return h


def captcha_blob(resp: Any) -> str:
    if resp is None:
        return ""
    headers = getattr(resp, "headers", None) or {}
    blob = _header(headers, "x-ims-captcha-encrypted")
    if blob:
        return blob
    try:
        data = resp.json() if callable(getattr(resp, "json", None)) else None
    except Exception:
        data = None
    if isinstance(data, dict):
        v = data.get("captchaEncryptedData") or data.get("captcha_encrypted_data") or ""
        if isinstance(v, str):
            return v
    return ""


def is_captcha_required(status: int, body: str) -> bool:
    low = (body or "").lower()
    if "use /v4/accounts" in low:
        return False
    if "captcha_required" in low:
        return True
    if status in (400, 403) and ("captcha" in low or "arkose" in low):
        return True
    return False


def already_completed(status: int, body: str) -> bool:
    """IMS already wrote the profile (often on the captcha_required PUT)."""
    if status not in (400, 409):
        return False
    low = (body or "").lower()
    if "already set" in low:
        return True
    if "invalid_field" in low and "already" in low:
        return True
    return False


def token_meta(token: str) -> str:
    pk = ""
    for part in (token or "").split("|"):
        if part.startswith("pk="):
            pk = part
            break
    return f"len={len(token or '')} {pk}".strip()


def inject_solver_cookies(client: Any, cookies: list[dict[str, str]] | None) -> None:
    """Merge Arkose cookies; never overwrite IMS session identity cookies."""
    if client is None or not cookies:
        return
    jar = getattr(client, "cookies", None)
    session = getattr(client, "session", None)
    for ck in cookies:
        if not isinstance(ck, dict):
            continue
        name = str(ck.get("name") or "").strip()
        value = str(ck.get("value") or "").strip()
        if not name or not value:
            continue
        if name.lower() in _SESSION_IDENTITY_COOKIES:
            continue
        if isinstance(jar, dict):
            jar[name] = value
        if session is not None:
            try:
                session.cookies.set(name, value)
            except Exception:
                pass


def load_captcha_config() -> tuple[str, str]:
    """provider, api_key. Settings first, env overrides.

    Env: ADOBE_CAPTCHA_PROVIDER, ADOBE_CAPTCHA_KEY
    (YESCAPTCHA_KEY / TWOCAPTCHA_KEY / CAPSOLVER_KEY / EZCAPTCHA_KEY as fallbacks).
    """
    provider, key = "", ""
    try:
        from app.crud import setting as setting_crud
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            s = setting_crud.get_settings(db)
            provider = (getattr(s, "captcha_provider", "") or "").strip()
            key = (getattr(s, "captcha_key", "") or "").strip()
        finally:
            db.close()
    except Exception:
        pass
    provider = (os.environ.get("ADOBE_CAPTCHA_PROVIDER") or provider or "").strip().lower()
    key = (os.environ.get("ADOBE_CAPTCHA_KEY") or key or "").strip()
    if not key:
        if provider in ("2captcha", ""):
            key = (os.environ.get("TWOCAPTCHA_KEY") or "").strip()
        elif provider == "capsolver":
            key = (os.environ.get("CAPSOLVER_KEY") or "").strip()
        elif provider in ("ez", "ezcaptcha"):
            key = (os.environ.get("EZCAPTCHA_KEY") or "").strip()
        elif provider in ("yescaptcha", "yes"):
            key = (os.environ.get("YESCAPTCHA_KEY") or "").strip()
    if key and not provider:
        provider = "2captcha"
    if provider in ("none", "off", "disabled"):
        return "", key
    return provider, key


def solve(
    *,
    provider: str,
    api_key: str,
    website_url: str,
    blob: str,
    user_agent: str = "",
    proxy_url: str = "",
    log: Optional[LogFn] = None,
    poll: Optional[Callable[..., str]] = None,
    harvest_fn=None,
    solver=None,
) -> ArkoseResult:
    """Solve Arkose for the IMS blob.

    yescaptcha: harvest this blob's gt2, classify tiles, submit /fc/ca/
    on the same session (adAuto signup path, no Cloak pool).
    2captcha/capsolver/ez: leftover FunCaptchaTask widget path.
    """
    provider = (provider or "").strip().lower()
    if provider in ("yescaptcha", "yes"):
        res = solve_session(
            api_key=api_key,
            website_url=website_url,
            blob=blob,
            user_agent=user_agent,
            proxy_url=proxy_url,
            log=log,
            harvest_fn=harvest_fn,
            solver=solver,
        )
        if log:
            log(
                f"✓ arkose token {token_meta(res.token)} "
                f"suppressed={res.suppressed} via={res.via}"
            )
        return ArkoseResult(
            token=res.token, cookies=res.cookies,
            suppressed=res.suppressed, via=res.via or "yescaptcha-session",
        )
    token = solve_funcaptcha(
        provider=provider, api_key=api_key, website_url=website_url,
        blob=blob, user_agent=user_agent, proxy_url=proxy_url, log=log, poll=poll,
    )
    return ArkoseResult(token=token, via=provider)


def solve_funcaptcha(
    *,
    provider: str,
    api_key: str,
    website_url: str,
    blob: str,
    user_agent: str = "",
    proxy_url: str = "",
    log: Optional[LogFn] = None,
    poll: Optional[Callable[..., str]] = None,
) -> str:
    """Create a FunCaptcha task with the IMS blob and poll for the token.

    YesCaptcha's widget API is offline; yescaptcha must go through solve()
    (same-session classify), not this function.
    """
    lf = log if callable(log) else (lambda _m: None)
    provider = (provider or "").strip().lower()
    if provider in ("yescaptcha", "yes"):
        raise ArkoseError(
            "YesCaptcha FunCaptcha 协议接口已下线,请用 session-solve 分类"
            "(设置 captcha_provider=yescaptcha,走 arkose.solve)"
        )
    api_base = _PROVIDERS.get(provider)
    if not api_base:
        raise ArkoseError(
            f"未知打码平台 {provider or '(空)'},支持: yescaptcha / 2captcha / capsolver / ez"
        )
    if not api_key:
        raise ArkoseError(f"{provider} 未配置 API Key")
    if not blob:
        raise ArkoseError("captcha_required 但没有 x-ims-captcha-encrypted blob")

    task = build_funcaptcha_task(
        provider, website_url=website_url, blob=blob,
        user_agent=user_agent, proxy_url=proxy_url,
    )
    lf(
        f"solving arkose via {provider} "
        f"blob={len(blob)} website={website_url} proxy={'有' if _worker_proxy(proxy_url) else '无'}"
    )
    create_poll = poll or create_and_poll
    token = (create_poll(api_base, api_key, task) or "").strip()
    if not token:
        raise ArkoseError(f"{provider} 打码返回空 token")
    lf(f"✓ arkose token {token_meta(token)} suppressed={('sup=1' in token)}")
    return token


def build_funcaptcha_task(
    provider: str,
    *,
    website_url: str,
    blob: str,
    user_agent: str = "",
    proxy_url: str = "",
) -> dict[str, Any]:
    website = (website_url or "").strip() or DEFAULT_WEBSITE_URL
    provider = (provider or "").strip().lower()
    worker_proxy = _worker_proxy(proxy_url)

    if provider in ("ez", "ezcaptcha"):
        # ez FunCaptchaTaskProxyless, data={"blob": ...}. Do not send a proxy field.
        surl_host = urlparse(SIGNUP_SURL).netloc or "arks-client.adobe.com"
        origin = _origin_only(website) or website
        data: dict[str, Any] = {
            "type": "FunCaptchaTaskProxyless",
            "websiteURL": origin,
            "websiteKey": SIGNUP_PUBLIC_KEY,
            "funcaptchaApiJSSubdomain": surl_host,
        }
        if user_agent:
            data["userAgent"] = user_agent
        blob_json = _blob_json(blob)
        if blob_json:
            data["data"] = blob_json
        return data

    data = {
        "websiteURL": website,
        "websitePublicKey": SIGNUP_PUBLIC_KEY,
        "funcaptchaApiJSSubdomain": "arks-client.adobe.com",
    }
    if user_agent:
        data["userAgent"] = user_agent
    blob_json = _blob_json(blob)
    if blob_json:
        data["data"] = blob_json

    if worker_proxy:
        data["type"] = "FunCaptchaTask"
        ptype, host, port, user, password = _parse_proxy(worker_proxy)
        if ptype == "socks5h":
            ptype = "socks5"
        data["proxyType"] = ptype
        data["proxyAddress"] = host
        data["proxyPort"] = port
        if user:
            data["proxyLogin"] = user
            data["proxyPassword"] = password
    else:
        data["type"] = (
            "FunCaptchaTaskProxyLess" if provider == "capsolver" else "FunCaptchaTaskProxyless"
        )
    return data


def create_and_poll(api_base: str, client_key: str, task: dict[str, Any],
                    timeout: int = 180) -> str:
    sess = requests.Session()
    sess.trust_env = False
    try:
        cr = sess.post(
            f"{api_base.rstrip('/')}/createTask",
            json={"clientKey": client_key, "task": task},
            timeout=30,
        )
        body = _json(cr)
        if int(body.get("errorId") or 0) != 0:
            raise ArkoseError(
                f"createTask: {body.get('errorCode') or ''} {body.get('errorDescription') or cr.text[:180]}"
            )
        solution = (body.get("solution") or {}).get("token") if isinstance(body.get("solution"), dict) else ""
        if body.get("status") == "ready" and solution:
            return str(solution)
        task_id = body.get("taskId")
        if task_id in (None, ""):
            raise ArkoseError(f"createTask 未返回 taskId: {_clip(cr.text, 180)}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(3)
            pr = sess.post(
                f"{api_base.rstrip('/')}/getTaskResult",
                json={"clientKey": client_key, "taskId": task_id},
                timeout=30,
            )
            pb = _json(pr)
            if int(pb.get("errorId") or 0) != 0:
                raise ArkoseError(
                    f"getTaskResult: {pb.get('errorCode') or ''} {pb.get('errorDescription') or pr.text[:180]}"
                )
            sol = (pb.get("solution") or {}).get("token") if isinstance(pb.get("solution"), dict) else ""
            if pb.get("status") == "ready" and sol:
                return str(sol)
        raise ArkoseError("captcha timeout")
    finally:
        sess.close()


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if callable(getter):
        v = getter(name)
        if v:
            return str(v)
        # Some test doubles are case-sensitive dicts.
        for k, val in (headers.items() if hasattr(headers, "items") else []):
            if str(k).lower() == name.lower() and val:
                return str(val)
        return ""
    return ""


def _blob_json(blob: str) -> str:
    if not blob:
        return ""
    return json.dumps({"blob": blob}, separators=(",", ":"))


def _origin_only(raw: str) -> str:
    try:
        u = urlparse(raw)
    except Exception:
        return raw
    if u.scheme and u.netloc:
        return f"{u.scheme}://{u.netloc}"
    return raw


def _worker_proxy(proxy_url: str) -> str:
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


def _parse_proxy(proxy_url: str) -> tuple[str, str, int, str, str]:
    u = urlparse(proxy_url)
    scheme = (u.scheme or "http").lower()
    host = u.hostname or ""
    port = u.port or (443 if scheme == "https" else 80)
    user = u.username or ""
    password = u.password or ""
    return scheme, host, int(port), user, password


def _json(resp: Any) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n]
