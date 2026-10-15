"""Authenticated, cached server metrics. GET never starts jobs or probes services."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import get_current_user, require_superuser
from app.services.server_monitor import MONITOR
from app.services.sub2_monitor import SUB2_MONITOR

router = APIRouter(prefix="/monitor", tags=["服务器监控"], dependencies=[Depends(get_current_user)])


@router.get("/snapshot")
def snapshot(response: Response, minutes: int = Query(default=15, ge=1, le=60)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return MONITOR.snapshot(minutes)


@router.get("/user-requests", dependencies=[Depends(require_superuser)])
def user_requests(response: Response, minutes: int = Query(default=15, ge=1, le=60)) -> dict:
    if minutes not in (5, 15, 30, 60):
        raise HTTPException(status_code=422, detail="请选择 5、15、30 或 60 分钟")
    response.headers["Cache-Control"] = "no-store"
    return SUB2_MONITOR.snapshot(minutes)
