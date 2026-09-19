from __future__ import annotations

from typing import Any

import requests
from sqlalchemy import select

from app.crud import adobe_account as adobe_crud
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.models.adobe_member import AdobeMember
from app.services.job_manager import Job


def batch_name(email: str) -> str:
    return (email or "").split("@", 1)[0].strip()


def post_import_batch(
    *,
    base_url: str,
    api_key: str,
    batch: str,
    cookies: list[dict[str, str]],
    timeout: int,
) -> tuple[bool, str]:
    if not base_url or not api_key:
        return False, "未配置 BASE_URL 或 KEY"
    if not batch:
        return False, "批次名称为空"
    if not cookies:
        return False, "cookies 为空"
    url = base_url.rstrip("/") + "/api/v1/providers/adobe/accounts/import-batch"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"batch": batch, "cookies": cookies},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return False, str(exc)[:300]
    text = (resp.text or "")[:500]
    if 200 <= resp.status_code < 300:
        return True, text or f"HTTP {resp.status_code}"
    return False, f"HTTP {resp.status_code}: {text}"


def _qualified_members(db, admin_id: int) -> list[AdobeMember]:
    return list(
        db.scalars(
            select(AdobeMember).where(
                AdobeMember.admin_id == admin_id,
                AdobeMember.is_admin == False,  # noqa: E712
                AdobeMember.credits.is_not(None),
                AdobeMember.credits > 20,
            )
        )
    )


def import_pool_batch_worker(job: Job) -> None:
    """把本地积分大于 20 的子号 cookie 批量同步到自有号池。"""
    admin_ids = [int(x) for x in (job.meta.get("admin_ids") or [])]
    db = SessionLocal()
    try:
        settings = setting_crud.get_settings(db)
        base_url = (settings.pool_api_base_url or "").strip()
        api_key = (settings.pool_api_key or "").strip()
        timeout = max(1, int(settings.request_timeout or 30))
        totals = {
            "admins": len(admin_ids),
            "batches_imported": 0,
            "batches_failed": 0,
            "cookies_sent": 0,
            "qualified_members": 0,
            "skipped_no_cookie": 0,
            "skipped_empty": 0,
        }
        teams: list[dict[str, Any]] = []
        for aid in admin_ids:
            account = adobe_crud.get(db, aid)
            teams.append({
                "admin_id": aid,
                "email": account.email if account else f"#{aid}",
                "target": 1,
                "success": 0,
                "fail": 0,
                "status": "pending",
                "message": "",
                "prefix": "",
            })
        job.target = len(admin_ids)
        job.set_extra("teams", teams)
        job.log(f"任务开始:批量更新号池,母号 {len(admin_ids)} 个")

        if not base_url or not api_key:
            job.status = "error"
            job.error = "未配置自有号池 BASE_URL 或 KEY"
            job.log(job.error)
            return

        for idx, admin_id in enumerate(admin_ids, start=1):
            if job.cancelled:
                job.log("任务已取消")
                break
            team = teams[idx - 1]
            team["prefix"] = f"[{idx}/{len(admin_ids)} {team['email']}] "
            team["status"] = "running"
            job.set_extra("teams", teams)

            account = adobe_crud.get(db, admin_id)
            if not account:
                team["status"] = "error"
                team["message"] = "母号不存在"
                team["fail"] = 1
                job.bump(fail=1)
                job.log(f"{team['prefix']}母号不存在,已跳过")
                continue

            rows = _qualified_members(db, admin_id)
            totals["qualified_members"] += len(rows)
            cookies = [
                {"cookie": (row.cookie or "").strip()}
                for row in rows
                if (row.cookie or "").strip()
            ]
            skipped_no_cookie = len(rows) - len(cookies)
            totals["skipped_no_cookie"] += skipped_no_cookie
            batch = batch_name(account.email)
            job.log(
                f"{team['prefix']}本地积分 > 20 子号 {len(rows)} 个,"
                f"可同步 cookie {len(cookies)} 个"
            )

            if not rows:
                totals["skipped_empty"] += 1
                team["status"] = "done"
                team["success"] = 1
                team["message"] = "没有积分 > 20 的本地子号,跳过"
                job.bump(success=1)
                job.set_extra("teams", teams)
                continue
            if not cookies:
                team["status"] = "partial"
                team["fail"] = 1
                team["message"] = f"积分 > 20 子号 {len(rows)} 个,但都没有 cookie"
                job.bump(fail=1)
                job.log(f"{team['prefix']}{team['message']}")
                job.set_extra("teams", teams)
                continue

            ok, message = post_import_batch(
                base_url=base_url,
                api_key=api_key,
                batch=batch,
                cookies=cookies,
                timeout=timeout,
            )
            if ok:
                totals["batches_imported"] += 1
                totals["cookies_sent"] += len(cookies)
                team["status"] = "done"
                team["success"] = 1
                team["message"] = f"已同步 batch={batch},cookies={len(cookies)}"
                job.bump(success=1)
                job.log(f"{team['prefix']}{team['message']}")
            else:
                totals["batches_failed"] += 1
                team["status"] = "error"
                team["fail"] = 1
                team["message"] = f"同步失败:{message[:180]}"
                job.bump(fail=1)
                job.log(f"{team['prefix']}{team['message']}")
            job.set_extra("teams", teams)

        totals["teams_done"] = sum(1 for t in teams if t["status"] == "done")
        totals["teams_error"] = sum(1 for t in teams if t["status"] == "error")
        totals["teams_partial"] = sum(1 for t in teams if t["status"] == "partial")
        job.result = totals
        if totals["teams_error"] or totals["teams_partial"]:
            job.status = "error" if totals["teams_done"] == 0 else "done"
        job.log(
            "任务完成:"
            f"同步批次 {totals['batches_imported']},失败 {totals['batches_failed']},"
            f"发送 cookie {totals['cookies_sent']},无 cookie 跳过 {totals['skipped_no_cookie']}"
        )
    finally:
        db.close()
