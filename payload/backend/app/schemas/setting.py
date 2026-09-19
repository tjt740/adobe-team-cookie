from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    proxy_enabled: bool = False
    proxy_url: str = ""
    concurrency: int = 5
    request_timeout: int = 30
    register_country: str = "SG"
    register_locale: str = "en_US"
    # 号池默认导出格式:token(FF-iOS 全量) / cookie(纯 CK)
    export_format: str = "token"
    # 自建号池网关配置
    pool_api_base_url: str = ""
    pool_api_key: str = ""
    # 外部子号对外接口 API Key
    external_api_key: str = ""
    # 被邀请子号补全资料 PUT /signin/v4/accounts 的 Arkose 打码
    captcha_provider: str = ""
    captcha_key: str = ""


class SettingsUpdate(BaseModel):
    proxy_enabled: bool | None = None
    proxy_url: str | None = None
    concurrency: int | None = Field(default=None, ge=1, le=1000)
    request_timeout: int | None = Field(default=None, ge=1, le=600)
    register_country: str | None = Field(default=None, min_length=2, max_length=2)
    register_locale: str | None = Field(default=None, min_length=2, max_length=10)
    export_format: str | None = Field(default=None, pattern="^(token|cookie)$")
    pool_api_base_url: str | None = None
    pool_api_key: str | None = None
    external_api_key: str | None = None
    captcha_provider: str | None = Field(
        default=None,
        pattern="^(yescaptcha|yes|2captcha|capsolver|ez|ezcaptcha|none|)$",
    )
    captcha_key: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class ProxyTestRequest(BaseModel):
    # 留空则测试当前已保存的代理配置;否则测试传入的多行文本
    proxy_url: str | None = None


class ProxyTestItem(BaseModel):
    proxy: str
    ok: bool
    ip: str = ""
    latency_ms: int = 0
    message: str = ""


class ProxyTestResult(BaseModel):
    total: int = 0
    ok_count: int = 0
    items: list[ProxyTestItem] = []
