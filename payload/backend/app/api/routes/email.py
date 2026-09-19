from dataclasses import asdict
import random
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
import requests
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import email as crud
from app.crud import setting as setting_crud
from app.db.session import get_db
from app.schemas.common import (
    BatchIds,
    BatchImportRequest,
    BatchImportResult,
    MessageResult,
    Page,
)
from app.schemas.email import (
    EmailCreate,
    EmailOut,
    EmailUpdate,
    MoeMailGenerateRequest,
    MailDetailOut,
    MailListOut,
)
from app.services import mail_test

router = APIRouter(
    prefix="/emails",
    tags=["邮箱管理"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[EmailOut], summary="分页查询")
def list_emails(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    keyword: str = "",
    is_used: bool | None = None,
    db: Session = Depends(get_db),
) -> Page[EmailOut]:
    items, total = crud.list_emails(
        db, page=page, size=size, keyword=keyword.strip(), is_used=is_used
    )
    return Page(items=items, total=total, page=page, size=size)


@router.post("", response_model=EmailOut, summary="新增单个邮箱")
def create_email(data: EmailCreate, db: Session = Depends(get_db)) -> EmailOut:
    if crud.get_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已存在")
    return crud.create(db, data)


@router.put("/{email_id}", response_model=EmailOut, summary="编辑邮箱")
def update_email(
    email_id: int, data: EmailUpdate, db: Session = Depends(get_db)
) -> EmailOut:
    obj = crud.get(db, email_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邮箱不存在")
    if data.email and data.email != obj.email and crud.get_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已存在")
    return crud.update(db, obj, data)


@router.delete("/{email_id}", response_model=MessageResult, summary="删除单个邮箱")
def delete_email(email_id: int, db: Session = Depends(get_db)) -> MessageResult:
    obj = crud.get(db, email_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邮箱不存在")
    crud.delete_many(db, [email_id])
    return MessageResult(message="删除成功")


@router.post("/batch-delete", response_model=MessageResult, summary="批量删除")
def batch_delete(payload: BatchIds, db: Session = Depends(get_db)) -> MessageResult:
    count = crud.delete_many(db, payload.ids)
    return MessageResult(message=f"已删除 {count} 条")


@router.post("/batch-import", response_model=BatchImportResult, summary="批量导入")
def batch_import(
    payload: BatchImportRequest, db: Session = Depends(get_db)
) -> BatchImportResult:
    return crud.batch_import(db, payload.content, payload.on_duplicate)


@router.post("/moemail/generate", response_model=BatchImportResult, summary="批量创建 MoeMail 邮箱")
def generate_moemail(
    payload: MoeMailGenerateRequest, db: Session = Depends(get_db)
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
        imported = crud.batch_import(db, line, payload.on_duplicate)
        result.created += imported.created
        result.updated += imported.updated
        result.skipped += imported.skipped
        result.failed += imported.failed
        result.errors.extend(imported.errors)
    return result


def _require_creds(obj) -> None:
    if not (obj.refresh_token and obj.client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱缺少 Refresh Token / Client ID,无法收取邮件",
        )


@router.get("/{email_id}/messages", response_model=MailListOut, summary="收取邮件列表")
def fetch_messages(
    email_id: int,
    top: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MailListOut:
    obj = crud.get(db, email_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邮箱不存在")
    _require_creds(obj)

    settings = setting_crud.get_settings(db)
    res = mail_test.fetch_inbox(
        email_addr=obj.email,
        refresh_token=obj.refresh_token,
        client_id=obj.client_id,
        proxy_url="",
        timeout=settings.request_timeout,
        top=top,
    )
    if res.new_refresh_token and res.new_refresh_token != obj.refresh_token:
        obj.refresh_token = res.new_refresh_token
        db.commit()

    return MailListOut(
        success=res.success,
        message=res.message,
        source=res.source,
        messages=[asdict(m) for m in (res.messages or [])],
    )


@router.get("/{email_id}/message", response_model=MailDetailOut, summary="查看邮件详情")
def fetch_message_detail(
    email_id: int,
    message_id: str = Query(..., description="邮件 ID(列表返回的 id)"),
    source: str = Query("graph", description="graph / imap,与列表来源一致"),
    db: Session = Depends(get_db),
) -> MailDetailOut:
    obj = crud.get(db, email_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邮箱不存在")
    _require_creds(obj)

    settings = setting_crud.get_settings(db)
    res = mail_test.fetch_message(
        email_addr=obj.email,
        refresh_token=obj.refresh_token,
        client_id=obj.client_id,
        message_id=message_id,
        source=source,
        proxy_url="",
        timeout=settings.request_timeout,
    )
    if res.new_refresh_token and res.new_refresh_token != obj.refresh_token:
        obj.refresh_token = res.new_refresh_token
        db.commit()

    return MailDetailOut(
        success=res.success,
        message=res.message,
        subject=res.subject,
        from_addr=res.from_addr,
        to_addr=res.to_addr,
        date=res.date,
        body_html=res.body_html,
        body_text=res.body_text,
    )
