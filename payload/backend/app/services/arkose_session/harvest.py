"""One-shot Playwright gt2 harvest (not Cloak pool).

Adobe grades the widget that POSTs /fc/gt2/. FunCaptchaTask opens a second
widget on the solver worker and that token is refused. We inject api.js on
the same website+blob+proxy the complete-account PUT used, capture THIS
session's token/ARID/cookies/UA, then close the page. Session-solve does
PoW / classify / /fc/ca/ over HTTP.

Cloak harvest pool is the proven production path in adAuto. This backend
uses Playwright first because the pool is not wired here yet.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from app.services.arkose_session.util import clip

LogFn = Callable[[str], None]

CALLBACK_NAME = "adregSetupEnforcement"
SIGNUP_PUBLIC_KEY = "436DD567-5435-4B14-89A6-2F1188E11334"
SIGNUP_SURL = "https://arks-client.adobe.com"

_HARVEST_GATE = threading.Semaphore(int(os.environ.get("ADOBE_ARKOSE_HARVEST_GATE") or "2"))

_INJECT_JS = r"""({ publicKey, surl, blob, callbackName }) => {
  const w = window;
  w.__adregArkose = {
    token: '',
    error: '',
    ready: false,
    shown: false,
    suppressed: false,
    completionType: '',
    scriptLoaded: false,
    callbackFired: false,
  };
  try {
    if ('documentMode' in document) {
      Object.defineProperty(document, 'documentMode', {
        configurable: true,
        get: () => undefined,
      });
    }
  } catch (e) {}
  const host = String(surl).replace(/\/$/, '');
  let box = document.getElementById('adreg-arkose');
  if (!box) {
    box = document.createElement('div');
    box.id = 'adreg-arkose';
    box.setAttribute('style', 'width:100%;min-height:400px');
    document.body.appendChild(box);
  }
  w[callbackName] = (enforcement) => {
    w.__adregArkose.callbackFired = true;
    w.__adregEnforcement = enforcement;
    try {
      const mode = document.documentMode;
      if (mode !== undefined) {
        w.__adregArkose.error = 'documentMode=' + String(mode);
        Object.defineProperty(document, 'documentMode', {
          configurable: true,
          get: () => undefined,
        });
      }
    } catch (e) {}
    const cfg = {
      publicKey,
      selector: '#adreg-arkose',
      language: 'en',
      mode: 'inline',
      onReady: () => {
        w.__adregArkose.ready = true;
        try { enforcement.run && enforcement.run(); } catch (e) {}
      },
      onShown: () => { w.__adregArkose.shown = true; },
      onHide: () => undefined,
      onSuppress: () => { w.__adregArkose.suppressed = true; },
      onCompleted: (response) => {
        w.__adregArkose.token = (response && response.token) || '';
        if (response && response.suppressed) {
          w.__adregArkose.suppressed = true;
          w.__adregArkose.completionType = 'transparent';
        }
      },
      onError: (err) => {
        if (typeof err === 'string') { w.__adregArkose.error = err; return; }
        w.__adregArkose.error = String((err && (err.message || err.error)) || err);
      },
    };
    if (blob) cfg.data = { blob };
    const ret = enforcement.setConfig(cfg, true);
    if (ret && typeof ret.then === 'function') {
      ret.then(() => undefined).catch((e) => { w.__adregArkose.error = String(e); });
    }
  };
  const s = document.createElement('script');
  s.src = host + '/v2/' + publicKey + '/api.js';
  s.async = false;
  s.defer = false;
  s.setAttribute('data-callback', callbackName);
  s.onload = () => { w.__adregArkose.scriptLoaded = true; };
  s.onerror = () => { w.__adregArkose.error = 'failed to load arkose api.js'; };
  document.head.appendChild(s);
}"""


class HarvestError(RuntimeError):
    pass


class NavigationFailed(HarvestError):
    """Died getting the harvest browser onto the page; no waves were served."""


@dataclass
class HarvestSeed:
    token: str
    cookies: list[dict[str, str]] = field(default_factory=list)
    arid: str = ""
    user_agent: str = ""
    pow: bool | None = None
    enforcement: str = ""
    suppressed: bool = False


def _playwright_proxy(proxy_url: str) -> dict[str, str] | None:
    proxy_url = (proxy_url or "").strip()
    if not proxy_url:
        return None
    if "://" not in proxy_url:
        proxy_url = "http://" + proxy_url
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return None
    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    proxy: dict[str, str] = {"server": server}
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    return proxy


def _looks_like_token(s: str) -> bool:
    if len(s) < 40 or len(s) > 8000 or "|" not in s:
        return False
    return bool(re.search(r"pk=|[a-f0-9]{8,}\.[0-9]+", s, re.I))


def _parse_maybe_token(raw: str) -> str:
    trimmed = (raw or "").strip()
    try:
        obj = json.loads(trimmed)
        tok = ""
        if isinstance(obj, dict):
            tok = obj.get("token") or ((obj.get("solution") or {}) if isinstance(obj.get("solution"), dict) else {}).get("token") or ""
        if tok and _looks_like_token(str(tok)):
            return str(tok)
    except Exception:
        pass
    if _looks_like_token(trimmed):
        return trimmed
    return ""


def _parse_gt2_body(raw: str) -> tuple[str, bool | None]:
    trimmed = (raw or "").strip()
    try:
        obj = json.loads(trimmed)
        if isinstance(obj, dict) and obj.get("token") and _looks_like_token(str(obj["token"])):
            pow_v = obj.get("pow")
            return str(obj["token"]), pow_v if isinstance(pow_v, bool) else None
    except Exception:
        pass
    return _parse_maybe_token(trimmed), None


def _enforcement_url(url: str) -> str:
    path = (url or "").split("?", 1)[0]
    if re.search(r"/v2/[\d.]+/enforcement\.[a-f0-9]+\.html$", path, re.I):
        return path
    return ""


def _cookie_arid(cookies: list[dict[str, str]]) -> str:
    for c in cookies:
        if str(c.get("name") or "").upper() == "ARID" and c.get("value"):
            return str(c["value"])
    return ""


def _token_suppressed(token: str) -> bool:
    return "sup=1" in (token or "")


def harvest_gt2(
    *,
    website_url: str,
    blob: str,
    public_key: str = SIGNUP_PUBLIC_KEY,
    surl: str = SIGNUP_SURL,
    proxy_url: str = "",
    user_agent: str = "",
    timeout_ms: int = 90_000,
    log: LogFn | None = None,
) -> HarvestSeed:
    """Open a real page, inject Arkose with the IMS blob, capture this gt2."""
    lf = log if callable(log) else (lambda _m: None)
    website_url = (website_url or "").strip() or "https://auth.services.adobe.com/en_US/index.html"
    public_key = (public_key or "").strip() or SIGNUP_PUBLIC_KEY
    surl = (surl or "").strip().rstrip("/") or SIGNUP_SURL
    if not blob:
        raise HarvestError("harvest gt2 needs IMS blob")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise HarvestError("playwright 未安装,无法收 gt2") from e

    headless = (os.environ.get("ADOBE_ARKOSE_HEADLESS") or "1").strip().lower() not in (
        "0", "false", "no", "off",
    )
    network: dict[str, Any] = {
        "token": "",
        "pow": None,
        "arid": "",
        "enforcement": "",
    }
    user_data_dir = tempfile.mkdtemp(prefix="okad-arkose-gt2-")
    _HARVEST_GATE.acquire()
    try:
        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {
                "headless": headless,
                "user_data_dir": user_data_dir,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                "viewport": {"width": 1365, "height": 900},
                "locale": "en-US",
            }
            proxy = _playwright_proxy(proxy_url)
            if proxy:
                launch_kwargs["proxy"] = proxy
            if user_agent:
                launch_kwargs["user_agent"] = user_agent
            ctx = p.chromium.launch_persistent_context(**launch_kwargs)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    session = ctx.new_cdp_session(page)
                    session.send("Page.setBypassCSP", {"enabled": True})
                except Exception as e:  # noqa: BLE001
                    lf(f"gt2 harvest csp bypass failed: {clip(str(e), 160)}")
                page.add_init_script(
                    "globalThis.__name = globalThis.__name || function (f) { return f; };"
                )
                page.add_init_script(
                    "Object.defineProperty(window, 'setupEnforcementSignUp', "
                    "{configurable:true, writable:true, value: () => undefined});"
                )

                def on_response(res) -> None:
                    url = res.url or ""
                    if not re.search(r"arkose|funcaptcha|arks-client|/fc/", url, re.I):
                        return
                    path = url.split("?", 1)[0]
                    is_gt2 = bool(re.search(r"/fc/gt2/", path, re.I))
                    enf = _enforcement_url(url)
                    if enf and not network["enforcement"]:
                        network["enforcement"] = enf
                    try:
                        headers = {k.lower(): v for k, v in res.headers.items()}
                    except Exception:
                        headers = {}
                    arid = (headers.get("x-ark-arid") or "").strip()
                    if arid and not network["arid"]:
                        network["arid"] = arid
                    if not is_gt2:
                        return
                    try:
                        body = res.text()
                    except Exception:
                        return
                    tok, pow_v = _parse_gt2_body(body)
                    if tok and not network["token"]:
                        network["token"] = tok
                        network["pow"] = pow_v
                        lf(f"gt2 harvest token from network len={len(tok)} pow={pow_v}")

                page.on("response", on_response)
                nav_timeout = min(timeout_ms, 90_000)
                lf(f"gt2 harvest goto {clip(website_url, 180)}")
                try:
                    page.goto(website_url, wait_until="domcontentloaded", timeout=nav_timeout)
                except PlaywrightTimeoutError as e:
                    raise NavigationFailed(f"page.goto timeout: {clip(str(e), 160)}") from e
                except Exception as e:  # noqa: BLE001
                    msg = str(e)
                    if _is_nav_msg(msg):
                        raise NavigationFailed(msg) from e
                    raise HarvestError(f"page.goto: {clip(msg, 160)}") from e

                page.evaluate(
                    "globalThis.__name = globalThis.__name || function (f) { return f; };"
                )
                page.evaluate(
                    _INJECT_JS,
                    {
                        "publicKey": public_key,
                        "surl": surl,
                        "blob": blob,
                        "callbackName": CALLBACK_NAME,
                    },
                )
                lf(f"gt2 harvest arkose injected pk={public_key} blob={len(blob)}")

                deadline = time.time() + timeout_ms / 1000
                last_err = ""
                while time.time() < deadline:
                    if network["token"]:
                        break
                    try:
                        state = page.evaluate("() => window.__adregArkose || {}") or {}
                    except Exception:
                        state = {}
                    if isinstance(state, dict):
                        last_err = str(state.get("error") or "")
                        tok = str(state.get("token") or "")
                        if tok and _looks_like_token(tok) and not network["token"]:
                            network["token"] = tok
                            break
                    page.wait_for_timeout(250)

                if not network["token"]:
                    raise HarvestError(
                        f"gt2 harvest timeout token empty error={clip(last_err, 160)}"
                    )

                cookies = _collect_cookies(page)
                ua = ""
                try:
                    ua = page.evaluate("() => navigator.userAgent") or ""
                except Exception:
                    ua = user_agent
                arid = network["arid"] or _cookie_arid(cookies)
                suppressed = _token_suppressed(network["token"])
                try:
                    state = page.evaluate("() => window.__adregArkose || {}") or {}
                    if isinstance(state, dict) and state.get("suppressed"):
                        suppressed = True
                except Exception:
                    pass
                lf(
                    f"gt2 harvest done suppressed={suppressed} arid={bool(arid)} "
                    f"cookies={len(cookies)} pow={network['pow']}"
                )
                return HarvestSeed(
                    token=network["token"],
                    cookies=cookies,
                    arid=arid,
                    user_agent=ua or user_agent,
                    pow=network["pow"],
                    enforcement=network["enforcement"],
                    suppressed=suppressed,
                )
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    finally:
        _HARVEST_GATE.release()
        shutil.rmtree(user_data_dir, ignore_errors=True)


def _collect_cookies(page) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    try:
        all_cks = page.context.cookies()
    except Exception:
        return out
    for c in all_cks:
        blob = f"{c.get('domain', '')} {c.get('name', '')}"
        if not re.search(r"adobe|arks-client|arkose|funcaptcha", blob, re.I):
            continue
        item = {"name": str(c.get("name") or ""), "value": str(c.get("value") or "")}
        if c.get("domain"):
            item["domain"] = str(c["domain"])
        if c.get("path"):
            item["path"] = str(c["path"])
        if item["name"] and item["value"]:
            out.append(item)
    return out


def _is_nav_msg(msg: str) -> bool:
    low = (msg or "").lower()
    return any(
        n in low
        for n in (
            "page.goto",
            "err_connection",
            "err_proxy",
            "err_tunnel_connection_failed",
            "err_name_not_resolved",
            "err_timed_out",
            "net::err",
        )
    )
