from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdobeMember(Base):
    """某个管理账号(org)下批量添加的子账号(成员)。

    号池:registered=True 且有 cookie/access_token 的成员即可导出为 newbanana 格式。
    """

    __tablename__ = "adobe_members"
    __table_args__ = (UniqueConstraint("admin_id", "email", name="uq_admin_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    member_id: Mapped[str] = mapped_column(String(255), default="")
    # 状态:granted=已授权, registered=已注册可用, member=已是成员,
    #       failed=失败, removed_failed=移除失败
    status: Mapped[str] = mapped_column(String(32), default="")
    message: Mapped[str] = mapped_column(String(500), default="")

    # ---- newbanana 号池字段 ----
    display_name: Mapped[str] = mapped_column(String(255), default="")
    cookie: Mapped[str] = mapped_column(Text, default="")
    access_token: Mapped[str] = mapped_column(Text, default="")
    arp_session_id: Mapped[str] = mapped_column(Text, default="")
    credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registered: Mapped[bool] = mapped_column(default=False, index=True)
    # True 表示这条是「母号」自身(adobe_accounts 的镜像行),用于在号池里也能拉
    # 母号自己的前端生成 token(与管理控制台的 admin_token 不同)。
    is_admin: Mapped[bool] = mapped_column(default=False, index=True)
    # True 表示这条是直接「导入」的独立账号(不属于平台母号,admin_id=0)。
    is_imported: Mapped[bool] = mapped_column(default=False, index=True)
    # 子号自身邮箱的 OAuth(收 OTP 用,便于以后续期/重登)
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    client_id: Mapped[str] = mapped_column(String(255), default="")
    # 可选:第三方取信接口 URL(例如 xiaoheifk mail-new),用于 Graph/IMAP 不兼容的邮箱
    mail_url: Mapped[str] = mapped_column(Text, default="")
    # FF-iOS 受信任登录:device_token(约 1 年)可免验证码刷新 access_token;
    # device_id 是该号绑定的「设备」标识(刷新时需原样回传)。
    device_token: Mapped[str] = mapped_column(Text, default="")
    device_id: Mapped[str] = mapped_column(String(64), default="")
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    export_count: Mapped[int] = mapped_column(Integer, default=0)
    # 已推送进 Sub2 的时间戳。Sub2 实存去重对 token/cookie 分叉号会漏配(账号身份≠cookie
    # 解析身份)→ 同一号每轮被当"待推"反复重推成"更新"空转。推送成功即打此标,
    # _candidates 跳过已打标的,根治影子待推。被余额自愈删本地时此行一并删除,不留残标。
    sub2_pushed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
