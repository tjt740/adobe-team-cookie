"""Saved login choice is independent of the last successful Adobe session."""
import pytest
from sqlalchemy import create_engine, text

from app.models.external_member import ExternalMember
from app.services import external_login
from app.services.job_manager import Job, JOBS
from tests.test_route_external_member import _FakeJob, _record_job


def test_save_preference_preserves_current_session_and_survives_requery(client, db, monkeypatch):
    profile = {"current_kind": "personal", "current_profile_id": "p@AdobeID", "fetched_at": "2026-09-29T07:00:00Z"}
    member = ExternalMember(email="pref@example.com", cookie="private-cookie", access_token="private-token",
                            account_profile=profile, credits_total=4000, login_status="ok")
    db.add(member); db.commit()
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: pytest.fail("Saving a preference must not start login"))
    response = client.patch(f"/api/external/members/{member.id}/login-profile", json={"profile_preference": "personal"})
    assert response.status_code == 200
    assert response.json()["profile_preference"] == "personal"
    db.refresh(member)
    assert member.profile_preference == "personal"
    assert member.account_profile == profile
    assert member.cookie == "private-cookie" and member.access_token == "private-token"
    assert member.credits_total == 4000
    row = client.get("/api/external/members").json()["items"][0]
    assert row["profile_preference"] == "personal" and row["account_profile"]["current_kind"] == "personal"
    assert "private-cookie" not in str(row) and "private-token" not in str(row)


def test_reset_preference_restores_original_behavior_without_changing_session(client, db):
    member = ExternalMember(email="reset@example.com", profile_preference="personal",
                            cookie="existing-cookie", account_profile={"current_kind": "personal"})
    db.add(member); db.commit()
    response = client.patch(f"/api/external/members/{member.id}/login-profile", json={"profile_preference": ""})
    assert response.status_code == 200 and response.json()["profile_preference"] == ""
    db.refresh(member)
    assert member.profile_preference == "" and member.cookie == "existing-cookie"
    assert member.account_profile == {"current_kind": "personal"}


@pytest.mark.parametrize("value", ["auto", "DEL-", None])
def test_preference_validation_rejects_unknown_values(client, db, value):
    member = ExternalMember(email="invalid@example.com")
    db.add(member); db.commit()
    assert client.patch(f"/api/external/members/{member.id}/login-profile", json={"profile_preference": value}).status_code == 422
    db.refresh(member)
    assert member.profile_preference == ""


def test_missing_member_returns_404(client):
    assert client.patch('/api/external/members/999/login-profile', json={"profile_preference": "personal"}).status_code == 404


@pytest.mark.parametrize("count,preference", [(1, "personal"), (2, "organization"), (2, "")])
def test_batch_save_only_changes_selected_accounts_without_login(client, db, monkeypatch, count, preference):
    members = [ExternalMember(email=f"batch-{i}@example.com", profile_preference="personal" if i == 0 else "organization",
                              cookie=f"cookie-{i}", account_profile={"current_kind": "personal"}) for i in range(3)]
    db.add_all(members); db.commit()
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: pytest.fail("Saving preferences must not start login"))
    ids = [m.id for m in members[:count]]
    response = client.patch('/api/external/members/login-profile', json={"ids": ids + ids, "profile_preference": preference})
    assert response.status_code == 200 and response.json()["updated"] == count
    for i, member in enumerate(members):
        db.refresh(member)
        assert member.profile_preference == (preference if i < count else "organization")
        assert member.cookie == f"cookie-{i}" and member.account_profile == {"current_kind": "personal"}


@pytest.mark.parametrize("status", ["running", "pausing", "paused", "cancelling", "missing"])
def test_batch_save_does_not_partially_apply_on_conflict(client, db, status):
    members = [ExternalMember(email=f"conflict-{i}@example.com") for i in range(2)]
    db.add_all(members); db.commit()
    ids = [m.id for m in members]
    if status == "missing":
        ids.append(999)
    else:
        _record_job(1, [members[1].id], state=status)
    response = client.patch('/api/external/members/login-profile', json={"ids": ids, "profile_preference": "personal"})
    assert response.status_code == (404 if status == "missing" else 409)
    for member in members:
        db.refresh(member)
        assert member.profile_preference == ""


@pytest.mark.parametrize("payload", [{"ids": [], "profile_preference": "personal"},
                                     {"ids": [1], "profile_preference": "auto"}, {"ids": [1]}])
def test_batch_save_requires_accounts_and_explicit_valid_preference(client, payload):
    assert client.patch('/api/external/members/login-profile', json=payload).status_code == 422


