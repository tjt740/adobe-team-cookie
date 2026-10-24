from types import SimpleNamespace
import time

import pytest

from app.crud import external_member as crud
from app.services import adobe_otp, external_login, firefly, supply_mail


class Http:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        data = next(self.responses)
        return SimpleNamespace(status_code=200, json=lambda: data)

    def close(self):
        pass


def response(data, code=200):
    return {"code": code, "data": data}


@pytest.mark.parametrize("sep", ["----", "|", "\t"])
@pytest.mark.parametrize("password", ["Adobe9!", "M.password", "Password@example", "12345678-1234-1234-1234-123456789abc"])
def test_two_fields_are_adobe_password_not_mail_credentials(db, sep, password):
    result = crud.import_lines(db, f"one@example.com{sep}{password}")
    member = crud.get_by_email(db, "one@example.com")
    assert result["created"] == 1 and result["failed"] == 0
    assert member.adobe_password == password
    assert not member.mail_password and not member.refresh_token and not member.client_id


def test_password_only_overwrite_preserves_original_mail_and_note(db):
    crud.import_lines(db, "one@example.com----Old9!")
    member = crud.get_by_email(db, "one@example.com")
    member.mail_url = "https://mail.example.com/inbox"
    member.note = "keep"
    db.commit()
    result = crud.import_lines(db, "one@example.com|New8!\none@example.com|New7!", "overwrite")
    assert result["updated"] == 2
    assert member.adobe_password == "New7!" and member.note == "keep"
    assert member.mail_url == "https://mail.example.com/inbox"


def test_empty_password_and_invalid_email_report_without_echoing_secret(db):
    result = crud.import_lines(db, "one@example.com----\ninvalid----Secret9!")
    assert result["failed"] == 2 and "Secret9!" not in str(result)


def test_lookup_uses_exact_require_id_without_status_and_normalizes_html():
    http = Http([
        response({"list": [{"id": 99, "username": "other@example.com"}]}),
        response({"rows": [{"id": 8, "username": "ONE@example.com"}], "total": 1}),
        response({"list": [
            {"id": 1, "to": "Other <other@example.com>", "subject": "Adobe code 111111"},
            {"id": 2, "to": "One <one@example.com>", "subject": "Adobe verification",
             "content": '<style>#123456{color:#999999}</style><p>Code:&nbsp;654321</p><script>alert(1)</script>',
             "createTime": "2026-10-05 12:00:00"},
        ]}),
        response([], 1005),
    ])
    mailbox = supply_mail.SupplyMailbox("Bearer secret-token", http=http)
    mails = mailbox.messages("one@example.com")
    assert len(mails) == 1 and "654321" in mails[0]["body"]
    assert "123456" not in mails[0]["body"] and "alert" not in mails[0]["body"]
    assert mails[0]["date"] == "2026-10-05T04:00:00+00:00"
    assert http.calls[0][1]["headers"]["Token"] == "secret-token"
    assert http.calls[2][1]["json"] == {"id": 8}
    assert all("status" not in options["json"] for _, options in http.calls)
    assert mailbox.messages("one@example.com") == []
    assert len(http.calls) == 4  # 第二次复用 require id。


def test_http_200_with_business_401_fails_without_echoing_provider_payload():
    mailbox = supply_mail.SupplyMailbox("secret-token", http=Http([{
        "code": 401, "message": "Token secret-token invalid",
    }]))
    with pytest.raises(supply_mail.SupplyMailError, match="Token 已失效") as error:
        mailbox.test()
    assert "secret-token" not in str(error.value)


def test_config_is_saved_visible_preserved_and_clearable(client, db):
    secret = "A" * 32
    assert not client.get("/api/external/mail/config").json()["configured"]
    saved = client.put("/api/external/mail/config", json={"token": "Bearer " + secret})
    assert saved.status_code == 200 and saved.json()["configured"]
    assert saved.json()["token"] == secret
    assert saved.headers["Cache-Control"] == "no-store"
    loaded = client.get("/api/external/mail/config")
    assert loaded.json()["token"] == secret
    assert loaded.headers["Cache-Control"] == "no-store"
    assert supply_mail.get_token(db) == secret
    client.put("/api/external/mail/config", json={"token": ""})
    assert supply_mail.get_token(db) == secret
    bad = client.put("/api/external/mail/config", json={"token": "private-value" * 100})
    assert bad.status_code == 422 and "private-value" not in bad.text
    client.put("/api/external/mail/config", json={"clear_token": True})
    assert not supply_mail.get_token(db)


def test_mail_routes_handle_missing_account_and_configuration(client, db):
    assert client.get("/api/external/members/999/mail").status_code == 404
    crud.import_lines(db, "one@example.com|Known9!")
    member = crud.get_by_email(db, "one@example.com")
    result = client.get(f"/api/external/members/{member.id}/mail")
    assert result.status_code == 400 and "保存" in result.text
    assert client.post("/api/external/mail/test").status_code == 400


def test_mail_config_requires_admin_session(client):
    from app.api.deps import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/external/mail/config").status_code == 401
    assert client.put("/api/external/mail/config", json={"token": "secret"}).status_code == 401


def test_supply_otp_skips_old_unknown_date_unrelated_and_used_codes(monkeypatch):
    now = time.time()
    pages = iter([
        [dict(timestamp=now - 600, subject="Adobe code 111111", sender="", body=""),
         dict(timestamp=None, subject="Adobe code 222222", sender="", body=""),
         dict(timestamp=now, subject="Order code 333333", sender="shop", body=""),
         dict(timestamp=now, subject="Adobe code 444444", sender="", body="")],
        [dict(timestamp=now, subject="Adobe code 444444", sender="", body=""),
         dict(timestamp=now, subject="Adobe code 555555", sender="", body="")],
    ])

    class Mailbox:
        def __init__(self, token):
            assert token == "supply-token"
        def messages(self, *args, **kwargs):
            return next(pages)
        def close(self):
            pass

    monkeypatch.setattr(supply_mail, "SupplyMailbox", Mailbox)
    logs = []
    poll, holder = adobe_otp.make_otp_poller(refresh_token="", client_id="", supply_token="supply-token", log=logs.append)
    assert poll("one@example.com", timeout=1) == "444444"
    assert poll("one@example.com", timeout=1) == "555555"
    assert not holder.rotated
    assert not any("supply-token" in line or "444444" in line for line in logs)


