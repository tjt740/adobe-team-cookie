import json
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.crud.setting import _set
from app.models.setting import Setting
from app.services import supply_mail, supply_mail_health as health


@pytest.fixture
def mailbox(monkeypatch):
    state = SimpleNamespace(calls=[], closed=0, error=None)

    class Mailbox:
        def __init__(self, token):
            self.token = token

        def test(self):
            state.calls.append(self.token)
            if state.error:
                raise state.error
            return {"ok": True, "total": 21, "message": "supply.ink 邮件连接成功"}

        def close(self):
            state.closed += 1

    monkeypatch.setattr(supply_mail, "SupplyMailbox", Mailbox)
    return state


def test_manual_result_persists_and_replacing_or_clearing_token_resets_it(client, mailbox):
    path = "/api/external/mail/config"
    saved = client.put(path, json={"token": "first-token"}).json()
    assert saved["token"] == "first-token" and saved["health"]["status"] == "untested"
    assert saved["health"]["next_check_at"] and saved["health"]["checked_at"] is None
    tested = client.post("/api/external/mail/test").json()
    assert tested["ok"] and tested["health"]["status"] == "ok"
    assert tested["health"]["next_check_at"] - tested["health"]["checked_at"] == 3600
    loaded = client.get(path).json()
    assert loaded["health"] == tested["health"]
    # Saving an unchanged Token and the legacy empty-string update retain the result.
    for value in ("first-token", ""):
        same = client.put(path, json={"token": value}).json()
        assert same["token"] == "first-token" and same["health"] == tested["health"]
    replaced = client.put(path, json={"token": "next-token"}).json()
    assert replaced["health"]["status"] == "untested" and replaced["health"]["checked_at"] is None
    mailbox.error = supply_mail.SupplyMailError("supply.ink Token 已失效")
    failed = client.post("/api/external/mail/test")
    assert failed.status_code == 400
    assert client.get(path).json()["health"]["status"] == "error"
    cleared = client.put(path, json={"clear_token": True}).json()
    assert cleared["token"] == "" and cleared["health"] == {
        "status": "untested", "checked_at": None, "next_check_at": None,
    }
    assert mailbox.calls == ["first-token", "next-token"] and mailbox.closed == 2


def test_hourly_checks_are_durable_throttled_and_retry_failures(db, SessionLocal, mailbox):
    _set(db, supply_mail.TOKEN_KEY, "hourly-token")
    health.reset(db, "hourly-token", now=100)
    db.commit()
    assert health.check(db, force=False, now=3699) is None
    assert not mailbox.calls
    assert health.check(db, force=False, now=3700)["health"]["status"] == "ok"
    # A fresh service session uses the saved deadline, including after a restart.
    with SessionLocal() as next_db:
        assert health.check(next_db, force=False, now=7299) is None
        mailbox.error = supply_mail.SupplyMailError("连接失败")
        with pytest.raises(supply_mail.SupplyMailError):
            health.check(next_db, force=False, now=7300)
        assert health.snapshot(next_db)["status"] == "error"
        assert health.check(next_db, force=False, now=10899) is None
        mailbox.error = None
        assert health.check(next_db, force=False, now=10900)["health"]["status"] == "ok"
    assert mailbox.calls == ["hourly-token"] * 3 and mailbox.closed == 3


def test_legacy_tokens_get_checked_and_missing_tokens_are_skipped(db, mailbox):
    assert health.check(db, force=False, now=100) is None
    assert not mailbox.calls
    _set(db, supply_mail.TOKEN_KEY, "legacy-token")
    db.commit()
    assert health.check(db, force=False, now=100)["health"]["status"] == "ok"
    # Outdated results for a different Token cannot make the current Token green.
    _set(db, supply_mail.TOKEN_KEY, "replacement-token")
    db.commit()
    assert health.snapshot(db)["status"] == "untested"
    record = db.scalar(select(Setting.value).where(Setting.key == health.HEALTH_KEY))
    assert "legacy-token" not in record


def test_background_tick_updates_status_without_page_requests(SessionLocal, monkeypatch, mailbox):
    monkeypatch.setattr(health, "SessionLocal", SessionLocal)
    monkeypatch.setattr(health.time, "time", lambda: 5000)
    with SessionLocal() as db:
        _set(db, supply_mail.TOKEN_KEY, "background-token")
        db.commit()
    mailbox.error = supply_mail.SupplyMailError("连接失败")
    health.tick()
    health.tick()
    with SessionLocal() as db:
        assert health.snapshot(db) == {"status": "error", "checked_at": 5000, "next_check_at": 8600}
    assert mailbox.calls == ["background-token"]


def test_unexpected_provider_failure_is_sanitized_and_persisted(client, mailbox):
    client.put("/api/external/mail/config", json={"token": "private-token"})
    mailbox.error = RuntimeError("private-token in a malformed response")
    failed = client.post("/api/external/mail/test")
    assert failed.status_code == 400 and "private-token" not in failed.text
    assert client.get("/api/external/mail/config").json()["health"]["status"] == "error"
    assert mailbox.closed == 1


@pytest.mark.parametrize("record", ["broken", "[]", json.dumps({"token_hash": "other", "status": "ok"})])
def test_bad_or_unrelated_health_records_remain_neutral(db, record):
    _set(db, supply_mail.TOKEN_KEY, "token")
    _set(db, health.HEALTH_KEY, record)
    db.commit()
    assert health.snapshot(db)["status"] == "untested"


def test_monitor_start_is_idempotent_and_stop_joins_worker(monkeypatch):
    called = threading.Event()
    monkeypatch.setattr(health, "tick", called.set)
    try:
        health.start()
        assert called.wait(2)
        thread = health._thread
        health.start()
        assert health._thread is thread
    finally:
        health.stop()
    assert not thread.is_alive()
