"""Notes persist independently of login results and imported credentials."""
import pytest
from sqlalchemy import create_engine, text

from app.crud.external_member import import_lines
from app.models.external_member import ExternalMember
from app.services import external_login
from app.services.job_manager import JOBS


def test_edit_and_clear_note_without_changing_login_state(client, db, monkeypatch):
    member = ExternalMember(email="note@example.com", cookie="existing-cookie", access_token="existing-token",
                            credits_available=4000, login_status="ok", profile_preference="personal")
    db.add(member); db.commit()
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: pytest.fail("Saving a note must not start login"))
    for note in ('多行备注\n<b>按原文显示</b> & "内容"', '更新后的备注', ''):
        response = client.patch(f"/api/external/members/{member.id}/note", json={"note": note})
        assert response.status_code == 200 and response.json()["note"] == note
        db.refresh(member)
        assert member.note == note
        assert member.cookie == "existing-cookie" and member.access_token == "existing-token"
        assert member.credits_available == 4000 and member.profile_preference == "personal"
        assert member.login_status == "ok"
        row = client.get('/api/external/members').json()['items'][0]
        assert row['note'] == note and 'cookie' not in row and 'access_token' not in row


@pytest.mark.parametrize("payload", [{"note": "字" * 1001}, {"note": None}, {}])
def test_invalid_note_does_not_overwrite_saved_text(client, db, payload):
    member = ExternalMember(email="validation@example.com", note="保留备注")
    db.add(member); db.commit()
    assert client.patch(f"/api/external/members/{member.id}/note", json=payload).status_code == 422
    db.refresh(member)
    assert member.note == "保留备注"


def test_note_length_boundary_and_missing_account(client, db):
    member = ExternalMember(email="boundary@example.com")
    db.add(member); db.commit()
    assert client.patch(f"/api/external/members/{member.id}/note", json={"note": "字" * 1000}).status_code == 200
    assert client.patch('/api/external/members/99999/note', json={"note": "内容"}).status_code == 404


def test_import_and_relogin_preserve_note(db, SessionLocal, monkeypatch):
    member = ExternalMember(email="keep@example.com", note="需要保留的备注")
    db.add(member); db.commit()
    content = "keep@example.com----p----11111111-2222-3333-4444-555555555555----M." + "t" * 60
    assert import_lines(db, content, on_duplicate="overwrite")["updated"] == 1
    db.refresh(member)
    assert member.note == "需要保留的备注"
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login.firefly, "register_account", lambda **kw: {"cookie": "new=1", "credits": 10, "credits_total": 10})
    assert external_login.login_and_store(member.id)["ok"]
    db.refresh(member)
    assert member.note == "需要保留的备注" and member.credits_total == 10


def test_note_migration_keeps_existing_data_and_is_repeatable(tmp_path, monkeypatch):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT, cookie TEXT)'))
        conn.execute(text("INSERT INTO external_members VALUES (1, 'keep@example.com', 'cookie=keep')"))
    monkeypatch.setattr(init_db, "engine", engine)
    init_db._run_migrations()
    with engine.begin() as conn:
        assert tuple(conn.execute(text('SELECT email,cookie,note FROM external_members')).one()) == ('keep@example.com', 'cookie=keep', '')
        conn.execute(text("UPDATE external_members SET note='已填写备注'"))
    init_db._run_migrations()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT note FROM external_members')).scalar_one() == '已填写备注'
    engine.dispose()
