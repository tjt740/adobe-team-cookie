from sqlalchemy import inspect, text

from app.core.config import settings
from app.crud import user as user_crud
from app.db.session import Base, SessionLocal, engine

# 确保模型被导入,以便 create_all 能识别到表
from app.models import adobe_account as _adobe_model  # noqa: F401
from app.models import adobe_member as _adobe_member_model  # noqa: F401
from app.models import email as _email_model  # noqa: F401
from app.models import external_member as _external_member_model  # noqa: F401
from app.models import setting as _setting_model  # noqa: F401
from app.models import user as _user_model  # noqa: F401

# 针对已存在的表新增的列(SQLite 轻量迁移):表名 -> {列名: 列定义}
_MIGRATIONS: dict[str, dict[str, str]] = {
    "adobe_accounts": {
        "is_valid": "BOOLEAN",
        "check_message": "VARCHAR(500) DEFAULT ''",
        "last_checked_at": "DATETIME",
        "has_org": "BOOLEAN",
        "admin_token": "TEXT DEFAULT ''",
        "admin_cookie": "TEXT DEFAULT ''",
        "org_id": "VARCHAR(255) DEFAULT ''",
        "product_id": "VARCHAR(255) DEFAULT ''",
        "product_name": "VARCHAR(255) DEFAULT ''",
        "license_group_id": "VARCHAR(255) DEFAULT ''",
        "member_count": "INTEGER DEFAULT 0",
        "mail_url": "TEXT DEFAULT ''",
        "last_login_at": "DATETIME",
        "mail_ok": "BOOLEAN",
        "mail_message": "VARCHAR(500) DEFAULT ''",
        "mail_checked_at": "DATETIME",
    },
    "adobe_members": {
        "display_name": "VARCHAR(255) DEFAULT ''",
        "cookie": "TEXT DEFAULT ''",
        "access_token": "TEXT DEFAULT ''",
        "arp_session_id": "TEXT DEFAULT ''",
        "credits": "FLOAT",
        "expires_at": "INTEGER",
        "registered": "BOOLEAN DEFAULT 0",
        "is_admin": "BOOLEAN DEFAULT 0",
        "is_imported": "BOOLEAN DEFAULT 0",
        "refresh_token": "TEXT DEFAULT ''",
        "client_id": "VARCHAR(255) DEFAULT ''",
        "mail_url": "TEXT DEFAULT ''",
        "device_token": "TEXT DEFAULT ''",
        "device_id": "VARCHAR(64) DEFAULT ''",
        "exported_at": "DATETIME",
        "export_count": "INTEGER DEFAULT 0",
    },
    "emails": {
        "mail_url": "TEXT DEFAULT ''",
    },
    "external_members": {
        "mail_password": "VARCHAR(255) DEFAULT ''",
        "adobe_password": "VARCHAR(255) DEFAULT ''",
        "client_id": "VARCHAR(255) DEFAULT ''",
        "refresh_token": "TEXT DEFAULT ''",
        "mail_url": "TEXT DEFAULT ''",
        "cookie": "TEXT DEFAULT ''",
        "access_token": "TEXT DEFAULT ''",
        "expires_at": "INTEGER",
        "credits_available": "FLOAT",
        "credits_total": "FLOAT",
        "first_login_done": "BOOLEAN DEFAULT 0",
        "login_status": "VARCHAR(32) DEFAULT 'never'",
        "subscription_ok": "BOOLEAN DEFAULT 0",
        "last_login_at": "DATETIME",
        "message": "VARCHAR(500) DEFAULT ''",
    },
}


def _run_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    with engine.begin() as conn:
        for table, columns in _MIGRATIONS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    print(f"[init_db] 迁移:为 {table} 新增列 {name}")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()

    db = SessionLocal()
    try:
        existing = user_crud.get_by_username(db, settings.FIRST_ADMIN_USERNAME)
        if not existing:
            user_crud.create_user(
                db,
                username=settings.FIRST_ADMIN_USERNAME,
                password=settings.FIRST_ADMIN_PASSWORD,
                nickname=settings.FIRST_ADMIN_NICKNAME,
                is_superuser=True,
            )
            print(
                f"[init_db] 已创建默认管理员: {settings.FIRST_ADMIN_USERNAME} "
                f"/ {settings.FIRST_ADMIN_PASSWORD}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("[init_db] 数据库初始化完成")
