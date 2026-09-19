"""对外 cookie 刷新接口(X-API-Key 鉴权,无 JWT)。

严格遵守 self-cookie-provider-api.md:key 错→401;body 非法/缺 email→400;
业务结果一律 200 + {ok, email, cookie, code, message}。手动解析 body 以避免
FastAPI 默认的 422,并绕开 main.py 的全局校验异常处理器。

注:鉴权与查号两步复用 FastAPI 注入的 `db`(Depends(get_db)),而不是在路由内
另开 SessionLocal()——测试通过 `client` fixture 覆写 get_db 指向内存库,
若路由内部另建 SessionLocal() 会绕过该覆写,查到的是真实磁盘库(空的),
导致测试不可控。`login_and_store` 内部仍保留它自己的 SessionLocal(生产环境
正确;测试里被 monkeypatch 整体替换,不受影响)。

注:真正的登录调用(`login_and_store`,含 per-email 锁)通过
`starlette.concurrency.run_in_threadpool` 丢进线程池执行,不在事件循环线程上
同步阻塞——否则这个唯一的 async 路由会把「不同邮箱最多 10 个并发」串行化成
一个一个排队,和契约的并发/超时约定冲突。
"""

from __future__ import annotations

import hmac
import json
import threading

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.crud import external_member as crud
from app.crud import setting as setting_crud
from app.db.session import get_db
from app.services import external_login, log_store

router = APIRouter(prefix="/api/v1/adobe", tags=["对外接口"])


def _resp(status_code: int, payload: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/cookie/refresh", summary="对外:按邮箱重登刷新 cookie")
async def refresh_cookie(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    # 1. 鉴权(先鉴权,不先读 body)。用 hmac.compare_digest 做定长比较,
    # 避免逐字符 `!=` 比较在共享密钥场景下留下时序侧信道。
    configured = (setting_crud.get_settings(db).external_api_key or "").strip()
    provided = (x_api_key or "").strip()
    # 按字节比较,而不是 str:Starlette 对 header 是按 latin-1 解码的,
    # 非 ASCII 的 X-API-Key 会让 hmac.compare_digest(str, str) 抛
    # TypeError 逃逸成 500——但契约要求密钥错一律 401。
    if not configured or not hmac.compare_digest(provided.encode(), configured.encode()):
        return _resp(401, {"detail": "invalid api key"})

    # 2. 解析 body
    try:
        raw = await request.body()
        data = json.loads(raw or b"{}")
        if not isinstance(data, dict):
            raise ValueError("body not object")
    except Exception:  # noqa: BLE001
        return _resp(400, {"detail": "invalid json"})
    # email 必须是非空字符串;非字符串类型(如数字/数组)不能直接 .strip(),
    # 否则会抛 AttributeError 逃逸成 500,这里显式按 400 处理。
    raw_email = data.get("email")
    if not isinstance(raw_email, str) or not raw_email.strip():
        return _resp(400, {"detail": "missing email"})
    email = raw_email.strip()

    # 3. 查号 → 实时重登(业务结果一律 200)
    m = crud.get_by_email(db, email)
    member_id = m.id if m else None

    if member_id is None:
        _log("WARNING", f"cookie/refresh 未知邮箱 {email}")
        return _resp(200, {"ok": False, "email": email, "cookie": "",
                           "code": "account_disabled", "message": "unknown email"})

    def _do_login() -> dict:
        # 锁 + 真正登录都放进线程池同一个同步函数里执行,避免持锁等待时
        # 仍占用事件循环线程(per-email 锁本身是同步原语,不能直接 await)。
        with _email_lock(email):
            return external_login.login_and_store(
                member_id, log=lambda m2: _log("INFO", f"[{email}] {m2}")
            )

    try:
        # login_and_store 是分钟级耗时的同步阻塞调用(网络登录),必须丢进
        # 线程池执行,否则这个 async 路由会在事件循环线程上串行卡住所有请求,
        # 违反契约里「不同邮箱最多 10 个并发」「5 分钟同步等待」的要求。
        res = await run_in_threadpool(_do_login)
    except Exception as e:  # noqa: BLE001
        # login_and_store 内部已经 try/except 大部分登录异常;这里兜底捕获
        # 落库(_save_success/_save_failure 的 db.commit())等未被内部捕获的
        # 异常,确保业务失败也一律回 200,不让 5xx 逃逸给对接方。
        _log("ERROR", f"[{email}] cookie/refresh 内部异常: {str(e)[:200]}")
        return _resp(200, {"ok": False, "email": email, "cookie": "",
                           "code": "internal", "message": str(e)[:200]})

    return _resp(200, {
        "ok": bool(res["ok"]), "email": email,
        "cookie": res.get("cookie") or "",
        "code": res.get("code") or "", "message": res.get("message") or "",
    })


# ---- per-email 防并发锁(幂等/防御性,对接方声明同邮箱不并发)----
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _email_lock(email: str) -> threading.Lock:
    key = email.lower()
    with _locks_guard:
        lk = _locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _locks[key] = lk
        return lk


def _log(level: str, msg: str) -> None:
    try:
        log_store.STORE.add(level, "external_cookie", msg)
    except Exception:  # noqa: BLE001
        pass
