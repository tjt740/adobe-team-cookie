"""号池管理:跨所有 Adobe 母号的已注册子号,支持 newbanana 格式导出。"""

from __future__ import annotations

import json
import random
import secrets
import time

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
import requests
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import adobe_account as adobe_crud
from app.crud import adobe_member as member_crud
from app.crud import setting as setting_crud
from app.db.session import get_db
from app.schemas.adobe_account import (
    JobStatusOut,
    PoolBatchLoginFilter,
    PoolItemOut,
    PoolMemberDetail,
    PoolMemberUpdate,
    PoolMoeMailGenerateRequest,
    RefreshARPRequest,
    RefreshARPResult,
    RefreshTokenResult,
    TestImageRequest,
    TestImageResult,
)
from app.schemas.common import (
    BatchIds,
    BatchImportRequest,
    BatchImportResult,
    MessageResult,
    Page,
)
from app.services import adobe_admin, firefly_arp, firefly_image, pool_login, proxy_pool
from app.services import mail_test
from app.services.adobe_otp import _extract_adobe_otp, _strip_html
from app.services.job_manager import JOBS

router = APIRouter(
    prefix="/pool",
    tags=["号池管理"],
    dependencies=[Depends(get_current_user)],
)


def _to_item(member, admin_email: str) -> PoolItemOut:
    return PoolItemOut(
        id=member.id,
        admin_id=member.admin_id,
        admin_email=admin_email,
        email=member.email,
        display_name=member.display_name or "",
        member_id=member.member_id or "",
        status=member.status or "",
        credits=member.credits,
        expires_at=member.expires_at,
        registered=bool(member.registered),
        is_admin=bool(member.is_admin),
        is_imported=bool(member.is_imported),
        has_token=bool(member.access_token),
        has_cookie=bool(member.cookie),
        has_arp=bool(member.arp_session_id),
        exported_at=member.exported_at,
        export_count=int(member.export_count or 0),
        created_at=member.created_at,
    )


@router.get("", response_model=Page[PoolItemOut], summary="号池分页查询")
def list_pool(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    keyword: str = "",
    registered_only: bool = True,
    pool_type: str = Query("", pattern="^(|all|imported|sub|admin)$"),
    has_token: str = Query("", pattern="^(|yes|no)$"),
    credit_status: str = Query("", pattern="^(|unknown|known)$"),
    credit_value: float | None = Query(None),
    status_filter: str = Query("", pattern="^(|failed|registered|pending)$"),
    export_status: str = Query("", pattern="^(|exported|unexported)$"),
    db: Session = Depends(get_db),
) -> Page[PoolItemOut]:
    # 确保每个母号在号池里都有一条可拉取的镜像行
    member_crud.ensure_admin_self_rows(db)
    token_filter: bool | None = None
    if has_token == "yes":
        token_filter = True
    elif has_token == "no":
        token_filter = False
    pt = "" if pool_type in ("", "all") else pool_type
    rows, total = member_crud.list_pool(
        db,
        page=page,
        size=size,
        keyword=keyword.strip(),
        registered_only=registered_only,
        pool_type=pt,
        has_token=token_filter,
        credit_status=credit_status,
        credit_value=credit_value,
        status_filter=status_filter,
        export_status=export_status,
    )
    items = [_to_item(m, admin_email) for m, admin_email in rows]
    return Page(items=items, total=total, page=page, size=size)


