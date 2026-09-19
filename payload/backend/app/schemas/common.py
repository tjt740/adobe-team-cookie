from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class BatchIds(BaseModel):
    ids: list[int]
    auto_retry: bool = True
    max_retries: int = Field(default=2, ge=0, le=5)


class BatchImportRequest(BaseModel):
    content: str
    # 重复邮箱处理:skip=跳过, overwrite=覆盖更新
    on_duplicate: str = "skip"
    # 这批母号所属号池平台:adobe_gemini(banana,默认)/ adobe_gpt(生图)
    platform: str = "adobe_gemini"


class BatchImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int
    errors: list[str] = []


class MessageResult(BaseModel):
    success: bool = True
    message: str = "操作成功"
