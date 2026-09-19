#!/usr/bin/env python3
"""取一个账号的最新 Adobe 验证码(复用后端 adobe_otp 的收码逻辑)。

用法:  python3 otp_helper.py <email> <refresh_token> <client_id> [mail_url]
成功: 把验证码打到 stdout(单行);过程日志走 stderr;失败退出码非 0。
环境: OTP_TIMEOUT(秒,默认 180)。需要后端依赖(curl_cffi/requests 等)可导入。
"""
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "payload", "backend"))
sys.path.insert(0, _BACKEND)

from app.services.adobe_otp import make_otp_poller  # noqa: E402


def _log(m: str) -> None:
    print(m, file=sys.stderr, flush=True)


def main() -> int:
    if len(sys.argv) < 4:
        _log("usage: otp_helper.py <email> <refresh_token> <client_id> [mail_url]")
        return 64
    email = sys.argv[1].strip()
    refresh_token = sys.argv[2].strip()
    client_id = sys.argv[3].strip()
    mail_url = (sys.argv[4].strip() if len(sys.argv) > 4 else "")
    timeout = max(30, min(int(os.environ.get("OTP_TIMEOUT", "180")), 600))

    poll, _holder = make_otp_poller(
        refresh_token=refresh_token, client_id=client_id, mail_url=mail_url,
        timeout=timeout, log=_log,
    )
    try:
        code = poll(email, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        _log(f"OTP_ERROR: {type(e).__name__}: {str(e)[:200]}")
        return 2
    code = (code or "").strip()
    if not code:
        _log("OTP_ERROR: empty code")
        return 3
    print(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
