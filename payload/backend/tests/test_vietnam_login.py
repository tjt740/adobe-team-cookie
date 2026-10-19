"""越南登录：取码站契约、仅密码认证、账号隔离与批量导入。全部使用合成凭据。"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import requests

from app.crud import external_member as crud
from app.services import external_login, external_sub2, firefly, supply_mail, vietnam_otp
from app.services.job_manager import JOBS, JobCancelled


class Clock:
    now = 1_800_000_000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Http:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, data = next(self.replies)
        def json():
            if isinstance(data, Exception):
                raise data
            return data
        return SimpleNamespace(status_code=status, json=json)

    def close(self):
        self.closed = True


def job():
    return 202, dict(success=True, status="pending", jobId="synthetic-job", pollIntervalMs=1500)


def found(clock, code="123456", **values):
    return 200, dict(status="done", success=True, otp=code,
        receivedAt=datetime.fromtimestamp(clock.time(), timezone.utc).isoformat(), **values)


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(vietnam_otp.time, "time", value.time)
    monkeypatch.setattr(vietnam_otp.time, "monotonic", value.time)
    monkeypatch.setattr(vietnam_otp.time, "sleep", value.sleep)
    return value


def mailbox(monkeypatch, replies, logs=None, **kwargs):
    http = Http(replies)
    monkeypatch.setattr(vietnam_otp.requests, "Session", lambda: http)
    return vietnam_otp.make_vietnam_otp_poller(log=logs.append if logs is not None else None, **kwargs), http


def test_async_contract_sends_only_email_and_never_logs_code(monkeypatch, clock):
    logs = []
    poll, http = mailbox(monkeypatch, [job(), (200, {"status": "running"}), found(clock)], logs)
    assert poll(" USER@Example.com ") == "123456" and http.closed
    assert http.calls[0][0:2] == ("POST", vietnam_otp.API_BASE + "/lookup")
    assert http.calls[0][2]["json"] == {"email": "user@example.com"}
    assert all(call[0] == "GET" and call[1].endswith("/lookup/synthetic-job") for call in http.calls[1:])
    assert all(call[2]["allow_redirects"] is False and call[2]["timeout"] <= 12 for call in http.calls)
    assert "123456" not in str(logs) and "synthetic-job" not in str(logs)
    assert poll.single_wait


@pytest.mark.parametrize("timestamp", [None, "not-a-date", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "2027-01-15T08:00:00"])
def test_rejects_stale_missing_future_or_ambiguous_date(monkeypatch, clock, timestamp):
    old = found(clock, "111111")[1]
    old["receivedAt"] = timestamp
    poll, http = mailbox(monkeypatch, [job(), (200, old), job(), found(clock, "222222")])
    assert poll("one@example.com", timeout=30) == "222222"
    assert len([call for call in http.calls if call[0] == "POST"]) == 2


def test_rejects_reused_code_and_keeps_accounts_separate(monkeypatch, clock):
    poll, http = mailbox(monkeypatch, [job(), found(clock), job(), found(clock), job(), found(clock, "654321"), job(), found(clock)])
    assert poll("one@example.com") == "123456"
    assert poll("ONE@example.com") == "654321"
    assert poll("two@example.com") == "123456"


@pytest.mark.parametrize("reply, message", [
    ((429, {"message": "secret-123456"}), "429"),
    ((503, {"message": "secret-123456"}), "503"),
    ((302, {}), "302"),
    ((200, ValueError("secret-123456")), "无法识别"),
    ((200, []), "无法识别"),
    ((200, {"status": "unknown"}), "任务状态"),
    ((200, {"status": "done", "kind": "auth_only", "message": "secret-123456"}), "密码登录"),
    ((200, {"status": "done", "email": "another@example.com"}), "邮箱不匹配"),
])
def test_service_errors_are_sanitized_and_do_not_trigger_other_provider(monkeypatch, clock, reply, message):
    poll, http = mailbox(monkeypatch, [job(), reply])
    with pytest.raises(vietnam_otp.VietnamOtpError, match=message) as caught:
        poll("one@example.com")
    assert "secret-123456" not in str(caught.value) and http.closed


def test_rebuilds_expired_or_empty_job_within_deadline(monkeypatch, clock):
    poll, http = mailbox(monkeypatch, [job(), (404, {}), job(), (200, {"status": "done", "success": False}), job(), found(clock)])
    assert poll("one@example.com", timeout=30) == "123456"
    assert len(http.calls) == 6


def test_valid_code_with_provider_warning_matches_the_portal_behavior(monkeypatch, clock):
    logs = []
    poll, _ = mailbox(monkeypatch, [job(), found(clock, authWarn=True)], logs)
    assert poll("one@example.com") == "123456"
    assert any("确认使用密码登录" in line for line in logs) and "123456" not in str(logs)


def test_timeout_and_cancellation_close_connection(monkeypatch, clock):
    poll, http = mailbox(monkeypatch, [job()] + [(200, {"status": "running"})] * 20)
    start = clock.time()
    with pytest.raises(vietnam_otp.VietnamOtpError, match="超时"):
        poll("one@example.com", timeout=4)
    assert clock.time() - start <= 4 and http.closed
    def cancel():
        if clock.time() > start + 4.25:
            raise JobCancelled()
    poll, http = mailbox(monkeypatch, [job()], check_cancelled=cancel)
    with pytest.raises(JobCancelled):
        poll("one@example.com")
    assert http.closed and len(http.calls) == 1


def test_connection_error_does_not_echo_third_party_details(monkeypatch, clock):
    poll, http = mailbox(monkeypatch, [])
    def fail(*a, **kw):
        raise requests.ConnectionError("secret-password-and-code")
    http.request = fail
    with pytest.raises(vietnam_otp.VietnamOtpError, match="连接失败") as caught:
        poll("one@example.com")
    assert "secret-password" not in str(caught.value) and http.closed


def test_batch_import_tabs_special_characters_snapshot_and_company_filter(client, db, monkeypatch):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    password = "Fake&9@*c@!$"
    content = "\n".join(f"synthetic{i}@example.com\t{password}" for i in range(101))
    response = client.post("/api/external/members/import", json={"content": content, "otp_mode": "vietnam"})
    assert response.status_code == 200 and response.json()["created"] == 101
    assert response.json()["sequential_login"] is True
    assert snapshots[0]["batch_size"] == 50 and len(snapshots[0]["member_ids"]) == 101
    assert set(snapshots[0]["member_otp_modes"].values()) == {"vietnam"}
    assert not any(snapshots[0]["member_code_login"].values())
    member = crud.get_by_email(db, "synthetic0@example.com")
    assert member.adobe_password == password and not member.mail_password
    rows = client.get("/api/external/members?size=200").json()["items"]
    assert len(rows) == 101 and all(r["otp_mode"] == "vietnam" and not r["uses_supply_mail"] for r in rows)
    assert password not in str(rows) and password not in str(snapshots)
    assert client.get("/api/external/members?is_company=true").json()["total"] == 0
    assert client.get("/api/external/members?is_company=false").json()["total"] == 101


def test_mode_selection_is_explicit_and_overwrite_preserves_credentials(db):
    crud.import_lines(db, "ordinary@example.com\tAdobe9!")
    ordinary = crud.get_by_email(db, "ordinary@example.com")
    assert ordinary.otp_mode == "auto"
    ordinary.note, ordinary.cookie = "keep", "ims_sid=keep"
    ordinary.force_code_login = True
    db.commit()
    assert crud.import_lines(db, ordinary.email, otp_mode="vietnam")["skipped"] == 1
    assert ordinary.otp_mode == "auto"
    result = crud.import_lines(db, ordinary.email, "overwrite", otp_mode="vietnam")
    assert result["updated"] == 1 and ordinary.otp_mode == "vietnam" and not ordinary.force_code_login
    assert ordinary.note == "keep" and ordinary.cookie == "ims_sid=keep" and ordinary.adobe_password == "Adobe9!"
    crud.import_lines(db, ordinary.email, "overwrite")
    assert ordinary.otp_mode == "vietnam" and not ordinary.force_code_login
    result = crud.import_lines(db, "missing@example.com\nvalid@example.com\tAdobe8!", otp_mode="vietnam")
    assert result["failed"] == result["created"] == 1
    assert crud.get_by_email(db, "missing@example.com") is None


def test_switch_requires_password_and_cannot_modify_active_login(client, db, monkeypatch):
    from app.api.routes import external_member as routes
    crud.import_lines(db, "missing@example.com\nwith@example.com\tAdobe9!")
    missing, member = [crud.get_by_email(db, e) for e in ("missing@example.com", "with@example.com")]
    assert client.patch(f"/api/external/members/{missing.id}/otp-mode", json={"otp_mode": "vietnam"}).status_code == 400
    assert client.patch(f"/api/external/members/{member.id}/otp-mode", json={"otp_mode": "vietnam"}).status_code == 200
    db.refresh(member)
    assert member.otp_mode == "vietnam" and not member.force_code_login
    monkeypatch.setattr(routes, "_active_jobs", lambda ids: {member.id: {"status": "running"}})
    assert client.patch(f"/api/external/members/{member.id}/otp-mode", json={"otp_mode": "auto"}).status_code == 409


@pytest.mark.parametrize("challenge", [False, True])
def test_password_login_mfa_cookie_storage_and_sub2(db, SessionLocal, monkeypatch, clock, challenge):
    crud.import_lines(db, "one@example.com\tSynthetic9!", otp_mode="vietnam")
    member = crud.get_by_email(db, "one@example.com")
    # 本次任务仍使用提交时的路线快照。
    member.otp_mode = "auto"
    db.commit()
    poll, mailbox_http = mailbox(monkeypatch, [job(), found(clock)])
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login, "FORCE_CODE_LOGIN", True)
    monkeypatch.setattr(supply_mail, "get_token", lambda db: pytest.fail("Vietnam login must not read supply Token"))
    monkeypatch.setattr(firefly, "make_otp_poller", lambda **kw: pytest.fail("must not use default mail provider"))
    monkeypatch.setattr(firefly._adm, "_passwordless_login", lambda *a, **kw: pytest.fail("must use password"))
    replies = iter(([{"errorCode": "challenge_required"}] if challenge else []) + [{"token": "verified"}])
    def post(*a, **kw):
        assert kw["json"]["password"] == "Synthetic9!"
        data = next(replies)
        return SimpleNamespace(status_code=401 if "errorCode" in data else 200, headers={}, json=lambda: data)
    http = SimpleNamespace(post=post, close=lambda: None, cookies={}, session=SimpleNamespace(cookies={"ims_sid": "vietnam"}))
    codes, synced, logs = [], [], []
    auth = SimpleNamespace(authorize=lambda *a: None, client=http, susi_token="", headers=lambda: {},
        auth_state_encrypted="", identity_verification_token="", start_email_mfa=lambda *a: True,
        send_email_challenge=lambda: True, verify_email_challenge=lambda code: codes.append(code) or True)
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: http)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: ["password"])
    def acquire(*a, **kw):
        assert kw["password_only"] is True and not kw["force_code_login"] and kw["poll"].single_wait
        assert auth.susi_token == "verified"
        return "firefly-token"
    monkeypatch.setattr(firefly, "_acquire_firefly_token", acquire)
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *a, **kw: {})
    monkeypatch.setattr(firefly, "fetch_credits_detail", lambda *a, **kw: {"available": 4000, "total": 4000})
    monkeypatch.setattr(external_sub2, "after_login", lambda mid, **kw: synced.append(mid))
    result = external_login.login_and_store(member.id, otp_mode="vietnam", log=logs.append)
    assert result["ok"] and synced == [member.id]
    assert codes == (["123456"] if challenge else [])
    assert len(mailbox_http.calls) == (2 if challenge else 0)
    assert "123456" not in str(logs) and "Synthetic9!" not in str(logs)
    db.refresh(member)
    assert member.cookie == "ims_sid=vietnam" and member.login_status == "ok"


def test_password_rejection_never_starts_passwordless_login(monkeypatch):
    http = SimpleNamespace(close=lambda: None)
    auth = SimpleNamespace(authorize=lambda *a: None, susi_token="")
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: http)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: ["password"])
    monkeypatch.setattr(firefly, "_try_password_session", lambda *a, **kw: False)
    monkeypatch.setattr(firefly._adm, "_passwordless_login", lambda *a, **kw: pytest.fail("must not fall back"))
    with pytest.raises(firefly._adm.AdminError, match="密码认证失败"):
        firefly.register_account(email="one@example.com", refresh_token="", client_id="", adobe_password="Bad9!",
                                password_only=True, otp_poller=lambda *a, **kw: "123456")


def test_long_provider_job_is_not_interrupted_by_automatic_resend(monkeypatch):
    from app.services import adobe_admin
    poll = vietnam_otp.make_vietnam_otp_poller()
    calls = []
    def wrapper(email, timeout):
        calls.append(timeout)
        return "123456"
    wrapper.single_wait = poll.single_wait
    def resend():
        pytest.fail("must wait for the asynchronous job instead of resending")
    assert adobe_admin._poll_email_code_with_retry("one@example.com", wrapper, lambda msg: None, 180, resend=resend) == "123456"
    assert calls == [180]


@pytest.mark.parametrize("password, force", [("", False), ("Known9!", True)])
def test_invalid_password_only_options_fail_before_network(monkeypatch, password, force):
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: pytest.fail("must reject before contacting Adobe"))
    with pytest.raises(firefly._adm.AdminError, match="需要 Adobe 密码"):
        firefly.register_account(email="one@example.com", refresh_token="", client_id="", password_only=True,
                                 adobe_password=password, force_code_login=force)


def test_token_exchange_reauthentication_cannot_fall_back_to_code_login(monkeypatch):
    def post(*a, **kw):
        return SimpleNamespace(status_code=401, headers={}, json=lambda: {"errorCode": "invalid_authentication"})
    http = SimpleNamespace(post=post)
    auth = SimpleNamespace(susi_token="", client=http, authorize=lambda *a: None,
        start_email_mfa=lambda *a: True, headers=lambda: {}, auth_state_encrypted="", identity_verification_token="")
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: ["password"])
    monkeypatch.setattr(firefly._adm, "_browser_code_login", lambda *a, **kw: pytest.fail("must not use code login"))
    with pytest.raises(firefly._adm.AdminError, match="密码认证失败"):
        firefly._acquire_firefly_token(auth, "one@example.com", lambda msg: None,
                                      password="Bad9!", password_only=True)
