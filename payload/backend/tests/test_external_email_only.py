from types import SimpleNamespace
from threading import Lock
import time

import pytest
from sqlalchemy import create_engine, text

from app.crud import external_member as crud
from app.crud.setting import _set
from app.services import external_login, external_sub2, firefly, supply_mail
from app.services.job_manager import JOBS, Job, JobCancelled


def test_email_only_mixed_import_and_same_batch_duplicates(db):
    result = crud.import_lines(db, "  one@example.com  \nONE@example.com\ntwo@example.com|Known9!\nnot-an-email")
    assert (result["created"], result["skipped"], result["failed"]) == (2, 1, 1)
    one = crud.get_by_email(db, "one@example.com")
    two = crud.get_by_email(db, "two@example.com")
    assert one.force_code_login and not one.adobe_password
    assert not two.force_code_login and two.adobe_password == "Known9!"
    assert result["ids"] == [one.id, two.id]


def test_batch_email_import_keeps_pasted_order_for_existing_rows(client, db, monkeypatch):
    crud.import_lines(db, "first@example.com|Known9!\nsecond@example.com|Known9!")
    first = crud.get_by_email(db, "first@example.com")
    second = crud.get_by_email(db, "second@example.com")
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    response = client.post("/api/external/members/import", json={
        "content": "second@example.com\nnew@example.com\nfirst@example.com\nSECOND@example.com",
        "on_duplicate": "overwrite", "otp_mode": "auto",
    })
    assert response.status_code == 200 and response.json()["sequential_login"] is True
    new = crud.get_by_email(db, "new@example.com")
    assert snapshots[0]["member_ids"] == [second.id, new.id, first.id]
    assert snapshots[0]["sequential_login"] is True
    assert all(snapshots[0]["member_code_login"].values())
    assert [m.id for m in crud.get_many(db, [second.id, first.id, second.id])] == [second.id, first.id]


@pytest.mark.parametrize("raise_error", [False, True])
def test_sequential_login_overrides_concurrency_and_continues_after_failure(SessionLocal, monkeypatch, raise_error):
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login.setting_crud, "get_settings", lambda db: SimpleNamespace(concurrency=8))
    monkeypatch.setattr(external_login, "log_login", lambda message: None)
    active = peak = 0
    started = []
    lock = Lock()

    def login(mid, **kw):
        nonlocal active, peak
        with lock:
            started.append(mid)
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(.02)  # 给错误的并发实现足够机会同时启动下一个账号。
            if mid == 3 and raise_error:
                raise RuntimeError("single account failure")
            return {"ok": mid != 3, "message": "failed" if mid == 3 else "ok"}
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(external_login, "login_and_store", login)
    job = Job(987, "external_login", {"member_ids": [7, 3, 9], "sequential_login": True})
    external_login.batch_login_worker(job)
    assert started == [7, 3, 9] and peak == 1
    assert job.result == {"total": 3, "success": 2, "fail": 1}
    assert [item["status"] for item in job.extra["items"]] == ["done", "failed", "done"]


def test_sequential_login_cancel_does_not_start_remaining_accounts(SessionLocal, monkeypatch):
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login, "log_login", lambda message: None)
    job = Job(987, "external_login", {"member_ids": [7, 3, 9], "sequential_login": True})
    started = []

    def login(mid, **kw):
        started.append(mid)
        job.cancel()
        kw["check_cancelled"]()

    monkeypatch.setattr(external_login, "login_and_store", login)
    with pytest.raises(JobCancelled):
        external_login.batch_login_worker(job)
    assert started == [7]
    assert job.success == job.fail == 0
    assert [item["status"] for item in job.extra["items"]] == ["cancelled", "pending", "pending"]


def test_email_overwrite_selects_code_and_retains_saved_data(db):
    crud.import_lines(db, "one@example.com|Known9!")
    member = crud.get_by_email(db, "one@example.com")
    member.note = "keep note"
    member.cookie = "ims_sid=keep"
    member.mail_url = "https://mail.example.com/inbox"
    member.sub2_links = {"target": {"account_id": 9}}
    db.commit()
    assert crud.import_lines(db, member.email)["skipped"] == 1
    assert not member.force_code_login  # 跳过不会改变已有账号的选择。
    result = crud.import_lines(db, "ONE@example.com", "overwrite")
    assert result["updated"] == 1 and member.force_code_login
    assert member.adobe_password == "Known9!" and member.cookie == "ims_sid=keep"
    assert member.note == "keep note" and member.mail_url == "https://mail.example.com/inbox"
    assert member.sub2_links == {"target": {"account_id": 9}}
    crud.import_lines(db, "one@example.com----New8!", "overwrite")
    assert not member.force_code_login and member.adobe_password == "New8!"


@pytest.mark.parametrize("password", ["", "Old9!"])
def test_code_login_without_mail_configuration_fails_before_adobe_request(monkeypatch, password):
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: pytest.fail("must not contact Adobe"))
    with pytest.raises(firefly._adm.AdminError, match="保存 supply.ink Token"):
        firefly.register_account(email="one@example.com", refresh_token="", client_id="",
                                 adobe_password=password, force_code_login=True)


