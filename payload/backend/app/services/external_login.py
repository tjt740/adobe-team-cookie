"""外部子号登录编排:每次调用无条件重新登录一个号,拿 cookie + 额度并落库。

复用 firefly.register_account(唯一产 cookie 的协议路径);失败原因映射到对接
文档约定的 code。并发批量登录用 ThreadPoolExecutor,并发数取「设置」。
"""

from __future__ import annotations

import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.crud import external_member as crud
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.services import firefly, log_store, proxy_pool
from app.services.job_manager import Job, JobCancelled
from app.schemas.account_profile import AccountProfile

SUBSCRIPTION_MIN = 1000.0

# 网络/代理失败时的额外重试轮数(每轮换一个出口 IP)。账号类错误不重试:
# 重试也救不回来,还会白耗一次验证码、加重 Adobe 对该邮箱来源的发码风控。
MAX_NETWORK_RETRIES = 1

# 全部改走验证码登录(不用密码)。默认 false:知道密码就用密码,省一次发码 ——
# 每多收一次验证码都会加重 Adobe 对该邮箱来源的发码风控。密码被拒时本来就会
# 自动退回验证码,所以默认值已经够稳。要全量走验证码把它设成 true。
FORCE_CODE_LOGIN = os.environ.get("FIREFLY_FORCE_CODE_LOGIN", "").lower() in ("1", "true", "yes")

# 单次尝试超过这么久(秒)才报网络错,就不再换 IP 重试:这种失败是卡在收验证码
# 那一段(收码本身要等到 otp_timeout),换个出口也只是再干等一轮;而
# /external/cookie 对接契约只给 5 分钟同步等待,翻倍会直接超时。
RETRY_MAX_ELAPSED = 120.0


def log_login(message: str) -> None:
    """单号与批量登录共享系统日志,失败不能混在 INFO 里。"""
    level = "ERROR" if message.startswith("✗") else "INFO"
    log_store.STORE.add(level, "external_login", message)


def _is_captcha_error(err: str) -> bool:
    """打码(Arkose)相关失败。

    补全资料走 PUT /signin/v4/accounts 要过 Arkose,arkose.py 的失败文案里带
    "captcha timeout" / "Arkose" 这类字样,会被 ``is_proxy_error`` 的 "timeout"
    标记误判成网络问题。它其实是打码平台/配置的问题:换出口 IP 救不回来,
    arkose.py 内部也已经自己重试过 ARKOSE_TRIES 次了。
    """
    low = (err or "").lower()
    return "captcha" in low or "arkose" in low


def _is_network_error(err: str) -> bool:
    """值得换个出口 IP 再试一次的错(排除打码类误判)。"""
    return proxy_pool.is_proxy_error(err) and not _is_captcha_error(err)


def _classify(err: str) -> str:
    low = (err or "").lower()
    if _is_network_error(low) or "rate" in low or "429" in low or "too many" in low:
        return "rate_limited"
    if "disabled" in low or "not found" in low or "no account" in low or "banned" in low:
        return "account_disabled"
    if "password" in low or "otp" in low or "captcha" in low or "验证码" in low or "login" in low:
        return "login_failed"
    return "internal"


