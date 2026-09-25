from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import capture_job_request, get_current_user
from app.crud import adobe_account as crud
from app.crud import adobe_member as member_crud
from app.crud import email as email_crud
from app.crud import setting as setting_crud
from app.db.session import get_db
from app.schemas.adobe_account import (
    AdminActionResult,
    AdobeAccountCreate,
    AdobeAccountOut,
    AdobeAccountUpdate,
    BatchAdminIdsRequest,
    BatchBuildTeamRequest,
    BatchGrantRequest,
    BatchGrantResult,
    BuildTeamRequest,
    CleanupMembersRequest,
    GrantItemResult,
    JobStatusOut,
    MemberOut,
    TestEmailResult,
)
from app.schemas.common import (
    BatchIds,
    BatchImportRequest,
    BatchImportResult,
    MessageResult,
    Page,
)
from app.services import (
    adobe_admin,
    firefly,
    member_cleanup,
    pool_login,
    provider_pool_sync,
    proxy_pool,
    remote_member_cleanup,
    team_builder,
)
from app.services.job_manager import JOBS
from app.services.mail_test import test_receive_email

router = APIRouter(
    prefix="/adobe-accounts",
    tags=["Adobe账号管理"],
    dependencies=[Depends(capture_job_request)],
)


@router.get("", response_model=Page[AdobeAccountOut], summary="分页查询")
def list_accounts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    keyword: str = "",
    db: Session = Depends(get_db),
) -> Page[AdobeAccountOut]:
    items, total = crud.list_accounts(db, page=page, size=size, keyword=keyword.strip())
    return Page(items=items, total=total, page=page, size=size)


@router.post("", response_model=AdobeAccountOut, summary="新增单个账号")
def create_account(
    data: AdobeAccountCreate, db: Session = Depends(get_db)
) -> AdobeAccountOut:
    if crud.get_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已存在")
    return crud.create(db, data)


@router.put("/{account_id}", response_model=AdobeAccountOut, summary="编辑账号")
def update_account(
    account_id: int, data: AdobeAccountUpdate, db: Session = Depends(get_db)
) -> AdobeAccountOut:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if data.email and data.email != account.email and crud.get_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已存在")
    return crud.update(db, account, data)


@router.delete("/{account_id}", response_model=MessageResult, summary="删除单个账号")
def delete_account(account_id: int, db: Session = Depends(get_db)) -> MessageResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    crud.delete(db, account)
    return MessageResult(message="删除成功")


@router.post("/batch-delete", response_model=MessageResult, summary="批量删除")
def batch_delete(payload: BatchIds, db: Session = Depends(get_db)) -> MessageResult:
    count = crud.delete_many(db, payload.ids)
    return MessageResult(message=f"已删除 {count} 条")


@router.post("/batch-import", response_model=BatchImportResult, summary="批量导入")
def batch_import(
    payload: BatchImportRequest, db: Session = Depends(get_db)
) -> BatchImportResult:
    return crud.batch_import(db, payload.content, payload.on_duplicate, payload.platform)


@router.post(
    "/{account_id}/test-email", response_model=TestEmailResult, summary="测试收邮件"
)
def test_email(account_id: int, db: Session = Depends(get_db)) -> TestEmailResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    settings = setting_crud.get_settings(db)
    proxy_url = proxy_pool.pick(settings)

    result = test_receive_email(
        email_addr=account.email,
        refresh_token=account.refresh_token,
        client_id=account.client_id,
        mail_url=account.mail_url,
        proxy_url=proxy_url,
        timeout=settings.request_timeout,
    )

    account.mail_ok = result.success
    account.mail_message = result.message[:500]
    account.mail_checked_at = datetime.now(timezone.utc)
    # 微软的 Refresh Token 是一次性轮换的,换令牌成功后必须存回新 token,
    # 否则旧 token 已作废,下次测试会失败。
    if result.new_refresh_token and result.new_refresh_token != account.refresh_token:
        account.refresh_token = result.new_refresh_token
    db.commit()

    return TestEmailResult(
        success=result.success,
        message=result.message,
        inbox_total=result.inbox_total,
        latest_subject=result.latest_subject,
        latest_from=result.latest_from,
    )


