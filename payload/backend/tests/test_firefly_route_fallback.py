"""新路线优先，原路线兜底；两条都失败后停止，不丢失已更新凭据。"""

from types import SimpleNamespace

import pytest

from app.models.external_member import ExternalMember
from app.services import external_login, firefly
from app.services.job_manager import JobCancelled


@pytest.fixture
def login(monkeypatch):
    events, logs, saved = [], [], []
    client = SimpleNamespace(
        close=lambda: events.append("close"), cookies={},
        session=SimpleNamespace(cookies={"ims_sid": "fresh"}),
    )
    auth = SimpleNamespace(authorize=lambda *a: None, client=client, susi_token="verified")
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: client)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *a, **kw: auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: [])
    monkeypatch.setattr(firefly._adm, "_passwordless_login", lambda *a, **kw: None)
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *a, **kw: {})
    monkeypatch.setattr(firefly, "fetch_credits_detail", lambda *a, **kw: {"available": 4000, "total": 4000})

    def run(*, primary=None, fallback=None, completion=None, missing_cookie=False):
        def acquire(*a, **kw):
            reuse_only = kw.get("reuse_only", False)
            events.append("primary" if reuse_only else "fallback")
            assert kw["force_code_login"] and kw["profile_preference"] == "personal"
            if not reuse_only:
                assert saved == [{"adobe_password": "Generated2!"}]
                assert kw["password"] == "Generated2!"
            error = primary if reuse_only else fallback
            if error is not None:
                raise error
            client.session.cookies = {} if missing_cookie and reuse_only else {"ims_sid": "fresh"}
            return "firefly-token"

        def complete(*a, **kw):
            events.append("complete")
            assert kw["legacy_completion"] is True
            if completion is not None:
                raise completion
            return "Generated2!"

        monkeypatch.setattr(firefly, "_acquire_firefly_token", acquire)
        monkeypatch.setattr(firefly._adm, "complete_sub_account", complete)
        return firefly.register_account(
            email="routes@example.com", refresh_token="", client_id="",
            otp_poller=lambda *a, **kw: "123456", force_code_login=True,
            profile_preference="personal", log=logs.append,
            on_credentials=lambda **kw: saved.append(kw),
        )

    return SimpleNamespace(run=run, events=events, logs=logs, saved=saved)


def test_primary_success_skips_original_route(login):
    result = login.run()
    assert result["cookie"] == "ims_sid=fresh" and not result["set_password"]
    assert login.events == ["primary", "close"] and not login.saved
    assert any("修复路线登录成功" in line for line in login.logs)
    assert not any("登录路线 2/2" in line for line in login.logs)


def test_ims_success_with_revoked_business_token_is_not_login_success(login, monkeypatch):
    def rejected(*args, error_out, **kwargs):
        error_out.update(message="积分查询凭证已失效（HTTP 401 / 401013）", http_status=401)
        return None

    monkeypatch.setattr(firefly, "fetch_credits_detail", rejected)
    with pytest.raises(firefly._adm.AdminError, match="登录会话验证失败.*401013"):
        login.run()
    assert login.events == ["primary", "close"]
    assert not login.saved


@pytest.mark.parametrize("message", ["Adobe 拒绝访问（HTTP 403）", "积分接口请求失败或超时，请稍后重试"])
def test_unknown_quota_does_not_reject_otherwise_authenticated_session(login, monkeypatch, message):
    def unavailable(*args, error_out, **kwargs):
        error_out.update(message=message)
        return None

    monkeypatch.setattr(firefly, "fetch_credits_detail", unavailable)
    record = login.run()
    assert record["cookie"] and record["credits"] is None
    assert record["credits_error"] == message


@pytest.mark.parametrize("error", [firefly._adm.AdminError("needs completion"), TimeoutError("connection timeout")])
def test_primary_failure_uses_original_route_once(login, error):
    result = login.run(primary=error)
    assert result["cookie"] == "ims_sid=fresh" and result["set_password"] == "Generated2!"
    assert login.events == ["primary", "complete", "fallback", "close"]
    assert any("切换原路线" in line for line in login.logs)
    assert any("原路线登录成功" in line for line in login.logs)
    assert not any("本次登录失败" in line for line in login.logs)


def test_missing_primary_cookie_also_uses_original_route(login):
    result = login.run(missing_cookie=True)
    assert result["cookie"] == "ims_sid=fresh"
    assert login.events == ["primary", "complete", "fallback", "close"]


@pytest.mark.parametrize("stage", ["completion", "fallback"])
def test_both_routes_fail_with_both_reasons_and_no_loop(login, stage):
    with pytest.raises(firefly.LoginRoutesExhausted) as caught:
        login.run(primary=firefly._adm.AdminError("primary rejected"),
                  **{stage: TimeoutError("original timeout")})
    assert "primary rejected" in str(caught.value) and "original timeout" in str(caught.value)
    expected = ["primary", "complete"] + (["fallback"] if stage == "fallback" else [])
    assert login.events == expected + ["close"]
    assert len(login.saved) == (1 if stage == "fallback" else 0)
    assert any("本次登录失败" in line for line in login.logs)


@pytest.mark.parametrize("stage", ["primary", "completion", "fallback"])
def test_cancellation_stops_without_becoming_route_failure(login, stage):
    kwargs = {} if stage == "primary" else {"primary": firefly._adm.AdminError("primary rejected")}
    kwargs[stage] = JobCancelled()
    with pytest.raises(JobCancelled):
        login.run(**kwargs)
    expected = ["primary"]
    if stage != "primary":
        expected += ["complete"]
    if stage == "fallback":
        expected += ["fallback"]
    assert login.events == expected + ["close"]
    assert not any("本次登录失败" in line for line in login.logs)


def test_exhausted_routes_are_not_restarted_by_proxy_retry(db, SessionLocal, monkeypatch):
    member = ExternalMember(email="failed@example.com", cookie="old=keep")
    db.add(member)
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    calls = []

    def fail(**kw):
        calls.append(kw)
        raise firefly.LoginRoutesExhausted(TimeoutError("primary timeout"), TimeoutError("original timeout"))

    monkeypatch.setattr(firefly, "register_account", fail)
    result = external_login.login_and_store(member.id, network_retries=3)
    assert not result["ok"] and len(calls) == 1
    assert "两条路线均登录失败" in result["message"]
    db.refresh(member)
    assert member.cookie == "old=keep" and member.login_status != "ok"
