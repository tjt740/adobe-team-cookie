"""后台任务管理器。

任务运行态保存在内存,同时把任务摘要和日志写入 SQLite,便于服务重启后
继续查看历史日志。运行中的任务仍由单实例进程内线程执行。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Optional

from sqlalchemy import text

from app.db.session import engine
from app.services.job_provenance import capture_meta, describe


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


ACTIVE_STATUSES = {"running", "pausing", "paused", "cancelling"}


class JobCancelled(BaseException):
    """Cooperative termination, not a login/network failure to retry."""


class Job:
    def __init__(
        self,
        job_id: int,
        job_type: str,
        meta: dict[str, Any],
        *,
        persist_cb: Callable[["Job"], None] | None = None,
    ):
        self.id = job_id
        self.type = job_type
        self.meta = meta
        self.status = "running"  # running / done / error
        self.created_at = int(time.time())
        self.finished_at: int | None = None
        self.logs: list[str] = []
        self.target = int(meta.get("target") or 0)
        self.success = 0
        self.fail = 0
        self.result: Any = None
        self.error = ""
        self.extra: dict[str, Any] = {}
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._persist_lock = threading.Lock()
        self._pause_requested = False
        self._active_items = 0
        self._persist_cb = persist_cb

    # ---- 供 worker 调用 ----
    def log(self, msg: str) -> None:
        self.check_cancelled()
        with self._lock:
            self.logs.append(f"{time.strftime('%H:%M:%S')} {msg}")
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]
        self.persist()

    def bump(self, *, success: int = 0, fail: int = 0) -> None:
        with self._lock:
            self.success += success
            self.fail += fail
        self.persist()

    def set_extra(self, key: str, value: Any) -> None:
        with self._lock:
            self.extra[key] = value
        self.persist()

    def record_item(self, item_id: int, **fields: Any) -> None:
        """Keep per-account results under the same lock as counters during concurrency."""
        with self._lock:
            items = [dict(item) for item in self.extra.get('items', [])]
            item = next((item for item in items if item.get('id') == item_id), None)
            if item is None:
                item = {'id': item_id}
                items.append(item)
            item.update(fields)
            self.extra['items'] = items
        self.persist()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelled()

    def begin_item(self) -> bool:
        with self._condition:
            while self._pause_requested and not self.cancelled:
                self._condition.wait()
            if self.cancelled:
                return False
            self._active_items += 1
            return True

    def end_item(self) -> None:
        with self._condition:
            self._active_items -= 1
            if self._pause_requested and not self._active_items and not self.cancelled:
                self.status = "paused"
                self.logs.append(f"{time.strftime('%H:%M:%S')} 已暂停，等待继续或终止")
        self.persist()

    def pause(self) -> bool:
        with self._condition:
            if self.type != "external_login" or self.status != "running":
                return False
            self._pause_requested = True
            self.status = "pausing" if self._active_items else "paused"
            self.logs.append(f"{time.strftime('%H:%M:%S')} 已请求暂停，当前账号完成后暂停后续账号")
        self.persist()
        return True

    def resume(self) -> bool:
        with self._condition:
            if self.status not in {"paused", "pausing"}:
                return False
            self._pause_requested = False
            self.status = "running"
            self.logs.append(f"{time.strftime('%H:%M:%S')} 已继续任务")
            self._condition.notify_all()
        self.persist()
        return True

    def cancel(self) -> bool:
        with self._condition:
            if self.status not in ACTIVE_STATUSES or self.cancelled:
                return False
            self._cancel.set()
            self.status = "cancelling"
            self.logs.append(f"{time.strftime('%H:%M:%S')} 已请求终止，等待当前请求退出")
            self._condition.notify_all()
        self.persist()
        return True

    def clear_logs(self) -> None:
        with self._lock:
            self.logs.clear()
        self.persist()

    def persist(self) -> None:
        if self._persist_cb:
            with self._persist_lock:
                self._persist_cb(self)

    def to_dict(self, *, log_offset: int = 0) -> dict[str, Any]:
        with self._lock:
            logs = self.logs[log_offset:] if log_offset > 0 else self.logs
            return {
                "id": self.id,
                "type": self.type,
                "operator": self.meta.get("operator") or "",
                "status": self.status,
                "target": self.target,
                "success": self.success,
                "fail": self.fail,
                "result": self.result,
                "error": self.error,
                "created_at": self.created_at,
                "finished_at": self.finished_at,
                "log_total": len(self.logs),
                "logs": logs,
                "meta": self.meta,
                "extra": dict(self.extra),
                "trace": describe(self.type, self.meta, self.extra),
            }

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "Job":
        job = cls(
            int(row["id"]),
            str(row["type"]),
            _json_loads(row.get("meta_json"), {}),
            persist_cb=None,
        )
        job.status = str(row.get("status") or "")
        job.target = int(row.get("target") or 0)
        job.success = int(row.get("success") or 0)
        job.fail = int(row.get("fail") or 0)
        job.result = _json_loads(row.get("result_json"), None)
        job.error = str(row.get("error") or "")
        job.created_at = int(row.get("created_at") or 0)
        finished = row.get("finished_at")
        job.finished_at = int(finished) if finished else None
        job.logs = list(_json_loads(row.get("logs_json"), []))
        job.extra = dict(_json_loads(row.get("extra_json"), {}))
        return job


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[int, Job] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._storage_ready = False

    def _ensure_storage(self) -> None:
        if self._storage_ready:
            return
        with self._lock:
            if self._storage_ready:
                return
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS job_records (
                        id INTEGER PRIMARY KEY,
                        type VARCHAR(80) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        target INTEGER DEFAULT 0,
                        success INTEGER DEFAULT 0,
                        fail INTEGER DEFAULT 0,
                        result_json TEXT,
                        error TEXT DEFAULT '',
                        created_at INTEGER,
                        finished_at INTEGER,
                        meta_json TEXT,
                        extra_json TEXT,
                        logs_json TEXT,
                        deleted INTEGER DEFAULT 0
                    )
                """))
                max_id = conn.execute(
                    text("SELECT max(id) FROM job_records")
                ).scalar()
                self._counter = max(self._counter, int(max_id or 0))
            self._storage_ready = True

    def _persist_job(self, job: Job) -> None:
        self._ensure_storage()
        data = job.to_dict()
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO job_records (
                        id, type, status, target, success, fail, result_json,
                        error, created_at, finished_at, meta_json, extra_json,
                        logs_json, deleted
                    )
                    VALUES (
                        :id, :type, :status, :target, :success, :fail,
                        :result_json, :error, :created_at, :finished_at,
                        :meta_json, :extra_json, :logs_json, 0
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        type=excluded.type,
                        status=excluded.status,
                        target=excluded.target,
                        success=excluded.success,
                        fail=excluded.fail,
                        result_json=excluded.result_json,
                        error=excluded.error,
                        created_at=excluded.created_at,
                        finished_at=excluded.finished_at,
                        meta_json=excluded.meta_json,
                        extra_json=excluded.extra_json,
                        logs_json=excluded.logs_json,
                        deleted=0
                """),
                {
                    "id": data["id"],
                    "type": data["type"],
                    "status": data["status"],
                    "target": data["target"],
                    "success": data["success"],
                    "fail": data["fail"],
                    "result_json": _json_dumps(data["result"]),
                    "error": data["error"],
                    "created_at": data["created_at"],
                    "finished_at": data["finished_at"],
                    "meta_json": _json_dumps(data["meta"]),
                    "extra_json": _json_dumps(data["extra"]),
                    "logs_json": _json_dumps(data["logs"]),
                },
            )

    def _get_record(self, job_id: int) -> Optional[Job]:
        self._ensure_storage()
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM job_records WHERE id=:id AND deleted=0"),
                {"id": job_id},
            ).mappings().first()
        return Job.from_record(dict(row)) if row else None

    def start(
        self, job_type: str, worker: Callable[[Job], None], *, meta: dict | None = None
    ) -> Job:
        meta = capture_meta(job_type, meta)
        self._ensure_storage()
        with self._lock:
            self._counter += 1
            job = Job(self._counter, job_type, meta or {}, persist_cb=self._persist_job)
            self._jobs[job.id] = job
            # 防止无限增长:仅保留最近 50 个任务
            if len(self._jobs) > 50:
                for k in sorted(self._jobs)[:-50]:
                    old = self._jobs.get(k)
                    if old and old.status not in ACTIVE_STATUSES:
                        self._jobs.pop(k, None)
            job.persist()

        def _runner() -> None:
            try:
                worker(job)
                with job._lock:
                    if job.status in ACTIVE_STATUSES and not job.cancelled:
                        job.status = "done"
            except JobCancelled:
                pass
            except Exception as e:
                with job._lock:
                    if not job.cancelled:
                        job.status = "error"
                        job.error = str(e)[:500]
                        job.logs.append(f"{time.strftime('%H:%M:%S')} 任务异常:{e}")
            finally:
                with job._condition:
                    if job.cancelled:
                        job.status = "cancelled"
                        job.logs.append(f"{time.strftime('%H:%M:%S')} 任务已终止，已完成的结果和日志已保留")
                    job.finished_at = int(time.time())
                    job._condition.notify_all()
                job.persist()

        threading.Thread(target=_runner, name=f"job-{job.id}", daemon=True).start()
        return job

    def get(self, job_id: int) -> Optional[Job]:
        return self._jobs.get(job_id) or self._get_record(job_id)

    def recover_interrupted(self, job_type: str) -> None:
        """Startup only: make interrupted tasks retryable without replaying writes."""
        self._ensure_storage()
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE job_records SET status='error', finished_at=:now,
                    error='服务已重启，任务中断；已保存的数据保留，请重新勾选重试'
                WHERE type=:job_type AND deleted=0
                    AND status IN ('running','pausing','paused','cancelling')
            """), {'now': int(time.time()), 'job_type': job_type})

    def list_recent(self, limit: int = 30) -> list[Job]:
        self._ensure_storage()
        with self._lock:
            running_or_memory = {jid: job for jid, job in self._jobs.items()}
        with engine.begin() as conn:
            rows = list(conn.execute(
                text("""
                    SELECT * FROM job_records
                    WHERE deleted=0
                    ORDER BY id DESC
                    LIMIT :limit
                """),
                {"limit": max(1, int(limit))},
            ).mappings())
        jobs: list[Job] = []
        seen: set[int] = set()
        for row in rows:
            jid = int(row["id"])
            seen.add(jid)
            jobs.append(running_or_memory.get(jid) or Job.from_record(dict(row)))
        for jid, job in running_or_memory.items():
            if jid not in seen:
                jobs.append(job)
        jobs.sort(key=lambda j: j.id, reverse=True)
        return jobs[:limit]

    def external_member_jobs(self, member_ids: list[int], *, limit: int = 1) -> dict[int, list[dict]]:
        """按账号查持久化历史,不受全局最近 30 条限制;列表不加载日志原文。"""
        if not member_ids:
            return {}
        self._ensure_storage()
        with engine.begin() as conn:
            rows = conn.execute(text("""
                WITH ranked AS (
                    SELECT j.id, j.type, j.status, j.target, j.success, j.fail,
                           j.error, j.created_at, j.finished_at,
                           json_extract(j.meta_json, '$.operator') AS operator,
                           json_array_length(j.logs_json) AS log_total,
                           CAST(m.value AS INTEGER) AS member_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY m.value ORDER BY j.id DESC
                           ) AS position
                    FROM job_records AS j, json_each(j.meta_json, '$.member_ids') AS m
                    JOIN external_members AS e ON e.id=m.value
                    WHERE j.deleted=0 AND j.type='external_login'
                      AND m.value IN (SELECT value FROM json_each(:member_ids))
                      AND j.created_at >= CAST(strftime('%s', e.created_at) AS INTEGER)
                      AND (json_type(j.meta_json, '$.member_emails') IS NULL
                           OR json_extract(j.meta_json, '$.member_emails."' || e.id || '"')=e.email)
                )
                SELECT * FROM ranked WHERE position <= :limit ORDER BY id DESC
            """), {"member_ids": _json_dumps(list(set(member_ids))), "limit": max(1, min(100, limit))}).mappings().all()
        out: dict[int, list[dict]] = {}
        for row in rows:
            data = Job.from_record(dict(row)).to_dict()
            data["operator"] = row["operator"] or ""
            data["log_total"] = int(row["log_total"] or 0)
            # Summary responses have no credentials, metadata or log bodies.
            data.pop("meta", None)
            out.setdefault(int(row["member_id"]), []).append(data)
        return out

    def find_active(self, job_type: str, admin_id: int) -> Optional[Job]:
        for job in self._jobs.values():
            if (
                job.type == job_type
                and job.status in ACTIVE_STATUSES
                and job.meta.get("admin_id") == admin_id
            ):
                return job
        return None

    def clear_logs(self, job_id: int) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.clear_logs()
            return True
        self._ensure_storage()
        with engine.begin() as conn:
            res = conn.execute(
                text("UPDATE job_records SET logs_json='[]' WHERE id=:id AND deleted=0"),
                {"id": job_id},
            )
        return bool(res.rowcount)

    def cancel(self, job_id: int) -> tuple[bool, str]:
        job = self._jobs.get(job_id)
        if not job:
            rec = self._get_record(job_id)
            if not rec:
                return False, "任务不存在"
            if rec.status in ACTIVE_STATUSES:
                rec.status = "cancelled"
                rec.finished_at = int(time.time())
                rec.logs.append(f"{time.strftime('%H:%M:%S')} 服务重启后标记为已停止")
                rec._persist_cb = self._persist_job
                rec.persist()
                return True, "任务已标记为停止"
            return False, "任务不在运行中"
        if not job.cancel():
            return False, "任务已结束或正在终止"
        return True, "已请求终止任务，等待当前请求退出"

    def pause(self, job_id: int) -> tuple[bool, str]:
        job = self._jobs.get(job_id)
        if not job:
            return False, "任务不存在或服务已重启，无法暂停历史任务"
        return (True, "已请求暂停，当前账号完成后暂停后续账号") if job.pause() else (False, "仅运行中的外部子号登录任务支持暂停")

    def resume(self, job_id: int) -> tuple[bool, str]:
        job = self._jobs.get(job_id)
        if not job:
            return False, "服务已重启，无法继续历史任务，请终止后重新提交"
        return (True, "已继续任务") if job.resume() else (False, "任务不在暂停状态")

    def delete_many(self, job_ids: list[int]) -> tuple[int, list[int]]:
        """删除任务。进行中的任务会跳过并返回其 ID。"""
        deleted = 0
        deleted_ids: set[int] = set()
        skipped_running: list[int] = []
        with self._lock:
            for jid in job_ids:
                job = self._jobs.get(jid)
                if not job:
                    continue
                if job.status in ACTIVE_STATUSES:
                    skipped_running.append(jid)
                    continue
                self._jobs.pop(jid, None)
                deleted += 1
                deleted_ids.add(jid)
        self._ensure_storage()
        with engine.begin() as conn:
            for jid in job_ids:
                if jid in skipped_running:
                    continue
                row = conn.execute(
                    text("SELECT status FROM job_records WHERE id=:id AND deleted=0"),
                    {"id": jid},
                ).first()
                if not row:
                    continue
                if str(row[0]) in ACTIVE_STATUSES:
                    skipped_running.append(jid)
                    continue
                res = conn.execute(
                    text("UPDATE job_records SET deleted=1 WHERE id=:id"),
                    {"id": jid},
                )
                if res.rowcount and jid not in deleted_ids:
                    deleted += 1
                    deleted_ids.add(jid)
        return deleted, skipped_running


JOBS = JobManager()