# ----------------------------------------------------------------------------
# Adobe Admin Console:登录 / 检测 / 成员(子账号)管理
# ----------------------------------------------------------------------------

def _proxy_and_timeout(db: Session) -> tuple[str, int]:
    """返回 (代理原始多行文本, 超时)。具体外呼时用 proxy_pool 轮询取单个。"""
    s = setting_crud.get_settings(db)
    return (s.proxy_url if s.proxy_enabled else ""), s.request_timeout


@router.post(
    "/{account_id}/login", response_model=AdminActionResult, summary="登录获取管理员权限"
)
def admin_login(account_id: int, db: Session = Depends(get_db)) -> AdminActionResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not ((account.refresh_token and account.client_id) or account.mail_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号缺少 Refresh Token / Client ID 或取信接口,无法自动收取验证码",
        )

    proxy_raw, _timeout = _proxy_and_timeout(db)
    proxy_url = proxy_pool.next_proxy(proxy_raw)
    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)

    try:
        res = adobe_admin.login_account(
            email=account.email,
            adobe_password=account.adobe_password,
            refresh_token=account.refresh_token,
            client_id=account.client_id,
            mail_url=account.mail_url,
            proxy_url=proxy_url,
            otp_timeout=180,
            log=_log,
        )
    except Exception as exc:  # noqa: BLE001
        account.is_valid = False
        account.check_message = str(exc)[:500]
        account.last_checked_at = datetime.now(timezone.utc)
        db.commit()
        return AdminActionResult(
            success=False, message=str(exc)[:500], has_org=False, logs=logs
        )

    rotated = res.get("rotated_refresh_token") or ""
    if rotated and rotated != account.refresh_token:
        account.refresh_token = rotated

    account.admin_token = res.get("token") or ""
    account.admin_cookie = res.get("cookie") or ""
    account.org_id = res.get("org_id") or ""
    account.product_id = res.get("product_id") or ""
    account.product_name = res.get("product_name") or ""
    account.license_group_id = res.get("license_group_id") or ""
    account.has_org = bool(res.get("has_org"))
    account.is_valid = bool(res.get("has_org"))
    account.last_login_at = datetime.now(timezone.utc)
    account.last_checked_at = datetime.now(timezone.utc)
    if res.get("has_org"):
        account.check_message = (
            f"组织 {res.get('org_count', 0)} 个 / 产品 {res.get('product_count', 0)} 个;"
            f"授权产品:{res.get('product_name') or res.get('product_id') or '-'}"
        )[:500]
        msg = "登录成功,已获取管理权限"
    else:
        account.check_message = res.get("message") or "登录成功但未发现可用组织/产品"
        msg = account.check_message
    db.commit()

    return AdminActionResult(
        success=bool(res.get("has_org")),
        message=msg,
        has_org=account.has_org,
        org_id=account.org_id,
        product_name=account.product_name,
        org_count=int(res.get("org_count") or 0),
        product_count=int(res.get("product_count") or 0),
        logs=logs,
    )


