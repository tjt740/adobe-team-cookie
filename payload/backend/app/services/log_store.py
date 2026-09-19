"""进程内日志缓冲:收集 HTTP 错误、未捕获异常和库的告警,供「日志管理」查看。

注意:内存环形缓冲(默认最近 3000 条),进程重启即清空。
"""

from __future__ import annotations

import logging
import threading
import time
import traceback as _tb
from collections import deque
from typing import Any

_MAXLEN = 3000


class LogStore:
    def __init__(self, maxlen: int = _MAXLEN) -> None:
        self._dq: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counter = 0

    def add(self, level: str, source: str, message: str, tb: str = "") -> None:
        with self._lock:
            self._counter += 1
            self._dq.append({
                "id": self._counter,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ts": time.time(),
                "level": (level or "INFO").upper(),
                "source": source or "",
                "message": message or "",
                "traceback": tb or "",
            })

    def list(
        self, *, level: str = "", keyword: str = "", limit: int = 200, since_id: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            items = list(self._dq)
        total = len(items)
        if level:
            lv = level.upper()
            items = [i for i in items if i["level"] == lv]
        if keyword:
            k = keyword.lower()
            items = [
                i for i in items
                if k in i["message"].lower() or k in i["source"].lower()
            ]
        if since_id:
            items = [i for i in items if i["id"] > since_id]
        items = items[-limit:][::-1]  # 最新在前
        return items, total

    def clear(self) -> None:
        with self._lock:
            self._dq.clear()


STORE = LogStore()


class _StoreHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            tb = ""
            if record.exc_info:
                tb = "".join(_tb.format_exception(*record.exc_info))
            STORE.add(record.levelname, record.name, record.getMessage(), tb)
        except Exception:
            pass


def install(level: int = logging.WARNING) -> None:
    """把缓冲处理器挂到 root logger,捕获库/应用的 WARNING+ 日志。"""
    root = logging.getLogger()
    if not any(isinstance(h, _StoreHandler) for h in root.handlers):
        h = _StoreHandler()
        h.setLevel(level)
        root.addHandler(h)
