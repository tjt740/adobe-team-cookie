"""firefly type2e 会话:密码 / 验证码 两条路怎么选。

线上炸过一次:_acquire_firefly_token 无条件拿 COMPLETE_PASSWORD 去登,对「本来
就已补全、密码不是我们设的」那种号必然

    401 invalid_authentication / authUserWithCredentials failed: LOGIN_FAILED

现在:知道密码才用密码,不知道就直接走验证码;密码被拒也退回验证码。
"""

from types import SimpleNamespace

import pytest

import app.services.external_login as el
import app.services.firefly as ff


@pytest.fixture
def spy(monkeypatch):
    """记录走了哪条路,并把真正发 HTTP 的收尾段短路掉。"""
    calls = {"code_login": 0, "pwd_login": 0, "code_reason": "", "sessions": []}

    def _fake_browser_code_login(auth, email, lf, *, poll=None, otp_timeout=180):
        calls["code_login"] += 1
        auth.susi_token = "susi.from.code"

    def _fake_finish(auth, a2, email, lf, cap):
        calls["sessions"].append(a2)
        return "FIREFLY_TOKEN"

    monkeypatch.setattr(ff._adm, "_browser_code_login", _fake_browser_code_login)
    monkeypatch.setattr(ff, "_finish_firefly_token", _fake_finish)
    return calls


class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


class _Client:
    def __init__(self, pwd_resp):
        self.pwd_resp = pwd_resp
        self.posts = []
        self.cookies = {}
        self.session = SimpleNamespace(cookies={})

    def get(self, *a, **kw):
        return _FakeResp(200, {})

    def post(self, url, **kw):
        self.posts.append(url)
        if "credential=password" in url:
            return self.pwd_resp
        return _FakeResp(200, {})

    def put(self, *a, **kw):
        return _FakeResp(200, {})


def _auth(pwd_resp):
    from app.services.adobe_protocol.admin_member_protocol import AdminAuth
    return AdminAuth(_Client(pwd_resp))


def _pwd_tried(auth) -> bool:
    return any("credential=password" in u for u in auth.client.posts)


@pytest.mark.parametrize("password,force_code", [("", False), ("Wrong1!", False), ("", True)])
def test_verified_otp_session_is_used_without_authenticating_again(spy, monkeypatch, password, force_code):
    auth = _auth(_FakeResp(401, {"errorCode": "invalid_authentication"}))
    auth.susi_token = "verified.otp.session"

    def unexpected_auth(*args, **kwargs):
        pytest.fail("A verified session must not be discarded for a new login")

    monkeypatch.setattr(ff, "AdminAuth", unexpected_auth)
    result = ff._acquire_firefly_token(
        auth, "reuse@ex.com", lambda _: None, password=password, force_code_login=force_code,
    )
    assert result == "FIREFLY_TOKEN"
    assert spy["sessions"] == [auth]
    assert spy["code_login"] == 0
    assert not _pwd_tried(auth)


def test_expired_existing_session_can_reauthenticate(spy, monkeypatch):
    auth = _auth(_FakeResp(200, {"token": "fresh-session"}))
    auth.susi_token = "expired-session"
    sessions = []

    def finish(original, current, *args):
        sessions.append(current)
        if current is original:
            raise ff._adm.AdminError("会话已失效")
        return "FIREFLY_TOKEN"

    monkeypatch.setattr(ff, "_finish_firefly_token", finish)
    assert ff._acquire_firefly_token(auth, "retry@ex.com", lambda _: None, password="Known1!") == "FIREFLY_TOKEN"
    assert sessions[0] is auth and sessions[1] is not auth
    assert _pwd_tried(auth)


def test_exchange_network_error_does_not_request_another_code(spy, monkeypatch):
    auth = _auth(_FakeResp())
    auth.susi_token = "verified-session"

    def fail(*args):
        raise TimeoutError("connection timeout")

    monkeypatch.setattr(ff, "_finish_firefly_token", fail)
    with pytest.raises(TimeoutError):
        ff._acquire_firefly_token(auth, "timeout@ex.com", lambda _: None)
    assert spy["code_login"] == 0


def test_no_password_goes_straight_to_code_login(spy, monkeypatch):
    """库里没存密码 → 不猜密码,直接验证码登录。"""
    auth = _auth(_FakeResp(401, {"errorCode": "invalid_authentication"}))
    tok = ff._acquire_firefly_token(auth, "a@ex.com", lambda _m: None,
                                    poll=lambda *a, **k: "123456", password="")
    assert tok == "FIREFLY_TOKEN"
    assert spy["code_login"] == 1
    assert not _pwd_tried(auth), "没密码时不该去试密码登录"


def test_force_code_login_skips_password_even_when_known(spy):
    """强制开关打开:知道密码也走验证码。"""
    auth = _auth(_FakeResp(200, {"token": "t"}))
    ff._acquire_firefly_token(auth, "a@ex.com", lambda _m: None,
                              poll=lambda *a, **k: "123456",
                              password="Known1!", force_code_login=True)
    assert spy["code_login"] == 1
    assert not _pwd_tried(auth)