def _admin_login_worker(job) -> None:
    """异步登录后台任务:登录 + 落库,进度写入 job.logs,结果写入 job.extra['result']。"""
    from app.db.session import SessionLocal
    class _JobCancelled(Exception):
        pass

    def _job_log(msg: str) -> None:
        if job.cancelled:
            raise _JobCancelled("任务已停止")
        job.log(msg)

    account_id = job.meta.get("admin_id")
    db = SessionLocal()
    try:
        account = crud.get(db, account_id)
        if not account:
            job.log("✗ 账号不存在")
            job.status = "error"
            job.error = "账号不存在"
            return
        if job.cancelled:
            return
        proxy_raw, _timeout = _proxy_and_timeout(db)
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        try:
            res = adobe_admin.login_account(
                email=account.email, adobe_password=account.adobe_password,
                refresh_token=account.refresh_token, client_id=account.client_id,
                mail_url=account.mail_url,
                proxy_url=proxy_url, otp_timeout=180, log=_job_log,
            )
            if job.cancelled:
                return
        except _JobCancelled:
            job.log("任务已停止")
            return
        except Exception as exc:  # noqa: BLE001
            account.is_valid = False
            account.check_message = str(exc)[:500]
            account.last_checked_at = datetime.now(timezone.utc)
            db.commit()
            job.set_extra("result", {"success": False, "has_org": False, "message": str(exc)[:200]})
            job.log(f"✗ 登录失败:{str(exc)[:200]}")
            return
        rotated = res.get("rotated_refresh_token") or ""
        if rotated and rotated != account.refresh_token:
            account.refresh_token = rotated
        account.admin_token = res.get("token") or ""
        account.admin_cookie = res.get("cookie") or ""
        account.org_id = res.get("org_id") or ""
        account.product_id = res.get("product_id") or ""
        account.product_name = res.get("product_name") or ""
        account.license_group_id = res.get("license_group_id") or ""
        account.has_org = bool(res.get("has_org"))
        account.is_valid = bool(res.get("has_org"))
        account.last_login_at = datetime.now(timezone.utc)
        account.last_checked_at = datetime.now(timezone.utc)
        if res.get("has_org"):
            account.check_message = (
                f"组织 {res.get('org_count', 0)} 个 / 产品 {res.get('product_count', 0)} 个;"
                f"授权产品:{res.get('product_name') or res.get('product_id') or '-'}"
            )[:500]
            msg = "登录成功,已获取管理权限"
        else:
            account.check_message = res.get("message") or "登录成功但未发现可用组织/产品"
            msg = account.check_message
        db.commit()
        job.set_extra("result", {
            "success": bool(res.get("has_org")), "has_org": account.has_org,
            "message": msg, "product_name": account.product_name,
        })
        job.log(("✓ " if res.get("has_org") else "⚠ ") + msg)
    finally:
        db.close()


@router.post(
    "/{account_id}/login-async", response_model=JobStatusOut, summary="异步登录(后台任务+进度)"
)
def admin_login_async(account_id: int, db: Session = Depends(get_db)) -> JobStatusOut:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not (account.refresh_token and account.client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号缺少 Refresh Token / Client ID,无法自动收取验证码",
        )
    existing = JOBS.find_active("admin_login", account_id)
    if existing:
        return JobStatusOut(**existing.to_dict())
    job = JOBS.start("admin_login", _admin_login_worker, meta={"admin_id": account_id})
    return JobStatusOut(**job.to_dict())


@router.post(
    "/{account_id}/check", response_model=AdminActionResult, summary="检测管理有效性"
)
def admin_check(account_id: int, db: Session = Depends(get_db)) -> AdminActionResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not account.admin_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="尚未登录,请先点击登录"
        )

    proxy_raw, _timeout = _proxy_and_timeout(db)
    proxy_url = proxy_pool.next_proxy(proxy_raw)
    try:
        res = adobe_admin.check_admin(
            token=account.admin_token, org_id=account.org_id, proxy_url=proxy_url
        )
    except Exception as exc:  # noqa: BLE001
        account.is_valid = False
        account.has_org = False
        account.check_message = f"检测失败(token 可能过期,请重新登录):{str(exc)[:400]}"
        account.last_checked_at = datetime.now(timezone.utc)
        db.commit()
        return AdminActionResult(
            success=False, message=account.check_message, has_org=False
        )

    account.is_valid = True
    account.has_org = True
    account.org_id = res.get("org_id") or account.org_id

    # 同步组织内真实成员数(让"成员数"列反映 Adobe 侧实际人数)
    member_total: int | None = None
    try:
        members = adobe_admin.fetch_members(
            token=account.admin_token,
            org_id=account.org_id,
            proxy_url=proxy_pool.next_proxy(proxy_raw),
        )
        member_total = len(members)
        account.member_count = member_total
    except Exception:  # noqa: BLE001
        pass

    account.check_message = (
        f"组织 {res.get('org_count', 0)} 个 / 产品 {res.get('product_count', 0)} 个"
        + (f" / 成员 {member_total} 个" if member_total is not None else "")
        + ",有效"
    )
    account.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    return AdminActionResult(
        success=True,
        message="有效(有组织/权限)"
        + (f",成员 {member_total} 个" if member_total is not None else ""),
        has_org=True,
        org_id=account.org_id,
        product_name=account.product_name,
        org_count=int(res.get("org_count") or 0),
        product_count=int(res.get("product_count") or 0),
    )


