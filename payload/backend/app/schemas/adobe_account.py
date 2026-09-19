from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdobeAccountBase(BaseModel):
    email: str
    hotmail_password: str = ""
    adobe_password: str = ""
    refresh_token: str = ""
    client_id: str = ""
    mail_url: str = ""
    remark: str = ""
    platform: str = "adobe_gemini"   # 号池平台归属:adobe_gemini(banana)/ adobe_gpt(生图)


class AdobeAccountCreate(AdobeAccountBase):
    pass


class AdobeAccountUpdate(BaseModel):
    email: str | None = None
    hotmail_password: str | None = None
    adobe_password: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    mail_url: str | None = None
    remark: str | None = None
    platform: str | None = None


class AdobeAccountOut(AdobeAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_valid: bool | None = None
    check_message: str = ""
    last_checked_at: datetime | None = None
    has_org: bool | None = None
    org_id: str = ""
    product_name: str = ""
    member_count: int = 0
    last_login_at: datetime | None = None
    mail_ok: bool | None = None
    mail_message: str = ""
    mail_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TestEmailResult(BaseModel):
    success: bool
    message: str
    inbox_total: int | None = None
    latest_subject: str | None = None
    latest_from: str | None = None


class AdminActionResult(BaseModel):
    """登录 / 检测 等管理动作的结果。"""

    success: bool
    message: str
    has_org: bool | None = None
    org_id: str = ""
    product_name: str = ""
    org_count: int = 0
    product_count: int = 0
    logs: list[str] = []


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    email: str
    member_id: str = ""
    status: str = ""
    message: str = ""
    display_name: str = ""
    credits: float | None = None
    expires_at: int | None = None
    registered: bool = False
    created_at: datetime
    updated_at: datetime


class PoolItemOut(BaseModel):
    """号池条目(跨母号),含 newbanana 字段。"""

    id: int
    admin_id: int
    admin_email: str = ""
    email: str
    display_name: str = ""
    member_id: str = ""
    status: str = ""
    credits: float | None = None
    expires_at: int | None = None
    registered: bool = False
    is_admin: bool = False
    is_imported: bool = False
    has_token: bool = False
    has_cookie: bool = False
    has_arp: bool = False
    exported_at: datetime | None = None
    export_count: int = 0
    created_at: datetime


class PoolMemberDetail(BaseModel):
    """号池条目完整信息(供编辑用,含敏感字段)。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    email: str
    display_name: str = ""
    member_id: str = ""
    status: str = ""
    message: str = ""
    credits: float | None = None
    expires_at: int | None = None
    registered: bool = False
    is_admin: bool = False
    is_imported: bool = False
    access_token: str = ""
    cookie: str = ""
    arp_session_id: str = ""
    refresh_token: str = ""
    client_id: str = ""


class PoolMemberUpdate(BaseModel):
    display_name: str | None = None
    status: str | None = None
    access_token: str | None = None
    cookie: str | None = None
    arp_session_id: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    credits: float | None = None


class TestImageRequest(BaseModel):
    prompt: str | None = None
    aspect_ratio: str = "1:1"
    quality: str = "medium"  # low / medium / high(gpt-image)
    width: int | None = 2048
    height: int | None = 2048


class TestImageResult(BaseModel):
    success: bool
    message: str
    image_url: str = ""
    prompt: str = ""


class RefreshARPRequest(BaseModel):
    prompt: str | None = "cartoon watermelon sticker"
    headless: bool = True
    timeout_seconds: int = Field(default=120, ge=30, le=300)


class RefreshARPResult(BaseModel):
    success: bool = True
    message: str = ""
    arp_session_id: str = ""
    has_access_token: bool = False


class RefreshTokenResult(BaseModel):
    success: bool
    message: str
    credits: float | None = None
    expires_at: int | None = None


class PoolBatchLoginFilter(BaseModel):
    """按筛选条件批量协议登录(不必逐页勾选)。"""
    keyword: str = ""
    registered_only: bool = False
    pool_type: str = "imported"  # all / imported / sub / admin
    has_token: bool | None = False  # None=全部, True=有token, False=无token
    credit_status: str = ""  # "" / unknown / known
    credit_value: float | None = None  # 精确额度筛选,如 0 / 10 / 500
    status_filter: str = ""  # "" / failed / registered / pending
    export_status: str = ""  # "" / exported / unexported
    auto_retry: bool = True  # 首轮结束后自动重试仍无 token 的账号
    max_retries: int = Field(default=2, ge=0, le=5)  # 额外重试轮数(不含首轮)


class PoolMoeMailGenerateRequest(BaseModel):
    api_key: str = Field(min_length=1)
    count: int = Field(default=1, ge=1, le=500)
    domain: str = "edu6.site"
    name_prefix: str = ""
    expiry_time: int = 0
    password: str = ""


class BuildTeamRequest(BaseModel):
    count: int = 9
    mode: str = "target"  # target=补到 count 个满额 / add=在现有基础上精确新增 count 个(1:1)


class BatchBuildTeamRequest(BaseModel):
    admin_ids: list[int] = []
    count: int = 9
    mode: str = "target"


class BatchAdminIdsRequest(BaseModel):
    admin_ids: list[int] = []


class CleanupMembersRequest(BaseModel):
    admin_ids: list[int] = []
    mode: str = "all"


class JobStatusOut(BaseModel):
    id: int
    type: str
    status: str
    target: int = 0
    success: int = 0
    fail: int = 0
    result: dict | None = None
    error: str = ""
    created_at: int | None = None
    finished_at: int | None = None
    log_total: int = 0
    logs: list[str] = []
    extra: dict | None = None


class BatchGrantRequest(BaseModel):
    """批量加子账号并授权。emails 为空时从邮箱池取 count 个未使用邮箱。"""

    count: int = 0
    emails: list[str] = []


class GrantItemResult(BaseModel):
    email: str
    ok: bool
    message: str = ""


class BatchGrantResult(BaseModel):
    total: int
    granted: int
    failed: int
    items: list[GrantItemResult] = []