@router.get("/export", summary="导出号池(newbanana 格式)")
def export_pool(
    format: str = Query("default", pattern="^(default|json|cookies|tokens)$"),
    keyword: str = "",
    pool_type: str = Query("", pattern="^(|all|imported|sub|admin)$"),
    has_token: str = Query("", pattern="^(|yes|no)$"),
    credit_status: str = Query("", pattern="^(|unknown|known)$"),
    credit_value: float | None = Query(None),
    status_filter: str = Query("", pattern="^(|failed|registered|pending)$"),
    export_status: str = Query("", pattern="^(|exported|unexported)$"),
    db: Session = Depends(get_db),
) -> Response:
    # format=default:按「设置 → 号池默认导出格式」解析。
    # token → newbanana 全量 JSON(cookie + access_token + device_token);
    # cookie → 纯 CK 格式([{cookie, name}])。
    if format == "default":
        export_pref = (setting_crud.get_settings(db).export_format or "token").lower()
        format = "cookies" if export_pref == "cookie" else "json"

    token_filter: bool | None = None
    if has_token == "yes":
        token_filter = True
    elif has_token == "no":
        token_filter = False
    pt = "" if pool_type in ("", "all") else pool_type
    rows = member_crud.export_pool(
        db,
        keyword=keyword.strip(),
        registered_only=False,
        pool_type=pt,
        has_token=token_filter,
        credit_status=credit_status,
        credit_value=credit_value,
        status_filter=status_filter,
        export_status=export_status,
    )
    ts = int(time.time())
    exported_members = []

    if format == "tokens":
        exported_members = [m for m, _ in rows if m.access_token]
        body = "\n".join(m.access_token for m in exported_members)
        _mark_exported(db, exported_members)
        return Response(
            body,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=pool_tokens_{ts}.txt"},
        )

    if format == "cookies":
        exported_members = [m for m, _ in rows if m.cookie]
        items = [
            {"cookie": m.cookie or "", "name": m.email}
            for m in exported_members
        ]
    else:  # json:newbanana 全量
        exported_members = [m for m, _ in rows]
        items = [
            {
                "cookie": m.cookie or "",
                "name": m.email,
                "access_token": m.access_token or "",
                "device_token": m.device_token or "",
                "device_id": m.device_id or "",
                "arp_session_id": m.arp_session_id or "",
                "credits": m.credits if m.credits is not None and m.credits >= 0 else 0,
                "expires_at": m.expires_at,
            }
            for m, _ in rows
        ]

    body = json.dumps(items, ensure_ascii=False, indent=2)
    fname = f"pool_{format}_{ts}.json"
    _mark_exported(db, exported_members)
    return Response(
        body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


def _mark_exported(db: Session, members: list) -> None:
    if not members:
        return
    now = datetime.now(timezone.utc)
    for member in members:
        member.exported_at = now
        member.export_count = int(member.export_count or 0) + 1
    db.commit()


@router.post("/import", response_model=BatchImportResult, summary="导入邮箱到号池(独立账号)")
def import_pool(payload: BatchImportRequest, db: Session = Depends(get_db)) -> BatchImportResult:
    res = member_crud.import_pool_lines(db, payload.content)
    return BatchImportResult(**res)


@router.post("/moemail/generate", response_model=BatchImportResult, summary="创建 MoeMail 邮箱并导入号池")
def generate_moemail_pool(
    payload: PoolMoeMailGenerateRequest, db: Session = Depends(get_db)
) -> BatchImportResult:
    api_key = payload.api_key.strip()
    domains = ("edu0.buzz", "edu1.store", "edu6.site", "edu8.buzz")
    domain = payload.domain.strip().lower()
    if domain not in {*domains, "random"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的 MoeMail 域名")

    result = BatchImportResult(created=0, updated=0, skipped=0, failed=0, errors=[])
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    prefix = payload.name_prefix.strip()
    for idx in range(payload.count):
        name = ""
        if prefix:
            suffix = secrets.token_hex(3) if payload.count > 1 else ""
            name = f"{prefix}{idx + 1 if not suffix else suffix}"
        body = {"expiryTime": payload.expiry_time, "domain": random.choice(domains) if domain == "random" else domain}
        if name:
            body["name"] = name
        try:
            r = requests.post(
                "https://edu6.site/api/emails/generate",
                headers=headers,
                json=body,
                timeout=20,
            )
        except requests.RequestException as exc:
            result.failed += 1
            result.errors.append(f"第 {idx + 1} 个:请求失败 {str(exc)[:120]}")
            continue
        if r.status_code not in (200, 201):
            result.failed += 1
            result.errors.append(f"第 {idx + 1} 个:创建失败 {r.status_code}:{(r.text or '')[:120]}")
            continue
        data = r.json() or {}
        address = (data.get("email") or data.get("address") or "").strip()
        email_id = (data.get("id") or "").strip()
        if not address or not email_id:
            result.failed += 1
            result.errors.append(f"第 {idx + 1} 个:响应缺少邮箱或 emailId")
            continue
        line = (
            f"{address}----{payload.password or ''}----"
            f"moemail://edu6.site?api_key={api_key}&email_id={email_id}"
        )
        imported = member_crud.import_pool_lines(db, line)
        result.created += imported["created"]
        result.updated += imported["updated"]
        result.skipped += imported["skipped"]
        result.failed += imported["failed"]
        result.errors.extend(imported["errors"])
    return result


@router.get("/{member_id}", response_model=PoolMemberDetail, summary="号池条目详情(编辑用)")
def get_member(member_id: int, db: Session = Depends(get_db)) -> PoolMemberDetail:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    return PoolMemberDetail.model_validate(m)


def _test_moemail(mail_url: str, email: str) -> MessageResult:
    from urllib.parse import parse_qsl, urlparse

    parsed = urlparse(mail_url)
    qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    api_key = (qs.get("api_key") or qs.get("key") or "").strip()
    email_id = (qs.get("email_id") or qs.get("emailId") or parsed.path.strip("/")).strip()
    if not (api_key and email_id):
        return MessageResult(success=False, message="MoeMail 缺少 api_key 或 email_id")
    base = f"https://{parsed.netloc or 'edu6.site'}"
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    r = requests.get(f"{base}/api/emails/{email_id}", headers=headers, timeout=15)
    if r.status_code != 200:
        return MessageResult(success=False, message=f"MoeMail 邮件列表失败 {r.status_code}:{(r.text or '')[:120]}")
    messages = (r.json() or {}).get("messages") or []
    if not messages:
        return MessageResult(message=f"MoeMail 连通正常:{email},暂无邮件")
    latest = messages[0]
    mid = latest.get("id")
    subject = latest.get("subject") or ""
    if mid:
        detail = requests.get(f"{base}/api/emails/{email_id}/{mid}", headers=headers, timeout=15)
        if detail.status_code == 200:
            msg = (detail.json() or {}).get("message") or {}
            text = _strip_html(f"{msg.get('subject') or subject} {msg.get('content') or ''} {msg.get('html') or ''}")
            code = _extract_adobe_otp(subject, text)
            if code:
                return MessageResult(message=f"MoeMail 正常,最新 Adobe 验证码:{code}")
    return MessageResult(message=f"MoeMail 正常,最新邮件:{subject or '(无主题)'}")


@router.post("/{member_id}/test-mail", response_model=MessageResult, summary="测试号池账号收件")
def test_pool_mail(member_id: int, db: Session = Depends(get_db)) -> MessageResult:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    mail_url = (m.mail_url or "").strip()
    rt = (m.refresh_token or "").strip()
    cid = (m.client_id or "").strip()
    if mail_url.startswith("moemail://"):
        return _test_moemail(mail_url, m.email)
    if rt and cid and not rt.startswith("http"):
        settings = setting_crud.get_settings(db)
        res = mail_test.fetch_inbox(
            email_addr=m.email,
            refresh_token=rt,
            client_id=cid,
            proxy_url="",
            timeout=settings.request_timeout,
            top=5,
        )
        if res.new_refresh_token and res.new_refresh_token != m.refresh_token:
            m.refresh_token = res.new_refresh_token
            db.commit()
        latest = (res.messages or [None])[0]
        suffix = f",最新邮件:{latest.subject}" if latest else ""
        return MessageResult(success=res.success, message=f"{res.message}{suffix}")
    url = mail_test.normalize_mail_url(mail_url) or (
        mail_test.normalize_mail_url(rt) if mail_test.is_http_mail_url(rt) else ""
    )
    if url:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return MessageResult(success=False, message=f"外部取信 URL 返回 {r.status_code}")
        code = _extract_adobe_otp("", _strip_html(r.text or ""))
        if code:
            return MessageResult(message=f"外部取信 URL 正常,检测到 Adobe 验证码:{code}")
        return MessageResult(message="外部取信 URL 正常,未检测到 Adobe 验证码")
    return MessageResult(success=False, message="缺少 Refresh Token / Client ID 或取信配置")


@router.put("/{member_id}", response_model=PoolMemberDetail, summary="编辑号池条目")
def update_member(
    member_id: int, payload: PoolMemberUpdate, db: Session = Depends(get_db)
) -> PoolMemberDetail:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    fields = payload.model_dump(exclude_unset=True)
    for k, v in fields.items():
        setattr(m, k, v)
    m.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(m)
    return PoolMemberDetail.model_validate(m)


@router.post("/{member_id}/refresh-token", response_model=RefreshTokenResult, summary="刷新AT并查额度")
def refresh_token(member_id: int, db: Session = Depends(get_db)) -> RefreshTokenResult:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    res = pool_login.refresh_one_sync(member_id)
    return RefreshTokenResult(**res)


@router.post("/{member_id}/refresh-arp", response_model=RefreshARPResult, summary="浏览器捕获ARP")
def refresh_arp(
    member_id: int, payload: RefreshARPRequest, db: Session = Depends(get_db)
) -> RefreshARPResult:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    if not m.cookie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号没有 cookie，无法加载浏览器会话")
    settings = setting_crud.get_settings(db)
    proxy_url = proxy_pool.pick(settings)
    res = firefly_arp.capture_arp_session_id(
        cookie=m.cookie,
        prompt=(payload.prompt or "").strip() or "cartoon watermelon sticker",
        proxy_url=proxy_url,
        headless=payload.headless,
        timeout_ms=max(30, min(300, payload.timeout_seconds)) * 1000,
    )
    if res.success and res.arp_session_id:
        m.arp_session_id = res.arp_session_id
        if res.access_token:
            m.access_token = res.access_token
        m.updated_at = datetime.now(timezone.utc)
        db.commit()
    return RefreshARPResult(
        success=res.success,
        message=res.message,
        arp_session_id=res.arp_session_id,
        has_access_token=bool(res.access_token),
    )


@router.post("/{member_id}/test-image", response_model=TestImageResult, summary="测试出图")
def test_image(
    member_id: int, payload: TestImageRequest, db: Session = Depends(get_db)
) -> TestImageResult:
    m = member_crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    if not m.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该子号没有 access_token,请先批量登录刷新",
        )
    settings = setting_crud.get_settings(db)
    proxy_url = proxy_pool.pick(settings)
    res = firefly_image.test_generate(
        access_token=m.access_token,
        arp_session_id=m.arp_session_id or "",
        prompt=(payload.prompt or "").strip()
        or "a cute corgi puppy running on a sunny beach, cinematic",
        proxy_url=proxy_url,
        aspect_ratio=payload.aspect_ratio or "1:1",
        quality=payload.quality or "medium",
        width=payload.width,
        height=payload.height,
        timeout=max(30, min(180, settings.request_timeout * 4 or 120)),
    )
    return TestImageResult(**res)


@router.post("/batch-login", response_model=JobStatusOut, summary="批量协议登录刷新Token")
def batch_login(payload: BatchIds, db: Session = Depends(get_db)) -> JobStatusOut:
    members = member_crud.get_many(db, payload.ids)
    if not members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账号"
        )
    job = JOBS.start(
        "pool_login",
        pool_login.pool_login_batch_worker,
        meta={
            "member_ids": [m.id for m in members],
            "target": len(members),
            "auto_retry": payload.auto_retry,
            "max_retries": payload.max_retries,
        },
    )
    return JobStatusOut(**job.to_dict())