@router.get(
    "/{account_id}/members", response_model=Page[MemberOut], summary="子账号(成员)列表"
)
def list_members(
    account_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    keyword: str = "",
    db: Session = Depends(get_db),
) -> Page[MemberOut]:
    if not crud.get(db, account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    items, total = member_crud.list_by_admin(
        db, account_id, page=page, size=size, keyword=keyword.strip()
    )
    return Page(items=items, total=total, page=page, size=size)


def _get_member_for_account(db: Session, account_id: int, member_id: int):
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    member = member_crud.get(db, member_id)
    if not member or member.admin_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子账号不存在")
    if member.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="母号镜像行不能清退")
    return account, member


def _refresh_member_credit(db: Session, member, proxy_raw: str) -> dict:
    logs: list[str] = []
    credits = None
    method = ""
    if (member.access_token or "").strip():
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        credits = firefly.fetch_credits(
            member.access_token,
            proxy_url=proxy_url,
            attempts=2,
            retry_delay=1.0,
        )
        method = "access_token"

    if credits is not None:
        member.credits = float(credits)
        member.registered = True
        member.status = "registered"
        member.message = f"余额已刷新: {credits}"
        member.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(member)
        return {
            "success": True,
            "email": member.email,
            "credits": member.credits,
            "message": member.message,
            "method": method,
            "logs": logs[-20:],
        }

    def _log(message: str) -> None:
        logs.append(message)

    res = pool_login.refresh_one_sync(member.id, log=_log)
    db.expire_all()
    refreshed = member_crud.get(db, member.id)
    if refreshed is not None:
        member = refreshed

    credits = res.get("credits")
    success = bool(res.get("success")) and credits is not None
    return {
        "success": success,
        "email": member.email,
        "credits": credits,
        "message": res.get("message") or member.message or "余额刷新失败",
        "method": "protocol_login",
        "expires_at": res.get("expires_at") or member.expires_at,
        "logs": logs[-20:],
    }


def _is_expected_credit(credits: float | int | None, expected_credits: float) -> bool:
    if credits is None:
        return False
    return abs(float(credits) - float(expected_credits)) <= 0.0001


@router.post("/{account_id}/members/{member_id}/refresh-credits", summary="刷新子账号余额")
def refresh_member_credits(
    account_id: int,
    member_id: int,
    db: Session = Depends(get_db),
) -> dict:
    _account, member = _get_member_for_account(db, account_id, member_id)
    proxy_raw, _timeout = _proxy_and_timeout(db)
    res = _refresh_member_credit(db, member, proxy_raw)
    return {
        "success": bool(res.get("success")),
        "action": "refreshed" if res.get("success") else "failed",
        "member_id": member_id,
        "email": res.get("email") or member.email,
        "credits": res.get("credits"),
        "message": res.get("message") or "",
        "method": res.get("method") or "",
        "expires_at": res.get("expires_at"),
        "logs": res.get("logs") or [],
    }


