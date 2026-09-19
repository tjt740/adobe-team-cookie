import json

import pytest

from app.services import arkose


class _Resp:
    def __init__(self, status=400, text="", headers=None, payload=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self._payload = payload

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text) if self.text else {}


class _Auth:
    def __init__(self):
        self.susi_token = "susi"
        self.identity_verification_token = "ivt-old"
        self.auth_state_encrypted = "ast-old"
        self.client_id = "clio-playground-web"
        self.auth_referer = "https://auth.services.adobe.com/en_US/index.html"

    def headers(self):
        return {
            "X-IMS-ClientId": self.client_id,
            "Authorization": f"Bearer {self.susi_token}",
            "X-Identity-Verification-Token": self.identity_verification_token,
            "X-IMS-Authentication-State-Encrypted": self.auth_state_encrypted,
            "Origin": "https://auth.services.adobe.com",
            "Referer": self.auth_referer,
            "Content-Type": "application/json",
        }


def test_complete_headers_always_set_v4_token_not_entcaptcha():
    h = arkose.complete_headers(_Auth(), "")
    assert h["x-ims-arkose-captcha-token"] == ""
    assert "X-IMS-EntCaptcha-Response" not in h
    h2 = arkose.complete_headers(_Auth(), "tok|pk=436DD567-5435-4B14-89A6-2F1188E11334")
    assert h2["x-ims-arkose-captcha-token"].startswith("tok|")


def test_echo_auth_state_from_captcha_required():
    auth = _Auth()
    arkose.echo_auth_state(auth, _Resp(headers={
        "x-ims-authentication-state-encrypted": "ast-new",
        "X-Identity-Verification-Token": "ivt-new",
    }))
    assert auth.auth_state_encrypted == "ast-new"
    assert auth.identity_verification_token == "ivt-new"


def test_captcha_blob_from_header_or_body():
    assert arkose.captcha_blob(_Resp(headers={"x-ims-captcha-encrypted": "BLOB"})) == "BLOB"
    assert arkose.captcha_blob(_Resp(payload={"captchaEncryptedData": "BODY"})) == "BODY"
    assert arkose.captcha_blob(_Resp()) == ""


def test_is_captcha_required_does_not_treat_v2_forbidden_as_blob():
    body = '{"errorCode":"forbidden","errorMessage":"Use /v4/accounts when Arkose captcha is enabled"}'
    assert arkose.is_captcha_required(403, body) is False
    assert arkose.is_captcha_required(400, '{"errorCode":"captcha_required"}') is True


def test_already_completed():
    assert arkose.already_completed(
        400, '{"errorCode":"invalid_field","errorMessage":"country code if it\'s already set"}'
    )
    assert not arkose.already_completed(403, "Use /v4/accounts")


def test_funcaptcha_task_includes_blob_and_strips_loopback_proxy():
    task = arkose.build_funcaptcha_task(
        "2captcha",
        website_url="https://auth.services.adobe.com/en_US/index.html",
        blob="ENC",
        user_agent="Mozilla/5.0",
        proxy_url="http://127.0.0.1:7890",
    )
    assert task["type"] == "FunCaptchaTaskProxyless"
    assert task["websitePublicKey"] == arkose.SIGNUP_PUBLIC_KEY
    assert json.loads(task["data"]) == {"blob": "ENC"}
    assert "proxyAddress" not in task


def test_funcaptcha_task_residential_proxy():
    task = arkose.build_funcaptcha_task(
        "2captcha",
        website_url="https://auth.services.adobe.com/en_US/index.html",
        blob="ENC",
        proxy_url="http://user:pass@1.2.3.4:8000",
    )
    assert task["type"] == "FunCaptchaTask"
    assert task["proxyAddress"] == "1.2.3.4"
    assert task["proxyLogin"] == "user"


def test_yescaptcha_widget_is_still_offline():
    with pytest.raises(arkose.ArkoseError, match="下线"):
        arkose.solve_funcaptcha(
            provider="yescaptcha", api_key="k",
            website_url="https://auth.services.adobe.com/", blob="x",
        )


def test_yescaptcha_solve_uses_session_not_widget(monkeypatch):
    seen = {}

    def _harvest(**kw):
        seen.update(kw)
        from app.services.arkose_session import HarvestSeed
        return HarvestSeed(
            token="sess|pk=436DD567-5435-4B14-89A6-2F1188E11334|sup=1",
            cookies=[{"name": "ARID", "value": "arid-1"}],
            arid="arid-1",
            suppressed=True,
        )

    res = arkose.solve(
        provider="yescaptcha", api_key="KEY",
        website_url="https://auth.services.adobe.com/en_US/index.html",
        blob="BLOB", proxy_url="http://user:pass@1.2.3.4:8000",
        harvest_fn=_harvest,
    )
    assert res.token.startswith("sess|")
    assert res.suppressed is True
    assert res.cookies[0]["name"] == "ARID"
    assert seen["blob"] == "BLOB"
    assert "1.2.3.4" in seen["proxy_url"]


def test_solve_funcaptcha_polls_token():
    def _poll(api_base, key, task):
        assert api_base == "https://api.2captcha.com"
        assert key == "KEY"
        assert json.loads(task["data"])["blob"] == "BLOB"
        return "solved-token|pk=436DD567-5435-4B14-89A6-2F1188E11334|sup=1"

    tok = arkose.solve_funcaptcha(
        provider="2captcha", api_key="KEY",
        website_url="https://auth.services.adobe.com/en_US/index.html",
        blob="BLOB", poll=_poll,
    )
    assert tok.startswith("solved-token")


def test_load_captcha_config_env_overrides(monkeypatch):
    monkeypatch.setenv("ADOBE_CAPTCHA_PROVIDER", "capsolver")
    monkeypatch.setenv("ADOBE_CAPTCHA_KEY", "from-env")
    provider, key = arkose.load_captcha_config()
    assert provider == "capsolver"
    assert key == "from-env"


def test_inject_solver_cookies_skips_relay():
    class C:
        cookies = {"relay": "keep"}
        session = None
    arkose.inject_solver_cookies(C, [
        {"name": "relay", "value": "overwrite"},
        {"name": "ARID", "value": "arid-1"},
    ])
    assert C.cookies["relay"] == "keep"
    assert C.cookies["ARID"] == "arid-1"
