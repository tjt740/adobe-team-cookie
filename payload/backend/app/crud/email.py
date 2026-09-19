import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.email import Email
from app.schemas.common import BatchImportResult
from app.schemas.email import EmailCreate, EmailUpdate

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_MOEMAIL_DOMAINS = {"edu0.buzz", "edu1.store", "edu6.site", "edu8.buzz"}
_EMAIL_COLUMNS = {c.name for c in Email.__table__.columns}


def _parse_email_line(line: str) -> dict[str, str] | None:
    """智能解析一行账号,兼容两种分隔符与字段顺序。

    支持::

        邮箱|密码|RefreshToken|ClientID
        邮箱----密码----ClientID----RefreshToken
        邮箱----密码----ClientID----RefreshToken----Adobe密码
        邮箱----密码----https://api.xxx/mail-new?refresh_token=...&client_id=...

    按字段特征归位:含 ``@`` 的是邮箱;UUID 形态的是 client_id;
    取信 URL 会保存为 mail_url,若 query 里带 refresh_token/client_id 则提取;
    以 ``M.`` 开头的是 Microsoft refresh_token;其余短串当作密码 —— 第一个是邮箱
    密码,第二个(若有)是这个号自己的 Adobe 密码。
    """
    if "----" in line:
        parts = [p.strip() for p in line.split("----")]
    elif "|" in line:
        parts = [p.strip() for p in line.split("|")]
    else:
        parts = [line.strip()]
    parts = [p for p in parts if p]
    if not parts:
        return None

    email = ""
    rest: list[str] = []
    for p in parts:
        if "@" in p and not email:
            email = p
        else:
            rest.append(p)
    if not email or "@" not in email:
        return None

    client_id = ""
    refresh_token = ""
    mail_url = ""
    moemail_api_key = ""
    moemail_email_id = ""
    leftover: list[str] = []
    for p in rest:
        parsed = urlparse(p)
        if parsed.scheme == "moemail":
            mail_url = p
            continue
        if p.startswith("mk_"):
            moemail_api_key = p
            continue
        if parsed.scheme in ("http", "https"):
            mail_url = mail_url or p
            if parsed.query:
                qs = parse_qs(parsed.query)
                if not refresh_token:
                    refresh_token = (qs.get("refresh_token") or [""])[0].strip()
                if not client_id:
                    client_id = (qs.get("client_id") or [""])[0].strip()
                if not moemail_api_key:
                    moemail_api_key = (qs.get("api_key") or qs.get("key") or [""])[0].strip()
                if not moemail_email_id:
                    moemail_email_id = (qs.get("email_id") or qs.get("emailId") or [""])[0].strip()
            continue
        if not client_id and _UUID_RE.match(p):
            if moemail_api_key:
                moemail_email_id = p
            else:
                client_id = p
        elif p.startswith("M."):
            refresh_token = p
        elif not refresh_token and len(p) > 60:
            refresh_token = p
        else:
            leftover.append(p)

    domain = email.rsplit("@", 1)[-1].lower()
    if moemail_api_key and domain in _MOEMAIL_DOMAINS and not mail_url.startswith("moemail://"):
        qs = {"api_key": moemail_api_key}
        if moemail_email_id:
            qs["email_id"] = moemail_email_id
        mail_url = f"moemail://edu6.site?{urlencode(qs)}"

    password = leftover[0] if leftover else ""
    # 第二个短串是这个号自己的 Adobe 密码(导入行末尾那一段),没有就是空。
    adobe_password = leftover[1] if len(leftover) > 1 else ""
    return {
        "email": email,
        "password": password,
        "adobe_password": adobe_password,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "mail_url": mail_url,
    }


def list_emails(
    db: Session,
    *,
    page: int = 1,
    size: int = 20,
    keyword: str = "",
    is_used: bool | None = None,
) -> tuple[list[Email], int]:
    stmt = select(Email)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Email.email.like(like), Email.remark.like(like)))
    if is_used is not None:
        stmt = stmt.where(Email.is_used == is_used)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(stmt.order_by(Email.id.desc()).offset((page - 1) * size).limit(size))
    )
    return items, total


def get(db: Session, email_id: int) -> Email | None:
    return db.get(Email, email_id)


def get_by_email(db: Session, email: str) -> Email | None:
    return db.scalar(select(Email).where(Email.email == email))


def take_unused(
    db: Session, count: int, exclude: set[str] | None = None
) -> list[Email]:
    """取出最多 count 个未使用的邮箱(不在此处标记已用)。

    ``exclude`` 是已被其它任务预占的邮箱(小写),用于并发拉号时避免争用。
    """
    if count <= 0:
        return []
    exclude = exclude or set()
    # 多取一些以便过滤掉已预占的,再截断到 count
    rows = list(
        db.scalars(
            select(Email)
            .where(Email.is_used == False)  # noqa: E712
            .order_by(Email.id.asc())
            .limit(count + len(exclude) + 10)
        )
    )
    if exclude:
        rows = [r for r in rows if r.email.lower() not in exclude]
    return rows[:count]


def mark_used_by_email(db: Session, email: str) -> None:
    row = get_by_email(db, email)
    if row and not row.is_used:
        row.is_used = True
        row.used_at = datetime.now(timezone.utc)


def create(db: Session, data: EmailCreate) -> Email:
    obj = Email(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, obj: Email, data: EmailUpdate) -> Email:
    payload = data.model_dump(exclude_unset=True)
    if "is_used" in payload:
        obj.used_at = datetime.now(timezone.utc) if payload["is_used"] else None
    for field, value in payload.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_many(db: Session, ids: list[int]) -> int:
    objs = list(db.scalars(select(Email).where(Email.id.in_(ids))))
    for obj in objs:
        db.delete(obj)
    db.commit()
    return len(objs)


def batch_import(db: Session, content: str, on_duplicate: str = "skip") -> BatchImportResult:
    """批量导入,兼容两种格式(每行一条):

    - ``邮箱|密码|RefreshToken|ClientID``
    - ``邮箱----密码----ClientID----RefreshToken``
    """
    result = BatchImportResult(created=0, updated=0, skipped=0, failed=0)

    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        fields = _parse_email_line(line)
        if not fields:
            result.failed += 1
            result.errors.append(f"第 {line_no} 行:邮箱格式无效")
            continue
        email = fields["email"]
        # 只取 Email 表真有的列:_parse_email_line 是跟外部子号等共用的,
        # 它多返回一个字段(如 adobe_password)不能把邮箱池导入整个带崩。
        data = {k: v for k, v in fields.items() if k in _EMAIL_COLUMNS}

        existing = get_by_email(db, email)
        if existing:
            if on_duplicate == "overwrite":
                for k, v in data.items():
                    setattr(existing, k, v)
                result.updated += 1
            else:
                result.skipped += 1
            continue

        db.add(Email(**data))
        result.created += 1

    db.commit()
    return result
