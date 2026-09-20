"""Adobe Admin Console 管理服务。

封装:管理员登录(自动收验证码)→ 发现组织/产品/授权组 → 批量加子账号并授权
→ 检测有效性 → 删除成员。所有网络请求复用内置协议(curl_cffi Chrome 指纹)。
"""

from __future__ import annotations

import random
import secrets
import string
import time
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from app.services import arkose as _arkose
from app.services.adobe_otp import make_otp_poller
from app.services.adobe_protocol import admin_member_protocol as _p
from app.services.adobe_protocol.admin_member_protocol import (
    AdminAuth,
    ProtocolError,
    add_member,
    choose_org,
    choose_product,
    client_from_state,
    find_member_id_by_email,
    get_organizations,
    get_products,
    list_members,
    remove_members,
)

LogFn = Callable[[str], None]
_AUTH_HOST = _p.AUTH_HOST

def _new_sub_password() -> str:
    """每个首次补全的账号使用独立密码,交由 Adobe 的密码预检确认。"""
    groups = (string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%")
    chars = [secrets.choice(group) for group in groups]
    chars.extend(secrets.choice("".join(groups)) for _ in range(16))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)

_FIRST_NAMES = [
    "Daniel", "Michael", "James", "David", "John", "Robert", "William", "Joseph",
    "Thomas", "Charles", "Emily", "Sarah", "Jessica", "Ashley", "Jennifer",
    "Amanda", "Laura", "Olivia", "Emma", "Sophia", "Ryan", "Kevin", "Brian",
    "Eric", "Steven", "Andrew", "Joshua", "Brandon", "Justin", "Aaron",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Taylor",
    "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
    "Clark", "Lewis", "Walker", "Hall", "Allen", "Young", "King", "Wright",
]

# marketingConsent 文案(与浏览器抓包一致,服务端会校验存在性)
_MARKETING_CONSENT_TEXT = (
    '<section data-id="MarketingConsent-Implicit"><p>By clicking Complete account, '
    "I agree that:</p><ul class=\"pl-300\"><li>I have read and accepted the "
    '<a href="https://www.adobe.com/legal/terms-linkfree.html" target="_blank" '
    'rel="noreferrer">Terms of Use</a>.</li><li>The '
    '<a href="https://www.adobe.com/privacy/policy-linkfree.html" target="_blank" '
    'rel="noreferrer">Adobe family of companies</a> may keep me informed with '
    '<a href="https://www.adobe.com/privacy/marketing-linkfree.html#mktg-email" '
    'target="_blank" rel="noreferrer">personalized</a> emails about products and '
    'services.</li></ul><p>See our <a '
    'href="https://www.adobe.com/privacy/policy-linkfree.html#info-share" '
    'target="_blank" rel="noreferrer">Privacy Policy</a> for more details or to '
    "opt-out at any time.</p></section>"
)


def _register_region() -> tuple[str, str]:
    """读取注册/补全账号所用的国家与 locale(默认 SG / en_US)。

    US 区会被 Adobe 的 firefly_geoip_blocking 及第三方模型地区灰度挡掉,
    SG(新加坡)实测放行。可在「系统设置」里调整。
    """
    try:
        from app.crud import setting as _setting_crud
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            s = _setting_crud.get_settings(db)
            return (s.register_country or "SG"), (s.register_locale or "en_US")
        finally:
            db.close()
    except Exception:
        return "SG", "en_US"


def _random_name() -> tuple[str, str]:
    return random.choice(_FIRST_NAMES), random.choice(_LAST_NAMES)


def _random_dob() -> dict[str, int]:
    """随机生成一个成年人的出生日期(规避 COPPA 未成年限制)。"""
    return {
        "day": random.randint(1, 28),
        "month": random.randint(1, 12),
        "year": random.randint(1980, 2000),
    }


_COMPLETE_PUT_TIMEOUT = 60
# PUT v4 回 400 但 errorCode=SERVICE_ERROR 时额外重试几次。
# 实测线上:同一个号相隔 90 秒两次提交,一次 captcha_required、一次
#   400 {"errorCode":"SERVICE_ERROR","errorMessage":"Error validating password
#        policy in CS for userId ...@AdobeID"}
# 同样的 payload、同样的密码却报不一样的错 —— 确定性的密码不合规不会时有时无,
# 这是 Adobe 侧的上游抖动。以前只对 status>=500 重试,这种包在 400 里的服务端
# 错误一次都不重试就把号判死了。
_COMPLETE_SERVICE_ERROR_RETRIES = 2
_COMPLETE_PUT_URL = "/signin/v4/accounts"


def _is_service_error(status: int, body: str) -> bool:
    """400/409 里包着的 Adobe 服务端错误(不是我们提交的数据有问题)。"""
    if status >= 500:
        return True
    if status not in (400, 409):
        return False
    low = (body or "").lower()
    return "service_error" in low or "internal_error" in low


def _put_complete_v4(auth: "AdminAuth", payload: dict[str, Any], lf: LogFn,
                     *, arkose_token: str = "") -> Any:
    """PUT /signin/v4/accounts. Echo IMS auth state from every response."""
    r = auth.client.put(
        f"{_AUTH_HOST}{_COMPLETE_PUT_URL}",
        headers=_arkose.complete_headers(auth, arkose_token),
        json=payload, timeout=_COMPLETE_PUT_TIMEOUT,
    )
    _arkose.echo_auth_state(auth, r)
    return r


