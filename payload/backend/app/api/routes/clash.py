from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr, StrictBool
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from urllib.parse import urlsplit
from requests.utils import get_environ_proxies

from app.api.deps import get_current_user
from app.crud.setting import get_settings, update_settings
from app.schemas.setting import SettingsUpdate
from app.db.session import get_db
from app.models.user import User
from app.services.clash import ClashError, ClashManager


def require_admin(user: User = Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(403, "仅管理员可以管理 Clash 订阅")
    return user


router = APIRouter(prefix="/settings/clash", tags=["设置"], dependencies=[Depends(require_admin)])


class SubscriptionRequest(BaseModel):
    url: SecretStr


class NodeRequest(BaseModel):
    node: str


class EnabledRequest(BaseModel):
    enabled: StrictBool


def ensure_idle(db):
    if inspect(db.get_bind()).has_table("job_records"):
        running = db.execute(text("SELECT count(*) FROM job_records WHERE status IN ('running','pausing','paused','cancelling') AND deleted=0")).scalar()
        if running:
            raise HTTPException(409, "有未结束的任务，请等任务结束或终止后再修改代理")


def result(operation, db):
    try:
        value = operation()
        settings = get_settings(db)
        value["proxy_enabled"] = settings.proxy_enabled
        try:
            value["clash_enabled"] = settings.proxy_enabled and settings.proxy_url.strip() == ClashManager().proxy_url()
        except ClashError:
            # Broken configuration must not prevent disabling an existing proxy.
            value["clash_enabled"] = settings.proxy_enabled
        # Subscription management and use of an existing proxy are independent.
        # Return only an endpoint, never proxy credentials or subscription URLs.
        raw = settings.proxy_url.strip().splitlines()[0] if settings.proxy_enabled and settings.proxy_url.strip() else ""
        source = "manual" if raw else "direct"
        if not raw:
            proxies = get_environ_proxies("https://firefly.adobe.com")
            raw = proxies.get("https") or proxies.get("all") or ""
            if raw:
                source = "environment"
        endpoint = ""
        try:
            parsed = urlsplit(raw if "://" in raw else "http://" + raw)
            if parsed.hostname:
                endpoint = parsed.hostname + (":" + str(parsed.port) if parsed.port else "")
        except ValueError:
            pass
        value["proxy_source"] = source
        value["proxy_endpoint"] = endpoint
        return value
    except ClashError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get("")
def status(db: Session = Depends(get_db)):
    return result(ClashManager().snapshot, db)


@router.put("/enabled")
def set_enabled(data: EnabledRequest, db: Session = Depends(get_db)):
    def change():
        manager = ClashManager()
        ensure_idle(db)
        if data.enabled:
            with manager.lock():
                ensure_idle(db)
                endpoint = manager.proxy_url()
                value = manager.status()  # Validate before persisting; failures leave settings intact.
                update_settings(db, SettingsUpdate(proxy_enabled=True, proxy_url=endpoint))
                return value
        # Do not contact the controller when turning off: it may be offline.
        update_settings(db, SettingsUpdate(proxy_enabled=False))
        return {"available": manager.available}
    return result(change, db)


@router.put("/subscription")
def update_subscription(data: SubscriptionRequest, db: Session = Depends(get_db)):
    return result(lambda: ClashManager().update(data.url.get_secret_value(), lambda: ensure_idle(db)), db)


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    return result(lambda: ClashManager().refresh(lambda: ensure_idle(db)), db)


@router.put("/node")
def select_node(data: NodeRequest, db: Session = Depends(get_db)):
    return result(lambda: ClashManager().select(data.node, lambda: ensure_idle(db)), db)
