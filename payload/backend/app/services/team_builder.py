"""拉号编排:为 Adobe 母号凑满 N 个已注册可用的子号(支持单主号 / 多主号批量)。

流程(每个子号):从邮箱池取未使用邮箱 → 邀请并分配产品(授权)→ 子号自助登录拿
firefly token/cookie/credits(注册)。失败则把该成员从组织移除并换下一个邮箱重拉,
直到注册成功数达到目标或邮箱池耗尽。批量时按主号顺序处理,主号未登录会自动登录。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.crud import adobe_account as adobe_crud
from app.crud import adobe_member as member_crud
from app.crud import email as email_crud
from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.services import adobe_admin, firefly, pool_claim, proxy_pool, remote_member_cleanup
from app.services.job_manager import Job

REQUIRED_CREDITS = 4000.0
MAX_ATTEMPTS_PER_SLOT = 5
MAX_PROXY_RETRIES_PER_EMAIL = 2
MAX_LICENSE_CLEANUP_ROUNDS = 3
TRANSIENT_FAILURE_MARKERS = (
    "curl:",
    "Connection reset",
    "WRONG_VERSION_NUMBER",
    "timeout",
    "timed out",
    "Network Error",
    "超时",       # 中文超时(如"收取 Adobe 验证码超时")——瞬态,不该烧邮箱
    "未取到",     # Graph/IMAP 均未取到验证码
    "未收到",
    "收取 Adobe 验证码",
)
LICENSE_FULL_MARKER = "ALLOWABLE_LICENSE_COUNT_EXCEEDED"


def _push_one_to_sub2(db, email: str, rec: dict, job: "Job", prefix: str,
                      platform: str | None = None) -> None:
    """成功注册一个子号,立刻用 **cookie** 推进 Sub2(默认协议 import-cookie)。
    platform=母号所属平台(adobe_gemini/adobe_gpt),推到对应平台分组;None=主平台。
    best-effort:失败不影响拉号,10分钟自愈那轮会自动补推。"""
    try:
        from app.api.routes.sub2 import _get_config
        from app.services import sub2_client as _sub2
        cfg = _get_config(db, platform)
        if not (cfg.get("enabled") and cfg.get("auto_push") and cfg.get("group_ids")):
            return
        ck = (rec.get("cookie") or "").strip()
        if not ck:
            return  # 无 cookie 不能走 cookie 导入
        item = {"name": rec.get("display_name") or email, "email": email, "cookie": ck,
                "credits": rec.get("credits"), "expires_at": rec.get("expires_at")}
        resp = _sub2.import_tokens({**cfg, "concurrency": cfg.get("concurrency", 10)}, [item])
        res = resp.get("result") or {}
        created = res.get("created") if isinstance(res, dict) else "?"
        job.log(f"{prefix}↗ 已推 Sub2:{email}(创建 {created})")
    except Exception as e:  # noqa: BLE001
        job.log(f"{prefix}↗ 推 Sub2 失败(不影响,稍后自愈补推):{str(e)[:80]}")


def _credits_ok(value: object) -> bool:
    try:
        return abs(float(value) - REQUIRED_CREDITS) < 0.0001
    except (TypeError, ValueError):
        return False


def _remove_best_effort(
    *, token: str, org_id: str, email: str, member_id: str = "", proxy_url: str = ""
) -> None:
    try:
        adobe_admin.remove_member(
            token=token,
            org_id=org_id,
            member_id=member_id,
            email=email,
            proxy_url=proxy_url,
        )
    except Exception:
        pass


def _attempt_label(job: Job, attempt_no: int, max_attempts: int) -> str:
    return f"[{attempt_no}/{max_attempts}] #{job.id}"


def _attempt_log(job: Job, prefix: str, label: str, msg: str) -> None:
    job.log(f"{prefix}{label} {msg}")


def _attempt_email_log(job: Job, prefix: str, label: str, email: str, msg: str) -> None:
    if label:
        _attempt_log(job, prefix, label, f"{email} {msg}")
    else:
        job.log(f"{prefix}[{email}] {msg}")


def _compact_error(msg: str, limit: int = 180) -> str:
    msg = " ".join((msg or "").split())
    if "placeOrder" in msg and "SERVICE_ERROR" in msg:
        return "placeOrder hint=SERVICE_ERROR（受理未开通，风控/支付被拒）"
    if "TRIAL_ALREADY_CONSUMED" in msg:
        return "TRIAL_ALREADY_CONSUMED(试用已消耗)"
    if "ALLOWABLE_LICENSE_COUNT_EXCEEDED" in msg:
        return "ALLOWABLE_LICENSE_COUNT_EXCEEDED(名额已满)"
    if "WRONG_VERSION_NUMBER" in msg:
        return "代理 TLS 异常(WRONG_VERSION_NUMBER)"
    if "Connection reset" in msg:
        return "代理连接被重置"
    if "额度不合格" in msg:
        return msg
    if "注册失败:" in msg:
        return msg.replace("注册失败:", "", 1)[:limit]
    if "授权失败:" in msg:
        return msg.replace("授权失败:", "", 1)[:limit]
    if len(msg) > limit:
        return msg[:limit] + "..."
    return msg


def _is_proxy_failure(msg: str) -> bool:
    return proxy_pool.is_proxy_error(msg)


def _is_license_full(msg: str) -> bool:
    return LICENSE_FULL_MARKER in (msg or "")


def _cleanup_remote_slots(
    db,
    job: Job,
    account,
    proxy_raw: str,
    prefix: str,
    label: str,
    *,
    reason: str,
) -> dict:
    _attempt_log(job, prefix, label, f"🧹 {reason}：开始清理全部远端占位")
    cleanup = remote_member_cleanup.cleanup_remote_members(
        db,
        account,
        proxy_raw=proxy_raw,
        limit=None,
        log=lambda m: _attempt_log(job, prefix, label, f"· {m}"),
    )
    _attempt_log(
        job,
        prefix,
        label,
        f"· 清理结果：远端 {cleanup['remote_total']}，候选 "
        f"{cleanup['cleanup_candidates']}，已移除 {cleanup['removed']}，"
        f"失败 {len(cleanup.get('failed') or [])}",
    )
    return cleanup


def _remove_failed_remote_member(
    *,
    token: str,
    org_id: str,
    email: str,
    member_id: str = "",
    proxy_raw: str,
    job: Job,
    prefix: str,
    reason: str,
    attempt_label: str = "",
) -> None:
    try:
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        res = adobe_admin.remove_member(
            token=token,
            org_id=org_id,
            member_id=member_id,
            email=email,
            proxy_url=proxy_url,
        )
        msg = (res.get("message") or "").strip()
        if res.get("ok"):
            proxy_pool.report_success(proxy_url)
            if attempt_label:
                _attempt_log(job, prefix, attempt_label, "· 远端清理：已移除失败占位")
            else:
                job.log(f"{prefix}remote cleanup [{email}] after {reason}: removed")
        else:
            proxy_pool.report_failure(proxy_url, msg)
            detail = msg[:160] or "not found or remove failed"
            if attempt_label:
                _attempt_log(job, prefix, attempt_label, f"· 远端清理：{detail}")
            else:
                job.log(
                    f"{prefix}remote cleanup [{email}] after {reason}: {detail}"
                )
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)[:160]
        try:
            proxy_pool.report_failure(proxy_url, detail)  # type: ignore[name-defined]
        except Exception:
            pass
        if attempt_label:
            _attempt_log(job, prefix, attempt_label, f"· 远端清理异常：{detail}")
        else:
            job.log(f"{prefix}remote cleanup [{email}] after {reason} failed:{detail}")


def _email_failure_reason(msg: str) -> str:
    if any(marker in msg for marker in TRANSIENT_FAILURE_MARKERS):
        return ""
    if "ALLOWABLE_LICENSE_COUNT_EXCEEDED" in msg:
        return ""
    if "TRIAL_ALREADY_CONSUMED" in msg:
        return "trial_consumed"
    if "authenticationstate" in msg:
        return "auth_state_failed"
    """
    if "credits" in msg or "棰濆害" in msg or "妫版繂瀹? in msg:
        return "bad_credit"
    if "注册失败" in msg or "娉ㄥ唽澶辫触" in msg:
        return "register_failed"
    if "授权失败" in msg or "鎺堟潈澶辫触" in msg:
        return "grant_failed"
    """
    lowered = msg.lower()
    if "credits" in lowered or "credit" in lowered:
        return "bad_credit"
    if "register" in lowered or "registration" in lowered:
        return "register_failed"
    if "users:batch partial error" in lowered or "grant" in lowered:
        return "grant_failed"
    return "failed"


def _register_one(
    *, token: str, org_id: str, product_id: str, lgid: str, proxy_url: str,
    email: str, refresh_token: str, client_id: str, job: Job, prefix: str = "",
    attempt_label: str = "",
) -> tuple[bool, dict, str]:
    """对单个邮箱执行:授权 + 注册。返回 (是否成功, newbanana记录, 失败原因)。"""
    _attempt_email_log(job, prefix, attempt_label, email, "🚀 第一步：邀请 + 分配产品(授权)")
    try:
        g = adobe_admin.grant_member(
            token=token, org_id=org_id, product_id=product_id,
            license_group_id=lgid, email=email, proxy_url=proxy_url,
        )
    except Exception as e:  # noqa: BLE001
        return False, {}, f"授权异常:{str(e)[:240]}"
    if not g.get("ok"):
        return False, {}, f"授权失败:{g.get('message') or ''}"[:480]

    _attempt_email_log(job, prefix, attempt_label, email, "✅ 授权通过")
    _attempt_email_log(job, prefix, attempt_label, email, "🔐 第二步：子号登录注册(收验证码，最长约 3 分钟)")
    try:
        rec = firefly.register_account(
            email=email, refresh_token=refresh_token, client_id=client_id,
            proxy_url=proxy_url, otp_timeout=180,
            account_id=g.get("member_id", ""),
            log=lambda m: _attempt_email_log(job, prefix, attempt_label, email, f"· {m}"),
        )
    except Exception as e:  # noqa: BLE001
        # 由外层统一清理,避免这里删一次、失败分支又按邮箱重复删一次。
        return False, {"member_id": g.get("member_id", "")}, f"注册失败:{str(e)[:200]}"

    rec["member_id"] = g.get("member_id", "")
    _attempt_email_log(job, prefix, attempt_label, email, "🔎 最后一步：回查真实订阅")
    _attempt_email_log(job, prefix, attempt_label, email, f"· 回查：{rec.get('credits')}")
    if not _credits_ok(rec.get("credits")):
        return (
            False,
            {"member_id": rec.get("member_id", "")},
            f"额度不合格:{rec.get('credits')} (要求 {int(REQUIRED_CREDITS)})",
        )
    return True, rec, ""


def _apply_login_result(account, res: dict) -> None:
    rotated = res.get("rotated_refresh_token") or ""
    if rotated and rotated != account.refresh_token:
        account.refresh_token = rotated
    account.admin_token = res.get("token") or ""
    account.admin_cookie = res.get("cookie") or ""
    account.org_id = res.get("org_id") or ""
    account.product_id = res.get("product_id") or ""
    account.product_name = res.get("product_name") or ""
    account.license_group_id = res.get("license_group_id") or ""
    account.has_org = bool(res.get("has_org"))
    account.is_valid = bool(res.get("has_org"))
    account.last_login_at = datetime.now(timezone.utc)
    account.last_checked_at = datetime.now(timezone.utc)


def _ensure_admin(db, account, proxy_raw: str, job: Job, prefix: str) -> bool:
    """确保主号已取得管理权限;缺失或失效时自动登录。返回是否可用。"""
    has_creds = bool(account.admin_token and account.org_id
                     and account.product_id and account.license_group_id)
    if has_creds:
        chk_err = ""
        for attempt in range(MAX_PROXY_RETRIES_PER_EMAIL + 1):
            proxy = proxy_pool.next_proxy(proxy_raw)
            try:
                adobe_admin.check_admin(
                    token=account.admin_token, org_id=account.org_id, proxy_url=proxy,
                )
                proxy_pool.report_success(proxy)
                return True
            except Exception as e:  # noqa: BLE001
                chk_err = str(e)
                if _is_proxy_failure(chk_err):
                    proxy_pool.report_failure(proxy, chk_err)
                    if attempt < MAX_PROXY_RETRIES_PER_EMAIL:
                        continue
                    # 代理连续失败:token 未必失效,别贸然 OTP 全量重登,本轮先用现有凭据继续
                    job.log(f"{prefix}⚠ check_admin 代理连续失败,暂用现有管理凭据:{_compact_error(chk_err)}")
                    return True
                break   # 非代理错误 → 可能真失效 → 降级重登
        job.log(f"{prefix}管理 token 校验失败,尝试重新登录:{chk_err[:120]}")

    if not ((account.refresh_token and account.client_id) or account.mail_url):
        job.log(f"{prefix}✗ 缺少 Refresh Token / Client ID 或取信接口,无法自动登录,跳过")
        return False

    job.log(f"{prefix}自动登录获取管理权限 …")
    res = None
    last_err = ""
    for attempt in range(MAX_PROXY_RETRIES_PER_EMAIL + 1):
        proxy = proxy_pool.next_proxy(proxy_raw)
        try:
            res = adobe_admin.login_account(
                email=account.email, adobe_password=account.adobe_password,
                refresh_token=account.refresh_token, client_id=account.client_id,
                mail_url=account.mail_url,
                proxy_url=proxy, otp_timeout=180,
                log=lambda m: job.log(f"{prefix}{m}"),
            )
            proxy_pool.report_success(proxy)
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            proxy_pool.report_failure(proxy, last_err)
            if _is_proxy_failure(last_err) and attempt < MAX_PROXY_RETRIES_PER_EMAIL:
                job.log(f"{prefix}🌐 登录代理失败,换代理重试 "
                        f"{attempt + 1}/{MAX_PROXY_RETRIES_PER_EMAIL}:{_compact_error(last_err)}")
                continue
            if _is_proxy_failure(last_err):
                # 代理连续失败:是代理问题不是账号问题,保留有效性,下轮再试
                account.check_message = ("登录代理连续失败:" + _compact_error(last_err))[:500]
                db.commit()
                job.log(f"{prefix}✗ 登录失败(代理连续失败,保留有效性,下轮重试)")
                return False
            # 真实登录失败 → 标记无效
            account.is_valid = False
            account.check_message = last_err[:500]
            db.commit()
            job.log(f"{prefix}✗ 登录失败:{last_err[:160]}")
            return False

    _apply_login_result(account, res)
    db.commit()
    if not account.has_org:
        job.log(f"{prefix}✗ 登录成功但未发现可用组织/产品,跳过")
        return False
    job.log(f"{prefix}✓ 已获取管理权限,授权产品:{account.product_name or account.product_id}")
    return True


def _mark_email_used_with_reason(db, email: str, reason: str) -> None:
    row = email_crud.get_by_email(db, email)
    if not row:
        return
    row.is_used = True
    row.used_at = datetime.now(timezone.utc)
    remark = (row.remark or "").strip()
    if reason and reason not in remark:
        row.remark = (remark + " " + reason).strip()


def _build_one_team(
    db, job: Job, account, count: int, proxy_raw: str, concurrency: int, team: dict,
    mode: str = "target",
) -> None:
    admin_id = account.id
    prefix = team.get("prefix", "")

    token = account.admin_token
    org_id = account.org_id
    product_id = account.product_id
    lgid = account.license_group_id

    registered_now = member_crud.count_registered_with_credit(
        db, admin_id, REQUIRED_CREDITS
    )
    team["success"] = registered_now
    job.bump(success=registered_now)
    remaining = count if mode == "add" else (count - registered_now)
    max_attempts = max(0, remaining) * MAX_ATTEMPTS_PER_SLOT
    attempts = 0
    added_now = 0
    email_failures = 0
    proxy_failures = 0
    consecutive_proxy_failures = 0
    cleanup_rounds = 0
    job.log(
        f"{prefix}任务开始：目标 {count}，已有合格 {registered_now}，"
        f"还需 {remaining}，最多尝试 {max_attempts} 个邮箱"
    )
    if remaining <= 0:
        team["status"] = "done"
        team["message"] = "target reached"
        return

    try:
        cleanup = _cleanup_remote_slots(
            db,
            job,
            account,
            proxy_raw,
            prefix,
            f"[预清理] #{job.id}",
            reason="拉号前预清理",
        )
        if cleanup["cleanup_candidates"]:
            cleanup_rounds += 1
    except Exception as e:  # noqa: BLE001
        job.log(f"{prefix}⚠ 拉号前预清理失败:{str(e)[:160]}")

    existing, _ = member_crud.list_by_admin(db, admin_id, page=1, size=1000)
    attempted: set[str] = {m.email.lower() for m in existing}

    while remaining > 0 and attempts < max_attempts and not job.cancelled:
        batch_size = max(1, min(concurrency, remaining, max_attempts - attempts))
        rows = pool_claim.claim(db, batch_size, extra_exclude=attempted)
        if not rows:
            job.log(f"{prefix}邮箱池已无可用邮箱")
            team["message"] = "email pool exhausted"
            break

        claimed_emails = [r.email for r in rows]
        for r in rows:
            attempted.add(r.email.lower())
        payloads = []
        for offset, r in enumerate(rows, start=1):
            attempt_no = attempts + offset
            payloads.append({
                "email": r.email,
                "refresh_token": r.refresh_token,
                "client_id": r.client_id,
                "proxy_retry": 0,
                "attempt_no": attempt_no,
                "attempt_label": _attempt_label(job, attempt_no, max_attempts),
            })

        try:
            job.log(
                f"{prefix}本批拉取 {len(payloads)} 个，并发 {len(payloads)}，"
                f"进度 {attempts}/{max_attempts}"
            )

            def _do(p: dict) -> tuple[dict, tuple[bool, dict, str]]:
                proxy_url = proxy_pool.next_proxy(proxy_raw)
                try:
                    result = _register_one(
                        token=token, org_id=org_id, product_id=product_id, lgid=lgid,
                        proxy_url=proxy_url, email=p["email"],
                        refresh_token=p["refresh_token"], client_id=p["client_id"],
                        job=job, prefix=prefix, attempt_label=p["attempt_label"],
                    )
                    ok, _rec, msg = result
                    if ok:
                        proxy_pool.report_success(proxy_url)
                    else:
                        proxy_pool.report_failure(proxy_url, msg)
                    return p, result
                except Exception as e:  # noqa: BLE001
                    proxy_pool.report_failure(proxy_url, str(e))
                    return p, (False, {}, f"single account error:{str(e)[:240]}")

            results: list[tuple[dict, tuple[bool, dict, str]]] = []
            with ThreadPoolExecutor(max_workers=len(payloads)) as ex:
                for res in ex.map(_do, payloads):
                    results.append(res)
        finally:
            pool_claim.release(claimed_emails)

        for p, (ok, rec, msg) in results:
            email = p["email"]
            attempt_label = p["attempt_label"]
            if _is_proxy_failure(msg):
                attempted.discard(email.lower())  # 代理失败邮箱会被释放,移出以便本母号复用
                proxy_failures += 1
                consecutive_proxy_failures += 1
                retry_no = int(p.get("proxy_retry") or 0) + 1
                if retry_no <= MAX_PROXY_RETRIES_PER_EMAIL and attempts < max_attempts:
                    p["proxy_retry"] = retry_no
                    _attempt_email_log(
                        job,
                        prefix,
                        attempt_label,
                        email,
                        f"🌐 代理失败：{_compact_error(msg)}，换代理重试 "
                        f"{retry_no}/{MAX_PROXY_RETRIES_PER_EMAIL}，不计入邮箱尝试",
                    )
                    retry_proxy = proxy_pool.next_proxy(proxy_raw)
                    try:
                        p_result = _register_one(
                            token=token,
                            org_id=org_id,
                            product_id=product_id,
                            lgid=lgid,
                            proxy_url=retry_proxy,
                            email=email,
                            refresh_token=p["refresh_token"],
                            client_id=p["client_id"],
                            job=job,
                            prefix=prefix,
                            attempt_label=attempt_label,
                        )
                        retry_ok, _retry_rec, retry_msg = p_result
                        if retry_ok:
                            proxy_pool.report_success(retry_proxy)
                        else:
                            proxy_pool.report_failure(retry_proxy, retry_msg)
                    except Exception as e:  # noqa: BLE001
                        proxy_pool.report_failure(retry_proxy, str(e))
                        p_result = (False, {}, f"single account error:{str(e)[:240]}")
                    ok, rec, msg = p_result
                    if _is_proxy_failure(msg):
                        proxy_failures += 1
                        consecutive_proxy_failures += 1
                        _attempt_email_log(
                            job,
                            prefix,
                            attempt_label,
                            email,
                            f"🌐 代理仍失败：{_compact_error(msg)}，释放邮箱稍后再试",
                        )
                        if consecutive_proxy_failures >= max(6, concurrency * 3):
                            team["message"] = "proxy failures too many, paused"
                            attempts = max_attempts
                            continue
                        continue
                else:
                    _attempt_email_log(
                        job,
                        prefix,
                        attempt_label,
                        email,
                        f"🌐 代理失败：{_compact_error(msg)}，不计入邮箱失败",
                    )
                    if consecutive_proxy_failures >= max(6, concurrency * 3):
                        team["message"] = "proxy failures too many, paused"
                        attempts = max_attempts
                        continue
                    continue

            if _is_license_full(msg):
                consecutive_proxy_failures = 0
                _attempt_email_log(
                    job, prefix, attempt_label, email,
                    f"🧹 名额已满：{_compact_error(msg)}，先清理远端占位，不计入邮箱失败",
                )
                if cleanup_rounds < MAX_LICENSE_CLEANUP_ROUNDS:
                    cleanup_rounds += 1
                    try:
                        cleanup = _cleanup_remote_slots(
                            db,
                            job,
                            account,
                            proxy_raw,
                            prefix,
                            attempt_label,
                            reason=f"名额已满，第 {cleanup_rounds}/{MAX_LICENSE_CLEANUP_ROUNDS} 轮",
                        )
                        if cleanup["removed"] <= 0 and not cleanup.get("failed"):
                            team["message"] = "license full and no removable remote members"
                            attempts = max_attempts
                            continue
                    except Exception as e:  # noqa: BLE001
                        team["message"] = f"license full, remote cleanup failed:{str(e)[:160]}"
                        attempts = max_attempts
                        continue
                else:
                    team["message"] = "license still full after cleanup rounds"
                    attempts = max_attempts
                    continue
                continue

            attempts += 1
            if ok:
                consecutive_proxy_failures = 0
                extra = {
                    "registered": True,
                    "display_name": rec.get("display_name") or "",
                    "cookie": rec.get("cookie") or "",
                    "access_token": rec.get("access_token") or "",
                    "credits": rec.get("credits"),
                    "expires_at": rec.get("expires_at"),
                    "refresh_token": rec.get("rotated_refresh_token")
                    or p["refresh_token"],
                    "client_id": p["client_id"],
                }
                member_crud.upsert(
                    db, admin_id, email=email, member_id=rec.get("member_id", ""),
                    status="registered", message="ready", extra=extra,
                )
                email_crud.mark_used_by_email(db, email)
                db.commit()
                _push_one_to_sub2(db, email, rec, job, prefix,  # 成功一个立刻 cookie 推 Sub2
                                  getattr(account, "platform", None))  # 按母号平台推对应分组
                job.bump(success=1)
                added_now += 1
                team["success"] = team.get("success", 0) + 1
                remaining -= 1
                _attempt_email_log(
                    job, prefix, attempt_label, email,
                    f"✅ 验证码通过啦，额度 {rec.get('credits')}",
                )
                continue

            job.bump(fail=1)
            consecutive_proxy_failures = 0
            email_failures += 1
            team["fail"] = team.get("fail", 0) + 1
            compact_msg = _compact_error(msg)
            _attempt_email_log(job, prefix, attempt_label, email, f"💔 未开通: {compact_msg}")

            failure_reason = _email_failure_reason(msg)
            if failure_reason:
                _mark_email_used_with_reason(db, email, failure_reason)
                db.commit()
                _attempt_email_log(
                    job, prefix, attempt_label, email,
                    f"🧺 已放入失败池：{failure_reason}",
                )

            _remove_failed_remote_member(
                token=token,
                org_id=org_id,
                email=email,
                member_id=rec.get("member_id", ""),
                proxy_raw=proxy_raw,
                job=job,
                prefix=prefix,
                reason=failure_reason or "transient_failure",
                attempt_label=attempt_label,
            )

            if "credits" in msg or "额度" in msg or "棰濆害" in msg:
                _mark_email_used_with_reason(db, email, "bad_credit")

        account.member_count = member_crud.count_by_admin(db, admin_id)
        db.commit()

    regd = member_crud.count_registered_with_credit(db, admin_id, REQUIRED_CREDITS)
    account.member_count = member_crud.count_by_admin(db, admin_id)
    db.commit()
    team["success"] = regd
    team["status"] = "done" if (added_now if mode == "add" else regd) >= count else "partial"
    if not team.get("message"):
        if regd >= count:
            team["message"] = f"registered {regd}/{count}"
        else:
            team["message"] = (
                f"registered {regd}/{count}, attempts {attempts}/{max_attempts}"
            )
    job.log(
        f"{prefix}🎉 全部完成：已有合格 {registered_now}，本次新增 {added_now}，"
        f"邮箱失败 {email_failures}，代理失败 {proxy_failures}，"
        f"最终合格 {regd}/{count}"
    )


def build_team_worker(job: Job) -> None:
    """单主号拉号。"""
    admin_id = int(job.meta.get("admin_id"))
    count = int(job.meta.get("count") or 9)
    mode = job.meta.get("mode") or "target"
    db = SessionLocal()
    try:
        account = adobe_crud.get(db, admin_id)
        if not account:
            job.status = "error"
            job.error = "母号不存在"
            return

        settings = setting_crud.get_settings(db)
        proxy_raw = settings.proxy_url if settings.proxy_enabled else ""
        concurrency = max(1, int(settings.concurrency or 1))
        n_proxy = proxy_pool.proxy_count(proxy_raw)
        if n_proxy:
            job.log(f"已配置 {n_proxy} 个代理,拉号时按行轮换出口")

        job.target = count
        team = {"admin_id": admin_id, "email": account.email, "target": count,
                "success": 0, "fail": 0, "status": "running", "message": "",
                "prefix": ""}
        job.set_extra("teams", [team])

        if not _ensure_admin(db, account, proxy_raw, job, ""):
            team["status"] = "error"
            team["message"] = account.check_message or "未取得管理权限"
            job.status = "error"
            job.error = team["message"]
            return

        _build_one_team(db, job, account, count, proxy_raw, concurrency, team, mode=mode)
        job.set_extra("teams", [team])
        regd = member_crud.count_registered(db, admin_id)
        job.result = {"target": count, "registered_total": regd}
        job.log(f"=== 完成:当前注册可用 {regd}/{count} ===")
    finally:
        db.close()


def build_team_batch_worker(job: Job) -> None:
    """多主号批量拉号(按主号顺序处理,每号内子号并发)。"""
    admin_ids = [int(a) for a in (job.meta.get("admin_ids") or [])]
    count = int(job.meta.get("count") or 9)
    mode = job.meta.get("mode") or "target"
    db = SessionLocal()
    try:
        settings = setting_crud.get_settings(db)
        proxy_raw = settings.proxy_url if settings.proxy_enabled else ""
        concurrency = max(1, int(settings.concurrency or 1))
        n_proxy = proxy_pool.proxy_count(proxy_raw)
        if n_proxy:
            job.log(f"已配置 {n_proxy} 个代理,拉号时按行轮换出口")

        job.target = count * len(admin_ids)
        teams: list[dict] = []
        for aid in admin_ids:
            acc = adobe_crud.get(db, aid)
            teams.append({
                "admin_id": aid,
                "email": acc.email if acc else f"#{aid}",
                "target": count, "success": 0, "fail": 0,
                "status": "pending", "message": "", "prefix": "",
            })
        job.set_extra("teams", teams)

        for idx, aid in enumerate(admin_ids, start=1):
            if job.cancelled:
                break
            team = teams[idx - 1]
            team["prefix"] = f"[{idx}/{len(admin_ids)} {team['email']}] "
            account = adobe_crud.get(db, aid)
            if not account:
                team["status"] = "error"
                team["message"] = "母号不存在"
                job.set_extra("teams", teams)
                continue

            team["status"] = "running"
            job.log(f"===== 开始处理母号 {team['email']} ({idx}/{len(admin_ids)}) =====")
            job.set_extra("teams", teams)
            try:
                if not _ensure_admin(db, account, proxy_raw, job, team["prefix"]):
                    team["status"] = "error"
                    team["message"] = account.check_message or "未取得管理权限,已跳过"
                    job.set_extra("teams", teams)
                    continue
                _build_one_team(db, job, account, count, proxy_raw, concurrency, team, mode=mode)
            except Exception as e:  # noqa: BLE001
                team["status"] = "error"
                team["message"] = str(e)[:200]
                job.log(f"{team['prefix']}✗ 异常:{str(e)[:200]}")
            job.set_extra("teams", teams)

        done = sum(1 for t in teams if t["status"] == "done")
        job.result = {"teams": len(admin_ids), "fully_done": done}
        job.log(f"=== 批量完成:{done}/{len(admin_ids)} 个主号已凑满 ===")
    finally:
        db.close()
