"""FF-iOS 原生登录(协议复刻):email + 密码 + 邮箱 OTP → 受信任的 access_token + device_token。

背景:Firefly 网页端(clio-playground-web)拿到的 token 会被 Adobe 反爬当成「不可信来源」,
generate-async 概率性返回伪装的 408 "system under load"。而 Firefly iOS App 走的原生设备登录
(client_id=FF-iOS, grant_type=device)拿到的 token 属于「受信任来源」,可稳定出图。

本模块完全用 HTTP 复刻了 iOS App 的 SUSI 登录流程(从手机抓包 HAR 还原),关键步骤:

  1. GET  ims/authorize/v3          建立 SUSI 会话(response_type=device)
  2. POST signin/v2/users/accounts  探测账号认证方式
  3. POST signin/v2/authenticationstate?purpose=multiFactorAuthentication  → state + IVT
  4. POST signin/v3/challenges?factor=email   发邮件验证码
  5. PUT  signin/v3/challenges {code}          校验验证码
  6. POST signin/v2/tokens?credential=password {password}  → susi_token
  7. GET  signin/v1/accounts/me               取 linkId / 实体账号 guid
  8. PUT  signin/v1/filterprofilemapping {guid}
  9. POST signin/v1/accounts/tokens {linkId}  → 切换到 T2E 实体账号 susi_token
 10. POST signin/v1/ims/tokens                → 短时 ims token(给 fromSusi 用)
 11. POST ims/fromSusi (form, response_type=device)  → 302 拿 authorization code
 12. POST ims/token/v4 (grant_type=device, code, device_id)  → access_token + device_token

device_token 有效期约 1 年,可随时用 refresh_with_device_token 换新的 access_token,无需再过验证码。
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import time
import uuid
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlencode, urlparse

try:
    from curl_cffi import requests as _cffi
    _HAS_CFFI = True
except ImportError:  # pragma: no cover
    import requests as _cffi  # type: ignore
    _HAS_CFFI = False

LogFn = Callable[[str], None]
OtpFn = Callable[..., str]

CLIENT_ID = "FF-iOS"
SCOPE = "creative_sdk,AdobeID,openid,creative_cloud,firefly_api"
REDIRECT_URI = "com.adobe.firefly.ios://login.complete"

AUTH_HOST = "https://auth.services.adobe.com"
IMS_HOST = "https://ims-na1.adobelogin.com"
IMS_BACKEND = "https://adobeid-na1.services.adobe.com"

IOS_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1"
)
SDK_UA = "Firefly/26.10.0 (AdobeCreativeSDK 11.0.2434;Apple;iPhone;iOS;26.6)"

# curl_cffi 0.13 起支持的 Safari 指纹;不可用时回退 Chrome。
_IMPERSONATE = "safari17_0"


class FireflyIOSError(RuntimeError):
    pass


def _mklog(log: Optional[LogFn]) -> LogFn:
    return log if callable(log) else (lambda _m: None)


def _hashed_device_id(device_id: str) -> str:
    digest = hashlib.sha256(device_id.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def new_device_id() -> str:
    """生成一个新的「设备」标识(大写 UUID),每个号固定绑一个即可。"""
    return str(uuid.uuid4()).upper()


def _decode_jwt(token: str) -> dict:
    if not token or token.count(".") < 2:
        return {}
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()).decode("utf-8", "ignore"))
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
        if expires_in > 86400 * 2:  # 毫秒
            expires_in //= 1000
        return created + expires_in
    except Exception:
        return None


def extract_account_id(token: str) -> str:
    claims = _decode_jwt(token)
    for k in ("user_id", "userId", "sub", "aa_id"):
        v = claims.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


class _Session:
    """curl_cffi 会话封装:统一 cookie、代理、指纹与重定向控制。"""

    def __init__(self, proxy_url: str = "") -> None:
        self.debug_id = str(uuid.uuid4())
        self.auth_state = ""
        self.ivt = ""
        self.susi_token = ""
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        if _HAS_CFFI:
            try:
                self.s = _cffi.Session(
                    timeout=30, proxies=proxies, verify=False, impersonate=_IMPERSONATE
                )
            except Exception:
                self.s = _cffi.Session(timeout=30, proxies=proxies, verify=False)
        else:  # pragma: no cover
            self.s = _cffi.Session()
            if proxies:
                self.s.proxies = proxies

    def close(self) -> None:
        try:
            self.s.close()
        except Exception:
            pass

    def _web_headers(self, *, auth: bool = False, state: bool = False, ivt: bool = False) -> dict:
        h = {
            "User-Agent": IOS_UA,
            "x-ims-clientid": CLIENT_ID,
            "x-debug-id": self.debug_id,
            "Origin": AUTH_HOST,
            "Referer": f"{AUTH_HOST}/zh_HANS/index.html",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-Hans-CN,zh-Hans;q=0.9",
            "Content-Type": "application/json",
        }
        if auth and self.susi_token:
            h["Authorization"] = f"Bearer {self.susi_token}"
        if state and self.auth_state:
            h["x-ims-authentication-state-encrypted"] = self.auth_state
        if ivt and self.ivt:
            h["x-identity-verification-token"] = self.ivt
        return h

    def _capture(self, resp) -> None:
        st = resp.headers.get("x-ims-authentication-state-encrypted")
        if st:
            self.auth_state = st
        ivt = resp.headers.get("x-identity-verification-token")
        if ivt:
            self.ivt = ivt


def _bridge_ecid() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(38))


def ff_ios_login(
    *,
    email: str,
    password: str,
    get_otp: OtpFn,
    device_id: str = "",
    proxy_url: str = "",
    otp_timeout: int = 180,
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """跑通 FF-iOS 原生登录,返回受信任 token。

    get_otp(email, timeout=...) -> str:收 6 位邮件验证码的回调(用 make_otp_poller 即可)。

    返回:{access_token, device_token, device_id, expires_at, dt_expires_at,
          user_id, display_name, email, account_type}
    """
    lf = _mklog(log)
    device_id = device_id or new_device_id()
    hdid = _hashed_device_id(device_id)
    bridge_ecid = _bridge_ecid()
    sess = _Session(proxy_url)
    try:
        # 1) authorize:建立 SUSI 设备会话
        authorize_params = {
            "client_id": CLIENT_ID,
            "scope": SCOPE,
            "force_marketing_permission": "true",
            "locale": "zh-Hans-CN",
            "idp_flow": "login",
            "response_type": "device",
            "device_name": "iPhone",
            "hashed_device_id": hdid,
            "bridge_ecid": bridge_ecid,
            "redirect_uri": REDIRECT_URI,
            "client_version": "15",
        }
        sess.s.get(
            f"{IMS_HOST}/ims/authorize/v3?{urlencode(authorize_params)}",
            headers={"User-Agent": IOS_UA},
            allow_redirects=True,
        )

        # 2) 探测认证方式
        r = sess.s.post(
            f"{AUTH_HOST}/signin/v2/users/accounts",
            headers=sess._web_headers(),
            data=json.dumps({"username": email, "usernameType": "EMAIL"}),
        )
        sess._capture(r)
        methods = ""
        try:
            arr = r.json()
            if isinstance(arr, list) and arr:
                methods = ",".join(
                    m.get("id", "") for m in (arr[0].get("authenticationMethods") or [])
                )
        except Exception:
            pass
        lf(f"[{email}] 认证方式:{methods or '未知'}")

        # 3) authenticationstate:开 MFA,拿 state + IVT
        r = sess.s.post(
            f"{AUTH_HOST}/signin/v2/authenticationstate?purpose=multiFactorAuthentication",
            headers=sess._web_headers(state=True, ivt=True),
            data=json.dumps({
                "extraPbaChecks": False,
                "pbaPolicy": None,
                "username": email,
                "usernameType": "EMAIL",
                "accountType": "individual",
                "deviceInfo": {"lsId": str(uuid.uuid4()), "hdId": hdid},
            }),
        )
        sess._capture(r)
        if r.status_code not in (200, 201):
            raise FireflyIOSError(
                f"authenticationstate 失败 {r.status_code}:{(r.text or '')[:200]}"
            )
        info = {}
        try:
            info = r.json() or {}
        except Exception:
            pass
        required = info.get("requiredActions") or []
        lf(f"[{email}] requiredActions={required} mfa={info.get('mfaStatus')}")

        # 4) 选 email 因子,发验证码
        if "MFA" in required or info.get("mfaStatus") == "REQUIRED":
            r = sess.s.get(
                f"{AUTH_HOST}/signin/v3/challenges?purpose=multiFactorAuthentication",
                headers=sess._web_headers(state=True, ivt=True),
            )
            sess._capture(r)
            r = sess.s.post(
                f"{AUTH_HOST}/signin/v3/challenges"
                "?purpose=multiFactorAuthentication&factor=email&extendedAuthState=false",
                headers=sess._web_headers(state=True, ivt=True),
                data=json.dumps({}),
            )
            sess._capture(r)
            if r.status_code != 200:
                raise FireflyIOSError(
                    f"发送邮件验证码失败 {r.status_code}:{(r.text or '')[:200]}"
                )
            lf(f"[{email}] 已发送邮件验证码,等待收码…")
            code = get_otp(email, timeout=otp_timeout)
            if not code:
                raise FireflyIOSError("未取到邮件验证码")
            lf(f"[{email}] 收到验证码 {code},校验中…")
            r = sess.s.put(
                f"{AUTH_HOST}/signin/v3/challenges?purpose=multiFactorAuthentication",
                headers=sess._web_headers(state=True, ivt=True),
                data=json.dumps({"code": str(code)}),
            )
            sess._capture(r)
            if r.status_code != 200:
                raise FireflyIOSError(
                    f"验证码校验失败 {r.status_code}:{(r.text or '')[:200]}"
                )

        # 5) 密码登录,拿 susi_token
        r = sess.s.post(
            f"{AUTH_HOST}/signin/v2/tokens?credential=password",
            headers=sess._web_headers(state=True, ivt=True),
            data=json.dumps({
                "username": email,
                "usernameType": "EMAIL",
                "password": password,
                "accountType": "individual",
                "rememberMe": True,
            }),
        )
        sess._capture(r)
        if r.status_code != 200:
            raise FireflyIOSError(
                f"密码登录失败 {r.status_code}:{(r.text or '')[:300]}"
            )
        sess.susi_token = (r.json() or {}).get("token") or ""
        if not sess.susi_token:
            raise FireflyIOSError("密码登录未返回 token")
        lf(f"[{email}] 密码登录成功")

        # 6) accounts/me:拿 linkId / 实体账号 guid
        link_id, guid = _resolve_link(sess, email, lf)

        # 7) filterprofilemapping(切到实体资料)
        if guid:
            sess.s.put(
                f"{AUTH_HOST}/signin/v1/filterprofilemapping",
                headers=sess._web_headers(auth=True, state=True),
                data=json.dumps({"guid": guid}),
            )

        # 8) accounts/tokens:用 linkId 换实体账号 susi_token
        if link_id:
            r = sess.s.post(
                f"{AUTH_HOST}/signin/v1/accounts/tokens",
                headers=sess._web_headers(auth=True, state=True),
                data=json.dumps({"linkId": link_id}),
            )
            sess._capture(r)
            tok = ""
            try:
                tok = (r.json() or {}).get("token") or ""
            except Exception:
                pass
            if tok:
                sess.susi_token = tok
                lf(f"[{email}] 已切换到实体账号资料")

        # 9) signin/v1/ims/tokens:短时 ims token(给 fromSusi)
        r = sess.s.post(
            f"{AUTH_HOST}/signin/v1/ims/tokens",
            headers=sess._web_headers(auth=True, state=True),
            data=json.dumps({"rememberMe": True, "reauthenticate": None}),
        )
        sess._capture(r)
        ims_token = ""
        try:
            ims_token = (r.json() or {}).get("token") or ""
        except Exception:
            pass
        if not ims_token:
            raise FireflyIOSError(
                f"ims/tokens 未返回 token {r.status_code}:{(r.text or '')[:200]}"
            )

        # 10) fromSusi:换 authorization code
        code = _from_susi(sess, ims_token, hdid, bridge_ecid, lf)

        # 11) token/v4:device grant → access_token + device_token
        result = _token_v4_device(sess, code, device_id, lf)
        result["device_id"] = device_id
        result["email"] = email
        return result
    finally:
        sess.close()


def _resolve_link(sess: _Session, email: str, lf: LogFn) -> tuple[str, str]:
    r = sess.s.get(
        f"{AUTH_HOST}/signin/v1/accounts/me?client_id={CLIENT_ID}",
        headers=sess._web_headers(auth=True, state=True),
    )
    try:
        data = r.json() or {}
    except Exception:
        return "", ""
    links = ((data.get("profileData") or {}).get("links")) or []
    if not links:
        return "", ""
    # 优先 active 的链接,否则取第一个
    link = next((x for x in links if (x.get("status") == "active")), links[0])
    link_id = link.get("ident") or ""
    guid = link.get("entitlementAccountUserId") or ""
    lf(f"[{email}] linkId={'有' if link_id else '无'} 实体guid={'有' if guid else '无'}")
    return link_id, guid


def _from_susi(
    sess: _Session, ims_token: str, hdid: str, bridge_ecid: str, lf: LogFn
) -> str:
    callback = (
        f"{IMS_HOST}/ims/adobeid/{CLIENT_ID}/AdobeID/device?"
        + urlencode({
            "redirect_uri": REDIRECT_URI,
            "hashed_device_id": hdid,
            "device_name": "iPhone",
            "code_challenge_method": "plain",
            "use_ms_for_expiry": "false",
        })
    )
    form = {
        "remember_me": "true",
        "callback": callback,
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "relay": sess.debug_id,
        "locale": "zh_HANS",
        "flow_type": "device",
        "idp_flow_type": "login",
        "ab_test": "device-show-confirmation",
        "s_p": "apple",
        "response_type": "device",
        "device_name": "iPhone",
        "hashed_device_id": hdid,
        "code_challenge_method": "plain",
        "redirect_uri": REDIRECT_URI,
        "use_ms_for_expiry": "false",
        "client_version": "15",
        "bridge_ecid": bridge_ecid,
        "flow": "signIn",
        "token": ims_token,
        "ecid": _bridge_ecid(),
    }
    r = sess.s.post(
        f"{IMS_BACKEND}/ims/fromSusi",
        headers={
            "User-Agent": IOS_UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": AUTH_HOST,
            "Referer": f"{AUTH_HOST}/zh_HANS/index.html",
        },
        data=urlencode(form),
        allow_redirects=False,
    )
    loc = r.headers.get("Location", "") or ""
    code = _code_from_url(loc)
    # 跟随重定向链直到拿到 code 或到达自定义 scheme
    hops = 0
    while not code and loc and loc.startswith("http") and hops < 6:
        hops += 1
        rr = sess.s.get(loc, headers={"User-Agent": IOS_UA}, allow_redirects=False)
        loc = rr.headers.get("Location", "") or ""
        code = _code_from_url(loc)
    if not code:
        raise FireflyIOSError(
            f"fromSusi 未拿到 authorization code(status={r.status_code} loc={loc[:120]})"
        )
    lf("[fromSusi] 已拿到 authorization code")
    return code


def _code_from_url(url: str) -> str:
    if not url:
        return ""
    for part in (urlparse(url).query, urlparse(url).fragment, url):
        qs = parse_qs(part, keep_blank_values=True)
        if qs.get("code"):
            return qs["code"][0]
    m = re.search(r"[?&#]code=([^&#]+)", url)
    return m.group(1) if m else ""


def _token_v4_device(sess: _Session, code: str, device_id: str, lf: LogFn) -> dict[str, Any]:
    r = sess.s.post(
        f"{IMS_HOST}/ims/token/v4",
        headers={
            "User-Agent": SDK_UA,
            "x-ims-clientid": CLIENT_ID,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urlencode({
            "client_id": CLIENT_ID,
            "code": code,
            "device_id": device_id,
            "grant_type": "device",
        }),
        allow_redirects=False,
    )
    if r.status_code != 200:
        raise FireflyIOSError(
            f"token/v4 device 失败 {r.status_code}:{(r.text or '')[:300]}"
        )
    data = r.json() or {}
    access_token = data.get("access_token") or ""
    device_token = data.get("device_token") or ""
    if not access_token or not device_token:
        raise FireflyIOSError("token/v4 未返回 access_token/device_token")
    lf("✓ FF-iOS 登录成功,已拿到 access_token + device_token")
    return _build_token_result(data, access_token, device_token)


def _build_token_result(data: dict, access_token: str, device_token: str) -> dict[str, Any]:
    now = int(time.time())
    exp_in = _ms_to_seconds(data.get("expires_in"))
    dt_exp_in = _ms_to_seconds(data.get("dt_expires_in"))
    return {
        "access_token": access_token,
        "device_token": device_token,
        "expires_at": (now + exp_in) if exp_in else extract_jwt_expiry(access_token),
        "dt_expires_at": (now + dt_exp_in) if dt_exp_in else None,
        "user_id": data.get("userId") or extract_account_id(access_token),
        "display_name": data.get("displayName") or "",
        "account_type": data.get("account_type") or "",
    }


def _ms_to_seconds(v: Any) -> int:
    """token/v4 的 expires_in / dt_expires_in 均为毫秒。"""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return n // 1000 if n >= 1000 else n


def _ff_headers(
    susi_token: str, debug_id: str, *, state: str = "", bearer: bool = True,
    content_json: bool = True,
) -> dict:
    h = {
        "User-Agent": IOS_UA,
        "x-ims-clientid": CLIENT_ID,
        "x-debug-id": debug_id,
        "Origin": AUTH_HOST,
        "Referer": f"{AUTH_HOST}/zh_HANS/index.html",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-Hans-CN,zh-Hans;q=0.9",
    }
    if content_json:
        h["Content-Type"] = "application/json"
    if bearer and susi_token:
        h["Authorization"] = f"Bearer {susi_token}"
    if state:
        h["x-ims-authentication-state-encrypted"] = state
    return h


def mint_ff_ios_device_token(
    client,
    susi_token: str,
    email: str,
    *,
    device_id: str = "",
    proxy_url: str = "",
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """在「已认证会话」里把 clio 的 susi_token 兑换成 FF-iOS 受信任 token。

    client:已经过验证码登录的 okad HttpClient(curl_cffi 会话,带 IMS 会话 cookie)。
    susi_token:验证码登录得到的会话 token(auth.services.adobe.com)。
    不需要 Adobe 密码。
    """
    lf = _mklog(log)
    device_id = device_id or new_device_id()
    hdid = _hashed_device_id(device_id)
    debug_id = str(uuid.uuid4())
    bridge_ecid = _bridge_ecid()

    # 1) FF-iOS 设备 authorize(在已认证会话内,建立设备流上下文)
    authorize_params = {
        "client_id": CLIENT_ID, "scope": SCOPE,
        "force_marketing_permission": "true", "locale": "zh-Hans-CN",
        "idp_flow": "login", "response_type": "device", "device_name": "iPhone",
        "hashed_device_id": hdid, "bridge_ecid": bridge_ecid,
        "redirect_uri": REDIRECT_URI, "client_version": "15",
    }
    try:
        client.get(
            f"{IMS_HOST}/ims/authorize/v3?{urlencode(authorize_params)}",
            headers={"User-Agent": IOS_UA}, allow_redirects=True,
        )
    except Exception:
        pass

    # 1.5) credential=sso:用已认证会话 cookie 换 FF-iOS 专用 susi_token
    cur_susi = susi_token
    try:
        r = client.post(
            f"{AUTH_HOST}/signin/v2/tokens"
            "?credential=sso&checkReauth=false&puser=&t2Only=false&euid=&pbaPolicy=",
            headers=_ff_headers("", debug_id, bearer=False),
            data=json.dumps({}),
        )
        sso_tok = ""
        try:
            sso_tok = (r.json() or {}).get("token") or ""
        except Exception:
            pass
        if sso_tok:
            cur_susi = sso_tok
            lf(f"[{email}] credential=sso 成功(FF-iOS 会话)")
        else:
            lf(f"[{email}] credential=sso 未返回 token({getattr(r, 'status_code', '?')}),"
               f"回退 clio 会话 token")
    except Exception as e:
        lf(f"[{email}] credential=sso 异常:{e}")

    # 2) accounts/me:拿 linkId / 实体账号 guid
    link_id, guid = "", ""
    try:
        r = client.get(
            f"{AUTH_HOST}/signin/v1/accounts/me?client_id={CLIENT_ID}",
            headers=_ff_headers(cur_susi, debug_id),
        )
        data = r.json() or {}
        links = ((data.get("profileData") or {}).get("links")) or []
        if links:
            link = next((x for x in links if x.get("status") == "active"), links[0])
            link_id = link.get("ident") or ""
            guid = link.get("entitlementAccountUserId") or ""
    except Exception as e:
        lf(f"[{email}] accounts/me 异常:{e}")
    lf(f"[{email}] linkId={'有' if link_id else '无'} 实体guid={'有' if guid else '无'}")

    # 3) filterprofilemapping(切实体资料)
    if guid:
        try:
            client.put(
                f"{AUTH_HOST}/signin/v1/filterprofilemapping",
                headers=_ff_headers(cur_susi, debug_id),
                data=json.dumps({"guid": guid}),
            )
        except Exception:
            pass

    # 4) accounts/tokens:用 linkId 换实体账号 susi_token
    if link_id:
        try:
            r = client.post(
                f"{AUTH_HOST}/signin/v1/accounts/tokens",
                headers=_ff_headers(cur_susi, debug_id),
                data=json.dumps({"linkId": link_id}),
            )
            tok = (r.json() or {}).get("token") or ""
            if tok:
                cur_susi = tok
                lf(f"[{email}] 已切换到实体账号资料")
        except Exception as e:
            lf(f"[{email}] accounts/tokens 异常:{e}")

    # 5) signin/v1/ims/tokens:短时 ims token(给 fromSusi)
    r = client.post(
        f"{AUTH_HOST}/signin/v1/ims/tokens",
        headers=_ff_headers(cur_susi, debug_id),
        data=json.dumps({"rememberMe": True, "reauthenticate": None}),
    )
    ims_token = ""
    try:
        ims_token = (r.json() or {}).get("token") or ""
    except Exception:
        pass
    if not ims_token:
        raise FireflyIOSError(
            f"ims/tokens 未返回 token {getattr(r, 'status_code', '?')}:"
            f"{(getattr(r, 'text', '') or '')[:200]}"
        )

    # 6) fromSusi(device)→ authorization code
    code = _from_susi_client(client, ims_token, hdid, bridge_ecid, debug_id, lf)

    # 7) token/v4 device → access_token + device_token
    result = _token_v4_device_client(client, code, device_id, lf)
    result["device_id"] = device_id
    result["email"] = email
    return result


def _from_susi_client(
    client, ims_token: str, hdid: str, bridge_ecid: str, debug_id: str, lf: LogFn
) -> str:
    callback = (
        f"{IMS_HOST}/ims/adobeid/{CLIENT_ID}/AdobeID/device?"
        + urlencode({
            "redirect_uri": REDIRECT_URI, "hashed_device_id": hdid,
            "device_name": "iPhone", "code_challenge_method": "plain",
            "use_ms_for_expiry": "false",
        })
    )
    form = {
        "remember_me": "true", "callback": callback, "client_id": CLIENT_ID,
        "scope": SCOPE, "relay": debug_id, "locale": "zh_HANS",
        "flow_type": "device", "idp_flow_type": "login",
        "ab_test": "device-show-confirmation", "s_p": "apple",
        "response_type": "device", "device_name": "iPhone",
        "hashed_device_id": hdid, "code_challenge_method": "plain",
        "redirect_uri": REDIRECT_URI, "use_ms_for_expiry": "false",
        "client_version": "15", "bridge_ecid": bridge_ecid, "flow": "signIn",
        "token": ims_token, "ecid": _bridge_ecid(),
    }
    r = client.post(
        f"{IMS_BACKEND}/ims/fromSusi",
        headers={
            "User-Agent": IOS_UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": AUTH_HOST, "Referer": f"{AUTH_HOST}/zh_HANS/index.html",
        },
        data=urlencode(form), allow_redirects=False,
    )
    loc = r.headers.get("Location", "") or ""
    code = _code_from_url(loc)
    hops = 0
    while not code and loc and loc.startswith("http") and hops < 6:
        hops += 1
        rr = client.get(loc, headers={"User-Agent": IOS_UA}, allow_redirects=False)
        loc = rr.headers.get("Location", "") or ""
        code = _code_from_url(loc)
    if not code:
        raise FireflyIOSError(
            f"fromSusi 未拿到 authorization code(status={r.status_code} loc={loc[:120]})"
        )
    lf("[fromSusi] 已拿到 authorization code")
    return code


def _token_v4_device_client(client, code: str, device_id: str, lf: LogFn) -> dict[str, Any]:
    r = client.post(
        f"{IMS_HOST}/ims/token/v4",
        headers={
            "User-Agent": SDK_UA, "x-ims-clientid": CLIENT_ID,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urlencode({
            "client_id": CLIENT_ID, "code": code,
            "device_id": device_id, "grant_type": "device",
        }),
        allow_redirects=False,
    )
    if r.status_code != 200:
        raise FireflyIOSError(
            f"token/v4 device 失败 {r.status_code}:{(r.text or '')[:300]}"
        )
    data = r.json() or {}
    access_token = data.get("access_token") or ""
    device_token = data.get("device_token") or ""
    if not access_token or not device_token:
        raise FireflyIOSError("token/v4 未返回 access_token/device_token")
    lf("✓ FF-iOS 设备 token 兑换成功(access_token + device_token)")
    return _build_token_result(data, access_token, device_token)


def login_pool_ff_ios(
    *,
    email: str,
    refresh_token: str,
    client_id: str,
    mail_url: str = "",
    device_id: str = "",
    proxy_url: str = "",
    otp_timeout: int = 180,
    use_proxy_for_mail: bool = False,
    log: Optional[LogFn] = None,
) -> dict[str, Any]:
    """号池账号免密码登录拿 FF-iOS 受信任 token(签名对齐 firefly.register_account)。

    步骤:okad 验证码登录(clio,建立已认证会话)→ 同会话 SSO 兑换 FF-iOS 设备 token。
    返回:{access_token, device_token, device_id, expires_at, dt_expires_at,
          user_id, display_name, rotated_refresh_token}。
    """
    # 延迟导入,避免循环依赖
    from app.services.adobe_otp import make_otp_poller
    from app.services.adobe_admin import _passwordless_login, complete_sub_account
    from app.services.adobe_protocol.admin_member_protocol import AdminAuth
    from app.services.firefly import CLIO_CLIENT_ID, FIREFLY_REDIRECT, FIREFLY_SCOPE
    from app.services.adobe_protocol import admin_member_protocol as _p

    lf = _mklog(log)
    if not ((refresh_token and client_id) or mail_url):
        raise FireflyIOSError("子号缺少 Refresh Token / Client ID 或取信配置")

    poller, holder = make_otp_poller(
        refresh_token=refresh_token, client_id=client_id, mail_url=mail_url,
        proxy_url=proxy_url, timeout=otp_timeout,
        use_proxy_for_mail=use_proxy_for_mail, log=lf,
    )
    client = _p.HttpClient(proxy=proxy_url)
    try:
        # 阶段一:clio 验证码登录,建立已认证会话(沿用 okad 既有实现)
        auth = AdminAuth(
            client, client_id=CLIO_CLIENT_ID, scope=FIREFLY_SCOPE,
            redirect=FIREFLY_REDIRECT,
        )
        auth.authorize(email, "en_US")
        _passwordless_login(auth, email, lf, poll=poller, otp_timeout=otp_timeout)
        if not auth.susi_token:
            raise FireflyIOSError("验证码登录未拿到会话 token")
        # 补全资料 + 激活企业(被邀请)资料,并把 susi 切到实体资料
        # (与 okad 正常流程一致;FF-iOS 设备授权要求实体资料处于激活态)
        try:
            complete_sub_account(auth, email, lf)
        except Exception as e:
            lf(f"补全/激活资料(忽略):{str(e)[:120]}")
        session_susi = auth.susi_token

        # 阶段二:同会话兑换 FF-iOS 设备 token(无需密码)
        rec = mint_ff_ios_device_token(
            client, session_susi, email,
            device_id=device_id, proxy_url=proxy_url, log=lf,
        )
        rec["rotated_refresh_token"] = holder.refresh_token if holder.rotated else ""
        return rec
    finally:
        try:
            client.close()
        except Exception:
            pass


def refresh_with_device_token(
    *, device_token: str, device_id: str, proxy_url: str = "", log: Optional[LogFn] = None
) -> dict[str, Any]:
    """用一年期 device_token 换新的 access_token(无需再过验证码)。"""
    lf = _mklog(log)
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    if _HAS_CFFI:
        try:
            s = _cffi.Session(timeout=30, proxies=proxies, verify=False, impersonate=_IMPERSONATE)
        except Exception:
            s = _cffi.Session(timeout=30, proxies=proxies, verify=False)
    else:  # pragma: no cover
        s = _cffi.Session()
        if proxies:
            s.proxies = proxies
    try:
        # 刷新 = 与初次相同的 grant_type=device,但用 device_token 代替 code。
        r = s.post(
            f"{IMS_HOST}/ims/token/v4",
            headers={
                "User-Agent": SDK_UA,
                "x-ims-clientid": CLIENT_ID,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=urlencode({
                "client_id": CLIENT_ID,
                "grant_type": "device",
                "device_token": device_token,
                "device_id": device_id,
            }),
            allow_redirects=False,
        )
        if r.status_code != 200:
            raise FireflyIOSError(
                f"device_token 刷新失败 {r.status_code}:{(r.text or '')[:300]}"
            )
        data = r.json() or {}
        access_token = data.get("access_token") or ""
        if not access_token:
            raise FireflyIOSError("device_token 刷新未返回 access_token")
        lf("✓ device_token 刷新 access_token 成功")
        now = int(time.time())
        exp_in = _ms_to_seconds(data.get("expires_in"))
        new_dt = data.get("device_token") or ""
        return {
            "access_token": access_token,
            "device_token": new_dt or device_token,
            "rotated_device_token": new_dt if new_dt and new_dt != device_token else "",
            "expires_at": (now + exp_in) if exp_in else extract_jwt_expiry(access_token),
            "user_id": data.get("userId") or extract_account_id(access_token),
        }
    finally:
        try:
            s.close()
        except Exception:
            pass
