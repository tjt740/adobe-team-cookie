"""Persist the latest Supply connection result and check saved tokens hourly."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.crud.setting import _set
from app.db.session import SessionLocal
from app.models.setting import Setting
from app.services import supply_mail, supply_mail_tokens as tokens

INTERVAL = 3600
HEALTH_KEY = "supply_mail_health"
LOCK = tokens.LOCK
_checks = {}
_stop = threading.Event()
_thread: threading.Thread | None = None


def _fingerprint(token):
    return hashlib.sha256(token.encode()).hexdigest()


def health_key(token_id=tokens.DEFAULT_ID):
    return HEALTH_KEY if token_id == tokens.DEFAULT_ID else HEALTH_KEY + ":" + token_id


def snapshot(db, token=None, *, token_id=tokens.DEFAULT_ID):
    if token is None:
        item = tokens.entry(db, token_id)
        token = item.token if item else ""
    empty = {"status": "untested", "checked_at": None, "next_check_at": None}
    if not token:
        return empty
    try:
        record = json.loads(db.scalar(select(Setting.value).where(Setting.key == health_key(token_id))) or "{}")
    except (TypeError, ValueError):
        return empty
    if not isinstance(record, dict) or record.get("token_hash") != _fingerprint(token):
        return empty
    if record.get("status") not in {"untested", "ok", "error"}:
        return empty
    for field in ("checked_at", "next_check_at"):
        if record.get(field) is not None and not isinstance(record[field], (int, float)):
            return empty
    return {key: record.get(key) for key in empty}


def reset(db, token, *, now=None, token_id=tokens.DEFAULT_ID):
    now = time.time() if now is None else now
    _set(db, health_key(token_id), json.dumps({
        "token_hash": _fingerprint(token), "status": "untested", "checked_at": None,
        "next_check_at": now + INTERVAL if token else None,
    }))


def check(db, *, force=True, now=None, token_id=tokens.DEFAULT_ID):
    with LOCK:
        guard = _checks.setdefault(token_id, threading.Lock())
    with guard:
        db.expire_all()
        item = tokens.entry(db, token_id)
        token = item.token if item else ""
        if not token or (not force and not item.enabled):
            if force:
                raise supply_mail.SupplyMailError("请先保存 supply.ink Token")
            return None
        started = time.time() if now is None else now
        health = snapshot(db, token, token_id=token_id)
        if not force and health["next_check_at"] and health["next_check_at"] > started:
            return None
        mailbox = supply_mail.SupplyMailbox(token)
        result, error = None, None
        try:
            result = mailbox.test()
            if not result.get("ok"):
                raise supply_mail.SupplyMailError("supply.ink 邮件连接测试失败")
        except supply_mail.SupplyMailError as exc:
            error = str(exc)
        except Exception:
            error = "supply.ink 邮件连接测试失败，请稍后重试"
        finally:
            mailbox.close()
        checked_at = time.time() if now is None else now
        with LOCK:
            db.expire_all()
            current = tokens.entry(db, token_id)
            if current is None or current.token != token or current.enabled != item.enabled:
                raise supply_mail.SupplyMailError("Token 配置已变更，请重新测试")
            _set(db, health_key(token_id), json.dumps({
                "token_hash": _fingerprint(token), "status": "error" if error else "ok",
                "checked_at": checked_at, "next_check_at": checked_at + INTERVAL,
            }))
            db.commit()
        if error:
            raise supply_mail.SupplyMailError(error)
        return dict(result, token_id=token_id, health=snapshot(db, token, token_id=token_id))


def tick():
    with SessionLocal() as db:
        ids = [item.id for item in tokens.entries(db, active_only=True)]
    def test_one(token_id):
        with SessionLocal() as db:
            try:
                check(db, force=False, token_id=token_id)
            except supply_mail.SupplyMailError:
                pass  # Each Token retains its own failure and next deadline.
    if ids:
        with ThreadPoolExecutor(max_workers=min(4, len(ids)), thread_name_prefix="supply-check") as executor:
            for future in [executor.submit(test_one, token_id) for token_id in ids]:
                try:
                    future.result()
                except Exception:
                    pass  # A database/provider failure for one Token cannot skip the others.


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()

    def loop():
        while not _stop.is_set():
            try:
                tick()
            except Exception:
                pass  # A transient database failure is retried on the next tick.
            _stop.wait(30)

    _thread = threading.Thread(target=loop, daemon=True, name="supply-mail-health")
    _thread.start()


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=15)