@router.post(
    "/{account_id}/members/{member_id}/refresh-and-remove-empty",
    summary="刷新余额并清退无余额/非目标额度子账号",
)
def refresh_and_remove_empty_member(
    account_id: int,
    member_id: int,
    expected_credits: float = Query(4000.0, ge=0),
    remove_non_target: bool = Query(True),
    db: Session = Depends(get_db),
) -> dict:
    account, member = _get_member_for_account(db, account_id, member_id)
    if not (account.admin_token and account.org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="尚未登录,请先登录"
        )

    proxy_raw, _timeout = _proxy_and_timeout(db)
    refresh_res = _refresh_member_credit(db, member, proxy_raw)
    db.expire_all()
    member = member_crud.get(db, member_id)
    if not member or member.admin_id != account_id:
        return {
            "success": False,
            "action": "failed",
            "member_id": member_id,
            "email": refresh_res.get("email") or "",
            "credits": refresh_res.get("credits"),
            "message": "刷新后本地记录不存在",
            "refresh": refresh_res,
        }

    credits = refresh_res.get("credits")
    if credits is None:
        member.status = "failed"
        member.message = (refresh_res.get("message") or "余额刷新失败,未删除")[:500]
        member.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "success": False,
            "action": "refresh_failed",
            "member_id": member.id,
            "email": member.email,
            "credits": None,
            "message": "余额无法确认,未删除",
            "refresh": refresh_res,
        }

    low_or_empty = float(credits) <= 0.0001
    not_target = not _is_expected_credit(float(credits), expected_credits)
    should_remove = low_or_empty or (remove_non_target and not_target)
    if not should_remove:
        return {
            "success": True,
            "action": "kept",
            "member_id": member.id,
            "email": member.email,
            "credits": credits,
            "message": "余额合格,保留",
            "refresh": refresh_res,
        }

    reason = "余额为 0" if low_or_empty else f"余额不是 {expected_credits:g}"
    try:
        remove_res = adobe_admin.remove_member(
            token=account.admin_token,
            org_id=account.org_id,
            member_id=member.member_id,
            email=member.email,
            proxy_url=proxy_pool.next_proxy(proxy_raw),
        )
    except Exception as exc:  # noqa: BLE001
        remove_res = {"ok": False, "message": str(exc)[:300]}

    remove_message = remove_res.get("message") or ""
    remote_ok = bool(remove_res.get("ok")) or "未找到成员" in remove_message
    if not remote_ok:
        member.status = "removed_failed"
        member.message = f"{reason}; 远端移除失败: {remove_message}"[:500]
        member.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "success": False,
            "action": "remove_failed",
            "member_id": member.id,
            "email": member.email,
            "credits": credits,
            "message": member.message,
            "remote_removed": False,
            "local_removed": False,
            "pool_removed": False,
            "refresh": refresh_res,
        }

    email = member.email
    db.delete(member)
    pool_row = email_crud.get_by_email(db, email)
    pool_removed = False
    if pool_row:
        db.delete(pool_row)
        pool_removed = True
    db.flush()
    account.member_count = member_crud.count_by_admin(db, account_id)
    db.commit()
    return {
        "success": True,
        "action": "removed",
        "member_id": member_id,
        "email": email,
        "credits": credits,
        "message": f"{reason}; 已远端移除并删除本地号池记录",
        "remote_removed": True,
        "local_removed": True,
        "pool_removed": pool_removed,
        "refresh": refresh_res,
    }


