from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.crud.email import _parse_email_line
from app.models.external_member import ExternalMember


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
    return list(db.scalars(select(ExternalMember).where(ExternalMember.id.in_(ids))))


def import_lines(db: Session, content: str, on_duplicate: str = "skip", *, operator: str = "") -> dict:
    """导入 `邮箱----密码----ClientID----RefreshToken`(复用 _parse_email_line)。

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
    login_keys: set[str] = set()  # 本次新增/更新的邮箱(小写),导入后要跑登录
    for line_no, raw in enumerate((content or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        fields = _parse_email_line(line)
        if not fields:
            failed += 1
            errors.append(f"第 {line_no} 行:邮箱格式无效")
            continue
        email = fields["email"]
        rt = fields.get("refresh_token") or ""
        cid = fields.get("client_id") or ""
        mail_url = fields.get("mail_url") or ""
        if not ((rt and cid) or mail_url):
            failed += 1
            errors.append(f"第 {line_no} 行:缺少 ClientID/RefreshToken 或取信接口")
            continue
        key = email.lower()
        row = seen.get(key)
        if row is not None:
            # 本次调用内的重复行:不再走 DB 查重/二次 INSERT,直接复用同一行对象。
            if on_duplicate == "skip":
                skipped += 1
                continue
            updated += 1
            login_keys.add(key)
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
            login_keys.add(key)
        row.mail_password = fields.get("password") or row.mail_password
        # 导入行带了第 5 段就以它为准(覆盖此前自动写入的默认密码)
        row.adobe_password = fields.get("adobe_password") or row.adobe_password
        row.client_id = cid or row.client_id
        row.refresh_token = rt or row.refresh_token
        row.mail_url = mail_url or row.mail_url
        row.operator = operator
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    ids = [seen[k].id for k in login_keys if seen.get(k) is not None and seen[k].id is not None]
    return {"created": created, "updated": updated, "skipped": skipped,
            "failed": failed, "errors": errors, "ids": ids}


def list_members(
    db: Session,
    *,
    page: int = 1,
    size: int = 20,
    login_status: str | None = None,
    subscription_ok: bool | None = None,
    keyword: str = "",
) -> tuple[list[ExternalMember], int]:
    stmt = select(ExternalMember)
    if login_status:
        stmt = stmt.where(ExternalMember.login_status == login_status)
    if subscription_ok is not None:
        stmt = stmt.where(ExternalMember.subscription_ok == subscription_ok)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(ExternalMember.email.like(like), ExternalMember.message.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(ExternalMember.id.desc()).offset((page - 1) * size).limit(size)
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
) -> list[dict]:
    stmt = select(ExternalMember).where(ExternalMember.cookie != "")
    if ids is not None:
        stmt = stmt.where(ExternalMember.id.in_(ids))
    if login_status:
        stmt = stmt.where(ExternalMember.login_status == login_status)
    if subscription_ok is not None:
        stmt = stmt.where(ExternalMember.subscription_ok == subscription_ok)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(ExternalMember.email.like(like), ExternalMember.message.like(like)))
    rows = db.scalars(stmt.order_by(ExternalMember.id.desc())).all()
    return [{"cookie": r.cookie} for r in rows if (r.cookie or "").strip()]


def delete_many(db: Session, ids: list[int]) -> int:
    rows = get_many(db, ids)
    for r in rows:
        db.delete(r)
    db.commit()
    return len(rows)
