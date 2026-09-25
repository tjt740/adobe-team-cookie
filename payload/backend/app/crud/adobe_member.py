import json
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember


def list_by_admin(
    db: Session, admin_id: int, *, page: int = 1, size: int = 50, keyword: str = ""
) -> tuple[list[AdobeMember], int]:
    # 子号列表不含母号自身镜像行
    stmt = select(AdobeMember).where(
        AdobeMember.admin_id == admin_id, AdobeMember.is_admin == False  # noqa: E712
    )
    if keyword:
        stmt = stmt.where(AdobeMember.email.like(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(AdobeMember.id.desc()).offset((page - 1) * size).limit(size)
        )
    )
    return items, total


def count_by_admin(db: Session, admin_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AdobeMember)
        .where(
            AdobeMember.admin_id == admin_id,
            AdobeMember.is_admin == False,  # noqa: E712
        )
    ) or 0


def get(db: Session, member_id: int) -> AdobeMember | None:
    return db.get(AdobeMember, member_id)


def get_by_email(db: Session, admin_id: int, email: str) -> AdobeMember | None:
    return db.scalar(
        select(AdobeMember).where(
            AdobeMember.admin_id == admin_id, AdobeMember.email == email
        )
    )


def count_registered(db: Session, admin_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AdobeMember)
        .where(
            AdobeMember.admin_id == admin_id,
            AdobeMember.registered == True,  # noqa: E712
            AdobeMember.is_admin == False,  # noqa: E712
        )
    ) or 0


def count_registered_with_credit(
    db: Session, admin_id: int, expected_credits: float
) -> int:
    return db.scalar(
        select(func.count())
        .select_from(AdobeMember)
        .where(
            AdobeMember.admin_id == admin_id,
            AdobeMember.registered == True,  # noqa: E712
            AdobeMember.is_admin == False,  # noqa: E712
            AdobeMember.credits.is_not(None),
            AdobeMember.credits >= expected_credits - 0.0001,
            AdobeMember.credits <= expected_credits + 0.0001,
        )
    ) or 0


def upsert(
    db: Session,
    admin_id: int,
    *,
    email: str,
    member_id: str = "",
    status: str = "",
    message: str = "",
    extra: dict | None = None,
) -> AdobeMember:
    """新增或更新成员。extra 可携带 newbanana 字段(cookie/access_token/credits 等)。"""
    row = get_by_email(db, admin_id, email)
    if row:
        if member_id:
            row.member_id = member_id
        row.status = status or row.status
        row.message = message
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = AdobeMember(
            admin_id=admin_id,
            email=email,
            member_id=member_id,
            status=status,
            message=message,
        )
        db.add(row)
    for key, value in (extra or {}).items():
        setattr(row, key, value)
    return row


def ensure_admin_self_rows(db: Session) -> None:
    """为每个母号(adobe_accounts)在号池里建立/同步一条镜像行(is_admin=True)。

    幂等:已存在则补齐缺失的收码凭据;不存在则创建。用户主动从号池删除的母号除外。
    这样母号本身也能在
    号池里协议拉取「前端生成 token」(与管理控制台的 admin_token 不同)。
    """
    accounts = list(db.scalars(select(AdobeAccount).where(AdobeAccount.pool_hidden.is_not(True))))
    changed = False
    for acc in accounts:
        row = db.scalar(
            select(AdobeMember).where(
                AdobeMember.admin_id == acc.id,
                AdobeMember.email == acc.email,
            )
        )
        if row is None:
            row = AdobeMember(
                admin_id=acc.id,
                email=acc.email,
                is_admin=True,
                status="",
                message="母号(可协议拉取前端 token)",
                refresh_token=acc.refresh_token or "",
                client_id=acc.client_id or "",
                mail_url=acc.mail_url or "",
            )
            db.add(row)
            changed = True
        else:
            # 已存在则标记为母号并同步最新收码凭据。
            # 母号登录会轮换 Microsoft refresh_token;只在字段为空时补齐会
            # 让号池镜像继续使用旧 token,导致母号后续 Firefly 登录失败。
            if not row.is_admin:
                row.is_admin = True
                changed = True
            if row.refresh_token != (acc.refresh_token or ""):
                row.refresh_token = acc.refresh_token
                changed = True
            if row.client_id != (acc.client_id or ""):
                row.client_id = acc.client_id
                changed = True
            if row.mail_url != (acc.mail_url or ""):
                row.mail_url = acc.mail_url
                changed = True
    if changed:
        db.commit()


def _pool_base_stmt():
    return select(AdobeMember, AdobeAccount.email).outerjoin(
        AdobeAccount, AdobeAccount.id == AdobeMember.admin_id
    )


