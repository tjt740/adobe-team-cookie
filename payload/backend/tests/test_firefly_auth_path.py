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
    calls = {"code_login": 0, "pwd_login": 0, "code_reason": ""}

    def _fake_browser_code_login(auth, email, lf, *, poll=None, otp_timeout=180):
        calls["code_login"] += 1
        auth.susi_token = "susi.from.code"

    def _fake_finish(auth, a2, email, lf, cap):
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
