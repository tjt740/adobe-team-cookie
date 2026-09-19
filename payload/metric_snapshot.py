"""每 15 分钟采集一次核心指标写入 metric_history(adobeteam-snapshot.timer 调用)。"""
import os
import sys

sys.path.insert(0, "/opt/adobeteam/backend")
os.chdir("/opt/adobeteam/backend")

from app.api.routes.dashboard import snapshot_metrics
from app.db.session import SessionLocal

d = SessionLocal()
try:
    row = snapshot_metrics(d)
    print("snapshot OK:", row)
finally:
    d.close()