@pytest.mark.parametrize("status", ["running", "pausing", "paused", "cancelling"])
def test_cannot_change_preference_during_unfinished_login(client, db, status):
    member = ExternalMember(email="busy@example.com")
    db.add(member); db.commit()
    _record_job(1, [member.id], state=status)
    assert client.patch(f"/api/external/members/{member.id}/login-profile", json={"profile_preference": "personal"}).status_code == 409
    db.refresh(member)
    assert member.profile_preference == ""


@pytest.mark.parametrize("preference", [{}, {"profile_preference": ""}])
def test_import_without_choice_keeps_original_behavior(client, db, monkeypatch, preference):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw['meta']) or _FakeJob())
    content = "default@example.com----p----11111111-2222-3333-4444-555555555555----M." + "t" * 60
    response = client.post('/api/external/members/import', json={"content": content, **preference})
    assert response.status_code == 200
    member = db.query(ExternalMember).one()
    assert member.profile_preference == ""
    assert snapshots[-1]["member_profile_preferences"] == {str(member.id): ""}


def test_import_preference_is_saved_before_first_automatic_login(client, db, monkeypatch):
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw['meta']) or _FakeJob())
    content = "pref@example.com----p----11111111-2222-3333-4444-555555555555----M." + "t" * 60
    response = client.post('/api/external/members/import', json={"content": content, "profile_preference": "personal"})
    assert response.status_code == 200
    member = db.query(ExternalMember).one()
    assert member.profile_preference == "personal"
    assert snapshots[-1]["member_profile_preferences"] == {str(member.id): "personal"}
    # Older API clients omit the field: overwriting credentials preserves it.
    client.post('/api/external/members/import', json={"content": content, "on_duplicate": "overwrite"})
    db.refresh(member)
    assert member.profile_preference == "personal"
    # Explicit overwrite applies the newly selected preference.
    client.post('/api/external/members/import', json={"content": content, "on_duplicate": "overwrite", "profile_preference": "organization"})
    db.refresh(member)
    assert member.profile_preference == "organization"


def test_batch_login_freezes_each_members_choice(client, db, monkeypatch, SessionLocal):
    members = [ExternalMember(email="personal@example.com", profile_preference="personal"),
               ExternalMember(email="org@example.com", profile_preference="organization"),
               ExternalMember(email="unset@example.com")]
    db.add_all(members); db.commit()
    snapshots = []
    monkeypatch.setattr(JOBS, "start", lambda *a, **kw: snapshots.append(kw["meta"]) or _FakeJob())
    response = client.post('/api/external/members/batch-login', json={"ids": [m.id for m in members]})
    assert response.status_code == 200
    expected = {str(m.id): m.profile_preference for m in members}
    assert snapshots[0]["member_profile_preferences"] == expected
    members[0].profile_preference = "organization"
    members[2].profile_preference = "personal"
    db.commit()
    calls = {}
    def login(mid, **kwargs):
        calls[str(mid)] = kwargs["profile_preference"]
        return {"ok": True}
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    monkeypatch.setattr(external_login, "login_and_store", login)
    job = Job(5, 'external_login', snapshots[0])
    external_login.batch_login_worker(job)
    assert calls == expected and job.success == 3


@pytest.mark.parametrize("override,expected", [(None, "personal"), ("organization", "organization"), ("", "")])
def test_saved_or_job_snapshot_preference_reaches_protocol(db, SessionLocal, monkeypatch, override, expected):
    member = ExternalMember(email="protocol@example.com", refresh_token="mail", client_id="client", profile_preference="personal")
    db.add(member); db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    calls = []
    def register(**kwargs):
        calls.append(kwargs["profile_preference"])
        return {"cookie": "fresh=1", "credits": 4000, "credits_total": 4000}
    monkeypatch.setattr(external_login.firefly, "register_account", register)
    assert external_login.login_and_store(member.id, profile_preference=override)["ok"]
    assert calls == [expected]
    db.refresh(member)
    assert member.profile_preference == "personal"


def test_migration_preserves_existing_accounts_and_saved_preference(tmp_path, monkeypatch):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.db'))
    with engine.begin() as c:
        c.execute(text('CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT)'))
        c.execute(text("INSERT INTO external_members VALUES (1, 'keep@example.com')"))
    monkeypatch.setattr(init_db, "engine", engine)
    init_db._run_migrations()
    with engine.begin() as c:
        assert c.execute(text('SELECT profile_preference FROM external_members')).scalar_one() == ''
        c.execute(text("UPDATE external_members SET profile_preference='personal'"))
    init_db._run_migrations()
    with engine.connect() as c:
        assert tuple(c.execute(text('SELECT email,profile_preference FROM external_members')).one()) == ('keep@example.com', 'personal')
    engine.dispose()