def _login_with_proxy_retry(
    *, email: str, refresh_token: str, client_id: str, mail_url: str,
    proxy_raw: str, lf, adobe_password: str = "",
    on_credentials=None,
) -> tuple[dict | None, Exception | None]:
    """跑协议登录,网络/代理失败时换一个出口 IP 再试。返回 ``(rec, last_exc)``。

    只有 ``proxy_pool.is_proxy_error`` 命中的错误才重试;代理健康度同时上报,
    让下一次 ``random_proxy`` 自动躲开刚挂掉的出口。
    """
    used = ""
    last_exc: Exception | None = None

    def update_credentials(**values):
        nonlocal refresh_token, adobe_password
        refresh_token = values.get("refresh_token") or refresh_token
        adobe_password = values.get("adobe_password") or adobe_password
        if on_credentials:
            on_credentials(**values)

    for attempt in range(MAX_NETWORK_RETRIES + 1):
        proxy = proxy_pool.random_proxy(proxy_raw, exclude=used)
        if attempt == 0:
            lf(f"[{email}] 协议登录(proxy={'有' if proxy else '无'})…")
        else:
            tag = "已换代理 IP" if proxy and proxy != used else "无其它出口,原线路"
            lf(f"[{email}] 网络重试 {attempt}/{MAX_NETWORK_RETRIES}({tag})…")
        used = proxy
        started = time.monotonic()
        try:
            rec = firefly.register_account(
                email=email, refresh_token=refresh_token, client_id=client_id,
                mail_url=mail_url, proxy_url=proxy, otp_timeout=180,
                adobe_password=adobe_password,
                force_code_login=FORCE_CODE_LOGIN,
                log=lambda mm: lf(f"[{email}] {mm}"),
                on_credentials=update_credentials,
            )
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if not _is_network_error(str(e)):
                break  # 账号/验证码/打码类错误:换 IP 也没用
            proxy_pool.report_failure(proxy, str(e))
            if attempt >= MAX_NETWORK_RETRIES:
                break
            elapsed = time.monotonic() - started
            if elapsed > RETRY_MAX_ELAPSED:
                lf(f"🌐 [{email}] 网络/代理失败,但本次已耗时 {int(elapsed)}s"
                   f"(卡在收码段),不再换 IP 重试:{str(e)[:160]}")
                break
            lf(f"🌐 [{email}] 网络/代理失败:{str(e)[:160]}")
            continue
        proxy_pool.report_success(proxy)
        return rec, None
    return None, last_exc


def login_and_store(member_id: int, *, log=None, check_cancelled=None) -> dict:
    lf = log if callable(log) else (lambda _m: None)
    db = SessionLocal()
    try:
        m = crud.get(db, member_id)
        if not m:
            return {"ok": False, "cookie": "", "credits_available": None,
                    "credits_total": None, "code": "account_disabled",
                    "message": "库中无此邮箱"}
        email = m.email
        rt = m.refresh_token or ""
        cid = m.client_id or ""
        mail_url = m.mail_url or ""
        adobe_pwd = m.adobe_password or ""
        settings = setting_crud.get_settings(db)
    finally:
        db.close()

    # 复用「设置」里的代理池(settings.proxy_url),登录时随机取一个出口;
    # 网络原因挂掉时换一个出口 IP 再试一次(见 _login_with_proxy_retry)
    proxy_raw = (settings.proxy_url or "") if settings.proxy_enabled else ""
    rec, exc = _login_with_proxy_retry(
        email=email, refresh_token=rt, client_id=cid, mail_url=mail_url,
        adobe_password=adobe_pwd, proxy_raw=proxy_raw, lf=lf,
        on_credentials=lambda **values: _save_credentials(member_id, **values),
    )
    if check_cancelled:
        check_cancelled()
    if exc is not None:
        code = _classify(str(exc))
        detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=6))
        lf(f"✗ [{email}] 登录失败({code}):{detail}")
        lf(f"[{email}] 堆栈:\n{tb[-800:]}")
        _save_failure(member_id, code, str(exc)[:300])
        return {"ok": False, "cookie": "", "credits_available": None,
                "credits_total": None, "code": code, "message": str(exc)[:300]}
    rec = rec or {}

    cookie = rec.get("cookie") or ""
    if not cookie:
        lf(f"✗ [{email}] 登录成功但未取得 cookie")
        _save_failure(member_id, "login_failed", "登录成功但未取得 cookie")
        return {"ok": False, "cookie": "", "credits_available": rec.get("credits"),
                "credits_total": rec.get("credits_total"), "code": "login_failed",
                "message": "登录成功但未取得 cookie"}

    available = rec.get("credits")
    total = rec.get("credits_total")
    sub_ok = total >= SUBSCRIPTION_MIN if isinstance(total, (int, float)) else None
    _save_success(member_id, rec, sub_ok)
    subscription = "未能查询" if sub_ok is None else ("正常" if sub_ok else "掉")
    lf(f"✓ [{email}] 登录成功,额度 {available}/{total},订阅={subscription}")
    # Local login stays successful even if the optional downstream sync fails.
    try:
        from app.services import external_sub2
        external_sub2.after_login(member_id, session_factory=SessionLocal)
    except Exception:
        log_store.STORE.add("WARNING", "external_sub2", f"外部子号 #{member_id} 登录成功，Sub2 同步未能提交，请手动重试")
    return {"ok": True, "cookie": cookie, "credits_available": available,
            "credits_total": total, "code": "", "message": ""}


