"""日志管理:查看后端最近的请求错误 / 异常 / 告警。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.common import MessageResult
from app.schemas.log import LogListOut
from app.services.log_store import STORE

router = APIRouter(
    prefix="/logs",
    tags=["日志管理"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=LogListOut, summary="查询日志")
def list_logs(
    level: str = "",
    keyword: str = "",
    limit: int = Query(300, ge=1, le=2000),
) -> LogListOut:
    items, total = STORE.list(level=level, keyword=keyword.strip(), limit=limit)
    return LogListOut(items=items, total=total)


@router.post("/clear", response_model=MessageResult, summary="清空日志")
def clear_logs() -> MessageResult:
    STORE.clear()
    return MessageResult(message="日志已清空")
