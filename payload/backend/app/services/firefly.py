"""子账号(Firefly / clio-playground-web)登录与额度查询(纯 API,best-effort)。

复用管理登录里的免密码/验证码流程,但使用 clio-playground-web 客户端拿到
firefly 域的 access_token + 会话 cookie,再查询 credits,组装 newbanana 字段。
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from app.services import adobe_admin as _adm
from app.services.adobe_otp import make_otp_poller
from app.services.adobe_protocol import admin_member_protocol as _p
from app.services.adobe_protocol.admin_member_protocol import AdminAuth

try:
    from curl_cffi import requests as _cffi
    _HAS_CFFI = True
    from app.services.adobe_protocol.http_client import IMPERSONATE_TARGET
except ImportError:  # pragma: no cover
    import requests as _cffi  # type: ignore
    _HAS_CFFI = False
    IMPERSONATE_TARGET = "chrome124"

LogFn = Callable[[str], None]

CLIO_CLIENT_ID = "clio-playground-web"
FIREFLY_REDIRECT = "https://firefly.adobe.com/"

# 账号管理客户端(account.adobe.com)—— 浏览器用它建立 type2e 企业 IMS 会话,
# 之后 clio 的 check/v6/token 才能读到企业身份(额度 4000)。参数抓自浏览器。
SUNBREAK_CLIENT_ID = "SunbreakWebUI1"
SUNBREAK_REDIRECT = "https://account.adobe.com/"
SUNBREAK_SCOPE = (
    "AdobeID,openid,acct_mgmt_api,gnav,read_countries_regions,social.link,"
    "unlink_social_account,additional_info.address.mail_to,client.scopes.read,"
    "publisher.read,additional_info.account_type,additional_info.roles,"
    "additional_info.social,additional_info.screen_name,"
    "additional_info.optionalAgreements,additional_info.secondary_email,"
    "additional_info.secondary_email_verified,additional_info.phonetic_name,"
    "additional_info.dob,additional_info.ownerOrg,update_profile.all,"
    "security_profile.read,security_profile.update,admin_manage_user_consent,"
    "admin_slo,piip_write,mps,last_password_update,update_email,read_organizations,"
    "email_verification.w,bis.read.pan,bis.write.pi,bis.read.pi,security_profile.w,"
    "security_profile.r,passkey.r,passkey.w,email.w,pps.read,accounts.read,"
    "uds_write,uds_read,firefly_api,passkey_read,passkey_write,account_cluster.read,"
    "account_cluster.update,additional_info.authenticatingAccount"
)
FIREFLY_SCOPE = (
    "AdobeID,firefly_api,openid,pps.read,pps.write,"
    "additional_info.projectedProductContext,additional_info.ownerOrg,"
    "uds_read,uds_write,ab.manage,read_organizations,"
    "additional_info.roles,account_cluster.read,tk_platform,tk_platform_sync,profile"
)

IMS_VALIDATE_URL = (
    "https://ims-na1.adobelogin.com/ims/validate_token/v1"
    "?jslVersion=v2-v0.54.0-3-g58cfcb7"
)
ACCESS_PROFILE_URL = (
    "https://aps-web.adobe.io/webapps/access_profile/v3"
    "?include_disabled_fis=true"
)
ABP_PROFILE_URL = (
    "https://abp-profile-service.adobe.io/abp_profile/v1"
    "?include_sections=OFFER_DETAILS"
)
IMS_CHECK_URL = (
    "https://adobeid-na1.services.adobe.com/ims/check/v6/token"
    "?jslVersion=v2-v0.48.0-1-g1e322cb"
)
IMS_PROFILE_URL = "https://ims-na1.adobelogin.com/ims/profile/v1"
CREDITS_URL = "https://firefly.adobe.io/v1/credits/balance"
# Firefly Web uses a different API key for product/credits APIs than the IMS
# OAuth client used to exchange the access token.
CREDITS_API_KEY = "SunbreakWebUI1"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


def _mklog(log: Optional[LogFn]) -> LogFn:
    return log if callable(log) else (lambda _m: None)


def _proxies(proxy_url: str) -> dict | None:
    return {"http": proxy_url, "https": proxy_url} if proxy_url else None


def _new_session(proxy_url: str = ""):
    if _HAS_CFFI:
        return _cffi.Session(
            timeout=30, proxies=_proxies(proxy_url), verify=False,
            impersonate=IMPERSONATE_TARGET,
        )
    s = _cffi.Session()
    if proxy_url:
        s.proxies = _proxies(proxy_url)
    return s


def _decode_jwt(token: str) -> dict:
    if not token or "." not in token:
        return {}
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()))
    except Exception:
        return {}


def extract_jwt_expiry(token: str) -> int | None:
    claims = _decode_jwt(token)
    if not claims:
        return None
    if isinstance(claims.get("exp"), (int, float)):
        return int(claims["exp"])
    try:
        created = int(str(claims.get("created_at")))
        expires_in = int(str(claims.get("expires_in")))
        if created > 10_000_000_000:
            created //= 1000
        if expires_in > 86400 * 2:
            expires_in //= 1000
        return created + expires_in
    except Exception:
        return None


def extract_account_id(token: str) -> str:
    claims = _decode_jwt(token)
    for k in ("user_id", "aa_id", "sub"):
        v = claims.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _token_diagnostics(token: str) -> dict[str, Any]:
    claims = _decode_jwt(token)
    keys = ("user_id", "aa_id", "sub", "client_id", "ownerOrg", "owner_org")
    return {key: claims.get(key) for key in keys if claims.get(key)}


def _extract_token_value(obj: Any) -> str:
    """Extract a non-empty token value, including opaque SUSI tokens."""
    if isinstance(obj, dict):
        for key in (
            "token",
            "access_token",
            "accessToken",
            "tokenValue",
            "ims_access_token",
            "value",
        ):
            value = obj.get(key)
            if isinstance(value, str) and len(value) >= 16:
                return value
        for value in obj.values():
            if isinstance(value, (dict, list)):
                token = _extract_token_value(value)
                if token:
                    return token
    elif isinstance(obj, list):
        for value in obj:
            token = _extract_token_value(value)
            if token:
                return token
    elif isinstance(obj, str) and len(obj) >= 16:
        return obj
    return ""


def fetch_account_info(token: str, proxy_url: str = "", session=None) -> dict:
    if not token:
        return {}
    own_session = session is None
    sess = session or _new_session(proxy_url)
    try:
        r = sess.get(
            IMS_PROFILE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Origin": "https://firefly.adobe.com",
                "Referer": "https://firefly.adobe.com/",
            },
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        return {
            "display_name": data.get("displayName") or "",
            "email": data.get("email") or "",
            "user_id": data.get("userId") or "",
        }
    except Exception:
        return {}
    finally:
        if own_session:
            try:
                sess.close()
            except Exception:
                pass


def fetch_credits_detail(
    token: str,
    account_id: str = "",
    proxy_url: str = "",
    *,
    attempts: int = 1,
    retry_delay: float = 0.0,
    log: Optional[LogFn] = None,
    session=None,
) -> dict | None:
    """返回 {'available': float, 'total': float};None 表示查询失败。

    分母取 data['total']['quota']['total'](已由抓包核实),可用取 ['available']。
    """
    if not token:
        return None
    if not account_id:
        account_id = extract_account_id(token)
    if not account_id:
        return None
    attempts = max(1, int(attempts or 1))
    for attempt in range(attempts):
        own_session = session is None
        sess = session or _new_session(proxy_url)
        try:
            r = sess.get(
                CREDITS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-key": CREDITS_API_KEY,
                    "x-account-id": account_id,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": "https://firefly.adobe.com",
                    "Referer": "https://firefly.adobe.com/",
                },
            )
            if r.status_code == 200:
                data = r.json()
                quota = (data.get("total") or {}).get("quota") or {}
                available = quota.get("available")
                total = quota.get("total")
                if isinstance(available, (int, float)) or isinstance(total, (int, float)):
                    return {
                        "available": float(available) if isinstance(available, (int, float)) else 0.0,
                        "total": float(total) if isinstance(total, (int, float)) else 0.0,
                    }
                return {"available": 0.0, "total": 0.0}
            if callable(log):
                log(f"Firefly 额度接口返回 {r.status_code}: {(r.text or '')[:240]}")
        except Exception:
            if callable(log):
                log("Firefly 额度接口请求异常")
        finally:
            if own_session:
                try:
                    sess.close()
                except Exception:
                    pass
        if attempt + 1 < attempts and retry_delay > 0:
            time.sleep(retry_delay)
    return None


def fetch_credits(
    token: str,
    account_id: str = "",
    proxy_url: str = "",
    *,
    attempts: int = 1,
    retry_delay: float = 0.0,
    log: Optional[LogFn] = None,
    session=None,
) -> float | None:
    """返回额度;None 表示查询失败(区分于余额为 0)。"""
    if not token:
        return None
    if not account_id:
        account_id = extract_account_id(token)
    if not account_id:
        return None
    if callable(log):
        claims = _token_diagnostics(token)
        log(
            "Firefly credits request:"
            f" claims_user_id={claims.get('user_id') or '-'}"
            f" claims_aa_id={claims.get('aa_id') or '-'}"
            f" claims_sub={claims.get('sub') or '-'}"
            f" claims_client_id={claims.get('client_id') or '-'}"
            f" x-account-id={account_id}"
            f" x-api-key={CREDITS_API_KEY}"
            " origin=https://firefly.adobe.com"
            " referer=https://firefly.adobe.com/"
            " content-type=application/json"
            f" shared_session={'yes' if session is not None else 'no'}"
        )
    attempts = max(1, int(attempts or 1))
    for attempt in range(attempts):
        own_session = session is None
        sess = session or _new_session(proxy_url)
        try:
            r = sess.get(
                CREDITS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-key": CREDITS_API_KEY,
                    "x-account-id": account_id,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": "https://firefly.adobe.com",
                    "Referer": "https://firefly.adobe.com/",
                },
            )
            if r.status_code == 200:
                data = r.json()
                quota = (data.get("total") or {}).get("quota") or {}
                if isinstance(quota.get("available"), (int, float)):
                    return float(quota["available"])
                if isinstance(data.get("balance"), (int, float)):
                    return float(data["balance"])
                return 0.0
            if callable(log):
                log(f"Firefly 额度接口返回 {r.status_code}: {(r.text or '')[:240]}")
        except Exception:
            if callable(log):
                log("Firefly 额度接口请求异常")
        finally:
            if own_session:
                try:
                    sess.close()
                except Exception:
                    pass
        if attempt + 1 < attempts and retry_delay > 0:
            time.sleep(retry_delay)
    return None


def _firefly_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": CLIO_CLIENT_ID,
        "Origin": "https://firefly.adobe.com",
        "Referer": "https://firefly.adobe.com/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }


def _prepare_firefly_context(
    auth: "AdminAuth", token: str, lf: LogFn
) -> dict[str, Any]:
    """对齐 Firefly Web 登录后的 token 校验和 profile 初始化请求。"""
    context: dict[str, Any] = {}
    validate = auth.client.post(
        IMS_VALIDATE_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://firefly.adobe.com",
            "Referer": "https://firefly.adobe.com/",
        },
        data=urlencode({
            "type": "access_token",
            "client_id": CLIO_CLIENT_ID,
            "token": token,
        }),
        timeout=25,
    )
    context["validate_status"] = validate.status_code
    try:
        validate_data = validate.json()
    except Exception:
        validate_data = {}
    if isinstance(validate_data, dict):
        context["validate_valid"] = validate_data.get("valid")
        validate_token = validate_data.get("token")
        if isinstance(validate_token, dict):
            context["validate_user_id"] = validate_token.get("user_id") or ""
            context["validate_aa_id"] = validate_token.get("aa_id") or ""
            context["validate_client_id"] = validate_token.get("client_id") or ""
    if validate.status_code != 200:
        raise _adm.AdminError(
            f"firefly validate_token 失败 {validate.status_code}: "
            f"{(validate.text or '')[:240]}"
        )

    abp = auth.client.get(
        ABP_PROFILE_URL,
        headers=_firefly_headers(token),
        timeout=25,
    )
    context["abp_status"] = abp.status_code
    try:
        abp_data = abp.json()
    except Exception:
        abp_data = {}
    if isinstance(abp_data, dict):
        subscriptions = (abp_data.get("commerce_profile") or {}).get("subscriptions") or []
        if subscriptions and isinstance(subscriptions[0], dict):
            context["abp_owner_id"] = subscriptions[0].get("owner_id") or ""
        # 只记 [0] 会漏掉「个人 + 企业」并存的情况 —— 10 分/4000 分的分水岭
        # 正是额度挂在哪个 owner 上,整包记下来才看得见。
        context["abp_subscriptions"] = [
            {"owner_id": s.get("owner_id") or "",
             "offer_id": s.get("offer_id") or "",
             "status": s.get("status") or ""}
            for s in subscriptions if isinstance(s, dict)
        ]
    if abp.status_code != 200:
        lf(
            f"Firefly abp_profile 返回 {abp.status_code}: "
            f"{(abp.text or '')[:240]}"
        )

    profile = auth.client.post(
        ACCESS_PROFILE_URL,
        headers=_firefly_headers(token),
        json={
            "appDetails": {
                "nglAppId": "Firefly1",
                "nglAppVersion": "1.0",
                "nglLibRuntimeMode": "NAMED_USER_ONLINE",
                "locale": "en-US",
            },
            "accessControlRequest": {
                "checks": [{"namespaces": ["firefly", "pm", "rpm"]}]
            },
        },
        timeout=25,
    )
    context["access_profile_status"] = profile.status_code
    try:
        profile_data = profile.json()
    except Exception:
        profile_data = {}
    if isinstance(profile_data, dict):
        asnp = profile_data.get("asnp") or {}
        payload = asnp.get("payload") if isinstance(asnp, dict) else ""
        if isinstance(payload, str) and payload:
            try:
                encoded = payload + "=" * (-len(payload) % 4)
                decoded = json.loads(
                    base64.urlsafe_b64decode(encoded.encode()).decode()
                )
                context["access_profile_status_reason"] = (
                    decoded.get("profileStatusReason")
                )
                context["access_profile_status_text"] = (
                    decoded.get("profileStatusReasonText")
                )
                app_profile = decoded.get("appProfile") or {}
                items = app_profile.get("accessibleItems") or []
                if items and isinstance(items[0], dict):
                    source = items[0].get("source") or {}
                    context["access_profile_owner_id"] = source.get("owner_id") or ""
                # 同上:accessibleItems 也可能不止一条
                context["access_profile_owners"] = [
                    ((it.get("source") or {}).get("owner_id") or "")
                    for it in items if isinstance(it, dict)
                ]
            except Exception:
                pass
    if profile.status_code != 200:
        # profile 初始化失败不一定阻断 token,但保留状态方便定位 Adobe
        # 的上下文策略变化;额度请求仍会给出最终可操作错误。
        lf(
            f"Firefly access_profile 返回 {profile.status_code}: "
            f"{(profile.text or '')[:240]}"
        )
    return context


def _acquire_firefly_token(auth: "AdminAuth", email: str, lf: LogFn, *,
                           poll=None, password: str = "",
                           otp_timeout: int = 180,
                           force_code_login: bool = False) -> str:
    """走 SunbreakWebUI1 密码登录链建立 type2e 企业 IMS 会话,再让 clio 铸 type2e firefly token。

    浏览器实测、纯 HTTP 可复刻的正确链:
      密码登录(必要时邮箱 MFA) -> accounts/me 激活企业资料 link -> filtered_profiles 取企业 guid
      -> filterprofilemapping(guid=企业会员id) -> ims/tokens -> fromSusi(SunbreakWebUI1)
      -> clio check/v6/token(无 Bearer,靠 cookie) -> type2e token。
    企业 account_id 记到 auth._enterprise_account_id 供 fetch_credits(x-account-id)使用。
    """
    poll = poll or _p.poll_otp
    a2 = AdminAuth(auth.client, client_id=SUNBREAK_CLIENT_ID,
                   scope=SUNBREAK_SCOPE, redirect=SUNBREAK_REDIRECT)

    def cap(r):
        a2.auth_state_encrypted = r.headers.get(
            "x-ims-authentication-state-encrypted", a2.auth_state_encrypted)
        a2.identity_verification_token = r.headers.get(
            "x-identity-verification-token", a2.identity_verification_token)

    def code_login(why: str) -> None:
        """验证码登录(浏览器 codeLogin),不需要知道密码。

        _browser_code_login 自己会 authorize + start_email_mfa,所以这条路上
        不要预先建 authState。它还处理了「刚用 incompleteAccount 收过码,
        codeLogin 因子短暂 factor_unavailable」的冷却重试。
        """
        lf(f"firefly type2e:改用验证码登录({why})")
        _adm._browser_code_login(a2, email, lf, poll=poll, otp_timeout=otp_timeout)
        lf("firefly type2e:验证码会话已建立")

    # 不知道密码就别猜。以前这里无条件用 COMPLETE_PASSWORD,对「本来就已补全、
    # 密码不是我们设的」那种号(导入的/别人跑的)必然 401 invalid_authentication。
    if force_code_login or not password:
        code_login("强制" if force_code_login else "没有该号的 Adobe 密码")
        return _finish_firefly_token(auth, a2, email, lf, cap)

    def pwd_login():
        r = a2.client.post(
            f"{_p.AUTH_HOST}/signin/v2/tokens?credential=password",
            headers=a2.headers(),
            json={"username": email, "usernameType": "EMAIL", "password": password,
                  "accountType": "individual", "rememberMe": True}, timeout=25,
        )
        cap(r)
        try:
            return r, (r.json() or {})
        except Exception:
            return r, {}

    r, jd = pwd_login()
    tok = jd.get("token") or jd.get("access_token") or ""
    if not tok and jd.get("errorCode") == "challenge_required":
        lf("firefly type2e:密码登录需邮箱 MFA,收码中…")
        if not a2.send_email_challenge():
            st = getattr(a2, "last_email_challenge_status", None)
            body = (getattr(a2, "last_email_challenge_error", "") or getattr(a2, "last_email_challenge_body", "") or "")[:180]
            low = (body or "").lower()
            hint = "(疑似频控,过一会儿再试)" if st == 429 or "too many" in low or "rate" in low or "throttl" in low else ""
            raise _adm.AdminError(f"type2e MFA 发码失败 status={st}: {body}{hint}")
        code = poll(email, timeout=180)
        if not a2.verify_email_challenge(code):
            raise _adm.AdminError("type2e MFA 验证失败")
        r, jd = pwd_login()
        tok = jd.get("token") or jd.get("access_token") or ""
    if not tok:
        # 密码被拒(常见:这个号本来就已补全,密码不是我们设的)。以前到这里直接抛
        # "type2e 密码登录失败 401 invalid_authentication",整个号就废了;现在退回
        # 验证码登录再试一次 —— 验证码不需要知道密码。
        lf(f"firefly type2e:密码登录被拒 {r.status_code} "
           f"{jd.get('errorCode','')},退回验证码")
        code_login("密码登录被拒")
        return _finish_firefly_token(auth, a2, email, lf, cap)
    a2.susi_token = tok
    lf("firefly type2e:密码会话已建立")
    return _finish_firefly_token(auth, a2, email, lf, cap)


def _pick_enterprise_profile(
    a2: "AdminAuth", lf: LogFn, fps: list | None
) -> tuple[str, str]:
    """挑出这个号要切过去的企业资料,返回 ``(entitlementAccountUserId, 名字)``。

    为什么不能用 filtered_profiles 的结果:那个接口的 filter 是
    ``isSessionForwardProfile()``,只回「会话默认转发」的那一条 —— 实测一个挂在
    具名组织下的子号,它只返回 1 条 ``Personal Account``(个人 @AdobeID),具名
    企业资料压根不在列表里。拿这个个人 guid 去 filterprofilemapping,会话就一直
    停在个人身份上,clio 只会铸出 type1 token,额度接口于是只给个人免费层 10。

    企业资料只能从 ``accounts/me`` 的 ``profileData.links`` 拿,那里的
    ``entitlementAccountUserId`` 形如 ``<id>@<org>.e``,才是企业会员 id。
    用它当 guid 切一次会话,account_type 就变 type2e、额度变 4000(已实测:
    ClydieNomoto3868 10/10 → 3990/4000,ownerOrg 同时出现)。
    ``adobe_admin._select_org_profile`` 早就是这么做的,只是子号这条链没用上。

    这里的 accounts/me 是纯 GET:不切资料、不换 token、不动会话状态。
    取证日志一并保留 —— 缺了它们,上面这些结论当初根本查不出来。
    """
    try:
        raw = json.dumps(fps or [], ensure_ascii=False)
        lf(f"firefly 取证:filteredProfiles 共 {len(fps or [])} 条 {raw[:1000]}")
    except Exception as e:  # noqa: BLE001
        lf(f"firefly 取证:filteredProfiles 序列化失败:{e}")
    try:
        r = a2.client.get(
            f"{_p.AUTH_HOST}/signin/v1/accounts/me?client_id={a2.client_id}",
            headers=a2.headers(), timeout=15)
        data = r.json() if r.status_code == 200 else {}
        links = ((data.get("profileData") or {}).get("links")) or []
        lf(f"firefly 取证:accounts/me status={r.status_code} "
           f"企业资料 link 共 {len(links)} 条")
        for i, lk in enumerate(links):
            if not isinstance(lk, dict):
                continue
            lf(f"firefly 取证:link[{i}] desc={lk.get('description') or '-'}"
               f" status={lk.get('status') or '-'}"
               f" ident={lk.get('ident') or '-'}"
               f" entGuid={lk.get('entitlementAccountUserId') or '-'}")
        usable = [
            lk for lk in links
            if isinstance(lk, dict)
            and lk.get("entitlementAccountUserId")
            and lk.get("status", "active") == "active"
        ]
        if not usable:
            return "", ""
        # 组织被删之后 link 的 status 仍然是 active,死信号在 description 里
        # ("… Deleted")。把看着已删的排到最后而不是丢掉:全删光时仍要选得出来。
        # 与 adobe_admin._select_org_profile 同一套判据。
        dead = [lk for lk in usable if _p.looks_deleted_org(lk.get("description") or "")]
        if dead and len(dead) < len(usable):
            lf(f"firefly type2e:跳过 {len(dead)} 个已删组织的企业资料,优先选活的")
        elif dead:
            lf(f"⚠ firefly type2e:{len(dead)} 个企业资料全都看着已删,只能先用第一个")
        usable.sort(key=lambda lk: 1 if _p.looks_deleted_org(lk.get("description") or "") else 0)
        if len(usable) > 1:
            lf(f"⚠ firefly type2e:有 {len(usable)} 个可用企业资料,按顺序取第一个"
               f"(可能不是额度最多的那个)")
        pick = usable[0]
        return pick.get("entitlementAccountUserId") or "", pick.get("description") or ""
    except Exception as e:  # noqa: BLE001
        lf(f"firefly 取证:accounts/me 异常:{e}")
    return "", ""


def _finish_firefly_token(auth: "AdminAuth", a2: "AdminAuth", email: str,
                          lf: LogFn, cap) -> str:
    """会话建好之后的公共收尾:企业 profile -> ims/tokens -> fromSusi -> clio token。

    密码登录和验证码登录走到这里是一样的,所以抽出来共用。
    """
    # 企业资料 link 已在 complete_sub_account 里用补全会话激活过(激活会作废会话,不能放这里)。
    # filtered_profiles -> 企业会员 guid
    ent_guid = ""
    try:
        r = a2.client.get(
            f"{_p.AUTH_HOST}/signin/v2/accounts/filtered_profiles?filter=isSessionForwardProfile%28%29",
            headers=a2.headers(), timeout=15)
        cap(r)
        fps = (r.json() or {}).get("filteredProfiles") or []
        if fps:
            ent_guid = fps[0].get("userId") or ""
        lf(f"firefly type2e:filtered_profiles status={r.status_code} "
           f"session_forward_guid={ent_guid or '-'}")
        # filtered_profiles 只回 session-forward(个人)那条;真正带额度的具名企业
        # 资料要去 accounts/me 拿。拿得到就用企业的,拿不到才退回个人。
        org_guid, org_desc = _pick_enterprise_profile(a2, lf, fps)
        if org_guid:
            lf(f"firefly type2e:选择企业资料「{org_desc or '-'}」guid={org_guid}")
            ent_guid = org_guid
        elif ent_guid:
            lf("firefly type2e:无可用企业资料,沿用 session-forward 个人资料"
               "(该号若本该有组织额度,就会只拿到个人免费层)")
    except Exception as e:  # noqa: BLE001
        lf(f"firefly type2e:filtered_profiles 异常:{e}")
    if not ent_guid:
        raise _adm.AdminError(
            "type2e:accounts/me 无可用企业资料,filtered_profiles 也没返回任何 "
            "session-forward profile(会话可能没建起来)")

    # filterprofilemapping guid=企业会员id
    try:
        r = a2.client.put(
            f"{_p.AUTH_HOST}/signin/v1/filterprofilemapping", headers=a2.headers(),
            json={"filter": "isSessionForwardProfile()", "guid": ent_guid}, timeout=15)
        cap(r)
        lf(f"firefly type2e:filterprofilemapping status={r.status_code}")
    except Exception as e:  # noqa: BLE001
        lf(f"firefly type2e:filterprofilemapping 异常:{e}")

    # ims/tokens force
    try:
        r = a2.client.post(
            f"{_p.AUTH_HOST}/signin/v1/ims/tokens", headers=a2.headers(),
            json={"rememberMe": True, "reauthenticate": "force"}, timeout=25)
        cap(r)
        t2 = _p.extract_token_from_obj(r.json()) if r.status_code == 200 else ""
        if t2:
            a2.susi_token = t2
    except Exception as e:  # noqa: BLE001
        lf(f"firefly type2e:ims/tokens 异常:{e}")

    # fromSusi(SunbreakWebUI1)-> 建立 type2e IMS 会话 cookie
    try:
        a2.from_susi_token(None)
    except Exception as e:  # noqa: BLE001
        lf(f"firefly type2e:fromSusi 异常:{e}")

    # clio check/v6/token(无 Bearer,靠 cookie)-> type2e firefly token
    r = auth.client.post(
        f"{_p.IMS_BACKEND}/ims/check/v6/token?jslVersion=v2-v0.54.0-3-g58cfcb7",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                 "client_id": CLIO_CLIENT_ID, "Origin": "https://firefly.adobe.com",
                 "Referer": "https://firefly.adobe.com/"},
        data=urlencode({"client_id": CLIO_CLIENT_ID, "guest_allowed": "true",
                        "scope": FIREFLY_SCOPE}), timeout=25,
    )
    try:
        data = r.json() if isinstance(r.json(), dict) else {}
    except Exception:
        data = {}
    tok3 = data.get("access_token") or ""
    acct = data.get("account_type") or ""
    lf(f"firefly type2e:check/v6/token account_type={acct} got_token={bool(tok3)}")
    if not tok3:
        raise _adm.AdminError(f"firefly check/v6/token 未返回 token status={r.status_code}")
    if acct != "type2e":
        lf(f"⚠ firefly token 非 type2e(account_type={acct}),额度可能偏低")
    auth.susi_token = tok3
    auth._enterprise_account_id = ent_guid
    context = {
        "check_status": r.status_code,
        "check_account_type": acct,
        "check_user_id": data.get("userId") or ent_guid,
        "check_owner_org": data.get("ownerOrg") or "",
        "check_client_id": data.get("client_id") or CLIO_CLIENT_ID,
        "token_claims": _token_diagnostics(tok3),
    }
    try:
        context.update(_prepare_firefly_context(auth, tok3, lf))
    except Exception:
        pass
    auth._firefly_context = context
    lf(f"✓ 子号 firefly token 获取成功(account_type={acct})")
    return tok3


def register_account(
    *, email: str, refresh_token: str, client_id: str,
    mail_url: str = "", proxy_url: str = "", otp_timeout: int = 180,
    account_id: str = "", adobe_password: str = "",
    force_code_login: bool = False,
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """子账号自助登录(免密码验证码)→ 拿 firefly token + cookie + credits。

    返回 newbanana 记录:{access_token, cookie, credits, expires_at, display_name, user_id}。
    """
    lf = _mklog(log)
    if not ((refresh_token and client_id) or mail_url):
        raise _adm.AdminError("子号缺少 Refresh Token / Client ID 或取信配置,无法收验证码登录")

    # 显式传入收码器(不改全局),保证并发拉号时各子号互不干扰
    poller, holder = make_otp_poller(
        refresh_token=refresh_token, client_id=client_id,
        mail_url=mail_url, proxy_url=proxy_url, timeout=otp_timeout, log=lf,
    )
    client = _p.HttpClient(proxy=proxy_url)
    try:
        auth = AdminAuth(
            client, client_id=CLIO_CLIENT_ID, scope=FIREFLY_SCOPE,
            redirect=FIREFLY_REDIRECT,
        )
        auth.authorize(email, "en_US")
        methods = _adm._probe_auth_methods(auth, email)
        lf(f"子号 {email} 认证方式:{', '.join(methods) if methods else '无(免密码)'}")
        # 子号(被邀请的 TYPE2E)通常是免密码账号,用验证码登录
        _adm._passwordless_login(auth, email, lf, poll=poller, otp_timeout=otp_timeout)
        # 首次登录的被邀请号需补全账号(姓名/密码/生日)并激活企业资料。
        # 返回本次实际设置的密码(账号本来就已补全则是 ""),调用方据此记库。
        set_password = _adm.complete_sub_account(
            auth, email, lf, poll=poller, otp_timeout=otp_timeout
        )
        # 拿哪个密码去登:本次刚设的 > 库里存的 > 没有(走验证码)。
        # 不再无条件用 COMPLETE_PASSWORD —— 已补全的号密码未必是我们设的。
        pwd = set_password or (adobe_password or "").strip()
        token = _acquire_firefly_token(
            auth, email, lf, poll=poller, password=pwd,
            otp_timeout=otp_timeout, force_code_login=force_code_login,
        )
        cookie = _adm._session_cookie_str(client)

        info = fetch_account_info(token, proxy_url, session=client.session) or {}
        token_user_id = extract_account_id(token)
        profile_user_id = info.get("user_id") or ""
        context = getattr(auth, "_firefly_context", {})
        claims = _token_diagnostics(token)
        lf(
            "Firefly context:"
            f" check_status={context.get('check_status') or '-'}"
            f" check_account_type={context.get('check_account_type') or '-'}"
            f" check_user_id={context.get('check_user_id') or '-'}"
            f" check_ownerOrg={context.get('check_owner_org') or '-'}"
            f" check_client_id={context.get('check_client_id') or '-'}"
            f" claims_user_id={claims.get('user_id') or '-'}"
            f" claims_aa_id={claims.get('aa_id') or '-'}"
            f" claims_sub={claims.get('sub') or '-'}"
            f" claims_client_id={claims.get('client_id') or '-'}"
            f" claims_ownerOrg={claims.get('ownerOrg') or claims.get('owner_org') or '-'}"
            f" validate_status={context.get('validate_status') or '-'}"
            f" validate_valid={context.get('validate_valid')!r}"
            f" validate_user_id={context.get('validate_user_id') or '-'}"
            f" validate_aa_id={context.get('validate_aa_id') or '-'}"
            f" validate_client_id={context.get('validate_client_id') or '-'}"
            f" abp_status={context.get('abp_status') or '-'}"
            f" abp_owner_id={context.get('abp_owner_id') or '-'}"
            f" access_profile_status={context.get('access_profile_status') or '-'}"
            f" access_profile_reason={context.get('access_profile_status_reason') or '-'}"
            f" access_profile_owner_id={context.get('access_profile_owner_id') or '-'}"
            # status_text 一直在 context 里躺着却从来没打出来,1003 到底是
            # 「没订阅」还是别的,只有它说得清。
            f" access_profile_text={context.get('access_profile_status_text') or '-'}"
            f" access_profile_owners={context.get('access_profile_owners') or '-'}"
            f" abp_subs={context.get('abp_subscriptions') or '-'}"
            f" ims_profile_user_id={profile_user_id or '-'}"
        )
        if token_user_id and profile_user_id and token_user_id != profile_user_id:
            lf(
                "Firefly user_id 不一致:"
                f"token={token_user_id} profile={profile_user_id}"
            )
        # credits API 的 x-account-id 必须与【当前 token 的身份】自洽,不自洽会
        # 403 ErrMismatchOauthToken。它本身不是「选组织」的开关:线上有 26 次用
        # 个人 AdobeID 照样拿到 4000(因为那些号的额度就挂在个人资料上),也有
        # 同一个号用 .e 和用 @AdobeID 都拿到 4000 的自对照。
        # 真正决定拿 10 还是 4000 的是**会话切没切到企业资料**(见
        # _pick_enterprise_profile):切了 token 才是 type2e,额度才是组织的。
        # 切过去之后 _enterprise_account_id 就是那个 .e id,与 token 自洽。
        ent_from_auth = getattr(auth, "_enterprise_account_id", "") or ""
        user_id = token_user_id or profile_user_id
        credits_account_id = account_id or ent_from_auth or user_id
        lf(
            "credits x-account-id 选用:"
            f"chosen={credits_account_id or '-'}"
            f" (grant={account_id or '-'}"
            f" entitlement={ent_from_auth or '-'}"
            f" token={user_id or '-'})"
        )
        credits_detail = fetch_credits_detail(
            token,
            credits_account_id,
            proxy_url,
            attempts=3,
            retry_delay=3,
            log=lf,
            session=client.session,
        )
        credits = credits_detail["available"] if credits_detail else None
        credits_total = credits_detail["total"] if credits_detail else None
        expires_at = extract_jwt_expiry(token)

        return {
            "access_token": token,
            "cookie": cookie,
            "credits": credits,
            "credits_total": credits_total,
            "expires_at": expires_at,
            "display_name": info.get("display_name") or "",
            "user_id": user_id,
            "rotated_refresh_token": holder.refresh_token if holder.rotated else "",
            # 本次补全时我们给这个号设的 Adobe 密码;已补全的号是 ""
            "set_password": set_password,
        }
    finally:
        try:
            client.close()
        except Exception:
            pass
