from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdobeAccount(Base):
    """adminconsole.adobe.com 团队管理账号。"""

    __tablename__ = "adobe_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # 号池平台归属:adobe_gemini(banana,默认)/ adobe_gpt(生图)。子号从其母号 platform 推导,不单独存列。
    platform: Mapped[str] = mapped_column(String(32), default="adobe_gemini", server_default="adobe_gemini")
    hotmail_password: Mapped[str] = mapped_column(String(255), default="")
    adobe_password: Mapped[str] = mapped_column(String(255), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    client_id: Mapped[str] = mapped_column(String(255), default="")
    # 可选:第三方取信接口 URL,用于 Microsoft Graph/IMAP 授权不可用的母号。
    mail_url: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    # 管理有效性:None=未检测, True=能登录且有组织/权限, False=无效
    is_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    check_message: Mapped[str] = mapped_column(String(500), default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ---- Adobe Admin Console 管理态 ----
    # 是否拥有组织(企业/团队管理权限)
    has_org: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    admin_token: Mapped[str] = mapped_column(Text, default="")
    admin_cookie: Mapped[str] = mapped_column(Text, default="")
    org_id: Mapped[str] = mapped_column(String(255), default="")
    product_id: Mapped[str] = mapped_column(String(255), default="")
    product_name: Mapped[str] = mapped_column(String(255), default="")
    license_group_id: Mapped[str] = mapped_column(String(255), default="")
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ---- 收邮件(OTP)健康度 ----
    mail_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    mail_message: Mapped[str] = mapped_column(String(500), default="")
    mail_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
