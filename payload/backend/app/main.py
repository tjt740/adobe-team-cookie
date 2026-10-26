import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import admin_user, adobe_account, auth, dashboard, email, external_cookie, external_member, log as log_route, pool, setting, sub2
from app.core.config import settings
from app.db.init_db import init_db
from app.services import log_store
from app.api.routes import clash, integration, monitor
from app.services.server_monitor import MONITOR, RequestMetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表并创建默认管理员
    log_store.install()
    init_db()
    from app.services.job_manager import JOBS
    JOBS.recover_interrupted('pool_cookie_sub2')
    JOBS.recover_interrupted('external_login')
    JOBS.recover_interrupted('pool_login')
    from app.services import external_sub2
    external_sub2.resume_pending()
    from app.services import reliable_integration
    reliable_integration.start()
    from app.services import supply_mail_health
    supply_mail_health.start()
    MONITOR.start()
    log_store.STORE.add("INFO", "system", "服务启动完成")
    try:
        yield
    finally:
        supply_mail_health.stop()
        MONITOR.stop()
        reliable_integration.stop()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(RequestMetricsMiddleware, api_prefix=settings.API_PREFIX)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def _on_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 400 and request.url.path.startswith("/api"):
        level = "ERROR" if exc.status_code >= 500 else "WARNING"
        log_store.STORE.add(
            level, "http",
            f"{request.method} {request.url.path} -> {exc.status_code}: {exc.detail}",
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(settings.API_PREFIX + "/external/members/") and request.url.path.endswith("/otp"):
        return JSONResponse(status_code=422, content={"detail": "请输入本次请求对应的 6 位数字验证码"})
    if request.url.path == settings.API_PREFIX + "/external/mail/config" or request.url.path.startswith(settings.API_PREFIX + "/external/mail/tokens"):
        return JSONResponse(status_code=422, content={"detail": "请检查邮件配置参数：Token 最多 512 字符"})
    if request.url.path.startswith("/api/integration"):
        return JSONResponse(status_code=422, content={"detail": "请检查联动配置参数"})
    if request.url.path.startswith(settings.API_PREFIX + "/admin/users"):
        # Pydantic's default response and log contain invalid password input.
        return JSONResponse(status_code=422, content={"detail": "请检查参数：用户名 3～50 位字母、数字或 ._-；昵称最多 50 字；密码至少 10 个字符且不超过 72 字节"})
    if request.url.path.startswith(settings.API_PREFIX + "/settings/clash"):
        # Validation errors may otherwise echo a private subscription in input.
        return JSONResponse(status_code=422, content={"detail": "请检查订阅链接或节点参数"})
    log_store.STORE.add(
        "WARNING", "validation",
        f"{request.method} {request.url.path} -> 422: {exc.errors()}",
    )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def _on_unhandled(request: Request, exc: Exception):
    log_store.STORE.add(
        "ERROR", "exception",
        f"{request.method} {request.url.path}: {exc}",
        tb=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500, content={"detail": f"服务器内部错误:{exc}"[:300]}
    )


app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(admin_user.router, prefix=settings.API_PREFIX)
app.include_router(adobe_account.router, prefix=settings.API_PREFIX)
app.include_router(email.router, prefix=settings.API_PREFIX)
app.include_router(pool.router, prefix=settings.API_PREFIX)
app.include_router(setting.router, prefix=settings.API_PREFIX)
app.include_router(clash.router, prefix=settings.API_PREFIX)
app.include_router(log_route.router, prefix=settings.API_PREFIX)
app.include_router(sub2.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(monitor.router, prefix=settings.API_PREFIX)
app.include_router(external_member.router, prefix=settings.API_PREFIX)
app.include_router(integration.router)
app.include_router(integration.external)
app.include_router(external_cookie.router)  # 自带 /api/v1/adobe 前缀,不加 API_PREFIX


@app.get("/api/health", tags=["系统"], summary="健康检查")
def health() -> dict:
    return {"status": "ok"}
