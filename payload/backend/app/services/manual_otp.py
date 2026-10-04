"""外部子号的手动验证码交接。验证码仅在当前进程内等待一次消费。"""

from dataclasses import dataclass, field
from math import ceil
from threading import Condition
import time
import uuid


class ManualOtpError(RuntimeError):
    pass


@dataclass
class _Pending:
    email: str
    deadline: float
    expires_at: int
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    code: str | None = None


class ManualOtpBroker:
    def __init__(self):
        self._condition = Condition()
        self._pending: dict[int, _Pending] = {}

    def status(self, member_id: int) -> dict | None:
        with self._condition:
            pending = self._pending.get(member_id)
            if not pending or pending.deadline <= time.monotonic() or pending.code is not None:
                return None
            return {"request_id": pending.request_id, "email": pending.email,
                    "expires_at": pending.expires_at}

    def submit(self, member_id: int, request_id: str, code: str) -> None:
        # API 校验之外再兜底；异常文案始终不含原始输入。
        if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
            raise ValueError("请输入 6 位数字验证码")
        with self._condition:
            pending = self._pending.get(member_id)
            if not pending or pending.request_id != request_id or pending.deadline <= time.monotonic():
                raise ManualOtpError("验证码请求已失效，请刷新账号状态；登录超时后需重新登录")
            if pending.code is not None:
                raise ManualOtpError("验证码已提交，请等待登录结果")
            pending.code = code
            self._condition.notify_all()

    def request(self, member_id: int, email: str, *, timeout: float = 180,
                check_cancelled=None, log=None) -> str:
        if check_cancelled:
            check_cancelled()
        wait_s = max(.05, min(float(timeout or 180), 300))
        pending = _Pending(email=email, deadline=time.monotonic() + wait_s,
                           expires_at=ceil(time.time() + wait_s))
        with self._condition:
            existing = self._pending.get(member_id)
            if existing and existing.deadline > time.monotonic():
                raise ManualOtpError("该账号已在等待手动验证码，请在原任务中提交")
            self._pending[member_id] = pending
        try:
            if log:
                log(f"等待手动验证码，请在账号行点击「填验证码」（{ceil(wait_s)} 秒内）")
            while True:
                if check_cancelled:
                    check_cancelled()
                with self._condition:
                    remaining = pending.deadline - time.monotonic()
                    if remaining <= 0:
                        raise ManualOtpError("手动验证码等待超时，请重新登录获取新验证码")
                    if pending.code is not None:
                        code = pending.code
                        pending.code = None
                        if self._pending.get(member_id) is pending:
                            del self._pending[member_id]
                        return code
                    self._condition.wait(timeout=min(.25, remaining))
        finally:
            with self._condition:
                if self._pending.get(member_id) is pending:
                    del self._pending[member_id]
                pending.code = None


BROKER = ManualOtpBroker()
