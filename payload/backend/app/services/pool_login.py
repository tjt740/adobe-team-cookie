"""号池批量登录:对已注册子号重新执行协议登录,刷新 access_token / cookie / 额度。

复用 firefly.register_account(纯 API 协议登录:Graph 收验证码 → Adobe IMS 换 token),
每个子号用自己库里存的 refresh_token + client_id 收码,互不影响。并发数取「设置」。
"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.crud import adobe_account as account_crud
from app.crud import adobe_member as member_crud
from app.crud import email as email_crud
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.services import firefly, firefly_ios, proxy_pool
from app.services.job_manager import Job


def _login_one(payload: dict, proxy_raw: str, job: Job) -> bool:
    email = payload["email"]
    mid = payload["id"]
    if not ((payload["refresh_token"] and payload["client_id"]) or payload.get("mail_url")):
        job.bump(fail=1)
        job.log(f"✗ [{email}] 缺少 Refresh Token / Client ID 或取信配置,跳过")
        _save(mid, status="failed", message="缺少子号 Refresh Token / Client ID 或取信配置")
        return False

    job.log(f"[{email}] FF-iOS 协议登录中(验证码登录→换设备 token,免密码)…")
    try:
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        rec = firefly_ios.login_pool_ff_ios(
            email=email,
            refresh_token=payload["refresh_token"],
            client_id=payload["client_id"],
            mail_url=payload.get("mail_url", ""),
            device_id=payload.get("device_id", ""),
            proxy_url=proxy_url,
            otp_timeout=180,
            use_proxy_for_mail=False,
            log=lambda m: job.log(f"[{email}] {m}"),
        )
    except Exception as e:  # noqa: BLE001
        job.bump(fail=1)
        detail = f"{type(e).__name__}: {str(e)[:200]}"
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__, limit=6))
        job.log(f"✗ [{email}] 登录失败:{detail}")
        job.log(f"[{email}] 异常堆栈摘要:\n{tb[-1200:]}")
        _save(mid, status="failed", message=f"登录失败:{str(e)[:200]}")
        return False

    access_token = rec.get("access_token") or ""
    proxy_url = proxy_pool.next_proxy(proxy_raw)
    credits = (
        firefly.fetch_credits(
            access_token,
            proxy_url=proxy_url,
            log=lambda m: job.log(f"[{email}] {m}"),
        )
        if access_token
        else None
    )
    _save(
        mid,
        status="registered",
        message="已获取 FF-iOS 受信任 token",
        extra={
            "registered": True,
            "display_name": rec.get("display_name") or "",
            "access_token": access_token,
            "device_token": rec.get("device_token") or "",
            "device_id": rec.get("device_id") or "",
            "credits": credits,
            "expires_at": rec.get("expires_at"),
            "refresh_token": rec.get("rotated_refresh_token") or payload["refresh_token"],
        },
    )
    job.bump(success=1)
    job.log(f"✓ [{email}] 登录成功,已获取 FF-iOS token(额度 {credits})")
    return True


def _save(member_id: int, *, status: str, message: str, extra: dict | None = None) -> None:
    """单独开一个 Session 落库(并发线程各用各的连接)。"""
    db = SessionLocal()
    try:
        row = member_crud.get(db, member_id)
        if not row:
            return
        row.status = status
        row.message = message
        row.updated_at = datetime.now(timezone.utc)
        for k, v in (extra or {}).items():
            setattr(row, k, v)
        # 母号镜像的 refresh_token 由 adobe_accounts 作为权威来源保存。
        # Microsoft refresh token 轮换后,只写成员行会在下一轮解析凭据时丢失新 token。
        if row.is_admin and row.admin_id:
            rotated = (extra or {}).get("refresh_token") or ""
            if rotated:
                account = account_crud.get(db, row.admin_id)
                if account and account.refresh_token != rotated:
                    account.refresh_token = rotated
        db.commit()
    finally:
        db.close()


def _resolve_creds(db, member) -> tuple[str, str, str]:
    """解析收码凭据。

    母号镜像以 adobe_accounts 为权威来源,因为母号登录可能轮换
    refresh_token;普通子号才优先使用成员行并回退邮箱池。
    """
    if member.is_admin and member.admin_id:
        account = account_crud.get(db, member.admin_id)
        if account:
            rt = account.refresh_token or ""
            cid = account.client_id or ""
            mail_url = account.mail_url or ""
            if (
                member.refresh_token != rt
                or member.client_id != cid
                or member.mail_url != mail_url
            ):
                member.refresh_token = rt
                member.client_id = cid
                member.mail_url = mail_url
                db.commit()
            return rt, cid, mail_url

    rt = member.refresh_token or ""
    cid = member.client_id or ""
    mail_url = member.mail_url or ""
    if not (rt and cid):
        pool_email = email_crud.get_by_email(db, member.email)
        if pool_email:
            rt = rt or (pool_email.refresh_token or "")
            cid = cid or (pool_email.client_id or "")
            mail_url = mail_url or (pool_email.mail_url or "")
            if rt and cid and not (member.refresh_token and member.client_id):
                member.refresh_token = rt
                member.client_id = cid
                member.mail_url = mail_url
                db.commit()
    return rt, cid, mail_url


def _build_payloads(db, member_ids: list[int]) -> list[dict]:
    members = member_crud.get_many(db, member_ids)
    payloads = []
    for m in members:
        rt, cid, mail_url = _resolve_creds(db, m)
        payloads.append(
            {
                "id": m.id,
                "email": m.email,
                "refresh_token": rt,
                "client_id": cid,
                "mail_url": mail_url,
                "device_id": m.device_id or "",
            }
        )
    db.commit()
    return payloads


def _ids_without_token(member_ids: list[int]) -> list[int]:
    db = SessionLocal()
    try:
        members = member_crud.get_many(db, member_ids)
        return [m.id for m in members if not (m.access_token or "").strip()]
    finally:
        db.close()


def refresh_one_sync(member_id: int, log=None) -> dict:
    """对单个子号同步刷新 AT,刷新后查询额度。返回 {success,message,credits,expires_at}。

    优先用 device_token 免验证码刷新(快);无 device_token 或刷新失败时回退整登。
    """
    lf = log if callable(log) else (lambda _m: None)
    db = SessionLocal()
    try:
        m = member_crud.get(db, member_id)
        if not m:
            return {"success": False, "message": "条目不存在", "credits": None, "expires_at": None}
        email = m.email
        settings = setting_crud.get_settings(db)
        proxy_raw = settings.proxy_url if settings.proxy_enabled else ""
        device_token = m.device_token or ""
        device_id = m.device_id or ""
        rt, cid, mail_url = _resolve_creds(db, m)
    finally:
        db.close()

    # 快路径:device_token 免验证码刷新 access_token
    if device_token and device_id:
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        lf(f"[{email}] 用 device_token 刷新 AT(免验证码)…")
        try:
            rec = firefly_ios.refresh_with_device_token(
                device_token=device_token, device_id=device_id,
                proxy_url=proxy_url, log=lambda mm: lf(f"[{email}] {mm}"),
            )
            token = rec.get("access_token") or ""
            credits = (
                firefly.fetch_credits(token, proxy_url=proxy_url, log=lf)
                if token
                else None
            )
            _save(
                member_id, status="registered", message="device_token 已刷新 AT",
                extra={
                    "registered": True,
                    "access_token": token,
                    "credits": credits,
                    "expires_at": rec.get("expires_at"),
                    "device_token": rec.get("device_token") or device_token,
                },
            )
            lf(f"[{email}] ✓ device_token 刷新成功,额度 {credits}")
            return {"success": True, "message": "device_token 已刷新 AT 并查询额度",
                    "credits": credits, "expires_at": rec.get("expires_at")}
        except Exception as e:  # noqa: BLE001
            lf(f"[{email}] device_token 刷新失败({str(e)[:120]}),回退整登")

    if not ((rt and cid) or mail_url):
        _save(member_id, status="failed", message="缺少子号 Refresh Token / Client ID 或取信配置")
        return {"success": False, "message": "缺少子号 Refresh Token / Client ID 或取信配置",
                "credits": None, "expires_at": None}

    proxy_url = proxy_pool.next_proxy(proxy_raw)
    lf(f"[{email}] FF-iOS 协议登录刷新(验证码登录→换设备 token)…")
    try:
        rec = firefly_ios.login_pool_ff_ios(
            email=email, refresh_token=rt, client_id=cid,
            mail_url=mail_url, device_id=device_id, proxy_url=proxy_url, otp_timeout=180,
            use_proxy_for_mail=False,
            log=lambda mm: lf(f"[{email}] {mm}"),
        )
    except Exception as e:  # noqa: BLE001
        _save(member_id, status="failed", message=f"刷新失败:{str(e)[:200]}")
        return {"success": False, "message": f"刷新失败:{str(e)[:200]}",
                "credits": None, "expires_at": None}

    token = rec.get("access_token") or ""
    credits = None
    if token:
        lf(f"[{email}] 登录成功,查询额度 …")
        q = firefly.fetch_credits(token, proxy_url=proxy_url, log=lf)
        if q is not None and q >= 0:
            credits = q
    expires_at = rec.get("expires_at")
    _save(
        member_id, status="registered", message="已获取 FF-iOS 受信任 token",
        extra={
            "registered": True,
            "display_name": rec.get("display_name") or "",
            "access_token": token,
            "device_token": rec.get("device_token") or "",
            "device_id": rec.get("device_id") or "",
            "credits": credits,
            "expires_at": expires_at,
            "refresh_token": rec.get("rotated_refresh_token") or rt,
        },
    )
    lf(f"[{email}] ✓ 已获取 FF-iOS token,额度 {credits}")
    return {"success": True, "message": "已获取 FF-iOS 受信任 token 并查询额度",
            "credits": credits, "expires_at": expires_at}


def _run_round(payloads: list[dict], proxy_raw: str, concurrency: int, job: Job) -> None:
    def _do(p: dict) -> bool:
        if job.cancelled:
            return False
        return _login_one(p, proxy_raw, job)

    with ThreadPoolExecutor(max_workers=min(concurrency, len(payloads))) as ex:
        for _ in ex.map(_do, payloads):
            pass


def pool_login_batch_worker(job: Job) -> None:
    all_member_ids = [int(x) for x in (job.meta.get("member_ids") or [])]
    auto_retry = bool(job.meta.get("auto_retry", True))
    max_retries = max(0, int(job.meta.get("max_retries") if job.meta.get("max_retries") is not None else 2))

    db = SessionLocal()
    try:
        settings = setting_crud.get_settings(db)
        proxy_raw = settings.proxy_url if settings.proxy_enabled else ""
        concurrency = max(1, int(settings.concurrency or 1))
        n_proxy = proxy_pool.proxy_count(proxy_raw)
        if n_proxy:
            job.log(f"已配置 {n_proxy} 个代理,登录时按行轮换出口")
    finally:
        db.close()

    job.target = len(all_member_ids)
    if not all_member_ids:
        job.log("没有可登录的子号")
        return

    retry_hint = f",失败自动重试最多 {max_retries} 轮" if auto_retry and max_retries else ""
    job.log(
        f"开始批量协议登录,共 {len(all_member_ids)} 个,"
        f"并发 {min(concurrency, len(all_member_ids))}{retry_hint}"
    )

    pending_ids = list(all_member_ids)
    round_num = 0
    max_rounds = 1 + (max_retries if auto_retry else 0)

    while pending_ids and round_num < max_rounds:
        round_num += 1
        if round_num > 1:
            job.log(f"=== 第 {round_num} 轮重试,{len(pending_ids)} 个仍无 token,30s 后开始 ===")
            time.sleep(30)

        db = SessionLocal()
        try:
            payloads = _build_payloads(db, pending_ids)
        finally:
            db.close()

        if not payloads:
            break

        if round_num == 1:
            job.log(f"首轮 {len(payloads)} 个")
        _run_round(payloads, proxy_raw, concurrency, job)

        if job.cancelled:
            job.log("任务已取消")
            break

        pending_ids = _ids_without_token(all_member_ids)
        if not pending_ids:
            job.log("全部账号已拿到 token")
            break

    still = len(_ids_without_token(all_member_ids))
    job.result = {
        "total": len(all_member_ids),
        "success": job.success,
        "fail": job.fail,
        "still_no_token": still,
    }
    job.log(f"=== 完成:成功 {job.success} / 失败 {job.fail} / 仍无 token {still} ===")
