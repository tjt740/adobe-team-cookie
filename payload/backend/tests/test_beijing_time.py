import os
import time

import pytest

from app.core.timezone import beijing_time
from app.services.job_manager import Job
from app.services.log_store import LogStore


@pytest.mark.parametrize("host_timezone", ["UTC", "America/Los_Angeles", "Asia/Shanghai"])
def test_logs_use_beijing_time_across_date_boundary(monkeypatch, host_timezone):
    original = os.environ.get("TZ")
    # 2026-10-17 16:02:18 UTC is the next day in Beijing.
    timestamp = 1792252938.25
    monkeypatch.setenv("TZ", host_timezone)
    time.tzset()
    monkeypatch.setattr(time, "time", lambda: timestamp)
    try:
        assert beijing_time(0) == "1970-01-01 08:00:00"
        store = LogStore()
        store.add("info", "test", "服务已启动")
        rows, total = store.list()
        assert total == 1
        assert rows[0]["time"] == "2026-10-18 00:02:18"
        assert rows[0]["ts"] == timestamp

        job = Job(1, "external_login", {})
        job.log("开始处理")
        assert job.created_at == int(timestamp)
        assert job.pause()
        assert job.resume()
        assert job.cancel()
        assert all(line.startswith("00:02:18 ") for line in job.logs)
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()
