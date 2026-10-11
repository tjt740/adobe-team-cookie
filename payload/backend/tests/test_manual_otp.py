from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import time

import pytest

from app.crud import external_member as crud
from app.models.external_member import ExternalMember
from app.services import external_login, external_sub2, firefly, manual_otp, supply_mail
from app.services.job_manager import JOBS, Job, JobCancelled


@pytest.fixture
def engine(tmp_path):
    # HTTP requests and the login worker need independent transactions. A
    # StaticPool shares one connection and lets request teardown roll back the
    # worker's uncommitted cookie write, unlike the application's file database.
    from sqlalchemy import create_engine
    from app.db.session import Base
    value = create_engine(
        "sqlite:///" + str(tmp_path / "manual-otp.db"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def broker(monkeypatch):
    value = manual_otp.ManualOtpBroker()
    monkeypatch.setattr(manual_otp, "BROKER", value)
    return value


def waiting(broker, mid):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        challenge = broker.status(mid)
        if challenge:
            return challenge
        time.sleep(.01)
    pytest.fail("manual OTP request did not become ready")


def test_requests_are_isolated_single_use_and_do_not_echo_codes(broker):
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(broker.request, 1, "one@example.com", timeout=2)
        b = pool.submit(broker.request, 2, "two@example.com", timeout=2)
        one, two = waiting(broker, 1), waiting(broker, 2)
        assert one["request_id"] != two["request_id"]
        with pytest.raises(manual_otp.ManualOtpError):
            broker.submit(2, one["request_id"], "111111")
        broker.submit(2, two["request_id"], "222222")
        broker.submit(1, one["request_id"], "111111")
        assert a.result(timeout=2) == "111111" and b.result(timeout=2) == "222222"
        assert broker.status(1) is None and broker.status(2) is None
        with pytest.raises(manual_otp.ManualOtpError) as error:
            broker.submit(1, one["request_id"], "111111")
        assert "111111" not in str(error.value)
        repeat = pool.submit(broker.request, 1, "one@example.com", timeout=2)
        current = waiting(broker, 1)
        assert current["request_id"] != one["request_id"]
        with pytest.raises(manual_otp.ManualOtpError):
            broker.submit(1, one["request_id"], "333333")
        broker.submit(1, current["request_id"], "444444")
        assert repeat.result(timeout=2) == "444444"


def test_waiting_cancels_and_times_out_without_retaining_request(broker):
    cancelled = Event()
    def check():
        if cancelled.is_set():
            raise JobCancelled()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(broker.request, 1, "one@example.com", timeout=2, check_cancelled=check)
        challenge = waiting(broker, 1)
        cancelled.set()
        with pytest.raises(JobCancelled):
            result.result(timeout=2)
        assert broker.status(1) is None
        with pytest.raises(manual_otp.ManualOtpError):
            broker.submit(1, challenge["request_id"], "123456")
    with pytest.raises(manual_otp.ManualOtpError, match="等待超时"):
        broker.request(1, "one@example.com", timeout=.05)
    assert broker.status(1) is None


def test_duplicate_waiter_does_not_replace_original(broker):
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(broker.request, 1, "one@example.com", timeout=2)
        challenge = waiting(broker, 1)
        with pytest.raises(manual_otp.ManualOtpError, match="原任务"):
            broker.request(1, "one@example.com", timeout=.1)
        assert broker.status(1) == challenge
        broker.submit(1, challenge["request_id"], "123456")
        assert result.result(timeout=2) == "123456"


def test_manual_import_and_provider_tag_preserve_data(client, db, monkeypatch, broker):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    member = ExternalMember(email="one@example.com", adobe_password="Known9!", cookie="ims_sid=keep", note="keep")
    db.add(member); db.commit()
    response = client.post('/api/external/members/import', json={
        "content": member.email, "on_duplicate": "overwrite", "otp_mode": "manual",
    })
    assert response.status_code == 200
    db.refresh(member)
    assert member.otp_mode == "manual" and member.force_code_login
    assert member.cookie == "ims_sid=keep" and member.adobe_password == "Known9!" and member.note == "keep"
    assert snapshots[0]["member_otp_modes"] == {str(member.id): "manual"}
    row = client.get('/api/external/members').json()["items"][0]
    assert row["otp_mode"] == "manual" and not row["uses_supply_mail"]
    client.post('/api/external/members/import', json={"content": member.email, "on_duplicate": "overwrite"})
    db.refresh(member)
    assert member.otp_mode == "manual"
    assert client.patch(f'/api/external/members/{member.id}/otp-mode', json={"otp_mode": "auto"}).status_code == 200
    assert client.get('/api/external/members').json()["items"][0]["uses_supply_mail"]
    from app.api.routes import external_member as routes
    monkeypatch.setattr(routes, "_active_jobs", lambda ids: {member.id: {"status": "running"}})
    assert client.patch(f'/api/external/members/{member.id}/otp-mode', json={"otp_mode": "manual"}).status_code == 409


def test_request_submission_is_authenticated_and_sanitized(client, db, broker, monkeypatch):
    from app.api.deps import get_current_user
    from app.main import app
    from app.services import log_store
    member = ExternalMember(email="one@example.com", otp_mode="manual")
    db.add(member); db.commit()
    path = f'/api/external/members/{member.id}/otp'
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(broker.request, member.id, member.email, timeout=3)
        challenge = waiting(broker, member.id)
        status = client.get(path)
        assert status.json()["challenge"] == challenge and status.headers["cache-control"] == "no-store"
        logs = []
        monkeypatch.setattr(log_store.STORE, "add", lambda *a, **kw: logs.append((a, kw)))
        secret = "private-otp-input"
        invalid = client.post(path, json={"request_id": challenge["request_id"], "code": secret})
        assert invalid.status_code == 422 and secret not in invalid.text and secret not in str(logs)
        user_override = app.dependency_overrides.pop(get_current_user)
        try:
            assert client.get(path).status_code == 401
            assert client.post(path, json={"request_id": challenge["request_id"], "code": "123456"}).status_code == 401
            assert client.patch(path + '-mode', json={"otp_mode": "auto"}).status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = user_override
        assert client.post(path, json={"request_id": "0"*32, "code": "123456"}).status_code == 409
        accepted = client.post(path, json={"request_id": challenge["request_id"], "code": "123456"})
        assert accepted.status_code == 200 and "123456" not in accepted.text
        assert result.result(timeout=2) == "123456"
        assert client.post(path, json={"request_id": challenge["request_id"], "code": "123456"}).status_code == 409


@pytest.mark.parametrize("with_password", [False, True])
def test_manual_login_continues_cookie_storage_and_sub2_without_auto_mail(
    client, db, SessionLocal, monkeypatch, broker, with_password,
):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or SimpleNamespace(id=987))
    line = "one@example.com" + ("|Known9!" if with_password else "")
    assert client.post('/api/external/members/import', json={"content": line, "otp_mode": "manual"}).status_code == 200
    member = crud.get_by_email(db, "one@example.com")
    # 改了下一次模式，本任务仍使用提交时的手动模式快照。
    member.otp_mode = "auto"
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login, "FORCE_CODE_LOGIN", False)
    monkeypatch.setattr(firefly, "make_otp_poller", lambda **kw: pytest.fail("manual mode must not build automatic mail poller"))
    monkeypatch.setattr(supply_mail, "SupplyMailbox", lambda *a, **kw: pytest.fail("manual mode must not contact supply.ink"))
    synced = []
    monkeypatch.setattr(external_sub2, "after_login", lambda mid, **kw: synced.append(mid))
    def push_after_login(mid, target, **kw):
        synced.append(mid)
        return {'status': 'pending', 'message': '已提交 Sub2 推送'}
    monkeypatch.setattr(external_sub2, "queue_login_push", push_after_login)
    replies = iter([{"errorCode":"challenge_required"}, {"token":"verified-password"}])
    def post(*a, **kw):
        data = next(replies)
        return SimpleNamespace(status_code=401 if "errorCode" in data else 200, headers={}, json=lambda:data)
    http = SimpleNamespace(close=lambda:None, session=SimpleNamespace(cookies={"ims_sid":"manual"}), cookies={}, post=post)
    codes = []
    auth = SimpleNamespace(authorize=lambda *a:None, client=http, susi_token="", headers=lambda:{},
        auth_state_encrypted="", identity_verification_token="", start_email_mfa=lambda *a:True,
        send_email_challenge=lambda:True, verify_email_challenge=lambda code:codes.append(code) or True)
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw:http)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw:auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a:["password"])
    def code_login(auth, email, log, *, poll, **kw):
        assert poll.manual_input is True
        codes.append(poll(email, timeout=3)); auth.susi_token = "verified-code"
    monkeypatch.setattr(firefly._adm, "_passwordless_login", code_login)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", lambda *a, **kw:"")
    def acquire(auth, *a, **kw):
        assert auth.susi_token == ("verified-password" if with_password else "verified-code")
        return "firefly-token"
    monkeypatch.setattr(firefly, "_acquire_firefly_token", acquire)
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *a, **kw:{})
    monkeypatch.setattr(firefly, "fetch_credits_detail", lambda *a, **kw:{"available":4000,"total":4000})
    job = Job(987, 'external_login', snapshots[0])
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(external_login.batch_login_worker, job)
        challenge = waiting(broker, member.id)
        assert client.post(f'/api/external/members/{member.id}/otp', json={
            "request_id":challenge["request_id"], "code":"654321",
        }).status_code == 200
        result.result(timeout=3)
    assert job.success == 1 and job.fail == 0 and codes == ["654321"] and synced == [member.id]
    assert not any("654321" in line for line in job.logs)
    db.refresh(member)
    assert member.cookie == "ims_sid=manual" and member.login_status == "ok"


