from datetime import datetime, timezone
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.crud.email import _parse_email_line
from app.models.external_member import ExternalMember
from app.schemas.account_profile import ProfilePreference
from app.schemas.external_member import OtpMode


def get(db: Session, mid: int) -> ExternalMember | None:
    return db.get(ExternalMember, mid)


def get_by_email(db: Session, email: str) -> ExternalMember | None:
    e = (email or "").strip()
    if not e:
        return None
    return db.scalar(
        select(ExternalMember).where(func.lower(ExternalMember.email) == e.lower())
    )


def get_many(db: Session, ids: list[int]) -> list[ExternalMember]:
    if not ids:
        return []
    rows = {row.id: row for row in db.scalars(select(ExternalMember).where(ExternalMember.id.in_(ids)))}
    return [rows[mid] for mid in dict.fromkeys(ids) if mid in rows]


def import_lines(db: Session, content: str, on_duplicate: str = "skip", *, operator: str = "",
                 profile_preference: ProfilePreference | None = None,
                 otp_mode: OtpMode | None = None) -> dict:
    """导入邮箱、账号密码或完整邮箱凭据。

    同一次 ``content`` 内出现重复邮箱时(常见于粘贴的名单本身带重复行),
    不能仅靠 ``get_by_email`` 查库判重——本次调用只在结尾统一 ``commit()``,
    session 是 ``autoflush=False``,同批 ``db.add()`` 的新行查不到,会导致
    第二条重复行再次 INSERT 触发 email 唯一约束的 IntegrityError,进而让
    整批(含更早已成功的行)一起回滚。因此额外维护一个"本次调用内已处理
    邮箱 -> 行对象"的本地映射,判重时同时查库 + 查本地映射。
    """
    created = updated = skipped = failed = 0
    errors: list[str] = []
    seen: dict[str, ExternalMember] = {}  # 本次调用内已处理的邮箱(小写)-> 行对象
    login_keys: dict[str, None] = {}  # 按首次出现的顺序登录，同批重复邮箱只登录一次
    for line_no, raw in enumerate((content or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        # 两段格式明确是 Adobe 密码，不能按 UUID/M./URL 等特征猜测密码用途。
        sep = "----" if "----" in line else "|" if "|" in line else "\t"
        parts = line.split(sep)
        email_only = len(parts) == 1
        password_only = len(parts) == 2
        fields = ({"email": parts[0].strip(), "adobe_password": parts[1].strip()}
                  if password_only else _parse_email_line(line))
        if fields and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", fields["email"]):
            fields = None
        if not fields:
            failed += 1
            errors.append(f"第 {line_no} 行:邮箱格式无效")
            continue
        email = fields["email"]
        rt = fields.get("refresh_token") or ""
        cid = fields.get("client_id") or ""
        mail_url = fields.get("mail_url") or ""
        if not (email_only or (rt and cid) or mail_url or fields.get("adobe_password")):
            failed += 1
            errors.append(f"第 {line_no} 行:缺少 Adobe 密码、ClientID/RefreshToken 或取信接口")
            continue
        key = email.lower()
        row = seen.get(key)
        if row is not None:
            # 本次调用内的重复行:不再走 DB 查重/二次 INSERT,直接复用同一行对象。
            if on_duplicate == "skip":
                skipped += 1
                continue
            updated += 1
            login_keys[key] = None
        else:
            row = get_by_email(db, email)
            if row is not None:
                if on_duplicate == "skip":
                    skipped += 1
                    seen[key] = row
                    continue
                updated += 1
            else:
                row = ExternalMember(email=email)
                db.add(row)
                created += 1
            seen[key] = row
            login_keys[key] = None
        row.mail_password = fields.get("password") or row.mail_password
        # 导入行带了第 5 段就以它为准(覆盖此前自动写入的默认密码)
        row.adobe_password = fields.get("adobe_password") or row.adobe_password
        row.force_code_login = email_only
        if otp_mode is not None:
            row.otp_mode = otp_mode
        row.client_id = cid or row.client_id
        row.refresh_token = rt or row.refresh_token
        row.mail_url = mail_url or row.mail_url
        row.operator = operator
        if profile_preference is not None:
            row.profile_preference = profile_preference
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    ids = [seen[k].id for k in login_keys if seen.get(k) is not None and seen[k].id is not None]
    return {"created": created, "updated": updated, "skipped": skipped,
            "failed": failed, "errors": errors, "ids": ids}


def _filtered_members(
    *,
    login_status: str | None = None,
    subscription_ok: bool | None = None,
    keyword: str = "",
    ids: list[int] | None = None,
    imported_from: datetime | None = None,
    imported_before: datetime | None = None,
):
    stmt = select(ExternalMember)
    if ids is not None:
        stmt = stmt.where(ExternalMember.id.in_(ids))
    if imported_from is not None:
        stmt = stmt.where(ExternalMember.created_at >= imported_from)
    if imported_before is not None:
        stmt = stmt.where(ExternalMember.created_at < imported_before)
    if login_status:
        stmt = stmt.where(ExternalMember.login_status == login_status)
    if subscription_ok is not None:
        stmt = stmt.where(ExternalMember.subscription_ok == subscription_ok)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(ExternalMember.email.like(like), ExternalMember.message.like(like)))
    return stmt


def list_members(
    db: Session,
    *,
    page: int = 1,
    size: int | None = 200,
    login_status: str | None = None,
    subscription_ok: bool | None = None,
    keyword: str = "",
    ids: list[int] | None = None,
    imported_from: datetime | None = None,
    imported_before: datetime | None = None,
) -> tuple[list[ExternalMember], int]:
    stmt = _filtered_members(login_status=login_status, subscription_ok=subscription_ok,
                             keyword=keyword, ids=ids, imported_from=imported_from,
                             imported_before=imported_before)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(ExternalMember.id.desc()).offset((page - 1) * size if size is not None else 0).limit(size)
        )
    )
    return items, total


def export_cookies(
    db: Session,
    *,
    login_status: str | None = None,
    subscription_ok: bool | None = None,
    keyword: str = "",
    ids: list[int] | None = None,
    imported_from: datetime | None = None,
    imported_before: datetime | None = None,
) -> list[dict]:
    stmt = _filtered_members(login_status=login_status, subscription_ok=subscription_ok,
                             keyword=keyword, ids=ids, imported_from=imported_from,
                             imported_before=imported_before).where(ExternalMember.cookie != "")
    rows = db.scalars(stmt.order_by(ExternalMember.id.desc())).all()
    return [{"cookie": r.cookie} for r in rows if (r.cookie or "").strip()]


def delete_many(db: Session, ids: list[int]) -> int:
    rows = get_many(db, ids)
    for r in rows:
        db.delete(r)
    db.commit()
    return len(rows)