@router.get("/{account_id}/members/remote-preview", summary="Preview remote member cleanup")
def preview_remote_members(
    account_id: int, db: Session = Depends(get_db)
) -> dict:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if not (account.admin_token and account.org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="admin login required"
        )
    proxy_raw, _timeout = _proxy_and_timeout(db)
    remote, plans = remote_member_cleanup.analyze_remote_members(
        db, account, proxy_raw=proxy_raw
    )
    remote_only = [p.as_dict() for p in plans if p.reason == "remote_only"]
    local_not_qualified = [
        p.as_dict() for p in plans if p.reason == "local_not_qualified"
    ]
    return {
        "remote_total": len(remote),
        "cleanup_candidates": len(plans),
        "remote_only": len(remote_only),
        "remote_only_items": remote_only,
        "local_not_qualified": len(local_not_qualified),
        "local_not_qualified_items": local_not_qualified,
        "candidates": [p.as_dict() for p in plans],
    }


@router.post("/{account_id}/members/cleanup-remote", summary="Cleanup remote member slots")
def cleanup_remote_members(
    account_id: int, db: Session = Depends(get_db)
) -> dict:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if not (account.admin_token and account.org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="admin login required"
        )
    proxy_raw, _timeout = _proxy_and_timeout(db)
    res = remote_member_cleanup.cleanup_remote_members(
        db, account, proxy_raw=proxy_raw
    )
    account.member_count = member_crud.count_by_admin(db, account_id)
    db.commit()
    return res


@router.post(
    "/{account_id}/members/batch-grant",
    response_model=BatchGrantResult,
    summary="批量加子账号并授权",
)
def batch_grant(
    account_id: int, payload: BatchGrantRequest, db: Session = Depends(get_db)
) -> BatchGrantResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not (account.admin_token and account.org_id and account.product_id
            and account.license_group_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号尚未取得管理权限,请先登录(并确认已发现组织/产品)",
        )

    proxy_raw, _timeout = _proxy_and_timeout(db)
    proxy_url = proxy_pool.next_proxy(proxy_raw)

    # 1) 确定要授权的邮箱:优先用传入列表,否则从邮箱池取未使用的
    from_pool = False
    if payload.emails:
        emails = [e.strip() for e in payload.emails if e.strip() and "@" in e]
    else:
        pool_rows = email_crud.take_unused(db, payload.count)
        emails = [r.email for r in pool_rows]
        from_pool = True
    if not emails:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可用于授权的邮箱(邮箱池为空或未填写列表)",
        )

    # 2) 批量授权前先校验 token 仍有效,避免逐个失败
    try:
        adobe_admin.check_admin(
            token=account.admin_token, org_id=account.org_id, proxy_url=proxy_url
        )
    except Exception as exc:  # noqa: BLE001
        account.is_valid = False
        account.has_org = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"管理 token 已失效,请重新登录:{str(exc)[:200]}",
        ) from exc

    token = account.admin_token
    org_id = account.org_id
    product_id = account.product_id
    lgid = account.license_group_id

    def _do(email: str) -> tuple[str, dict]:
        return email, adobe_admin.grant_member(
            token=token, org_id=org_id, product_id=product_id,
            license_group_id=lgid, email=email,
            proxy_url=proxy_pool.next_proxy(proxy_raw),
        )

    # 3) 并发执行网络请求(不触碰数据库),回到主线程后统一落库
    s = setting_crud.get_settings(db)
    workers = max(1, min(s.concurrency, len(emails)))
    results: list[tuple[str, dict]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(_do, emails):
            results.append(r)

    items: list[GrantItemResult] = []
    granted = 0
    for email, res in results:
        ok = bool(res.get("ok"))
        member_crud.upsert(
            db,
            account_id,
            email=email,
            member_id=res.get("member_id") or "",
            status="granted" if ok else "failed",
            message=res.get("message") or "",
        )
        if ok:
            granted += 1
            if from_pool:
                email_crud.mark_used_by_email(db, email)
        items.append(GrantItemResult(email=email, ok=ok, message=res.get("message") or ""))

    account.member_count = member_crud.count_by_admin(db, account_id)
    db.commit()

    return BatchGrantResult(
        total=len(items), granted=granted, failed=len(items) - granted, items=items
    )


@router.post(
    "/{account_id}/members/batch-delete",
    response_model=MessageResult,
    summary="批量移除子账号",
)
def batch_delete_members(
    account_id: int, payload: BatchIds, db: Session = Depends(get_db)
) -> MessageResult:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not (account.admin_token and account.org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="尚未登录,请先登录"
        )

    proxy_raw, _timeout = _proxy_and_timeout(db)
    rows = member_crud.delete_many(db, account_id, payload.ids)

    removed = 0
    for row in rows:
        try:
            res = adobe_admin.remove_member(
                token=account.admin_token,
                org_id=account.org_id,
                member_id=row.member_id,
                email=row.email,
                proxy_url=proxy_pool.next_proxy(proxy_raw),
            )
        except Exception as exc:  # noqa: BLE001
            res = {"ok": False, "message": str(exc)[:300]}

        message = res.get("message") or ""
        if res.get("ok") or "未找到成员" in message:
            db.delete(row)
            removed += 1
        else:
            row.status = "removed_failed"
            row.message = res.get("message") or "移除失败"

    account.member_count = member_crud.count_by_admin(db, account_id)
    db.commit()
    return MessageResult(message=f"已移除 {removed} / {len(rows)} 个成员")


def _start_cleanup_members_job(
    admin_ids: list[int],
    mode: str,
    db: Session,
) -> JobStatusOut:
    ids = [int(a) for a in dict.fromkeys(admin_ids) if int(a) > 0]
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个母号"
        )
    found = {a.id for a in crud.list_by_ids(db, ids)}
    missing = [a for a in ids if a not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"母号不存在:{missing}"
        )
    normalized_mode = member_cleanup.normalize_cleanup_mode(mode)
    job = JOBS.start(
        "子号清退",
        member_cleanup.cleanup_members_worker,
        meta={
            "admin_ids": ids,
            "mode": normalized_mode,
            "target": 0,
            "label": member_cleanup.cleanup_mode_label(normalized_mode),
        },
    )
    return JobStatusOut(**job.to_dict())


