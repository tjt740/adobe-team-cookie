from __future__ import annotations

from typing import Any

import requests
from sqlalchemy import select

from app.crud import adobe_account as adobe_crud
from app.crud import adobe_member as member_crud
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.services import adobe_admin, proxy_pool
from app.services.job_manager import Job


CLEANUP_MODES = {"all", "remote", "local"}


def normalize_cleanup_mode(mode: str | None) -> str:
    value = (mode or "all").strip().lower()
    return value if value in CLEANUP_MODES else "all"


def cleanup_mode_label(mode: str) -> str:
    return {
        "all": "清退所有子号",
        "remote": "删除 Adobe 远程所有子号",
        "local": "删除本地所有子号",
    }.get(mode, mode)


def _local_members(db, admin_id: int) -> list[AdobeMember]:
    return list(
        db.scalars(
            select(AdobeMember).where(
                AdobeMember.admin_id == admin_id,
                AdobeMember.is_admin == False,  # noqa: E712
            )
        )
    )


def _fetch_remote_members(
    account: AdobeAccount,
    proxy_raw: str,
    *,
    pages: int = 20,
) -> list[dict[str, Any]]:
    last_exc: Exception | None = None
    for _ in range(5):
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        try:
            rows = adobe_admin.fetch_members(
                token=account.admin_token,
                org_id=account.org_id,
                proxy_url=proxy_url,
                pages=pages,
            )
            proxy_pool.report_success(proxy_url)
            account_email = (account.email or "").strip().lower()
            return [
                r for r in rows
                if (r.get("email") or "").strip().lower() != account_email
            ]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            proxy_pool.report_failure(proxy_url, str(exc))
    raise RuntimeError(f"拉取远程成员失败:{last_exc}") from last_exc


def _remove_remote_member(
    account: AdobeAccount,
    item: dict[str, Any],
    proxy_raw: str,
) -> tuple[bool, str]:
    email = (item.get("email") or "").strip()
    member_id = (item.get("member_id") or "").strip()
    try:
        res = adobe_admin.remove_member(
            token=account.admin_token,
            org_id=account.org_id,
            member_id=member_id,
            email=email,
            proxy_url=proxy_pool.next_proxy(proxy_raw),
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]
    message = res.get("message") or ""
    ok = bool(res.get("ok")) or "未找到成员" in message
    return ok, message


def _batch_name(email: str) -> str:
    return (email or "").split("@", 1)[0].strip()


def _delete_provider_batch(
    *,
    base_url: str,
    api_key: str,
    batch: str,
    timeout: int,
) -> tuple[bool, str]:
    if not base_url or not api_key:
        return False, "未配置 BASE_URL 或 KEY"
    if not batch:
        return False, "批次名称为空"
    url = base_url.rstrip("/") + "/api/v1/providers/adobe/accounts/delete-batch"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"batch": batch},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return False, str(exc)[:300]
    text = (resp.text or "")[:500]
    if 200 <= resp.status_code < 300:
        return True, text or f"HTTP {resp.status_code}"
    return False, f"HTTP {resp.status_code}: {text}"