def _complete_profile_with_arkose(auth: "AdminAuth", payload: dict[str, Any],
                                  lf: LogFn) -> None:
    """First PUT without token; on captcha_required, solve blob and retry.

    IMS enables Arkose on complete-account. PUT /signin/v2/accounts now returns
    403 "Use /v4/accounts when Arkose captcha is enabled". Keep the same HTTP
    client for both PUTs — a fresh TLS session drops the incompleteAccount
    state and the retry is refused even with a good token.
    """
    last_err: Exception | None = None
    tries = 1 + _COMPLETE_SERVICE_ERROR_RETRIES
    for net_try in range(1, tries + 1):
        try:
            lf(f"PUT v4 accounts arkose={False}")
            r = _put_complete_v4(auth, payload, lf, arkose_token="")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if net_try >= tries:
                raise AdminError(f"补全账号请求异常:{e}") from e
            lf(f"补全账号请求异常:{e},准备重试…")
            time.sleep(2)
            continue
        status = r.status_code
        body = r.text or ""
        lf(f"PUT v4 status={status} arkose=false")
        if status == 200:
            return
        if _arkose.already_completed(status, body):
            lf(f"补全资料 IMS 回报已写入({status}),继续")
            return
        if _is_service_error(status, body) and net_try <= _COMPLETE_SERVICE_ERROR_RETRIES:
            lf(f"补全账号失败 {status}(Adobe 服务端错误),"
               f"第 {net_try}/{_COMPLETE_SERVICE_ERROR_RETRIES} 次重试:{body[:160]}")
            time.sleep(3 * net_try)
            continue
        if not _arkose.is_captcha_required(status, body):
            raise AdminError(f"补全账号失败 {status}: {body[:240]}")
        _retry_complete_after_arkose(auth, payload, r, lf)
        return
    if last_err:
        raise AdminError(f"补全账号请求异常:{last_err}") from last_err
    raise AdminError("补全账号失败")


def _retry_complete_after_arkose(auth: "AdminAuth", payload: dict[str, Any],
                                 first: Any, lf: LogFn) -> None:
    blob = _arkose.captcha_blob(first)
    if not blob:
        raise AdminError(
            "补全账号 captcha_required 但缺少 x-ims-captcha-encrypted,无法打码"
        )
    provider, api_key = _arkose.load_captcha_config()
    if not provider or not api_key:
        raise AdminError(
            "补全账号需要 Arkose 打码:请在设置里填 captcha_provider "
            "(yescaptcha) 和 captcha_key,或环境变量 "
            "ADOBE_CAPTCHA_PROVIDER / ADOBE_CAPTCHA_KEY"
        )
    website = getattr(auth, "auth_referer", "") or _arkose.DEFAULT_WEBSITE_URL
    user_agent = getattr(getattr(auth, "client", None), "user_agent", "") or ""
    proxy_url = getattr(getattr(auth, "client", None), "proxy", "") or ""
    last_err: Exception | None = None
    try_n = 1
    nav_retries = 0
    while try_n <= _arkose.ARKOSE_TRIES:
        try:
            result = _arkose.solve(
                provider=provider, api_key=api_key, website_url=website,
                blob=blob, user_agent=user_agent, proxy_url=proxy_url, log=lf,
            )
        except Exception as e:  # noqa: BLE001
            last_err = e
            if _arkose.not_retryable(e) or _arkose.is_unknown_question(e):
                raise AdminError(f"补全账号 Arkose 失败: {e}") from e
            if _arkose.is_navigation_failed(e) and nav_retries < 3:
                nav_retries += 1
                lf(
                    f"arkose 导航失败,不计入 {_arkose.ARKOSE_TRIES} 次配额 "
                    f"(第 {nav_retries}/3 次免费重试)"
                )
                continue
            lf(f"arkose 打码失败({try_n}/{_arkose.ARKOSE_TRIES}):{e}")
            try_n += 1
            continue
        token = getattr(result, "token", result) or ""
        cookies = getattr(result, "cookies", None)
        _arkose.inject_solver_cookies(auth.client, cookies)
        lf(f"PUT v4 retry after arkose (same client) try={try_n}")
        try:
            r = _put_complete_v4(auth, payload, lf, arkose_token=token)
        except Exception as e:  # noqa: BLE001
            last_err = e
            lf(f"补全账号打码后请求异常:{e}")
            try_n += 1
            continue
        status = r.status_code
        body = r.text or ""
        lf(f"PUT v4 retry status={status} arkose=true")
        if status == 200 or _arkose.already_completed(status, body):
            if status != 200:
                lf("PUT v4 retry 回报账号已补全,沿用当前会话")
            return
        if _arkose.is_captcha_required(status, body):
            blob = _arkose.captcha_blob(r) or blob
            last_err = AdminError(f"arkose token 被拒 {status}: {body[:180]}")
            lf(str(last_err))
            try_n += 1
            continue
        raise AdminError(f"补全账号失败 {status}: {body[:240]}")
    raise AdminError(f"补全账号 Arkose 失败: {last_err}")