def test_email_import_runs_code_mail_login_and_preserves_mode_after_password_generated(
    client, db, SessionLocal, monkeypatch,
):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *args, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    _set(db, supply_mail.TOKEN_KEY, "test-supply-token")
    db.commit()
    result = client.post("/api/external/members/import", json={"content": "one@example.com"})
    assert result.status_code == 200 and result.json()["job_id"] == 987
    member = crud.get_by_email(db, "one@example.com")
    assert snapshots[0]["member_code_login"] == {str(member.id): True}
    assert client.get("/api/external/members").json()["items"][0]["force_code_login"]
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login, "FORCE_CODE_LOGIN", False)
    synced = []
    monkeypatch.setattr(external_sub2, "after_login", lambda mid, **kw: synced.append(mid))
    def push_after_login(mid, target, **kw):
        synced.append(mid)
        return {'status': 'pending', 'message': '已提交 Sub2 推送'}
    monkeypatch.setattr(external_sub2, "queue_login_push", push_after_login)
    codes = []

    class Mailbox:
        def __init__(self, token):
            assert token == "test-supply-token"
        def messages(self, email, **kwargs):
            assert email == member.email
            return [dict(timestamp=time.time(), subject="Adobe verification code 654321", sender="", body="")]
        def close(self):
            pass

    monkeypatch.setattr(supply_mail, "SupplyMailbox", Mailbox)
    http = SimpleNamespace(close=lambda: None, session=SimpleNamespace(cookies={"ims_sid": "fresh"}), cookies={})
    auth = SimpleNamespace(authorize=lambda *a: None, client=http, susi_token="")
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: http)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: ["password"])
    monkeypatch.setattr(firefly, "_try_password_session", lambda *a, **kw: pytest.fail("email-only must bypass password"))

    def code_login(auth, email, log, *, poll, **kw):
        codes.append(poll(email, timeout=1))
        auth.susi_token = "verified-code"

    monkeypatch.setattr(firefly._adm, "_passwordless_login", code_login)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", lambda *a, **kw: pytest.fail("usable OTP session must not set a password"))

    def acquire(auth, *a, **kw):
        assert auth.susi_token == "verified-code" and kw["force_code_login"] is True
        return "firefly-token"

    monkeypatch.setattr(firefly, "_acquire_firefly_token", acquire)
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *a, **kw: {})
    monkeypatch.setattr(firefly, "fetch_credits_detail", lambda *a, **kw: {"available": 4000, "total": 4000})
    job = Job(987, "external_login", snapshots[0])
    external_login.batch_login_worker(job)
    assert job.success == 1 and job.fail == 0
    db.refresh(member)
    assert not member.adobe_password and member.force_code_login
    assert member.cookie == "ims_sid=fresh" and member.login_status == "ok"
    assert external_login.login_and_store(member.id)["ok"]  # 重登仍直接使用验证码，不设置密码。
    assert codes == ["654321", "654321"] and synced == [member.id, member.id]
    monkeypatch.setattr(external_sub2, "config", lambda db: {
        "base_url": "http://localhost:8080", "admin_token": "secret", "platform": "adobe", "group_ids": [1],
    })
    _, ids, skipped = external_sub2.prepare(db, [member.id])
    assert ids == [member.id] and skipped == []


def test_queued_job_keeps_selected_login_method(client, db, SessionLocal, monkeypatch):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    client.post("/api/external/members/import", json={"content": "one@example.com\ntwo@example.com|Known9!"})
    one = crud.get_by_email(db, "one@example.com")
    two = crud.get_by_email(db, "two@example.com")
    one.force_code_login = False
    two.force_code_login = True
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    calls = {}

    def login(mid, **kwargs):
        calls[str(mid)] = kwargs["force_code_login"]
        return {"ok": True}

    monkeypatch.setattr(external_login, "login_and_store", login)
    job = Job(987, "external_login", snapshots[0])
    external_login.batch_login_worker(job)
    assert calls == {str(one.id): True, str(two.id): False} and job.success == 2


def test_existing_database_migration_preserves_data_and_is_idempotent(monkeypatch):
    from app.db import init_db
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT)"))
            conn.execute(text("INSERT INTO external_members (email) VALUES ('keep@example.com')"))
        monkeypatch.setattr(init_db, "engine", engine)
        init_db._run_migrations()
        with engine.begin() as conn:
            assert tuple(conn.execute(text("SELECT email, force_code_login FROM external_members")).one()) == ("keep@example.com", 0)
            assert conn.execute(text("SELECT otp_mode FROM external_members")).scalar_one() == "auto"
            conn.execute(text("UPDATE external_members SET force_code_login=1"))
            conn.execute(text("UPDATE external_members SET otp_mode='manual'"))
        init_db._run_migrations()
        with engine.begin() as conn:
            assert conn.execute(text("SELECT force_code_login FROM external_members")).scalar_one() == 1
            assert conn.execute(text("SELECT otp_mode FROM external_members")).scalar_one() == "manual"
    finally:
        engine.dispose()
