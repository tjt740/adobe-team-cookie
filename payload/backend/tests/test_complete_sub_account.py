import json

import pytest

from app.services import adobe_admin as adm
from app.services.adobe_admin import AdminError, complete_sub_account


class FakeResp:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text if text else (json.dumps(self._payload) if self._payload else "")
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 Chrome/136"
        self.proxy = "http://user:pass@10.0.0.9:8000"
        self.puts = []
        self.gets = []
        self.posts = []
        self.put_queue = []
        self.cookies = {}
        self.session = None

    def get(self, url, headers=None, **kw):
        self.gets.append(url)
        if "/accounts/me" in url:
            if len([u for u in self.gets if "/accounts/me" in u]) == 1:
                return FakeResp(200, {
                    "userId": "U1@AdobeID",
                    "firstName": "",
                    "profileData": {
                        "actions": [{"code": "IncompleteProfile"}],
                        "links": [],
                    },
                })
            return FakeResp(200, {
                "userId": "U1@AdobeID",
                "firstName": "Charles",
                "profileData": {"actions": [], "links": []},
            })
        return FakeResp(200, {})

    def post(self, url, headers=None, json=None, **kw):
        self.posts.append(url)
        return FakeResp(200, {})

    def put(self, url, headers=None, json=None, **kw):
        self.puts.append({"url": url, "headers": dict(headers or {}), "json": json})
        if self.put_queue:
            return self.put_queue.pop(0)
        return FakeResp(200, {})


class StubAuth:
    def __init__(self, client):
        self.client = client
        self.client_id = "clio-playground-web"
        self.susi_token = "susi.jwt"
        self.identity_verification_token = "ivt-1"
        self.auth_state_encrypted = "ast-1"
        self.auth_referer = "https://auth.services.adobe.com/en_US/index.html"
        self.debug_id = "dbg"

    def headers(self):
        return {
            "X-IMS-ClientId": self.client_id,
            "Authorization": f"Bearer {self.susi_token}",
            "X-Identity-Verification-Token": self.identity_verification_token,
            "X-IMS-Authentication-State-Encrypted": self.auth_state_encrypted,
            "Origin": "https://auth.services.adobe.com",
            "Referer": self.auth_referer,
            "Content-Type": "application/json",
            "X-Debug-Id": self.debug_id,
        }


def _logs():
    buf = []
    return buf, buf.append


def test_complete_puts_v4_not_v2():
    client = FakeClient()
    complete_sub_account(
        StubAuth(client), "a@ex.com", lambda _m: None,
        country="SG", locale="en_US",
    )
    assert client.puts, "should PUT complete account"
    assert all("/signin/v4/accounts" in p["url"] for p in client.puts)
    assert all("/signin/v2/accounts" not in p["url"] for p in client.puts)
    h = client.puts[0]["headers"]
    assert "x-ims-arkose-captcha-token" in h
    assert "X-IMS-EntCaptcha-Response" not in h
    assert h["x-ims-arkose-captcha-token"] == ""
    body = client.puts[0]["json"]["account"]
    assert body["userId"] == "U1@AdobeID"
    assert body["email"] == "a@ex.com"


def test_complete_v2_forbidden_is_not_silently_retried_as_captcha():
    client = FakeClient()
    client.put_queue = [FakeResp(
        403,
        {"errorCode": "forbidden",
         "errorMessage": "Use /v4/accounts when Arkose captcha is enabled"},
        text='{"errorCode":"forbidden","errorMessage":"Use /v4/accounts when Arkose captcha is enabled"}',
    )]
    with pytest.raises(AdminError, match="Use /v4/accounts"):
        complete_sub_account(
            StubAuth(client), "a@ex.com", lambda _m: None,
            country="SG", locale="en_US",
        )
    assert len(client.puts) == 1
    assert "/signin/v4/accounts" in client.puts[0]["url"]


def test_complete_captcha_required_retries_same_client_with_token(monkeypatch):
    client = FakeClient()
    client.put_queue = [
        FakeResp(
            400,
            {"errorCode": "captcha_required"},
            text='{"errorCode":"captcha_required"}',
            headers={
                "x-ims-captcha-encrypted": "BLOB-1",
                "x-ims-authentication-state-encrypted": "ast-2",
                "x-identity-verification-token": "ivt-2",
            },
        ),
        FakeResp(200, {"ok": True}),
    ]
    monkeypatch.setattr(adm._arkose, "load_captcha_config", lambda: ("yescaptcha", "KEY"))

    seen = {}

    def _solve(**kw):
        seen.update(kw)
        return adm._arkose.ArkoseResult(
            token="ARKOSE-TOKEN|pk=436DD567-5435-4B14-89A6-2F1188E11334",
            cookies=[{"name": "ARID", "value": "arid-1"}],
        )

    monkeypatch.setattr(adm._arkose, "solve", _solve)

    auth = StubAuth(client)
    logs, lf = _logs()
    complete_sub_account(auth, "a@ex.com", lf, country="SG", locale="en_US")

    assert len(client.puts) == 2
    assert client.puts[0]["headers"]["x-ims-arkose-captcha-token"] == ""
    assert client.puts[1]["headers"]["x-ims-arkose-captcha-token"].startswith("ARKOSE-TOKEN")
    assert client.puts[0]["url"] == client.puts[1]["url"]
    assert "/signin/v4/accounts" in client.puts[1]["url"]
    assert seen["blob"] == "BLOB-1"
    assert seen["proxy_url"] == client.proxy
    assert client.cookies.get("ARID") == "arid-1"
    # captcha_required 400 的新 auth state 必须带到 retry
    assert auth.auth_state_encrypted == "ast-2"
    assert auth.identity_verification_token == "ivt-2"
    assert any("PUT v4 retry after arkose" in m for m in logs)