@router.post("/batch-login-filter", response_model=JobStatusOut, summary="按筛选批量协议登录")
def batch_login_filter(
    payload: PoolBatchLoginFilter, db: Session = Depends(get_db)
) -> JobStatusOut:
    """对当前筛选条件下的全部账号开批量登录任务(无需逐页勾选)。"""
    member_crud.ensure_admin_self_rows(db)
    pt = "" if payload.pool_type in ("", "all") else payload.pool_type
    ids = member_crud.list_pool_ids(
        db,
        keyword=payload.keyword.strip(),
        registered_only=payload.registered_only,
        pool_type=pt,
        has_token=payload.has_token,
        credit_status=payload.credit_status,
        credit_value=payload.credit_value,
        status_filter=payload.status_filter,
        export_status=payload.export_status,
    )
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前筛选条件下没有可登录的账号",
        )
    job = JOBS.start(
        "pool_login",
        pool_login.pool_login_batch_worker,
        meta={
            "member_ids": ids,
            "target": len(ids),
            "auto_retry": payload.auto_retry,
            "max_retries": payload.max_retries,
        },
    )
    return JobStatusOut(**job.to_dict())


@router.post("/batch-login-retry/{job_id}", response_model=JobStatusOut, summary="重试任务中仍无token的账号")
def batch_login_retry_job(job_id: int, db: Session = Depends(get_db)) -> JobStatusOut:
    """对指定 pool_login 任务里仍未拿到 token 的账号再开一轮(默认自动重试)。"""
    src = JOBS.get(job_id)
    if not src or src.type != "pool_login":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或类型不匹配")
    member_ids = [int(x) for x in (src.meta.get("member_ids") or [])]
    if not member_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原任务没有账号列表")
    pending = [
        m.id
        for m in member_crud.get_many(db, member_ids)
        if not (m.access_token or "").strip()
    ]
    if not pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该任务范围内账号均已拿到 token")
    job = JOBS.start(
        "pool_login",
        pool_login.pool_login_batch_worker,
        meta={
            "member_ids": pending,
            "target": len(pending),
            "auto_retry": src.meta.get("auto_retry", True),
            "max_retries": src.meta.get("max_retries", 2),
            "retry_from_job": job_id,
        },
    )
    return JobStatusOut(**job.to_dict())


