"""Authenticated, cached server metrics. GET never starts jobs or probes services."""
from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_current_user
from app.services.server_monitor import MONITOR

router = APIRouter(prefix="/monitor", tags=["服务器监控"], dependencies=[Depends(get_current_user)])


@router.get("/snapshot")
def snapshot(response: Response, minutes: int = Query(default=15, ge=1, le=60)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return MONITOR.snapshot(minutes)