def complete_sub_account(
    auth: "AdminAuth", email: str, lf: LogFn, password: str | None = None,
    *, country: str = "", locale: str = "",
    poll: Optional[Callable] = None, otp_timeout: int = 180,
) -> str:
    """被邀请子号首次登录:若账号未补全,自动填写姓名/密码/生日并接受条款,
    然后激活并切换到企业(被邀请)资料,使后续可换取 firefly token。

    复用收到验证码后的 incompleteAccount 会话(auth.susi_token)。幂等:已补全则只切资料。

    返回**本次实际设置的密码**;账号本来就已补全(密码不是我们设的)时返回 ""。
    调用方据此决定要不要把密码记进库里。
    """
    try:
        r = auth.client.get(
            f"{_AUTH_HOST}/signin/v1/accounts/me?client_id={auth.client_id}",
            headers=auth.headers(), timeout=20,
        )
        data = r.json() if r.status_code == 200 else {}
    except Exception as e:  # noqa: BLE001
        lf(f"读取子号资料失败:{e}")
        return ""
    if not isinstance(data, dict) or not data:
        return ""

    profile = data.get("profileData") or {}
    actions = profile.get("actions") or []
    incomplete = any(
        (a.get("code") == "IncompleteProfile") for a in actions if isinstance(a, dict)
    ) or not data.get("firstName")

    if incomplete:
        password = password or _new_sub_password()
        if not country or not locale:
            cfg_country, cfg_locale = _register_region()
            country = country or cfg_country
            locale = locale or cfg_locale
        first, last = _random_name()
        dob = _random_dob()
        lf(f"账号未补全,自动补全资料(姓名 {first} {last} / 生日 {dob['year']} / "
           f"地区 {country} / 设置密码)…")
        # 密码预检请求失败不阻断,但明确拒绝时不能继续提交同一无效密码。
        # 这两个接口就是 Adobe 用来回答「这个密码能不能用」的 —— 以前调完把响应
        # 直接丢了,于是 PUT v4 回 SERVICE_ERROR "Error validating password policy
        # in CS" 时完全无从判断是 Adobe 抽风还是这个密码被拉黑。现在把状态码和
        # 响应体记进日志(不打印密码本身)。
        for label, path, body in (
            ("合规", "/signin/v1/passwords/validity?existingUser=true",
             {"password": password}),
            ("泄露", "/signin/v1/passwords/leak_verification",
             {"username": email, "password": password}),
        ):
            valid = None
            try:
                pr = auth.client.post(
                    f"{_AUTH_HOST}{path}", headers=auth.headers(), json=body, timeout=15
                )
                lf(f"密码{label}校验 status={pr.status_code} "
                   f"body={(pr.text or '')[:160]}")
                if pr.status_code == 200:
                    result = pr.json()
                    valid = result.get("valid") if isinstance(result, dict) else None
            except Exception as e:  # noqa: BLE001
                lf(f"密码{label}校验请求异常:{str(e)[:120]}")
            if valid is False:
                raise AdminError(f"Adobe 密码{label}校验未通过,未提交账号资料")

        account = {
            "email": email,
            "phoneNumber": None,
            "firstName": first,
            "lastName": last,
            "password": password,
            "countryCode": country,
            "phoneticFirstName": None,
            "phoneticLastName": None,
            "termsOfUseAcceptances": [
                {"accepted": True, "name": "ADOBE_MASTER", "language": locale}
            ],
            "marketingConsent": {"text": _MARKETING_CONSENT_TEXT, "accepted": True},
            "isPasswordless": False,
            "type": "individual",
            "dateOfBirth": dob,
        }
        # 空 userId 不要带:IMS 把 "userId":"" 和「不带 userId」当成不同请求.
        user_id = str(data.get("userId") or "").strip()
        if user_id:
            account["userId"] = user_id
        payload = {
            "account": account,
            "regionalOptInKorea": None,
            "regionalOptInChina": None,
            "locale": locale,
        }
        _complete_profile_with_arkose(auth, payload, lf)
        lf("✓ 已补全账号资料")
        # 重新拉取资料,拿到更新后的链接
        try:
            r = auth.client.get(
                f"{_AUTH_HOST}/signin/v1/accounts/me?client_id={auth.client_id}",
                headers=auth.headers(), timeout=20,
            )
            data = r.json() if r.status_code == 200 else data
            profile = data.get("profileData") or {}
        except Exception:
            pass

    # 用当前(补全/首登)会话先激活企业资料 link。必须在这里激活,而不是放到后面的
    # type2e 密码登录链里 —— 激活会作废当前会话,若在链中途激活会导致后续 filtered_profiles
    # 401。这里激活后,后面 firefly._acquire_firefly_token 的密码登录会话看到的就是 active。
    links = profile.get("links") or []
    link = next(
        (lk for lk in links if lk.get("ident") and lk.get("status") != "active"), None
    )
    if link:
        try:
            r = auth.client.post(
                f"{_AUTH_HOST}/signin/v2/links/{link['ident']}",
                headers=auth.headers(), json={"status": "active"}, timeout=15,
            )
            lf(f"激活企业资料 {link.get('description') or '-'} status={r.status_code}")
        except Exception as e:  # noqa: BLE001
            lf(f"激活企业资料异常:{e}")
    # 企业 type2e 会话 + firefly token 由 firefly._acquire_firefly_token 统一建立。
    return password if incomplete else ""


def _mklog(log: Optional[LogFn]) -> LogFn:
    return log if callable(log) else (lambda _m: None)


class AdminError(RuntimeError):
    pass


# ----------------------------------------------------------------------------
# 登录流程辅助(自动识别 密码 / 免密码 / MFA 账号)
# ----------------------------------------------------------------------------

