from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ExternalMember(Base):
    """外部导入的独立企业子号。

    与 adobe_members 隔离:不参与母号/组织编排,也不被 autopilot / sub2 /
    member_cleanup 等自动化扫描。cookie 由对外接口按需实时重登刷新。
    """

    __tablename__ = "external_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # 导入的微软邮箱凭据(收 Adobe 验证码用):邮箱----密码----ClientID----RefreshToken
    mail_password: Mapped[str] = mapped_column(String(255), default="")
    # 这个号的 Adobe 账号密码。导入行带第 5 段就用那一段;自己补全注册的号
    # 则在首登成功后写入我们设的默认密码(adobe_admin.COMPLETE_PASSWORD)。
    adobe_password: Mapped[str] = mapped_column(String(255), default="")
    client_id: Mapped[str] = mapped_column(String(255), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    mail_url: Mapped[str] = mapped_column(Text, default="")

    # 登录产出
    cookie: Mapped[str] = mapped_column(Text, default="")
    access_token: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_available: Mapped[float | None] = mapped_column(Float, nullable=True)
    credits_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 状态
    first_login_done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # never / ok / login_failed / account_disabled / rate_limited / internal
    login_status: Mapped[str] = mapped_column(String(32), default="never", index=True)
    subscription_ok: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message: Mapped[str] = mapped_column(String(500), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
