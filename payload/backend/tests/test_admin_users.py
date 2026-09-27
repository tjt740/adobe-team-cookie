from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import create_engine, text

from app.api.deps import get_current_user
from app.api.routes.admin_user import _write
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models.user import User

PASSWORD = 'test-admin-password-123'


@pytest.fixture
def admins(client, db):
    app.dependency_overrides.pop(get_current_user)
    rows = [User(username=name, nickname='', hashed_password=hash_password(PASSWORD),
                 is_active=True, is_superuser=superuser) for name, superuser in
            [('owner', True), ('colleague', True), ('legacy-user', False)]]
    db.add_all(rows)
    db.commit()
    return [dict(id=u.id, headers={'Authorization': 'Bearer ' + create_access_token(u.id)}) for u in rows]


def test_create_list_login_and_edit(client, db, admins):
    headers = admins[0]['headers']
    response = client.post('/api/admin/users', headers=headers,
                           json={'username': 'new.admin', 'nickname': '同事', 'password': PASSWORD})
    assert response.status_code == 201, response.text
    created = response.json()
    assert created['is_superuser'] and created['is_active']
    assert set(created) == {'id', 'username', 'nickname', 'is_active', 'is_superuser', 'created_at'}
    row = db.get(User, created['id'])
    assert row.hashed_password != PASSWORD and verify_password(PASSWORD, row.hashed_password)
    assert client.post('/api/auth/login', json={'username': 'new.admin', 'password': PASSWORD}).status_code == 200
    listed = client.get('/api/admin/users', headers=headers)
    assert len(listed.json()) == 4 and PASSWORD not in listed.text and 'hashed_password' not in listed.text
    assert client.patch(f"/api/admin/users/{row.id}", headers=headers, json={'nickname': '新昵称'}).json()['nickname'] == '新昵称'
    assert client.post('/api/admin/users', headers=headers, json={'username': 'new.admin', 'password': PASSWORD}).status_code == 409


def test_only_superusers_can_manage_users(client, admins):
    for method, path, body in [('get', '/api/admin/users', None),
                              ('post', '/api/admin/users', {'username': 'rogue', 'password': PASSWORD}),
                              ('patch', f"/api/admin/users/{admins[0]['id']}", {'is_active': False}),
                              ('post', f"/api/admin/users/{admins[0]['id']}/reset-password", {'password': PASSWORD})]:
        kwargs = {} if body is None else {'json': body}
        assert getattr(client, method)(path, headers=admins[2]['headers'], **kwargs).status_code == 403
        assert getattr(client, method)(path, **kwargs).status_code == 401


def test_reset_password_revokes_only_target_sessions(client, admins):
    target = admins[1]
    response = client.post(f"/api/admin/users/{target['id']}/reset-password", headers=admins[0]['headers'],
                           json={'password': 'replacement-password-123'})
    assert response.status_code == 200
    assert client.get('/api/auth/me', headers=target['headers']).status_code == 401
    assert client.get('/api/auth/me', headers=admins[0]['headers']).status_code == 200
    assert client.post('/api/auth/login', json={'username': 'colleague', 'password': PASSWORD}).status_code == 401
    login = client.post('/api/auth/login', json={'username': 'colleague', 'password': 'replacement-password-123'})
    fresh = {'Authorization': 'Bearer ' + login.json()['token']['access_token']}
    assert client.get('/api/admin/users', headers=fresh).status_code == 200
    oauth = client.post('/api/auth/login/oauth', data={'username': 'colleague', 'password': 'replacement-password-123'})
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + oauth.json()['access_token']}).status_code == 200


def test_disable_enable_does_not_revive_old_sessions(client, admins):
    target = admins[1]
    path = f"/api/admin/users/{target['id']}"
    assert client.patch(path, headers=admins[0]['headers'], json={'is_active': False}).status_code == 200
    assert client.get('/api/auth/me', headers=target['headers']).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'colleague', 'password': PASSWORD}).status_code == 403
    assert client.post('/api/auth/login/oauth', data={'username': 'colleague', 'password': PASSWORD}).status_code == 403
    assert client.patch(path, headers=admins[0]['headers'], json={'is_active': True}).status_code == 200
    assert client.get('/api/auth/me', headers=target['headers']).status_code == 401
    login = client.post('/api/auth/login', json={'username': 'colleague', 'password': PASSWORD})
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + login.json()['token']['access_token']}).status_code == 200


def test_self_disable_reset_and_role_changes_are_blocked(client, admins):
    owner = admins[0]
    path = f"/api/admin/users/{owner['id']}"
    assert client.patch(path, headers=owner['headers'], json={'is_active': False}).status_code == 400
    assert client.post(path + '/reset-password', headers=owner['headers'], json={'password': PASSWORD}).status_code == 400
    assert client.patch(path, headers=owner['headers'], json={'is_superuser': False}).status_code == 422
    assert client.patch(path, headers=owner['headers'], json={'username': 'rename'}).status_code == 422
    assert client.delete(path, headers=owner['headers']).status_code == 405
    assert client.patch(f"/api/admin/users/{admins[1]['id']}", headers=owner['headers'], json={'is_active': False}).status_code == 200
    assert client.patch(path, headers=owner['headers'], json={'is_active': False}).status_code == 400
    assert client.get('/api/auth/me', headers=owner['headers']).status_code == 200


@pytest.mark.parametrize('extra', [
    {'password': 'short'}, {'password': '密' * 25}, {'password': {'private': 'invalid-secret'}},
    {'username': 'a b'}, {'nickname': 'n' * 51}, {'is_superuser': False},
])
def test_invalid_inputs_never_echo_secrets(client, admins, monkeypatch, extra):
    from app.services import log_store
    logged = []
    monkeypatch.setattr(log_store.STORE, 'add', lambda *a, **kw: logged.append((a, kw)))
    body = {'username': 'new-admin', 'password': PASSWORD, **extra}
    response = client.post('/api/admin/users', headers=admins[0]['headers'], json=body)
    assert response.status_code == 422
    assert str(body['password']) not in response.text and 'invalid-secret' not in response.text
    assert not logged


def test_stale_authenticated_actor_cannot_disable_last_admin(client, admins, SessionLocal):
    # Two admins authenticate before either mutation. Once A disables B, B's
    # previously authorized request must not disable A or reset A's password.
    with SessionLocal() as stale:
        actor = stale.get(User, admins[1]['id'])
        assert actor.is_active
        assert client.patch(f"/api/admin/users/{actor.id}", headers=admins[0]['headers'], json={'is_active': False}).status_code == 200
        with pytest.raises(HTTPException) as caught:
            with _write(stale, actor):
                pytest.fail('stale actor reached write')
        assert caught.value.status_code == 401


def test_legacy_tokens_work_until_revoked(client, admins):
    token = jwt.encode({'sub': str(admins[1]['id']), 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {'Authorization': 'Bearer ' + token}
    assert client.get('/api/auth/me', headers=headers).status_code == 200
    client.post(f"/api/admin/users/{admins[1]['id']}/reset-password", headers=admins[0]['headers'], json={'password': PASSWORD})
    assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_existing_users_migrate_without_changing_credentials(tmp_path, monkeypatch):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, hashed_password TEXT)'))
        conn.execute(text("INSERT INTO users VALUES (1, 'owner', 'existing-hash')"))
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations()
    init_db._run_migrations()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT username, hashed_password, token_version FROM users')).one() == ('owner', 'existing-hash', 0)
    engine.dispose()
