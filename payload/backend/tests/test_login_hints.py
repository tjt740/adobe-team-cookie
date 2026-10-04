import json
from types import SimpleNamespace

import pytest

from app.core.security import create_access_token, hash_password
from app.crud.user import change_password
from app.models.user import User
from app.services import login_hints


@pytest.fixture
def hints(tmp_path, monkeypatch, engine):
    path = tmp_path / "login-hints.json"
    config = {"current_environment": "online", "public_on_loopback": False, "entries": [
        {"environment": "local", "label": "本地", "url": "http://127.0.0.1:18080", "username": "admin", "password": "Local9!"},
        {"environment": "online", "label": "线上", "url": "https://online.example.com", "username": "admin", "password": "Online9!"},
    ]}
    path.write_text(json.dumps(config))
    monkeypatch.setattr(login_hints, "HINTS_PATH", path)
    monkeypatch.setattr(login_hints, "engine", engine)
    return path, config


def user(db, *, superuser=True):
    row = User(username="admin", hashed_password=hash_password("Online9!"), is_superuser=superuser, is_active=True)
    db.add(row)
    db.commit()
    return row


def test_online_hints_are_private_and_never_cached(client, db, hints):
    assert client.get("/api/auth/login-hints").status_code == 401
    row = user(db)
    token = create_access_token(row.id, token_version=row.token_version)
    result = client.get("/api/auth/login-hints", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "private, no-store"
    assert [entry["password"] for entry in result.json()["entries"]] == ["Local9!", "Online9!"]
    row.token_version += 1
    db.commit()
    assert client.get("/api/auth/login-hints", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_non_admin_cannot_reveal_hints(client, db, hints):
    row = user(db, superuser=False)
    token = create_access_token(row.id)
    result = client.get("/api/auth/login-hints", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 403 and "Online9!" not in result.text


def test_local_login_page_requires_explicit_opt_in_and_loopback_host(hints):
    _, config = hints
    request = SimpleNamespace(url=SimpleNamespace(hostname="localhost"), client=SimpleNamespace(host="127.0.0.1"))
    assert not login_hints.public_local_request(request, config)
    config.update(current_environment="local", public_on_loopback=True)
    assert login_hints.public_local_request(request, config)
    request.client.host = "203.0.113.7"
    assert not login_hints.public_local_request(request, config)
    request.client.host = "127.0.0.1"
    request.url.hostname = "online.example.com"
    assert not login_hints.public_local_request(request, config)


def test_password_change_updates_current_hint_without_changing_other_environment(db, hints):
    path, _ = hints
    row = user(db)
    change_password(db, row, "Changed8!")
    config = login_hints.read_config()
    assert config["entries"][0]["password"] == "Local9!"
    assert config["entries"][1]["password"] == "Changed8!"
    assert path.stat().st_mode & 0o777 == 0o600
    assert login_hints.entries(db, config)[1]["password"] == "Changed8!"


def test_stale_hint_is_suppressed(db, hints):
    row = user(db)
    row.hashed_password = hash_password("Other8!")
    db.commit()
    entries = login_hints.entries(db, login_hints.read_config())
    assert entries[1]["password"] == "" and "已变更" in entries[1]["message"]


def test_missing_hints_does_not_create_plaintext_on_password_change(db, tmp_path, monkeypatch):
    path = tmp_path / "missing.json"
    monkeypatch.setattr(login_hints, "HINTS_PATH", path)
    change_password(db, user(db), "Changed8!")
    assert not path.exists()