def _save_credentials(member_id: int, *, refresh_token: str = "", adobe_password: str = "") -> None:
    db = SessionLocal()
    try:
        member = crud.get(db, member_id)
        if not member:
            return
        if refresh_token:
            member.refresh_token = refresh_token
        if adobe_password:
            member.adobe_password = adobe_password
        db.commit()
    finally:
        db.close()


def _save_success(member_id: int, rec: dict, sub_ok: bool | None) -> None:
    db = SessionLocal()
    try:
        m = crud.get(db, member_id)
        if not m:
            return
        m.cookie = rec.get("cookie") or m.cookie
        m.access_token = rec.get("access_token") or ""
        m.expires_at = rec.get("expires_at")
        m.credits_available = rec.get("credits")
        m.credits_total = rec.get("credits_total")
        # A successful new session supersedes the old profile snapshot, even if
        # metadata could not be fetched this time. Login failures retain it.
        profile = rec.get("account_profile")
        m.account_profile = AccountProfile.model_validate(profile).model_dump(mode="json") if profile else None
        m.first_login_done = True
        m.login_status = "ok"
        if sub_ok is not None:
            m.subscription_ok = sub_ok
        m.message = "登录成功" if sub_ok is not None else "登录成功,额度暂未能查询"
        m.last_login_at = datetime.now(timezone.utc)
        m.updated_at = datetime.now(timezone.utc)
        rotated = rec.get("rotated_refresh_token") or ""
        if rotated:
            m.refresh_token = rotated
        # 本次实际设置成功的密码才是权威值;已补全的账号不会返回 set_password。
        set_pw = (rec.get("set_password") or "").strip()
        if set_pw:
            m.adobe_password = set_pw
        db.commit()
    finally:
        db.close()


def _save_failure(member_id: int, code: str, message: str) -> None:
    db = SessionLocal()
    try:
        m = crud.get(db, member_id)
        if not m:
            return
        m.login_status = code  # 不清空已有 cookie
        m.message = message
        m.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def batch_login_worker(job: Job) -> None:
    def _log(message: str) -> None:
        job.log(message)
        log_login(message)

    member_ids = [int(x) for x in (job.meta.get("member_ids") or [])]
    job.set_extra('items', [{'id': mid, 'email': (job.meta.get('member_emails') or {}).get(str(mid), ''),
                             'status': 'pending', 'message': '等待登录'} for mid in member_ids])
    job.target = len(member_ids)
    if not member_ids:
        _log("没有可登录的外部子号")
        return
    db = SessionLocal()
    try:
        concurrency = max(1, int(setting_crud.get_settings(db).concurrency or 1))
    finally:
        db.close()
    _log(f"任务 #{job.id}:开始登录 {len(member_ids)} 个外部子号,并发 {min(concurrency, len(member_ids))}")

    def _do(mid: int) -> None:
        if not job.begin_item():
            return
        try:
            job.record_item(mid, status='running', message='正在登录')
            res = login_and_store(mid, log=_log, check_cancelled=job.check_cancelled)
            job.bump(success=1) if res["ok"] else job.bump(fail=1)
            job.record_item(mid, status='done' if res['ok'] else 'failed',
                            message=res.get('message') or ('登录成功' if res['ok'] else '登录失败，请查看执行记录'))
        except JobCancelled:
            job.record_item(mid, status='cancelled', message='本次登录已终止')
            return
        except Exception as e:  # noqa: BLE001
            # login_and_store 内部已兜底大部分异常;这里再兜底一层,
            # 避免个别账号在 DB 层等处抛出的异常经 ex.map 逃逸,
            # 导致整批任务被中止(JobManager 把整个 job 标记为 error)。
            job.bump(fail=1)
            job.record_item(mid, status='failed', message='登录异常，请查看执行记录')
            _log(f"✗ [id={mid}] 批量登录异常:{str(e)[:200]}")
        finally:
            job.end_item()

    with ThreadPoolExecutor(max_workers=min(concurrency, len(member_ids))) as ex:
        for _ in ex.map(_do, member_ids):
            pass
    job.result = {"total": len(member_ids), "success": job.success, "fail": job.fail}
    _log(f"任务 #{job.id} 完成:成功 {job.success} / 失败 {job.fail}")
