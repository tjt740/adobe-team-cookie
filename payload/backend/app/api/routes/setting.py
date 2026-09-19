from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.crud import setting as crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import MessageResult
from app.schemas.setting import (
    ChangePasswordRequest,
    ProxyTestRequest,
    ProxyTestResult,
    SettingsOut,
    SettingsUpdate,
)
from app.services import proxy_pool

router = APIRouter(
    prefix="/settings",
    tags=["设置"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=SettingsOut, summary="获取系统设置")
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return crud.get_settings(db)


@router.put("", response_model=SettingsOut, summary="更新系统设置")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    return crud.update_settings(db, data)


@router.post("/test-proxy", response_model=ProxyTestResult, summary="测试代理连通性")
def test_proxy(
    data: ProxyTestRequest, db: Session = Depends(get_db)
) -> ProxyTestResult:
    raw = data.proxy_url
    if raw is None:
        raw = crud.get_settings(db).proxy_url
    items = proxy_pool.test_all(raw or "")
    ok_count = sum(1 for i in items if i["ok"])
    return ProxyTestResult(total=len(items), ok_count=ok_count, items=items)


@router.get("/proxy-health", summary="查看运行时代理健康状态")
def proxy_health(db: Session = Depends(get_db)) -> dict:
    raw = crud.get_settings(db).proxy_url or ""
    items = proxy_pool.health_snapshot(raw)
    cooling = sum(1 for i in items if not i["healthy"])
    return {"total": len(items), "cooling": cooling, "items": items}


@router.post("/change-password", response_model=MessageResult, summary="修改管理员密码")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResult:
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误"
        )
    user_crud.change_password(db, current_user, data.new_password)
    return MessageResult(message="密码修改成功")