def cleanup_members_worker(job: Job) -> None:
    """清退母号子号任务。

    mode:
    - all: 先删除远程全部子号,成功后删除本地全部子号。
    - remote: 只删除 Adobe 远程组织里的全部子号。
    - local: 只删除本地 adobe_members 子号记录。
    """
    admin_ids = [int(x) for x in (job.meta.get("admin_ids") or [])]
    mode = normalize_cleanup_mode(str(job.meta.get("mode") or "all"))
    db = SessionLocal()
    try:
        settings = setting_crud.get_settings(db)
        proxy_raw = settings.proxy_url if settings.proxy_enabled else ""
        pool_api_base_url = (settings.pool_api_base_url or "").strip()
        pool_api_key = (settings.pool_api_key or "").strip()
        api_timeout = max(1, int(settings.request_timeout or 30))
        job.target = 0
        totals = {
            "admins": len(admin_ids),
            "remote_removed": 0,
            "remote_failed": 0,
            "local_removed": 0,
            "local_skipped": 0,
            "provider_batch_deleted": 0,
            "provider_batch_failed": 0,
        }
        teams: list[dict[str, Any]] = []
        for aid in admin_ids:
            account = adobe_crud.get(db, aid)
            teams.append({
                "admin_id": aid,
                "email": account.email if account else f"#{aid}",
                "target": 0,
                "success": 0,
                "fail": 0,
                "status": "pending",
                "message": "",
                "prefix": "",
            })
        job.set_extra("teams", teams)
        job.log(f"任务开始:{cleanup_mode_label(mode)},母号 {len(admin_ids)} 个")

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
                team["fail"] += 1
                team["target"] += 1
                job.target += 1
                job.bump(fail=1)
                job.log(f"{team['prefix']}母号不存在,已跳过")
                job.set_extra("teams", teams)
                continue

            remote_ok = True
            remote_removed = 0
            remote_failed = 0
            local_removed = 0
            provider_batch_ok = False

            if mode in {"all", "remote"}:
                if not (account.admin_token and account.org_id):
                    remote_ok = False
                    team["fail"] += 1
                    team["target"] += 1
                    job.target += 1
                    job.bump(fail=1)
                    job.log(f"{team['prefix']}缺少 admin_token/org_id,无法删除远程子号")
                else:
                    try:
                        remote_items = _fetch_remote_members(account, proxy_raw)
                    except Exception as exc:  # noqa: BLE001
                        remote_ok = False
                        remote_failed += 1
                        team["fail"] += 1
                        team["target"] += 1
                        job.target += 1
                        job.bump(fail=1)
                        job.log(f"{team['prefix']}拉取远程成员失败:{str(exc)[:200]}")
                        remote_items = []
                    team["target"] += len(remote_items)
                    job.target += len(remote_items)
                    job.log(f"{team['prefix']}远程子号 {len(remote_items)} 个,开始删除")
                    for item in remote_items:
                        if job.cancelled:
                            break
                        label = item.get("email") or item.get("member_id") or "-"
                        ok, message = _remove_remote_member(account, item, proxy_raw)
                        if ok:
                            remote_removed += 1
                            team["success"] += 1
                            job.bump(success=1)
                            if remote_removed % 10 == 0:
                                job.log(f"{team['prefix']}远程已删除 {remote_removed}/{len(remote_items)}")
                        else:
                            remote_ok = False
                            remote_failed += 1
                            team["fail"] += 1
                            job.bump(fail=1)
                            job.log(f"{team['prefix']}远程删除失败 {label}: {message[:160]}")
                    totals["remote_removed"] += remote_removed
                    totals["remote_failed"] += remote_failed

            should_delete_local = mode == "local" or (mode == "all" and remote_ok)
            if should_delete_local:
                rows = _local_members(db, admin_id)
                team["target"] += len(rows)
                job.target += len(rows)
                if rows:
                    job.log(f"{team['prefix']}开始删除本地子号 {len(rows)} 个")
                for row in rows:
                    db.delete(row)
                    local_removed += 1
                    team["success"] += 1
                    job.bump(success=1)
                account.member_count = 0
                db.commit()
                totals["local_removed"] += local_removed
            elif mode == "all":
                skipped = member_crud.count_by_admin(db, admin_id)
                totals["local_skipped"] += skipped
                if skipped:
                    job.log(f"{team['prefix']}远程未完全清退,跳过本地删除 {skipped} 个")

            if mode == "all" and remote_ok:
                batch = _batch_name(account.email)
                if pool_api_base_url and pool_api_key:
                    team["target"] += 1
                    job.target += 1
                    ok, message = _delete_provider_batch(
                        base_url=pool_api_base_url,
                        api_key=pool_api_key,
                        batch=batch,
                        timeout=api_timeout,
                    )
                    provider_batch_ok = ok
                    if ok:
                        totals["provider_batch_deleted"] += 1
                        team["success"] += 1
                        job.bump(success=1)
                        job.log(f"{team['prefix']}自有号池批次删除成功:{batch}")
                    else:
                        totals["provider_batch_failed"] += 1
                        team["fail"] += 1
                        job.bump(fail=1)
                        job.log(f"{team['prefix']}自有号池批次删除失败 {batch}: {message[:180]}")
                else:
                    job.log(f"{team['prefix']}未配置自有号池 BASE_URL/KEY,跳过批次删除")

            if remote_failed or (mode == "all" and pool_api_base_url and pool_api_key and not provider_batch_ok):
                team["status"] = "partial"
                team["message"] = (
                    f"远程删除成功 {remote_removed},失败 {remote_failed};"
                    f"本地删除 {local_removed}"
                )
                if mode == "all" and pool_api_base_url and pool_api_key and not provider_batch_ok:
                    team["message"] += ";自有号池批次删除失败"
            elif mode == "all" and not remote_ok:
                team["status"] = "error"
                team["message"] = "远程不可用,本地未删除"
            else:
                team["status"] = "done"
                team["message"] = f"远程删除 {remote_removed},本地删除 {local_removed}"
                if mode == "all" and pool_api_base_url and pool_api_key:
                    team["message"] += ",自有号池批次" + ("已删" if provider_batch_ok else "删除失败")
            job.log(f"{team['prefix']}{team['message']}")
            job.set_extra("teams", teams)

        totals["teams_done"] = sum(1 for t in teams if t["status"] == "done")
        totals["teams_partial"] = sum(1 for t in teams if t["status"] == "partial")
        totals["teams_error"] = sum(1 for t in teams if t["status"] == "error")
        job.result = totals
        if (
            totals["teams_error"]
            or totals["teams_partial"]
            or totals["remote_failed"]
            or totals["provider_batch_failed"]
        ):
            job.status = "error" if totals["teams_done"] == 0 else "done"
        job.log(
            "任务完成:"
            f"远程删除 {totals['remote_removed']},远程失败 {totals['remote_failed']},"
            f"本地删除 {totals['local_removed']},"
            f"自有号池批次删除 {totals['provider_batch_deleted']},"
            f"批次失败 {totals['provider_batch_failed']}"
        )
    finally:
        db.close()
