from types import SimpleNamespace

import pytest

from app.services import adobe_admin, external_login
from app.services.adobe_protocol.admin_member_protocol import AdminAuth


def auth_response(status, data):
    response = SimpleNamespace(status_code=status, headers={}, json=lambda: data)
    return AdminAuth(SimpleNamespace(post=lambda *args, **kwargs: response))


def test_missing_adobe_account_is_reported_without_sensitive_response(monkeypatch):
    auth = auth_response(401, {
        "errorCode": "invalid_authentication",
        "errorMessage": "Could not find account for username user@ex.com and type individual",
        "token": "secret-response-token",
    })
    logs = []
    monkeypatch.setattr("app.services.adobe_protocol.admin_member_protocol.log", logs.append)
    def unexpected_poll(*args, **kwargs):
        pytest.fail("Mailbox must not be accessed when Adobe rejects authentication state")
    with pytest.raises(adobe_admin.AdminError) as error:
        adobe_admin._passwordless_login(auth, "user@ex.com", logs.append, poll=unexpected_poll)
    message = str(error.value)
    assert "HTTP 401" in message and "invalid_authentication" in message
    assert "Adobe 未找到该邮箱对应的个人类型账号" in message
    assert external_login._classify(message) == "login_failed"
    assert "secret-response-token" not in message + "".join(logs)
    assert "user@ex.com" not in message + "".join(logs)


@pytest.mark.parametrize("status, data, expected", [
    (429, {"errorCode": "too_many_requests"}, "rate_limited"),
    (403, {"errorCode": "invalid_auth_session"}, "login_failed"),
    (503, {"errorCode": {"token": "secret"}}, "rate_limited"),
    (400, {"errorCode": "unsafe value: token=secret"}, "login_failed"),
])
def test_auth_failure_keeps_http_status_and_only_safe_error_codes(status, data, expected):
    auth = auth_response(status, data)
    with pytest.raises(adobe_admin.AdminError) as error:
        adobe_admin._passwordless_login(auth, "user@ex.com", lambda _: None)
    message = str(error.value)
    assert f"HTTP {status}" in message
    assert "secret" not in message
    assert external_login._classify(message) == expected


def test_success_clears_previous_failure():
    auth = auth_response(201, {})
    auth.last_email_mfa_error = "old failure"
    assert auth.start_email_mfa("user@ex.com")
    assert auth.last_email_mfa_error == ""


def test_legacy_auth_state_error_is_a_login_failure():
    assert external_login._classify("发起邮箱验证失败 (authenticationstate)") == "login_failed"
