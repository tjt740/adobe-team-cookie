"""Independent Supply credentials and email routing, separate from Sub2 identities."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import threading
import time
import uuid

from sqlalchemy import select

from app.crud.setting import _set
from app.db.session import SessionLocal
from app.models.setting import Setting
from app.services import supply_mail

DEFAULT_ID = "default"
ENTRY_PREFIX = "supply_mail_token_entry:"
BINDING_PREFIX = "supply_mail_binding:"
LOCK = threading.RLock()
MATCH_TIMEOUT = 45


class TokenConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TokenEntry:
    id: str
    name: str
    token: str = field(repr=False)
    enabled: bool = True

    @property
    def fingerprint(self):
        return hashlib.sha256(self.token.encode()).hexdigest()


def _json(value):
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def entries(db, *, active_only=False):
    stored = {row.key[len(ENTRY_PREFIX):]: _json(row.value) for row in db.scalars(
        select(Setting).where(Setting.key.startswith(ENTRY_PREFIX)).order_by(Setting.id))}
    meta = stored.pop(DEFAULT_ID, {})
    result = [TokenEntry(DEFAULT_ID, meta.get("name") or "默认 Token", supply_mail.get_token(db),
                         meta.get("enabled", True) is True)]
    result.extend(TokenEntry(key, value.get("name") or "Supply Token", value.get("token") or "",
                             value.get("enabled", True) is True)
                  for key, value in stored.items() if re.fullmatch(r"[a-f0-9]{32}", key))
    return [item for item in result if item.enabled and item.token] if active_only else result


def entry(db, token_id=DEFAULT_ID):
    return next((item for item in entries(db) if item.id == token_id), None)


def save(db, token_id, values, *, create=False):
    """Caller holds LOCK and commits token and health together."""
    current = entry(db, token_id)
    if create:
        token_id = uuid.uuid4().hex
        current = TokenEntry(token_id, "Supply Token", "")
    if current is None:
        raise TokenConfigError("Token 配置不存在，请刷新后重试")
    raw = values.get("token")
    token = re.sub(r"^Bearer\s+", "", (raw or "").strip(), flags=re.I) if raw is not None else current.token
    if not token and not values.get("clear_token") and not create:
        token = current.token  # Keep the legacy empty-string update behavior.
    if values.get("clear_token"):
        token = ""
    if create and not token:
        raise TokenConfigError("请先填写 supply.ink Token")
    if token and (len(token) > 512 or not re.fullmatch(r"[A-Za-z0-9._\-]+", token)):
        raise TokenConfigError("Token 格式无效，请粘贴 Token 裸串")
    if token and any(item.id != token_id and item.token == token for item in entries(db)):
        raise TokenConfigError("该 Token 已存在，请编辑已有配置")
    name = str(values.get("name") if values.get("name") is not None else current.name).strip()
    if len(name) > 80:
        raise TokenConfigError("名称最多 80 个字符")
    enabled = values.get("enabled") if values.get("enabled") is not None else current.enabled
    updated = TokenEntry(token_id, name or current.name, token, bool(enabled))
    record = {"name": updated.name, "enabled": updated.enabled}
    if token_id == DEFAULT_ID:
        _set(db, supply_mail.TOKEN_KEY, token)
    else:
        record["token"] = token
    _set(db, ENTRY_PREFIX + token_id, json.dumps(record, ensure_ascii=False))
    return updated, current.token != token or current.enabled != updated.enabled


def remove(db, token_id):
    if token_id == DEFAULT_ID:
        raise TokenConfigError("默认 Token 请使用清除操作")
    row = db.scalar(select(Setting).where(Setting.key == ENTRY_PREFIX + token_id))
    if not row:
        raise TokenConfigError("Token 配置不存在，请刷新后重试")
    db.delete(row)


def configured(db):
    return bool(entries(db, active_only=True))


def _binding_key(email):
    return BINDING_PREFIX + hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _pool_hash(tokens):
    return hashlib.sha256(json.dumps([(item.id, item.fingerprint) for item in tokens]).encode()).hexdigest()


def available(db, email, tokens=None):
    tokens = entries(db, active_only=True) if tokens is None else tokens
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0].id == DEFAULT_ID:
        return True
    binding = _json(db.scalar(select(Setting.value).where(Setting.key == _binding_key(email))))
    # Unknown mailboxes may be matched on their first login. A confirmed miss is
    # briefly excluded from automatic recovery; new credentials invalidate it.
    return not (binding.get("status") == "missing" and binding.get("pool_hash") == _pool_hash(tokens)
                and binding.get("expires_at", 0) > time.time())


class MailRouting:
    def __init__(self, tokens, email, preferred="", *, session_factory=None):
        self.tokens = tuple(tokens)
        self.email = email.strip().lower()
        self.preferred = preferred
        self.session_factory = session_factory or SessionLocal
        self.pinned = None

    def _remember(self, selected=None):
        try:
            with LOCK, self.session_factory() as db:
                current = entries(db, active_only=True)
                if selected and not any(item.id == selected.id and item.fingerprint == selected.fingerprint for item in current):
                    return
                if not selected and _pool_hash(current) != _pool_hash(self.tokens):
                    return
                record = ({"status": "matched", "token_id": selected.id, "token_hash": selected.fingerprint}
                          if selected else {"status": "missing", "pool_hash": _pool_hash(current),
                                            "expires_at": time.time() + 300})
                _set(db, _binding_key(self.email), json.dumps(record))
                db.commit()
        except Exception:
            pass  # A routing-cache write must never invalidate a successful login.

    def mailbox(self):
        return RoutedMailbox(self)


def routing(db, email, *, session_factory=None):
    tokens = entries(db, active_only=True)
    if len(tokens) == 1 and tokens[0].id == DEFAULT_ID:
        return None  # The existing default-only login keeps its original path.
    binding = _json(db.scalar(select(Setting.value).where(Setting.key == _binding_key(email))))
    preferred = next((item.id for item in tokens if item.id == binding.get("token_id")
                      and item.fingerprint == binding.get("token_hash")), "")
    return MailRouting(tokens, email, preferred, session_factory=session_factory)


def mailbox(db, email, *, session_factory=None):
    route = routing(db, email, session_factory=session_factory)
    return route.mailbox() if route is not None else supply_mail.SupplyMailbox(supply_mail.get_token(db))


class RoutedMailbox:
    def __init__(self, route):
        self.route = route
        self.bound = None

    def prepare(self):
        if self.bound is not None:
            return
        if not self.route.tokens:
            raise supply_mail.SupplyMailError("请先保存并启用 supply.ink Token")
        candidates = ([self.route.pinned] if self.route.pinned else
                      sorted(self.route.tokens, key=lambda item: item.id != self.route.preferred))
        deadline = time.monotonic() + MATCH_TIMEOUT
        uncertain = False
        for item in candidates:
            if time.monotonic() >= deadline:
                uncertain = True
                break
            client = supply_mail.SupplyMailbox(item.token)
            client.deadline = min(deadline, time.monotonic() + 12)
            try:
                client._account_id(self.route.email)  # Exact email match within this Token's account library.
            except supply_mail.SupplyAccountNotFound:
                client.close()
                continue
            except supply_mail.SupplyMailError:
                client.close()
                uncertain = True
                continue
            except Exception:
                client.close()
                uncertain = True
                continue
            client.deadline = None
            self.bound = client
            self.route.pinned = item
            self.route._remember(item)
            return
        if not uncertain and self.route.pinned is None:
            self.route._remember()
        raise supply_mail.SupplyMailError("暂时无法匹配该邮箱的 Supply Token，请稍后重试" if uncertain else
                                          "该邮箱未匹配到可取信的 Supply Token，请检查账号库")

    def messages(self, email, **kwargs):
        if email.strip().lower() != self.route.email:
            raise supply_mail.SupplyMailError("取信邮箱与本轮登录账号不一致")
        self.prepare()
        return self.bound.messages(email, **kwargs)

    def close(self):
        if self.bound is not None:
            self.bound.close()
            self.bound = None