def test_manual_password_success_does_not_wait_for_unneeded_code(db, SessionLocal, monkeypatch, broker):
    crud.import_lines(db, "one@example.com|Known9!", otp_mode="manual")
    member = crud.get_by_email(db, "one@example.com")
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_sub2, "after_login", lambda *a, **kw:None)
    def login(**kwargs):
        assert callable(kwargs["otp_poller"]) and kwargs["supply_token"] == ""
        return {"cookie":"ims_sid=direct", "credits":4000, "credits_total":4000}
    monkeypatch.setattr(firefly, "register_account", login)
    assert external_login.login_and_store(member.id)["ok"] and broker.status(member.id) is None


def test_manual_wait_failure_preserves_old_cookie(db, SessionLocal, monkeypatch, broker):
    crud.import_lines(db, "one@example.com", otp_mode="manual")
    member = crud.get_by_email(db, "one@example.com")
    member.cookie = "ims_sid=keep"; db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    def login(**kwargs):
        kwargs["otp_poller"](member.email, timeout=.05)
    monkeypatch.setattr(firefly, "register_account", login)
    result = external_login.login_and_store(member.id)
    db.refresh(member)
    assert not result["ok"] and result["code"] == "login_failed" and member.cookie == "ims_sid=keep"
    assert broker.status(member.id) is None


@pytest.mark.parametrize("fails", [False, True])
def test_manual_protocol_wait_uses_full_deadline_and_does_not_resend(fails):
    from app.services import adobe_admin
    calls = []
    def poll(email, timeout):
        calls.append((email, timeout))
        if fails:
            raise manual_otp.ManualOtpError("手动验证码等待超时")
        return "123456"
    poll.manual_input = True
    def resend():
        pytest.fail("manual waiting must not automatically resend")
    if fails:
        with pytest.raises(manual_otp.ManualOtpError):
            adobe_admin._poll_email_code_with_retry("one@example.com", poll, lambda msg:None, 180, resend=resend)
    else:
        assert adobe_admin._poll_email_code_with_retry("one@example.com", poll, lambda msg:None, 180, resend=resend) == "123456"
    assert calls == [("one@example.com", 180)]
