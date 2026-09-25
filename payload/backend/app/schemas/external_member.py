from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.adobe_account import JobStatusOut
from app.schemas.account_profile import AccountProfile


class ExternalMemberOut(BaseModel):
    """列表项(不含 cookie/token 等敏感原文)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    credits_available: float | None = None
    credits_total: float | None = None
    account_profile: AccountProfile | None = None
    login_status: str = "never"
    subscription_ok: bool = False
    first_login_done: bool = False
    has_cookie: bool = False
    # 只回「有没有」,不回明文密码
    has_adobe_password: bool = False
    last_login_at: datetime | None = None
    message: str = ""
    created_at: datetime
    operator: str = ""
    latest_job: JobStatusOut | None = None
    sub2_status: str = "not_pushed"
    sub2_message: str = ""
    sub2_account_id: int | None = None
    sub2_synced_at: str | None = None


class ExternalImportRequest(BaseModel):
    content: str
    on_duplicate: str = Field(default="skip", pattern="^(skip|overwrite)$")


class ExternalMemberExportItem(BaseModel):
    cookie: str
