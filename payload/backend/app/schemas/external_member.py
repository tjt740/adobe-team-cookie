from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.adobe_account import JobStatusOut
from app.schemas.account_profile import AccountProfile, ProfilePreference

AccountState = Annotated[str, StringConstraints(pattern=r"^(ok|never|login_failed|account_disabled|rate_limited|internal|has_cookie|no_cookie|has_password|no_password|task_(pending|running|otp|done|failed|interrupted|cancelled|paused|pausing|cancelling)|sub2_(error|other|recovered|unknown|[45][0-9]{2}))$")]

OtpMode = Literal["auto", "manual"]
CreditsField = Literal["available", "total"]
Sub2SyncStatus = Literal["not_pushed", "pending", "syncing", "synced", "failed"]
CurrentProfileKind = Literal["personal", "organization", "unknown"]


class ManualOtpChallenge(BaseModel):
    request_id: str
    email: str
    expires_at: int


class ExternalMemberOut(BaseModel):
    """列表项(不含 cookie/token 等敏感原文)。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    note: str = ""
    credits_available: float | None = None
    credits_total: float | None = None
    credits_error: str = ""
    account_profile: AccountProfile | None = None
    profile_preference: ProfilePreference = ""
    login_status: str = "never"
    subscription_ok: bool = False
    first_login_done: bool = False
    has_cookie: bool = False
    # 只回「有没有」,不回明文密码
    has_adobe_password: bool = False
    force_code_login: bool = False
    uses_supply_mail: bool = False
    otp_mode: OtpMode = "auto"
    otp_challenge: ManualOtpChallenge | None = None
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
    profile_preference: ProfilePreference | None = None
    otp_mode: OtpMode | None = None


class ExternalOtpModeUpdate(BaseModel):
    otp_mode: OtpMode


class ExternalOtpSubmit(BaseModel):
    request_id: str = Field(min_length=32, max_length=32, pattern="^[a-f0-9]{32}$")
    code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class ExternalProfilePreferenceUpdate(BaseModel):
    profile_preference: ProfilePreference


class ExternalNoteUpdate(BaseModel):
    note: str = Field(max_length=1000)


class SupplyMailConfigUpdate(BaseModel):
    # None / 空串保留已保存的 Token，显式 clear_token 才清除。
    token: str | None = Field(default=None, max_length=512)
    clear_token: bool = False


class ExternalBatchProfilePreferenceUpdate(ExternalProfilePreferenceUpdate):
    ids: list[int] = Field(min_length=1)


class ExternalLoginFilter(BaseModel):
    account_states: list[AccountState] = Field(default_factory=list, max_length=32)
    login_status: str | None = None
    subscription_ok: bool | None = None
    keyword: str = ""
    in_stock: bool | None = None
    sub2_status: Sub2SyncStatus | None = None
    sub2_health: str | None = Field(default=None, pattern=r"^(error|other|recovered|unknown|[45][0-9]{2})$")
    imported_from: datetime | None = None
    imported_before: datetime | None = None
    credits_field: CreditsField = "available"
    credits_min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    credits_max: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    current_profile: CurrentProfileKind | None = None
    is_company: bool | None = None


class ExternalMemberExportItem(BaseModel):
    cookie: str