def test_known_password_uses_password_login(spy):
    """知道密码就用密码 —— 省一次发码,别白白加重发码风控。"""
    auth = _auth(_FakeResp(200, {"token": "susi.tok"}))
    tok = ff._acquire_firefly_token(auth, "a@ex.com", lambda _m: None,
                                    poll=lambda *a, **k: "123456",
                                    password="Known1!")
    assert tok == "FIREFLY_TOKEN"
    assert _pwd_tried(auth)
    assert spy["code_login"] == 0, "密码登录成功就不该再收码"


def test_password_rejected_falls_back_to_code_login(spy):
    """回归:线上那个 401 invalid_authentication 不能再让整个号失败。"""
    auth = _auth(_FakeResp(401, {"errorCode": "invalid_authentication",
                                 "errorMessage": "authUserWithCredentials failed"}))
    logs = []
    tok = ff._acquire_firefly_token(auth, "a@ex.com", logs.append,
                                    poll=lambda *a, **k: "123456",
                                    password="Wrong1!")
    assert tok == "FIREFLY_TOKEN"
    assert _pwd_tried(auth)
    assert spy["code_login"] == 1
    assert any("密码登录被拒" in m for m in logs)


class _StatefulClient(_Client):
    """Adobe 拒绝缺少 Sunbreak 认证状态的密码请求。"""

    def __init__(self, *, state_ok=True):
        super().__init__(_FakeResp(200, {"token": "susi.tok"}))
        self.authorized = False
        self.state_ok = state_ok
        self.password_headers = None

    def get(self, url, **kw):
        if "/ims/authorize/v1?" in url:
            assert "client_id=SunbreakWebUI1" in url
            self.authorized = True
        return super().get(url, **kw)

    def post(self, url, **kw):
        if "/authenticationstate?" in url:
            assert self.authorized
            response = _FakeResp(200 if self.state_ok else 400)
            response.headers = {
                "x-ims-authentication-state-encrypted": "sunbreak-state",
                "x-identity-verification-token": "sunbreak-identity",
            }
            return response
        if "credential=password" in url:
            self.password_headers = kw["headers"]
            if self.password_headers.get("X-IMS-Authentication-State-Encrypted") != "sunbreak-state":
                return _FakeResp(400, {"errorCode": "invalid_auth_session"})
        return super().post(url, **kw)


def test_password_login_initializes_sunbreak_session(spy):
    client = _StatefulClient()
    auth = ff.AdminAuth(client)
    # 前一步验证码属于另一个客户端,不能依赖它的状态。
    auth.auth_state_encrypted = "old-clio-state"
    token = ff._acquire_firefly_token(
        auth, "state@ex.com", lambda _: None, password="Known1!",
    )
    assert token == "FIREFLY_TOKEN"
    assert client.authorized
    assert client.password_headers["X-Identity-Verification-Token"] == "sunbreak-identity"
    assert spy["code_login"] == 0


def test_password_session_failure_stops_before_password_or_resending_code(spy):
    client = _StatefulClient(state_ok=False)
    with pytest.raises(ff._adm.AdminError, match="无法建立密码登录认证会话"):
        ff._acquire_firefly_token(
            ff.AdminAuth(client), "state@ex.com", lambda _: None, password="Known1!",
        )
    assert client.password_headers is None
    assert spy["code_login"] == 0


# ---- 密码从库里取,不再硬编码 ----

def test_login_passes_stored_adobe_password(db, monkeypatch, SessionLocal):
    from app.models.external_member import ExternalMember

    m = ExternalMember(email="pw@ex.com", client_id="cid", refresh_token="M.tok",
                       adobe_password="Stored9!")
    db.add(m)
    db.commit()
    db.refresh(m)

    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings",
        lambda db: SimpleNamespace(proxy_enabled=False, proxy_url="", concurrency=1))
    seen = {}

    def _reg(**kw):
        seen.update(kw)
        return {"access_token": "at", "cookie": "k=v", "credits": 1.0,
                "credits_total": 1.0, "expires_at": 1, "display_name": "",
                "user_id": "", "set_password": ""}

    monkeypatch.setattr(el.firefly, "register_account", _reg)
    assert el.login_and_store(m.id)["ok"] is True
    assert seen["adobe_password"] == "Stored9!"
    assert seen["force_code_login"] is False   # 默认不强制,省发码


def test_force_code_login_env_flag_is_threaded(db, monkeypatch, SessionLocal):
    from app.models.external_member import ExternalMember

    m = ExternalMember(email="fc@ex.com", client_id="cid", refresh_token="M.tok")
    db.add(m)
    db.commit()
    db.refresh(m)

    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el, "FORCE_CODE_LOGIN", True)
    monkeypatch.setattr(
        el.setting_crud, "get_settings",
        lambda db: SimpleNamespace(proxy_enabled=False, proxy_url="", concurrency=1))
    seen = {}

    def _reg(**kw):
        seen.update(kw)
        return {"access_token": "at", "cookie": "k=v", "credits": 1.0,
                "credits_total": 1.0, "expires_at": 1, "display_name": "",
                "user_id": "", "set_password": ""}

    monkeypatch.setattr(el.firefly, "register_account", _reg)
    assert el.login_and_store(m.id)["ok"] is True
    assert seen["force_code_login"] is True