@router.post(
    "/{account_id}/members/cleanup-job",
    response_model=JobStatusOut,
    summary="创建子账号清退任务(单母号)",
)
def cleanup_account_members_job(
    account_id: int,
    payload: CleanupMembersRequest | None = None,
    db: Session = Depends(get_db),
) -> JobStatusOut:
    mode = payload.mode if payload else "all"
    return _start_cleanup_members_job([account_id], mode, db)


@router.post(
    "/members/cleanup-job",
    response_model=JobStatusOut,
    summary="创建子账号清退任务(多母号)",
)
def cleanup_selected_members_job(
    payload: CleanupMembersRequest,
    db: Session = Depends(get_db),
) -> JobStatusOut:
    return _start_cleanup_members_job(payload.admin_ids, payload.mode, db)


@router.post(
    "/members/import-pool-job",
    response_model=JobStatusOut,
    summary="创建批量更新自建号池任务",
)
def import_pool_job(
    payload: BatchAdminIdsRequest,
    db: Session = Depends(get_db),
) -> JobStatusOut:
    ids = [int(a) for a in dict.fromkeys(payload.admin_ids) if int(a) > 0]
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个母号"
        )
    found = {a.id for a in crud.list_by_ids(db, ids)}
    missing = [a for a in ids if a not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"母号不存在:{missing}"
        )
    job = JOBS.start(
        "批量更新号池",
        provider_pool_sync.import_pool_batch_worker,
        meta={"admin_ids": ids, "target": len(ids)},
    )
    return JobStatusOut(**job.to_dict())