def test_missing_supply_token_is_reported_only_if_code_is_required():
    poll, _ = adobe_otp.make_otp_poller(refresh_token="", client_id="")
    with pytest.raises(supply_mail.SupplyMailError, match="保存 supply.ink Token"):
        poll("one@example.com", timeout=1)


@pytest.mark.parametrize("mfa", [False, True])
def test_password_session_requests_mail_only_when_adobe_requires_it(mfa):
    replies = [dict(errorCode="challenge_required"), dict(token="verified")] if mfa else [dict(token="verified")]
    calls = []

    def post(url, **kwargs):
        assert kwargs["json"]["password"] == "Known9!"
        data = replies.pop(0)
        return SimpleNamespace(status_code=401 if "errorCode" in data else 200, headers={}, json=lambda: data)

    auth = SimpleNamespace(start_email_mfa=lambda email: True, client=SimpleNamespace(post=post),
                           headers=lambda: {}, auth_state_encrypted="", identity_verification_token="",
                           send_email_challenge=lambda: calls.append("send") or True,
                           verify_email_challenge=lambda code: calls.append(code) or True)
    def poll(*args, **kwargs):
        calls.append("poll")
        return "123456"
    assert firefly._try_password_session(auth, "one@example.com", "Known9!", lambda _: None, poll=poll, otp_timeout=30)
    assert auth.susi_token == "verified"
    assert calls == (["send", "poll", "123456"] if mfa else [])


@pytest.mark.parametrize("password_ok", [True, False])
def test_register_password_only_reuses_session_and_falls_back_when_rejected(monkeypatch, password_ok):
    calls = []
    data = {"token": "verified-password"} if password_ok else {"errorCode": "invalid_authentication"}
    client = SimpleNamespace(
        post=lambda *args, **kwargs: SimpleNamespace(status_code=200 if password_ok else 401, headers={}, json=lambda: data),
        close=lambda: calls.append("closed"), session=SimpleNamespace(cookies={"ims_sid": "fresh"}), cookies={},
    )
    auth = SimpleNamespace(authorize=lambda *args: None, start_email_mfa=lambda *args: True,
                           client=client, headers=lambda: {}, susi_token="", auth_state_encrypted="",
                           identity_verification_token="")
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *args, **kwargs: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *args: ["password"])
    def code_login(auth, email, log, *, poll, **kwargs):
        calls.append("code-login")
        auth.susi_token = "verified-code"
    monkeypatch.setattr(firefly._adm, "_passwordless_login", code_login)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", lambda *args, **kwargs: "")
    def acquire(auth, *args, **kwargs):
        assert auth.susi_token == ("verified-password" if password_ok else "verified-code")
        return "firefly-token"
    monkeypatch.setattr(firefly, "_acquire_firefly_token", acquire)
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *args, **kwargs: {})
    monkeypatch.setattr(firefly, "fetch_credits_detail", lambda *args, **kwargs: {"available": 4000, "total": 4000})
    result = firefly.register_account(email="one@example.com", adobe_password="Known9!", refresh_token="", client_id="")
    assert result["cookie"] == "ims_sid=fresh" and result["credits_total"] == 4000
    assert calls == (["closed"] if password_ok else ["code-login", "closed"])


def test_two_field_import_route_starts_login_without_supply_config(client, db, monkeypatch):
    from app.services.job_manager import JOBS
    calls = []
    def start(kind, worker, meta):
        calls.append(meta)
        return SimpleNamespace(id=987)
    monkeypatch.setattr(JOBS, "start", start)
    result = client.post("/api/external/members/import", json={"content": "one@example.com|Known9!"})
    assert result.status_code == 200 and result.json()["job_id"] == 987
    member = crud.get_by_email(db, "one@example.com")
    assert calls[0]["member_ids"] == [member.id] and member.adobe_password == "Known9!"


def test_password_only_login_gets_saved_supply_token_and_remains_pushable(db, SessionLocal, monkeypatch):
    from app.crud.setting import _set
    from app.services import external_sub2

    crud.import_lines(db, "one@example.com----Known9!")
    member = crud.get_by_email(db, "one@example.com")
    _set(db, supply_mail.TOKEN_KEY, "supply-secret")
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_sub2, "after_login", lambda *args, **kwargs: None)
    calls = []
    def login(**kwargs):
        calls.append(kwargs)
        return {"cookie": "ims_sid=fresh", "credits": 4000, "credits_total": 4000}
    monkeypatch.setattr(firefly, "register_account", login)
    assert external_login.login_and_store(member.id)["ok"]
    db.refresh(member)
    assert member.cookie == "ims_sid=fresh" and member.login_status == "ok"
    assert calls[0]["adobe_password"] == "Known9!" and calls[0]["supply_token"] == "supply-secret"
    assert calls[0]["client_id"] == "" and calls[0]["refresh_token"] == ""
    monkeypatch.setattr(external_sub2, "config", lambda db: {
        "base_url": "http://localhost:8080", "admin_token": "secret", "platform": "adobe", "group_ids": [1],
    })
    _, ids, skipped = external_sub2.prepare(db, [member.id])
    assert ids == [member.id] and skipped == []
