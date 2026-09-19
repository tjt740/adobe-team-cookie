"""邮箱池预占:并发拉号(多主号/多子号)时避免不同任务取到同一个邮箱。

进程内用一个锁 + 已预占集合实现"取号即占用",成功后转已用、失败后释放。
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from app.crud import email as email_crud
from app.models.email import Email

_lock = threading.Lock()
_claimed: set[str] = set()


def claim(db: Session, n: int, extra_exclude: set[str] | None = None) -> list[Email]:
    """原子地取 n 个未使用且未被预占的邮箱并标记预占。"""
    if n <= 0:
        return []
    with _lock:
        exclude = set(_claimed)
        if extra_exclude:
            exclude |= {e.lower() for e in extra_exclude}
        rows = email_crud.take_unused(db, n, exclude=exclude)
        for r in rows:
            _claimed.add(r.email.lower())
        return rows


def release(emails: list[str]) -> None:
    """释放预占(失败重拉或成功落库后调用)。"""
    if not emails:
        return
    with _lock:
        for e in emails:
            _claimed.discard(e.lower())