def _probe_auth_methods(auth: "AdminAuth", email: str) -> list[str]:
    r = auth.client.post(
        f"{_AUTH_HOST}/signin/v2/users/accounts",
        headers=auth.headers(), json={"email": email}, timeout=20,
    )
    auth.auth_state_encrypted = r.headers.get(
        "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
    auth.identity_verification_token = r.headers.get(
        "x-identity-verification-token", auth.identity_verification_token)
    methods: list[str] = []
    try:
        data = r.json()
        accounts = data if isinstance(data, list) else [data]
        for acc in accounts:
            if isinstance(acc, dict):
                methods += [str(m) for m in (acc.get("authenticationMethods") or [])]
    except Exception:
        pass
    return methods


def _fresh_auth_session(client, email: str) -> "AdminAuth":
    auth = AdminAuth(client)
    auth.authorize(email, "en_US")
    _probe_auth_methods(auth, email)
    return auth


# 收验证码:单次 30 秒;没收到就重新提交验证码邮件,不继续空等旧邮件。
_OTP_RETRY_ATTEMPTS = 3
_OTP_PER_TRY_SECONDS = 30


def _otp_per_try_seconds(otp_timeout: int) -> int:
    del otp_timeout
    return _OTP_PER_TRY_SECONDS


def _poll_email_code_with_retry(
    email: str,
    poll: Callable,
    lf: LogFn,
    otp_timeout: int,
    *,
    resend: Callable[[], None],
    refresh: Callable[[], None] | None = None,
) -> str:
    """分轮收取验证码:每轮只等 30 秒,超时则重新提交验证码邮件。"""
    per_try = _otp_per_try_seconds(otp_timeout)
    last_err: Exception | None = None
    for attempt in range(1, _OTP_RETRY_ATTEMPTS + 1):
        if attempt > 1:
            lf(f"第 {attempt}/{_OTP_RETRY_ATTEMPTS} 次重发验证码(本轮最多等 {per_try}s)…")
            if refresh:
                refresh()
            resend()
        else:
            lf(f"等待收取验证码(本轮 {per_try}s,超时自动重发,最多 {_OTP_RETRY_ATTEMPTS} 轮)…")
        try:
            return poll(email, timeout=per_try)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _OTP_RETRY_ATTEMPTS:
                lf(f"本轮未收到验证码,准备重试…")
    raise AdminError(str(last_err)[:200] if last_err else "收取 Adobe 验证码超时")


def _refresh_incomplete_challenge(auth: "AdminAuth") -> None:
    try:
        r = auth.client.get(
            f"{_AUTH_HOST}/signin/v3/challenges?purpose=incompleteAccount",
            headers=auth.headers(), timeout=15,
        )
        auth.auth_state_encrypted = r.headers.get(
            "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
        auth.identity_verification_token = r.headers.get(
            "x-identity-verification-token", auth.identity_verification_token)
    except Exception:
        pass


def _send_incomplete_account_email(auth: "AdminAuth") -> None:
    r = auth.client.post(
        f"{_AUTH_HOST}/signin/v3/challenges"
        "?purpose=incompleteAccount&factor=email&extendedAuthState=false",
        headers=auth.headers(), json={}, timeout=15,
    )
    if r.status_code != 200:
        body = r.text or ""
        if "confirmation_abuse_detected" in body:
            raise AdminError("Adobe 限制发送验证码:尝试次数过多,请稍后再试")
        raise AdminError(f"发送验证码邮件失败 {r.status_code}: {body[:200]}")
    auth.auth_state_encrypted = r.headers.get(
        "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
    auth.identity_verification_token = r.headers.get(
        "x-identity-verification-token", auth.identity_verification_token)


def _refresh_mfa_challenge(auth: "AdminAuth") -> None:
    try:
        r = auth.client.get(
            f"{_AUTH_HOST}/signin/v3/challenges?purpose=multiFactorAuthentication",
            headers=auth.headers(), timeout=15,
        )
        auth.auth_state_encrypted = r.headers.get(
            "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
        auth.identity_verification_token = r.headers.get(
            "x-identity-verification-token", auth.identity_verification_token)
    except Exception:
        pass


def _try_email_mfa_with_log(
    auth: "AdminAuth", email: str, lf: LogFn, poll: Optional[Callable] = None,
    otp_timeout: int = 180,
    *,
    start_state: bool = True,
) -> bool:
    poll = poll or _p.poll_otp
    if start_state and not auth.start_email_mfa(email):
        lf("✗ 发起邮箱 MFA 失败 (authenticationstate)")
        return False
    if not start_state:
        lf(
            "沿用密码 challenge MFA 状态:"
            f"state={'有' if auth.auth_state_encrypted else '无'}"
            f" ivt={'有' if auth.identity_verification_token else '无'}"
        )
    try:
        if not start_state:
            raise RuntimeError("skip challenge list for password challenge")
        r = auth.client.get(
            f"{_AUTH_HOST}/signin/v3/challenges?purpose=multiFactorAuthentication",
            headers=auth.headers(), timeout=15,
        )
        auth.auth_state_encrypted = r.headers.get(
            "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
        auth.identity_verification_token = r.headers.get(
            "x-identity-verification-token", auth.identity_verification_token)
    except Exception:
        pass
    if not auth.send_email_challenge():
        detail = str(getattr(auth, "last_email_challenge_error", "") or "")
        if "confirmation_abuse_detected" in detail:
            raise AdminError("Adobe 限制发送验证码:尝试次数过多,请稍后再试")
        lf("✗ Adobe 拒绝发送验证码邮件(会话可能已失效)")
        return False
    send_status = getattr(auth, "last_email_challenge_status", "-")
    send_body = str(getattr(auth, "last_email_challenge_body", "") or "")
    lf(
        "✓ 已请求 Adobe 发送验证码 …"
        f" send_status={send_status}"
        f" body={(send_body[:120] or '-')}"
        f" state={'有' if auth.auth_state_encrypted else '无'}"
        f" ivt={'有' if auth.identity_verification_token else '无'}"
    )

    def _resend_mfa() -> None:
        if not auth.send_email_challenge():
            raise AdminError("重发验证码邮件失败")

    try:
        code = _poll_email_code_with_retry(
            email, poll, lf, otp_timeout,
            resend=_resend_mfa, refresh=lambda: _refresh_mfa_challenge(auth),
        )
    except AdminError as e:
        lf(f"✗ 收验证码失败:{e}")
        return False
    if not auth.verify_email_challenge(code):
        detail = str(getattr(auth, "last_email_verify_error", "") or "")
        lf(f"✗ 验证码校验失败:{detail[:220] or '可能已过期或会话失效'}")
        lf("尝试 MFA code token fallback(抓包未包含,按验证码 token 交换推断)…")
        if auth.token_from_mfa_code(code):
            status = getattr(auth, "last_mfa_code_token_status", "-")
            lf(f"✓ MFA code token fallback 成功 status={status}")
            return True
        status = getattr(auth, "last_mfa_code_token_status", "-")
        body = str(getattr(auth, "last_mfa_code_token_body", "") or "")
        lf(f"✗ MFA code token fallback 失败 status={status}: {body[:220]}")
        return False
    lf("✓ 邮箱 MFA 验证成功")
    return True


def _passwordless_login(
    auth: "AdminAuth", email: str, lf: LogFn, poll: Optional[Callable] = None,
    otp_timeout: int = 180,
) -> None:
    poll = poll or _p.poll_otp
    if not auth.start_email_mfa(email):
        raise AdminError("发起邮箱验证失败 (authenticationstate)")
    _refresh_incomplete_challenge(auth)
    _send_incomplete_account_email(auth)
    lf("已发送验证码邮件 …")

    r = None
    for attempt in range(1, 4):
        if attempt > 1:
            lf(f"验证码被 Adobe 拒绝,第 {attempt}/3 次重发新验证码…")
            _refresh_incomplete_challenge(auth)
            _send_incomplete_account_email(auth)
        code = _poll_email_code_with_retry(
            email, poll, lf, otp_timeout,
            resend=lambda: _send_incomplete_account_email(auth),
            refresh=lambda: _refresh_incomplete_challenge(auth),
        )
        r = auth.client.post(
            f"{_AUTH_HOST}/signin/v3/tokens?credential=code",
            headers=auth.headers(),
            json={"purpose": "incompleteAccount", "code": str(code)}, timeout=25,
        )
        body = r.text or ""
        if r.status_code == 200:
            break
        if "invalid_code" not in body or attempt >= 3:
            raise AdminError(f"验证码换 token 失败 {r.status_code}: {body[:200]}")
    if r is None or r.status_code != 200:
        raise AdminError("验证码换 token 失败")
    try:
        data = r.json()
    except Exception:
        data = {}
    token = (data.get("token") or data.get("access_token") or "") if isinstance(data, dict) else ""
    if not token:
        raise AdminError(f"验证码登录未返回 token: {str(data)[:200]}")
    auth.susi_token = token
    auth.auth_state_encrypted = r.headers.get(
        "x-ims-authentication-state-encrypted", auth.auth_state_encrypted)
    auth.identity_verification_token = r.headers.get(
        "x-identity-verification-token", auth.identity_verification_token)
    lf("✓ 验证码登录成功")


def _browser_code_login(
    auth: "AdminAuth", email: str, lf: LogFn,
    *, poll: Optional[Callable] = None, otp_timeout: int = 180,
) -> None:
    """Reproduce the browser's fresh one-time-code login after completion."""
    poll = poll or _p.poll_otp
    auth.authorize(email, "en_US")
    methods = _probe_auth_methods(auth, email)
    lf(f"重新登录认证方式:{', '.join(methods) if methods else '未知'}")
    if not auth.start_email_mfa(email):
        raise AdminError("重新 codeLogin 无法建立 authenticationstate")
    _refresh_mfa_challenge(auth)

    per_try = _otp_per_try_seconds(otp_timeout)
    last_error = ""
    for attempt in range(1, _OTP_RETRY_ATTEMPTS + 1):
        if attempt > 1:
            lf(f"codeLogin 第 {attempt}/{_OTP_RETRY_ATTEMPTS} 次重发验证码…")
            _refresh_mfa_challenge(auth)
        sent = False
        for send_try in range(1, 5):
            if auth.send_code_login_challenge():
                sent = True
                break
            detail = str(getattr(auth, "last_email_challenge_error", "") or "")
            # 刚用 incompleteAccount 收过一次码,codeLogin 因子会短暂 factor_unavailable
            # (冷却)。等待后重建 challenge 再试,而不是直接失败。
            if "factor_unavailable" in detail and send_try < 4:
                wait = 15 * send_try
                lf(f"codeLogin 因子暂不可用(冷却),等待 {wait}s 后重试({send_try}/3)…")
                time.sleep(wait)
                _refresh_mfa_challenge(auth)
                continue
            raise AdminError(f"codeLogin 发送验证码失败:{detail[:200]}")
        if not sent:
            raise AdminError("codeLogin 发送验证码失败:factor_unavailable(冷却超时)")
        lf(
            "✓ 已请求浏览器 codeLogin 验证码 …"
            f" status={getattr(auth, 'last_email_challenge_status', '-') }"
        )
        try:
            code = poll(email, timeout=per_try)
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            lf(f"codeLogin 本轮收码失败:{last_error[:160]}")
            continue
        if auth.token_from_code_login(code):
            lf("✓ 浏览器 codeLogin 成功")
            return
        last_error = str(getattr(auth, "last_mfa_code_token_body", "") or "")
        lf(f"codeLogin 验证码未通过:{last_error[:180]}")

    raise AdminError(f"codeLogin 失败:{last_error[:200] or '未拿到会话 token'}")


def _browser_mfa_login(
    auth: "AdminAuth", email: str, lf: LogFn,
    *, poll: Optional[Callable] = None, otp_timeout: int = 180,
) -> None:
    """补全后用邮箱 MFA(credential=code, purpose=multiFactorAuthentication)重建会话。

    codeLogin(免密)因子被 Arkose captcha 门控,纯 HTTP 后端拿不到(factor_unavailable);
    而邮箱 MFA 因子无需 captcha,后端可稳定获取。其 token 的 credential_type 与
    incompleteAccount / password 不同,用于尝试通过企业资料转发接口。
    """
    poll = poll or _p.poll_otp
    auth.authorize(email, "en_US")
    if not auth.start_email_mfa(email):
        raise AdminError("重新 MFA 无法建立 authenticationstate")
    _refresh_mfa_challenge(auth)
    per_try = _otp_per_try_seconds(otp_timeout)
    last_error = ""
    for attempt in range(1, _OTP_RETRY_ATTEMPTS + 1):
        if attempt > 1:
            lf(f"MFA 第 {attempt}/{_OTP_RETRY_ATTEMPTS} 次重发验证码…")
            _refresh_mfa_challenge(auth)
        if not auth.send_email_challenge():
            detail = str(getattr(auth, "last_email_challenge_error", "") or "")
            if "confirmation_abuse_detected" in detail:
                raise AdminError("Adobe 限制发送验证码:尝试次数过多,请稍后再试")
            raise AdminError(f"MFA 发送验证码失败:{detail[:200]}")
        lf(
            "✓ 已请求邮箱 MFA 验证码 …"
            f" status={getattr(auth, 'last_email_challenge_status', '-')}"
        )
        try:
            code = poll(email, timeout=per_try)
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            lf(f"MFA 本轮收码失败:{last_error[:160]}")
            continue
        if auth.token_from_mfa_code(code):
            lf("✓ 邮箱 MFA 重登成功")
            return
        last_error = str(getattr(auth, "last_mfa_code_token_body", "") or "")
        lf(f"MFA 验证码未通过:{last_error[:180]}")
    raise AdminError(f"MFA 重登失败:{last_error[:200] or '未拿到会话 token'}")


def _select_org_profile(auth: "AdminAuth", lf: LogFn) -> None:
    """type2e(个人邮箱开通的企业资料)需要先选择企业资料才能拿到 admin token。"""
    try:
        r = auth.client.get(
            f"{_AUTH_HOST}/signin/v1/accounts/me"
            f"?client_id={_p.ONESIE_CLIENT_ID}",
            headers=auth.headers(), timeout=20,
        )
        data = r.json() if r.status_code == 200 else {}
    except Exception as e:
        lf(f"读取账号资料失败:{e}")
        return
    links = ((data.get("profileData") or {}).get("links")) or []
    active = [lk for lk in links if lk.get("ident")
             and lk.get("status", "active") == "active"]
    if not active:
        lf("无企业资料链接,按普通账号继续")
        return
    # 组织被删之后这个 link 的 status 仍然是 active,死信号在 description 里
    # ("… Deleted")。把看着已删的排到最后而不是丢掉:全删光时仍要选得出来。
    dead = [lk for lk in active if _p.looks_deleted_org(lk.get("description") or "")]
    if dead and len(dead) < len(active):
        lf(f"跳过 {len(dead)} 个已删组织的企业资料,优先选活的")
    elif dead:
        lf(f"⚠ {len(dead)} 个企业资料全都看着已删,只能先用第一个")
    active.sort(key=lambda lk: 1 if _p.looks_deleted_org(lk.get("description") or "") else 0)
    link = active[0]
    link_id = link["ident"]
    guid = link.get("entitlementAccountUserId") or ""
    lf(f"选择企业资料:{link.get('description') or '-'}")
    admin_filter = (
        '{"fallbackToAA":true};'
        "hasRole('ORG_ADMIN') or hasRole('STORAGE_ADMIN') or "
        "hasRole('DEPLOYMENT_ADMIN') or hasRole('PRODUCT_ADMIN') or "
        "hasRole('PRODUCT_SUPPORT_ADMIN') or hasRole('LICENSE_ADMIN') or "
        "hasRole('SUPPORT_ADMIN') or hasRole('USER_GROUP_ADMIN') or "
        "hasRole('CONTRACT_ADMIN')"
    )
    if guid:
        try:
            auth.client.put(
                f"{_AUTH_HOST}/signin/v1/filterprofilemapping",
                headers=auth.headers(),
                json={"filter": admin_filter, "guid": guid}, timeout=15,
            )
        except Exception:
            pass
    try:
        r = auth.client.post(
            f"{_AUTH_HOST}/signin/v1/ims/tokens",
            headers=auth.headers(),
            json={"rememberMe": True, "reauthenticate": "force"},
            timeout=25,
        )
    except Exception as e:
        lf(f"切换企业资料异常:{e}")
        return
    if r.status_code != 200:
        lf(f"切换企业资料失败 {r.status_code}: {(r.text or '')[:200]}")
        return
    try:
        tok = (r.json() or {}).get("token") or ""
    except Exception:
        tok = ""
    if tok:
        auth.susi_token = tok
        lf("✓ 已切换到企业资料(浏览器 ims/tokens force)")


def _acquire_admin_token(auth: "AdminAuth", lf: LogFn) -> str:
    try:
        r = auth.client.post(
            f"{_AUTH_HOST}/signin/v1/ims/tokens",
            headers=auth.headers(),
            json={"rememberMe": True, "reauthenticate": "force"}, timeout=25,
        )
        tok = ""
        try:
            tok = _p.extract_token_from_obj(r.json())
        except Exception:
            pass
        if tok:
            auth.susi_token = tok
            lf("✓ ims/tokens 换取成功")
    except Exception as e:
        lf(f"ims/tokens 异常:{e}")

    try:
        auth.from_susi_token(None)
    except Exception as e:
        lf(f"fromSusi 预热:{e}")

    def _check_token():
        r = auth.client.post(
            f"{_p.IMS_BACKEND}/ims/check/v6/token"
            "?jslVersion=v2-v0.31.0-2-g1e8a8a8",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "client_id": _p.ONESIE_CLIENT_ID,
                "Origin": "https://adminconsole.adobe.com",
                "Referer": "https://adminconsole.adobe.com/",
            },
            data=urlencode({
                "client_id": _p.ONESIE_CLIENT_ID,
                "scope": _p.ADMIN_SCOPE,
            }),
            timeout=25,
        )
        try:
            return r, (r.json() if isinstance(r.json(), dict) else {})
        except Exception:
            return r, {}

    try:
        r, data = _check_token()
        tok = data.get("access_token") if isinstance(data, dict) else ""
        if r.status_code == 200 and tok:
            lf("✓ 通过 check/v6/token 获取正式 access_token")
            return tok
        err = data.get("error") if isinstance(data, dict) else ""
        if err == "ride_AdobeID_acct_eoaChoose":
            raise AdminError(
                "该账号是 type2e(个人邮箱开通的企业资料),IMS 要求选择账号资料"
                "(eoaChoose),当前流程无法自动完成此选择。"
            )
        lf(f"check/v6/token 未返回 token status={r.status_code}")
    except AdminError:
        raise
    except Exception as e:
        lf(f"check/v6/token 异常:{e}")
    raise AdminError("无法获取有效的 admin access_token")


def _session_cookie_str(client) -> str:
    parts: dict[str, str] = {}
    try:
        jar = client.session.cookies
        d = jar.get_dict() if hasattr(jar, "get_dict") else dict(jar)
        parts.update({k: v for k, v in d.items() if v})
    except Exception:
        pass
    try:
        parts.update({k: v for k, v in (client.cookies or {}).items() if v})
    except Exception:
        pass
    return "; ".join(f"{k}={v}" for k, v in parts.items())


def _run_admin_login(email: str, password: str, proxy_url: str,
                     lf: LogFn, *, otp_timeout: int = 180,
                     poll: Optional[Callable] = None) -> tuple[str, str]:
    """统一登录,返回 (admin_access_token, cookie 字符串)。"""
    client = _p.HttpClient(proxy=proxy_url)
    try:
        auth = AdminAuth(client)
        auth.authorize(email, "en_US")
        methods = _probe_auth_methods(auth, email)
        has_password = any("password" in m.lower() for m in methods)
        lf(f"账号认证方式:{', '.join(methods) if methods else '无(免密码账号)'}")
        if has_password and password:
            # Adobe 现已对母号登录强制邮箱二次验证,密码直登(password_susi)几乎必然
            # 返回 invalid_auth_session("Start over")。直接走验证码登录
            # (incompleteAccount)——这才是真正能成的路径;失败再回退到
            # 「邮箱 MFA + 密码」组合作为安全网。跳过必败的密码直登可省一次往返、
            # 少给 Adobe 一次失败风控信号,也不再刷 invalid_auth_session 噪音日志。
            code_logged_in = False
            try:
                lf("使用验证码登录(incompleteAccount)…")
                _passwordless_login(auth, email, lf, poll=poll, otp_timeout=otp_timeout)
                code_logged_in = True
            except AdminError as e:
                lf(f"验证码登录未成功:{e},回退到邮箱 MFA + 密码 …")
            if not code_logged_in:
                auth = _fresh_auth_session(client, email)
                if not _try_email_mfa_with_log(
                    auth, email, lf, poll=poll, otp_timeout=otp_timeout,
                ):
                    raise AdminError("未收到 Adobe 验证码(验证码登录与 MFA 均未成功)")
                lf("邮箱 MFA 通过,尝试密码登录 …")
                if not auth.password_susi(email, password):
                    raise AdminError("MFA 后密码仍失败,请检查 Adobe 密码")
        else:
            lf("账号无密码,改用验证码登录(incompleteAccount)…")
            _passwordless_login(auth, email, lf, poll=poll, otp_timeout=otp_timeout)
        _select_org_profile(auth, lf)
        token = _acquire_admin_token(auth, lf)
        cookie_str = _session_cookie_str(client)
        return token, cookie_str
    finally:
        try:
            client.close()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# 对外服务接口
# ----------------------------------------------------------------------------

def _discover(token: str, proxy_url: str, lf: LogFn) -> dict[str, Any]:
    """发现组织 / 产品 / 授权组。返回含 has_org/product_name 的 dict。"""
    client = client_from_state({"proxy": proxy_url})
    try:
        orgs = get_organizations(client, token)
        org = choose_org(orgs)
        org_id = str(org.get("id") or org.get("orgId") or "")
        lf(f"✓ 发现组织 {len(orgs)} 个,选用 org_id={org_id}")
        products = get_products(client, token, org_id)
        pid, lgid, pinfo = choose_product(products)
        pname = (pinfo.get("longName") or pinfo.get("shortName")
                 or pinfo.get("code") or "").strip()
        lf(f"✓ 发现产品 {len(products)} 个,选用 {pname or pid}")
        return {
            "has_org": True,
            "org_id": org_id,
            "product_id": pid,
            "product_name": pname,
            "license_group_id": lgid,
            "org_count": len(orgs),
            "product_count": len(products),
        }
    finally:
        client.close()


def login_account(
    *, email: str, adobe_password: str, refresh_token: str, client_id: str,
    mail_url: str = "", proxy_url: str = "", otp_timeout: int = 180,
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """登录管理账号并发现组织/产品。返回管理态 + 轮换后的 refresh_token。"""
    lf = _mklog(log)
    if not ((refresh_token and client_id) or mail_url):
        raise AdminError("缺少 Refresh Token / Client ID 或取信接口,无法自动收取验证码")

    poller, holder = make_otp_poller(
        refresh_token=refresh_token, client_id=client_id,
        mail_url=mail_url, proxy_url=proxy_url, timeout=otp_timeout, log=lf,
    )
    original_poll = _p.poll_otp
    original_log = getattr(_p, "log", None)

    def _tee(msg: Any) -> None:
        try:
            lf(str(msg))
        finally:
            if callable(original_log):
                original_log(msg)

    _p.poll_otp = poller
    _p.log = _tee
    try:
        lf(f"开始登录 {email}(自动识别密码/免密码,如需验证码会自动等待)…")
        lf(f"使用代理:{proxy_url or '(无)'}")
        token, cookie = _run_admin_login(
            email, adobe_password, proxy_url, lf,
            otp_timeout=otp_timeout, poll=poller,
        )
        lf("✓ 登录成功,已获取 admin token")
        result: dict[str, Any] = {
            "token": token,
            "cookie": cookie,
            "rotated_refresh_token": holder.refresh_token if holder.rotated else "",
            "has_org": False,
            "org_id": "",
            "product_id": "",
            "product_name": "",
            "license_group_id": "",
            "org_count": 0,
            "product_count": 0,
        }
        try:
            lf("正在发现组织 / 产品 / 授权组 …")
            disc = _discover(token, proxy_url, lf)
            result.update(disc)
        except ProtocolError as e:
            lf(f"⚠ 未发现可用组织/产品:{e}")
            result["has_org"] = False
            result["message"] = "登录成功但无可用组织/产品"
        return result
    finally:
        _p.poll_otp = original_poll
        if callable(original_log):
            _p.log = original_log


def check_admin(*, token: str, org_id: str = "", proxy_url: str = "",
                log: Optional[LogFn] = None) -> dict[str, Any]:
    """用已有 token 检测组织/产品是否可读,判断是否仍有管理权限。"""
    lf = _mklog(log)
    if not token:
        raise AdminError("token 为空,请先登录")
    client = client_from_state({"proxy": proxy_url})
    try:
        orgs = get_organizations(client, token)
        oid = org_id or str(choose_org(orgs).get("id") or "")
        products = get_products(client, token, oid)
        lf(f"✓ 组织 {len(orgs)} 个 / 产品 {len(products)} 个,token 有效")
        return {
            "has_org": True,
            "org_id": oid,
            "org_count": len(orgs),
            "product_count": len(products),
        }
    finally:
        client.close()


def grant_member(*, token: str, org_id: str, product_id: str,
                 license_group_id: str, email: str,
                 proxy_url: str = "") -> dict[str, Any]:
    """添加子账号并分配产品(=授权)。返回 {ok, member_id, message}。"""
    client = client_from_state({"proxy": proxy_url})
    try:
        try:
            added = add_member(client, token, org_id, email, product_id, license_group_id)
        except ProtocolError as e:
            return {"ok": False, "member_id": "", "message": str(e)[:480]}
        mid = str(added.get("member_id") or "")
        try:
            if not mid:
                mid = find_member_id_by_email(client, token, org_id, email)
        except Exception:
            pass
        return {"ok": True, "member_id": mid, "message": "已授权"}
    finally:
        client.close()


def remove_member(*, token: str, org_id: str, member_id: str = "",
                  email: str = "", proxy_url: str = "") -> dict[str, Any]:
    client = client_from_state({"proxy": proxy_url})
    try:
        mid = (member_id or "").strip()
        if not mid and email:
            mid = find_member_id_by_email(client, token, org_id, email)
        if not mid:
            return {"ok": False, "message": f"未找到成员:{email or member_id}"}
        res = remove_members(client, token, org_id, [mid])
        return {"ok": bool(res.get("ok")), "message": "已移除" if res.get("ok")
                else f"移除失败:{(res.get('text') or '')[:200]}"}
    finally:
        client.close()


def fetch_members(*, token: str, org_id: str, proxy_url: str = "",
                  search: str = "", pages: int = 20) -> list[dict[str, Any]]:
    client = client_from_state({"proxy": proxy_url})
    try:
        return list_members(client, token, org_id, pages=pages, page_size=100,
                            search=search)
    finally:
        client.close()