def test_complete_captcha_without_solver_explains_config(monkeypatch):
    client = FakeClient()
    client.put_queue = [FakeResp(
        400, {"errorCode": "captcha_required"},
        text='{"errorCode":"captcha_required"}',
        headers={"x-ims-captcha-encrypted": "BLOB"},
    )]
    monkeypatch.setattr(adm._arkose, "load_captcha_config", lambda: ("", ""))
    with pytest.raises(AdminError, match="ADOBE_CAPTCHA"):
        complete_sub_account(
            StubAuth(client), "a@ex.com", lambda _m: None,
            country="SG", locale="en_US",
        )


def test_complete_already_set_is_success():
    client = FakeClient()
    client.put_queue = [FakeResp(
        400,
        {"errorCode": "invalid_field",
         "errorMessage": "It's not allowed to set country code if it's already set"},
        text='{"errorCode":"invalid_field","errorMessage":"It\'s not allowed to set country code if it\'s already set"}',
    )]
    complete_sub_account(
        StubAuth(client), "a@ex.com", lambda _m: None,
        country="SG", locale="en_US",
    )
    assert len(client.puts) == 1


# ---- Adobe 侧 SERVICE_ERROR 要重试,不能一次就判号死 ----

_SVC_ERR = ('{"errorCode":"SERVICE_ERROR","errorMessage":"Error validating '
            'password policy in CS for userId 9A11833F6AAC387C0A495C20@AdobeID"}')


def test_service_error_in_400_is_retried_then_succeeds(monkeypatch):
    """线上实测:同一个号两次提交,一次 captcha_required 一次 SERVICE_ERROR。
    确定性的密码不合规不会时有时无,所以这是 Adobe 抖动,必须重试。"""
    monkeypatch.setattr(adm.time, "sleep", lambda *_a: None)
    client = FakeClient()
    client.put_queue = [
        FakeResp(400, {"errorCode": "SERVICE_ERROR"}, text=_SVC_ERR),
        FakeResp(400, {"errorCode": "SERVICE_ERROR"}, text=_SVC_ERR),
        FakeResp(200, {}, text="{}"),
    ]
    logs, lf = _logs()
    complete_sub_account(StubAuth(client), "a@ex.com", lf,
                         country="SG", locale="en_US")
    assert len(client.puts) == 3, "SERVICE_ERROR 应该重试到成功"
    assert any("Adobe 服务端错误" in m for m in logs)


def test_service_error_gives_up_after_budget(monkeypatch):
    monkeypatch.setattr(adm.time, "sleep", lambda *_a: None)
    client = FakeClient()
    client.put_queue = [FakeResp(400, {"errorCode": "SERVICE_ERROR"}, text=_SVC_ERR)
                        for _ in range(6)]
    with pytest.raises(AdminError, match="SERVICE_ERROR"):
        complete_sub_account(StubAuth(client), "a@ex.com", lambda _m: None,
                             country="SG", locale="en_US")
    assert len(client.puts) == 1 + adm._COMPLETE_SERVICE_ERROR_RETRIES


def test_plain_400_still_fails_fast(monkeypatch):
    """不是服务端错误的 400(比如字段真有问题)不该白白重试。"""
    monkeypatch.setattr(adm.time, "sleep", lambda *_a: None)
    client = FakeClient()
    client.put_queue = [FakeResp(400, {"errorCode": "invalid_field"},
                                 text='{"errorCode":"invalid_field"}')
                        for _ in range(4)]
    with pytest.raises(AdminError, match="invalid_field"):
        complete_sub_account(StubAuth(client), "a@ex.com", lambda _m: None,
                             country="SG", locale="en_US")
    assert len(client.puts) == 1


def test_is_service_error_classification():
    assert adm._is_service_error(400, _SVC_ERR) is True
    assert adm._is_service_error(409, '{"errorCode":"INTERNAL_ERROR"}') is True
    assert adm._is_service_error(503, "") is True
    assert adm._is_service_error(400, '{"errorCode":"invalid_field"}') is False
    assert adm._is_service_error(400, '{"errorCode":"captcha_required"}') is False


# ---- 密码预检的响应要记进日志(以前直接丢掉) ----

def test_password_precheck_responses_are_logged():
    client = FakeClient()
    logs, lf = _logs()
    password = complete_sub_account(StubAuth(client), "a@ex.com", lf,
                                    country="SG", locale="en_US")
    assert any("密码合规校验 status=" in m for m in logs), "合规校验响应没记"
    assert any("密码泄露校验 status=" in m for m in logs), "泄露校验响应没记"
    # 密码明文不能进日志
    assert password and not any(password in m for m in logs)


def test_default_completion_password_is_unique_and_submitted():
    passwords = []
    for _ in range(2):
        client = FakeClient()
        password = complete_sub_account(StubAuth(client), "new@ex.com", lambda _: None,
                                        country="SG", locale="en_US")
        assert password == client.puts[0]["json"]["account"]["password"]
        assert len(password) == 20
        assert all(any(check(c) for c in password) for check in (str.isupper, str.islower, str.isdigit))
        passwords.append(password)
    assert passwords[0] != passwords[1]


def test_rejected_password_is_not_submitted():
    client = FakeClient()
    client.post = lambda *args, **kwargs: FakeResp(200, {"valid": False})
    with pytest.raises(AdminError, match="密码合规校验未通过"):
        complete_sub_account(StubAuth(client), "new@ex.com", lambda _: None,
                             password="Rejected", country="SG", locale="en_US")
    assert not client.puts