@router.post("/batch-delete", response_model=MessageResult, summary="从号池移除")
def batch_delete(payload: BatchIds, db: Session = Depends(get_db)) -> MessageResult:
    members = member_crud.get_many(db, payload.ids)
    if not members:
        return MessageResult(message="未找到要删除的条目")

    settings = setting_crud.get_settings(db)
    proxy_raw = settings.proxy_url if settings.proxy_enabled else ""

    # 按母号缓存 token,尽量同时把成员从组织里移除
    admin_cache: dict[int, object] = {}
    removed = 0
    for m in members:
        admin = admin_cache.get(m.admin_id)
        if admin is None:
            admin = adobe_crud.get(db, m.admin_id)
            admin_cache[m.admin_id] = admin
        # 母号镜像行不属于自己组织,跳过组织移除(删除后下次列表会自动重建)
        if not m.is_admin and admin and admin.admin_token and admin.org_id:
            try:
                adobe_admin.remove_member(
                    token=admin.admin_token, org_id=admin.org_id,
                    member_id=m.member_id, email=m.email,
                    proxy_url=proxy_pool.next_proxy(proxy_raw),
                )
            except Exception:
                pass
        db.delete(m)
        removed += 1

    # 更新各母号成员计数
    for admin_id, admin in admin_cache.items():
        if admin:
            admin.member_count = member_crud.count_by_admin(db, admin_id)
    db.commit()
    return MessageResult(message=f"已从号池移除 {removed} 条")
