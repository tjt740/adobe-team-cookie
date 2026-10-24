from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _valid_import_batch(value: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise ValueError("请选择有效的导入批次日期（YYYYMMDD）")
    return value


ImportBatch = Annotated[str, Field(pattern=r"^[0-9]{8}$"), AfterValidator(_valid_import_batch)]
DuplicateAction = Literal["skip", "overwrite"]


class EmailBase(BaseModel):
    email: str
    password: str = ""
    refresh_token: str = ""
    client_id: str = ""
    mail_url: str = ""
    remark: str = ""


class EmailCreate(EmailBase):
    import_batch: ImportBatch
    on_duplicate: DuplicateAction


class EmailBatchImportRequest(BaseModel):
    content: str
    import_batch: ImportBatch
    on_duplicate: DuplicateAction


class EmailFormatsRequest(BaseModel):
    keyword: str = ""
    is_used: bool | None = None
    import_batch: ImportBatch | None = None
    ids: list[int] | None = Field(default=None, max_length=10000)
    format: Literal["standard", "pipe"] = "standard"


class EmailFormatsOut(BaseModel):
    content: str
    total: int


class EmailUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    mail_url: str | None = None
    is_used: bool | None = None
    remark: str | None = None


class MoeMailGenerateRequest(BaseModel):
    api_key: str = Field(min_length=1)
    count: int = Field(default=1, ge=1, le=500)
    domain: str = "edu6.site"
    name_prefix: str = ""
    expiry_time: int = 0
    password: str = ""
    on_duplicate: DuplicateAction
    import_batch: ImportBatch


class EmailOut(EmailBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_batch: str | None
    imported_at: datetime | None
    is_used: bool
    used_at: datetime | None
    created_at: datetime


class MailSummaryOut(BaseModel):
    id: str
    subject: str = ""
    from_addr: str = ""
    date: str = ""
    folder: str = ""
    preview: str = ""
    is_read: bool | None = None
    source: str = ""


class MailListOut(BaseModel):
    success: bool
    message: str
    source: str = ""
    messages: list[MailSummaryOut] = []


class MailDetailOut(BaseModel):
    success: bool
    message: str
    subject: str = ""
    from_addr: str = ""
    to_addr: str = ""
    date: str = ""
    body_html: str = ""
    body_text: str = ""