@router.post(
    "/{account_id}/members/build-team",
    response_model=JobStatusOut,
    summary="一键拉号:凑满 N 个已注册子号",
)
def build_team(
    account_id: int, payload: BuildTeamRequest, db: Session = Depends(get_db)
) -> JobStatusOut:
    account = crud.get(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not (account.admin_token and account.org_id and account.product_id
            and account.license_group_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号尚未取得管理权限,请先登录(并确认已发现组织/产品)",
        )
    existing = JOBS.find_active("build_team", account_id)
    if existing:
        return JobStatusOut(**existing.to_dict())

    count = max(1, min(50, payload.count or 9))
    mode = payload.mode if payload.mode in ("target", "add") else "target"
    job = JOBS.start(
        "build_team",
        team_builder.build_team_worker,
        meta={"admin_id": account_id, "count": count, "target": count, "mode": mode},
    )
    return JobStatusOut(**job.to_dict())


@router.get("/jobs/{job_id}", response_model=JobStatusOut, summary="查询拉号任务进度")
def get_job(job_id: int, log_offset: int = 0) -> JobStatusOut:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return JobStatusOut(**job.to_dict(log_offset=log_offset))


@router.post(
    "/build-team-batch", response_model=JobStatusOut, summary="批量拉号(多主号)"
)
def build_team_batch(
    payload: BatchBuildTeamRequest, db: Session = Depends(get_db)
) -> JobStatusOut:
    admin_ids = [a for a in dict.fromkeys(payload.admin_ids)]  # 去重保序
    if not admin_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个主号"
        )
    found = {a.id for a in crud.list_by_ids(db, admin_ids)}
    missing = [a for a in admin_ids if a not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"主号不存在:{missing}"
        )
    count = max(1, min(50, payload.count or 9))
    mode = payload.mode if payload.mode in ("target", "add") else "target"
    job = JOBS.start(
        "build_team_batch",
        team_builder.build_team_batch_worker,
        meta={"admin_ids": admin_ids, "count": count, "target": count * len(admin_ids),
              "mode": mode},
    )
    return JobStatusOut(**job.to_dict())


@router.get("/jobs", response_model=list[JobStatusOut], summary="拉号任务列表")
def list_jobs(limit: int = 30) -> list[JobStatusOut]:
    out: list[JobStatusOut] = []
    for job in JOBS.list_recent(limit):
        d = job.to_dict()
        d["logs"] = []  # 列表只看汇总,详情走 /jobs/{id}
        out.append(JobStatusOut(**d))
    return out


@router.post("/jobs/batch-delete", response_model=MessageResult, summary="批量删除拉号任务")
def batch_delete_jobs(payload: BatchIds) -> MessageResult:
    if not payload.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择要删除的任务"
        )
    deleted, skipped = JOBS.delete_many(payload.ids)
    if skipped and not deleted:
        return MessageResult(
            success=False,
            message=f"进行中的任务不可删除(#{', #'.join(map(str, skipped))})",
        )
    if skipped:
        return MessageResult(
            message=(
                f"已删除 {deleted} 个任务;"
                f"跳过进行中的 #{', #'.join(map(str, skipped))}"
            ),
        )
    return MessageResult(message=f"已删除 {deleted} 个任务")


@router.post(
    "/jobs/{job_id}/cancel", response_model=MessageResult, summary="停止任务"
)
def cancel_job(job_id: int) -> MessageResult:
    ok, message = JOBS.cancel(job_id)
    if not ok and message == "任务不存在":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    return MessageResult(success=ok, message=message)


@router.post("/jobs/{job_id}/pause", response_model=MessageResult, summary="暂停外部子号登录任务")
def pause_job(job_id: int) -> MessageResult:
    ok, message = JOBS.pause(job_id)
    return MessageResult(success=ok, message=message)


@router.post("/jobs/{job_id}/resume", response_model=MessageResult, summary="继续外部子号登录任务")
def resume_job(job_id: int) -> MessageResult:
    ok, message = JOBS.resume(job_id)
    return MessageResult(success=ok, message=message)


@router.post(
    "/jobs/{job_id}/clear-logs", response_model=MessageResult, summary="清空任务日志"
)
def clear_job_logs(job_id: int) -> MessageResult:
    if not JOBS.clear_logs(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return MessageResult(message="已清空任务日志")
