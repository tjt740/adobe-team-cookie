from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.adobe_account import AdobeAccount
from app.schemas.adobe_account import AdobeAccountCreate, AdobeAccountUpdate
from app.schemas.common import BatchImportResult


def list_accounts(
    db: Session, *, page: int = 1, size: int = 20, keyword: str = ""
) -> tuple[list[AdobeAccount], int]:
    stmt = select(AdobeAccount)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AdobeAccount.email.like(like),
                AdobeAccount.client_id.like(like),
                AdobeAccount.remark.like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(AdobeAccount.id.desc()).offset((page - 1) * size).limit(size)
        )
    )
    return items, total


def get(db: Session, account_id: int) -> AdobeAccount | None:
    return db.get(AdobeAccount, account_id)


def get_by_email(db: Session, email: str) -> AdobeAccount | None:
    return db.scalar(select(AdobeAccount).where(AdobeAccount.email == email))


def list_by_ids(db: Session, ids: list[int]) -> list[AdobeAccount]:
    if not ids:
        return []
    return list(db.scalars(select(AdobeAccount).where(AdobeAccount.id.in_(ids))))


def create(db: Session, data: AdobeAccountCreate) -> AdobeAccount:
    account = AdobeAccount(**data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update(db: Session, account: AdobeAccount, data: AdobeAccountUpdate) -> AdobeAccount:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


def delete(db: Session, account: AdobeAccount) -> None:
    db.delete(account)
    db.commit()


def delete_many(db: Session, ids: list[int]) -> int:
    accounts = list(db.scalars(select(AdobeAccount).where(AdobeAccount.id.in_(ids))))
    for acc in accounts:
        db.delete(acc)
    db.commit()
    return len(accounts)


def batch_import(db: Session, content: str, on_duplicate: str = "skip",
                 platform: str = "adobe_gemini") -> BatchImportResult:
    """解析格式:邮箱|Hotmail密码|Adobe密码|Refresh Token|Client ID|取信URL(可选)。 
    platform=这批母号所属号池平台(adobe_gemini/adobe_gpt)。"""
    result = BatchImportResult(created=0, updated=0, skipped=0, failed=0)

    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        email = parts[0] if parts else ""
        if not email or "@" not in email:
            result.failed += 1
            result.errors.append(f"第 {line_no} 行:邮箱格式无效")
            continue

        fields = {
            "email": email,
            "hotmail_password": parts[1] if len(parts) > 1 else "",
            "adobe_password": parts[2] if len(parts) > 2 else "",
            "refresh_token": parts[3] if len(parts) > 3 else "",
            "client_id": parts[4] if len(parts) > 4 else "",
            "mail_url": parts[5] if len(parts) > 5 else "",
            "platform": platform or "adobe_gemini",
        }

        existing = get_by_email(db, email)
        if existing:
            if on_duplicate == "overwrite":
                for k, v in fields.items():
                    setattr(existing, k, v)
                result.updated += 1
            else:
                result.skipped += 1
            continue

        db.add(AdobeAccount(**fields))
        result.created += 1

    db.commit()
    return result
