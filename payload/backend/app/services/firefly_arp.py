"""Capture Firefly's browser-generated x-arp-session-id with Playwright.

The IMS token refresh flow cannot return x-arp-session-id. That header is
created by the real Firefly web app when it submits generate-async. We therefore
load the account cookies in Chromium, trigger a tiny generation, intercept the
submit request, and persist the captured ARP value.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LogFn = Callable[[str], None]

FIREFLY_URL = "https://firefly.adobe.com/"
GENERATE_URL_RE = re.compile(r"firefly-3p\.ff\.adobe\.io/v2/3p-images/generate-async")


@dataclass
class ARPCaptureResult:
    success: bool
    message: str
    arp_session_id: str = ""
    access_token: str = ""
    request_url: str = ""


def _parse_cookie_header(cookie_header: str) -> list[dict]:
    cookies: list[dict] = []
    for part in (cookie_header or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        # Host-only cookies cannot be represented from a raw Cookie header. Use
        # broad Adobe domains so both firefly.adobe.com and Adobe IMS pages can
        # see the session material needed by the web app.
        for domain in (".adobe.com", ".adobelogin.com"):
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                    "sameSite": "None",
                }
            )
    return cookies


def _playwright_proxy(proxy_url: str) -> dict | None:
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


def _try_auto_submit(page, prompt: str, log: LogFn) -> None:
    """Best-effort Firefly UI automation.

    Firefly's DOM changes often, so this deliberately tries broad selectors and
    returns silently if it cannot trigger the submit. In headed mode the opened
    browser can still be used manually while the network listener remains active.
    """

    selectors = [
        "textarea",
        "[contenteditable='true']",
        "[role='textbox']",
        "input[type='text']",
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(timeout=12_000)
            loc.fill(prompt, timeout=5_000)
            log(f"已填写 prompt(selector={sel})")
            break
        except Exception:
            try:
                loc.click(timeout=2_000)
                page.keyboard.insert_text(prompt)
                log(f"已输入 prompt(selector={sel})")
                break
            except Exception:
                continue

    button_texts = [
        "Generate",
        "生成",
        "Create",
        "Submit",
    ]
    for text in button_texts:
        try:
            page.get_by_role("button", name=re.compile(text, re.I)).click(timeout=5_000)
            log(f"已点击生成按钮({text})")
            return
        except Exception:
            continue
    for sel in [
        "button[type='submit']",
        "button:has-text('Generate')",
        "button:has-text('生成')",
    ]:
        try:
            page.locator(sel).first.click(timeout=5_000)
            log(f"已点击生成按钮(selector={sel})")
            return
        except Exception:
            continue
    log("未能自动点击生成按钮；如使用 headed=false 失败，可改用有界面模式手动点击一次生成")


def capture_arp_session_id(
    *,
    cookie: str,
    prompt: str = "cartoon watermelon sticker",
    proxy_url: str = "",
    headless: bool = True,
    timeout_ms: int = 120_000,
    log: LogFn | None = None,
) -> ARPCaptureResult:
    lf = log if callable(log) else (lambda _m: None)
    cookie = (cookie or "").strip()
    if not cookie:
        return ARPCaptureResult(False, "缺少 cookie，无法加载 Firefly 登录会话")

    captured: dict[str, str] = {}
    user_data_dir = tempfile.mkdtemp(prefix="okad-firefly-arp-")

    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": headless,
                "user_data_dir": user_data_dir,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                "viewport": {"width": 1365, "height": 900},
                "locale": "en-GB",
            }
            proxy = _playwright_proxy(proxy_url)
            if proxy:
                launch_kwargs["proxy"] = proxy
            ctx = p.chromium.launch_persistent_context(**launch_kwargs)
            try:
                ctx.add_cookies(_parse_cookie_header(cookie))
                page = ctx.new_page()

                def on_request(req) -> None:
                    if not GENERATE_URL_RE.search(req.url):
                        return
                    headers = {k.lower(): v for k, v in req.headers.items()}
                    arp = headers.get("x-arp-session-id", "")
                    auth = headers.get("authorization", "")
                    if arp:
                        captured["arp_session_id"] = arp
                        captured["access_token"] = auth.removeprefix("Bearer ").strip()
                        captured["request_url"] = req.url
                        lf("已捕获 generate-async 请求头 x-arp-session-id")

                page.on("request", on_request)
                page.goto(FIREFLY_URL, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(5_000)
                _try_auto_submit(page, prompt, lf)

                # Poll in Python so request listener has time to capture the
                # outbound call triggered by either auto-submit or manual click.
                elapsed = 0
                step = 1000
                while elapsed < timeout_ms:
                    if captured.get("arp_session_id"):
                        return ARPCaptureResult(
                            True,
                            "已捕获 ARP",
                            captured.get("arp_session_id", ""),
                            captured.get("access_token", ""),
                            captured.get("request_url", ""),
                        )
                    page.wait_for_timeout(step)
                    elapsed += step
                return ARPCaptureResult(
                    False,
                    "超时未捕获 generate-async。建议使用有界面模式打开后手动点一次生成。",
                )
            finally:
                ctx.close()
    except PlaywrightTimeoutError as exc:
        return ARPCaptureResult(False, f"浏览器等待超时:{exc}")
    except Exception as exc:
        return ARPCaptureResult(False, f"浏览器捕获失败:{exc}")
    finally:
        try:
            import shutil

            shutil.rmtree(Path(user_data_dir), ignore_errors=True)
        except Exception:
            pass