def _pool_filters(
    stmt,
    *,
    keyword: str = "",
    registered_only: bool = True,
    pool_type: str = "",
    has_token: bool | None = None,
    credit_status: str = "",
    credit_value: float | None = None,
    status_filter: str = "",
    export_status: str = "",
):
    if registered_only:
        # 母号镜像行 / 导入账号始终展示(便于拉取);子号仅展示已注册可用的
        stmt = stmt.where(
            or_(
                AdobeMember.registered == True,  # noqa: E712
                AdobeMember.is_admin == True,  # noqa: E712
                AdobeMember.is_imported == True,  # noqa: E712
            )
        )
    pt = (pool_type or "").strip().lower()
    if pt == "imported":
        stmt = stmt.where(AdobeMember.is_imported == True)  # noqa: E712
    elif pt == "admin":
        stmt = stmt.where(AdobeMember.is_admin == True)  # noqa: E712
    elif pt == "sub":
        stmt = stmt.where(
            AdobeMember.is_admin == False,  # noqa: E712
            AdobeMember.is_imported == False,  # noqa: E712
        )
    if has_token is True:
        stmt = stmt.where(AdobeMember.access_token != "")
    elif has_token is False:
        stmt = stmt.where(or_(AdobeMember.access_token == "", AdobeMember.access_token.is_(None)))
    cs = (credit_status or "").strip().lower()
    if cs == "unknown":
        stmt = stmt.where(
            AdobeMember.access_token != "",
            or_(AdobeMember.credits.is_(None), AdobeMember.credits < 0),
        )
    elif cs == "known":
        stmt = stmt.where(AdobeMember.credits.is_not(None), AdobeMember.credits >= 0)
    if credit_value is not None:
        # 额度通常是整数,这里用很小区间避免浮点存储导致等值比较漏掉。
        stmt = stmt.where(
            AdobeMember.credits.is_not(None),
            AdobeMember.credits >= credit_value - 0.0001,
            AdobeMember.credits <= credit_value + 0.0001,
        )
    sf = (status_filter or "").strip().lower()
    if sf == "failed":
        stmt = stmt.where(AdobeMember.status == "failed")
    elif sf == "registered":
        stmt = stmt.where(AdobeMember.access_token != "")
    elif sf == "pending":
        stmt = stmt.where(or_(AdobeMember.access_token == "", AdobeMember.access_token.is_(None)))
    es = (export_status or "").strip().lower()
    if es == "exported":
        stmt = stmt.where(AdobeMember.exported_at.is_not(None))
    elif es == "unexported":
        stmt = stmt.where(AdobeMember.exported_at.is_(None))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(AdobeMember.email.like(like), AdobeAccount.email.like(like))
        )
    return stmt


