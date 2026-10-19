"""Display log timestamps in Beijing time regardless of the host timezone."""

from datetime import datetime, timedelta, timezone
import time


BEIJING_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def beijing_time(timestamp: float | None = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp, BEIJING_TIMEZONE).strftime(fmt)
