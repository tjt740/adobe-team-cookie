"""越南登录的异步取码接口。仅提交邮箱，不传递 Adobe 密码。"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import time
from urllib.parse import quote

import requests

API_BASE = "https://otp.marydatch.com/api"


class VietnamOtpError(RuntimeError):
    pass


def _received_timestamp(value) -> float | None:
    try:
        received = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if received.tzinfo is None:
            return None
        return received.astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def make_vietnam_otp_poller(*, log=None, check_cancelled=None):
    """每个登录尝试独立保存已用码，等待上限包括提交、查询及间隔。"""
    lf = log if callable(log) else lambda _msg: None
    used_by_email: dict[str, set[str]] = {}

    def check():
        if check_cancelled:
            check_cancelled()

    def poll(email: str, timeout: int = 180, interval: float = 1.5, base_url: str = "") -> str:
        del base_url
        key = email.strip().lower()
        deadline = time.monotonic() + max(1, timeout)
        not_before = time.time() - 15
        used = used_by_email.setdefault(key, set())
        http = requests.Session()

        def pause(seconds):
            until = min(deadline, time.monotonic() + seconds)
            while time.monotonic() < until:
                check()
                time.sleep(max(0, min(.25, until - time.monotonic())))
            check()

        def request(method, path, **kwargs):
            check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VietnamOtpError("越南登录自动接码超时，请稍后重试")
            try:
                response = http.request(method, API_BASE + path,
                    headers={"Accept": "application/json"},
                    timeout=min(12, remaining), allow_redirects=False, **kwargs)
            except requests.RequestException:
                raise VietnamOtpError("越南取码站连接失败，请稍后重试") from None
            check()
            if time.monotonic() >= deadline:
                raise VietnamOtpError("越南登录自动接码超时，请稍后重试")
            if response.status_code == 429:
                raise VietnamOtpError("越南取码站请求过于频繁（429），请稍后重试")
            if response.status_code == 404 and method == "GET":
                return {"status": "expired"}
            if response.status_code not in (200, 202):
                raise VietnamOtpError(f"越南取码站返回 HTTP {response.status_code}，请稍后重试")
            try:
                data = response.json()
            except ValueError:
                raise VietnamOtpError("越南取码站返回了无法识别的数据") from None
            if not isinstance(data, dict):
                raise VietnamOtpError("越南取码站返回了无法识别的数据")
            # 第三方错误正文不进入日志，避免回显邮件、验证码或服务端凭据。
            return data

        lf("等待 Adobe 邮箱验证，正在通过越南取码站自动接码…")
        try:
            while time.monotonic() < deadline:
                job = request("POST", "/lookup", json={"email": key})
                job_id = job.get("jobId")
                if not isinstance(job_id, str) or not job_id or len(job_id) > 200:
                    raise VietnamOtpError("越南取码站未创建查询任务，请检查邮箱是否支持接码")
                try:
                    wait = float(job.get("pollIntervalMs", interval * 1000)) / 1000
                except (ValueError, TypeError):
                    wait = interval
                wait = max(1.5, min(wait, 10)) if math.isfinite(wait) else 1.5
                while time.monotonic() < deadline:
                    pause(wait)
                    if time.monotonic() >= deadline:
                        break
                    data = request("GET", "/lookup/" + quote(job_id, safe=""))
                    status = data.get("status")
                    if status in ("pending", "running"):
                        continue
                    if status == "expired":
                        break
                    if status != "done":
                        raise VietnamOtpError("越南取码站返回了无法识别的任务状态")
                    if data.get("kind") == "auth_only" and not (data.get("success") and data.get("otp")):
                        raise VietnamOtpError("越南取码站提示应使用 Adobe 密码登录，请检查登录方式后重试")
                    recipient = data.get("email")
                    if recipient is not None and str(recipient).strip().lower() != key:
                        raise VietnamOtpError("越南取码站返回的邮箱不匹配，已停止本次登录")
                    if data.get("success") is True:
                        code = str(data.get("otp") or "")
                        ts = _received_timestamp(data.get("receivedAt"))
                        now = time.time()
                        if (re.fullmatch(r"[0-9]{6}", code) and code != "000000"
                                and ts is not None and max(not_before, now - 300) <= ts <= now + 60
                                and code not in used):
                            used.add(code)
                            if data.get("authWarn"):
                                lf("越南取码站提示请确认使用密码登录，本次继续验证收到的验证码")
                            lf("✓ 已收到 Adobe 验证码（越南登录）")
                            return code
                        lf("越南取码站暂未返回本次登录的新验证码，继续等待…")
                    # 已结束但未找到新码，稍后重建查信任务，不向 Adobe 重复发码。
                    break
                pause(max(3, wait))
        finally:
            http.close()
        raise VietnamOtpError("越南登录自动接码超时，请确认邮箱已收到 Adobe 验证邮件后重试")

    poll.single_wait = True
    return poll