def list_pool(
    db: Session,
    *,
    page: int = 1,
    size: int = 50,
    keyword: str = "",
    registered_only: bool = True,
    pool_type: str = "",
    has_token: bool | None = None,
    credit_status: str = "",
    credit_value: float | None = None,
    status_filter: str = "",
    export_status: str = "",
) -> tuple[list[tuple[AdobeMember, str]], int]:
    """号池:成员 + 母号自身 + 导入账号(默认只看已注册可用的),附带母号邮箱。"""
    stmt = _pool_base_stmt()
    stmt = _pool_filters(
        stmt,
        keyword=keyword,
        registered_only=registered_only,
        pool_type=pool_type,
        has_token=has_token,
        credit_status=credit_status,
        credit_value=credit_value,
        status_filter=status_filter,
        export_status=export_status,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AdobeMember.is_admin.desc(), AdobeMember.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return [(r[0], r[1] or "") for r in rows], total


def list_pool_ids(
    db: Session,
    *,
    keyword: str = "",
    registered_only: bool = True,
    pool_type: str = "",
    has_token: bool | None = None,
    credit_status: str = "",
    credit_value: float | None = None,
    status_filter: str = "",
    export_status: str = "",
) -> list[int]:
    stmt = _pool_base_stmt()
    stmt = _pool_filters(
        stmt,
        keyword=keyword,
        registered_only=registered_only,
        pool_type=pool_type,
        has_token=has_token,
        credit_status=credit_status,
        credit_value=credit_value,
        status_filter=status_filter,
        export_status=export_status,
    )
    rows = db.execute(stmt.order_by(AdobeMember.id.desc())).all()
    return [r[0].id for r in rows]


def export_pool(
    db: Session,
    *,
    keyword: str = "",
    registered_only: bool = True,
    pool_type: str = "",
    has_token: bool | None = None,
    credit_status: str = "",
    credit_value: float | None = None,
    status_filter: str = "",
    export_status: str = "",
) -> list[tuple[AdobeMember, str]]:
    stmt = _pool_base_stmt()
    stmt = _pool_filters(
        stmt,
        keyword=keyword,
        registered_only=registered_only,
        pool_type=pool_type,
        has_token=has_token,
        credit_status=credit_status,
        credit_value=credit_value,
        status_filter=status_filter,
        export_status=export_status,
    )
    rows = db.execute(
        stmt.order_by(AdobeMember.is_admin.desc(), AdobeMember.id.desc())
    ).all()
    return [(r[0], r[1] or "") for r in rows]


def import_pool_lines(db: Session, content: str) -> dict:
    """把 `邮箱----密码----ClientID----RefreshToken` 等格式直接导入号池为独立账号
    (admin_id=0, is_imported=True)。返回 {created, updated, skipped, failed, errors}。
    """
    from app.crud.email import _parse_email_line  # 复用智能解析

    def _json_items(raw: str) -> list[dict] | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return None

    def _import_record(fields: dict, line_label: str) -> tuple[bool, str, bool]:
        """Return (ok, error, existed)."""
        email = (
            fields.get("email")
            or fields.get("name")
            or fields.get("user_id")
            or fields.get("display_name")
            or ""
        ).strip()
        if not email:
            return False, f"{line_label}:缺少邮箱/name", False
        rt = fields.get("refresh_token") or ""
        cid = fields.get("client_id") or ""
        mail_url = fields.get("mail_url") or ""
        access_token = fields.get("access_token") or ""
        device_token = fields.get("device_token") or ""
        device_id = fields.get("device_id") or ""
        cookie = fields.get("cookie") or ""
        has_ready_token = bool(access_token or device_token)
        if not (has_ready_token or (rt and cid) or mail_url):
            return False, f"{line_label}:缺少 token 或 Refresh Token / Client ID 或取信配置", False
        row = db.scalar(
            select(AdobeMember).where(
                AdobeMember.admin_id == 0, AdobeMember.email == email
            )
        )
        existed = bool(row)
        if row is None:
            row = AdobeMember(
                admin_id=0,
                email=email,
                is_imported=True,
            )
            db.add(row)
        row.is_imported = True
        row.status = "registered" if access_token else (row.status or "")
        row.message = "导入(已有 FF-iOS token)" if access_token else "导入(可协议拉取前端 token)"
        row.registered = bool(access_token) or row.registered
        if rt:
            row.refresh_token = rt
        if cid:
            row.client_id = cid
        if mail_url:
            row.mail_url = mail_url
        if access_token:
            row.access_token = access_token
        if device_token:
            row.device_token = device_token
        if device_id:
            row.device_id = device_id
        if cookie:
            row.cookie = cookie
        if fields.get("display_name"):
            row.display_name = fields.get("display_name") or ""
        if fields.get("credits") is not None:
            try:
                row.credits = float(fields.get("credits"))
            except (TypeError, ValueError):
                pass
        if fields.get("expires_at") is not None:
            try:
                row.expires_at = int(fields.get("expires_at"))
            except (TypeError, ValueError):
                pass
        row.updated_at = datetime.now(timezone.utc)
        return True, "", existed

    created = updated = failed = 0
    errors: list[str] = []
    json_items = _json_items(content.strip())
    if json_items is not None:
        for idx, item in enumerate(json_items, start=1):
            ok, err, existed = _import_record(item, f"第 {idx} 条")
            if ok:
                updated += 1 if existed else 0
                created += 0 if existed else 1
            else:
                failed += 1
                errors.append(err)
        db.commit()
        return {"created": created, "updated": updated, "skipped": 0,
                "failed": failed, "errors": errors}

    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        fields = _parse_email_line(line)
        if not fields:
            failed += 1
            errors.append(f"第 {line_no} 行:邮箱格式无效")
            continue
        ok, err, existed = _import_record(fields, f"第 {line_no} 行")
        if ok:
            if existed:
                updated += 1
            else:
                created += 1
        else:
            failed += 1
            errors.append(err)
            continue
    db.commit()
    return {"created": created, "updated": updated, "skipped": 0,
            "failed": failed, "errors": errors}


def get_many(db: Session, ids: list[int]) -> list[AdobeMember]:
    return list(db.scalars(select(AdobeMember).where(AdobeMember.id.in_(ids))))


def delete_many(db: Session, admin_id: int, ids: list[int]) -> list[AdobeMember]:
    rows = list(
        db.scalars(
            select(AdobeMember).where(
                AdobeMember.admin_id == admin_id, AdobeMember.id.in_(ids)
            )
        )
    )
    return rows
