from app.models.external_member import ExternalMember
from app.services.job_manager import JOBS


class _FakeJob:
    id = 999
    def to_dict(self, **kw):
        return {"id": 999, "type": "external_login", "status": "running", "target": 1,
                "success": 0, "fail": 0, "logs": []}


def test_import_and_list(client, db, monkeypatch):
    # 拦截 JOBS.start:导入会自动开批量登录任务,测试里不真的去登录(避免网络)
    started = {}
    def _fake_start(job_type, worker, meta=None):
        started["type"] = job_type
        started["ids"] = (meta or {}).get("member_ids")
        return _FakeJob()
    monkeypatch.setattr(JOBS, "start", _fake_start)

    r = client.post("/api/external/members/import", json={
        "content": "a@ex.com----p----11111111-2222-3333-4444-555555555555----M.tok1111111111111111111111111111111111111111111111111111111111",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 1
    assert body.get("job_id") == 999           # 导入后自动开了登录任务
    assert started.get("type") == "external_login" and len(started.get("ids") or []) == 1
    r2 = client.get("/api/external/members")
    lst = r2.json()
    assert lst["total"] == 1 and lst["items"][0]["email"] == "a@ex.com"
    assert lst["items"][0]["operator"] == "tester"
    assert lst["items"][0]["created_at"]


def test_list_filter_by_status(client, db):
    db.add(ExternalMember(email="ok@ex.com", login_status="ok", subscription_ok=True))
    db.add(ExternalMember(email="bad@ex.com", login_status="login_failed"))
    db.commit()
    r = client.get("/api/external/members", params={"login_status": "ok"})
    assert r.json()["total"] == 1


def test_export(client, db):
    db.add(ExternalMember(email="c@ex.com", cookie="k=v", login_status="ok"))
    db.commit()
    r = client.get("/api/external/members/export")
    assert r.status_code == 200
    assert r.json() == [{"cookie": "k=v"}]


def test_batch_delete(client, db):
    db.add(ExternalMember(email="d@ex.com"))
    db.commit()
    mid = db.query(ExternalMember).first().id
    r = client.request("DELETE", "/api/external/members/batch-delete", json={"ids": [mid]})
    assert r.status_code == 200 and r.json()["success"] is True


def test_single_member_can_relogin_as_background_job(client, db, monkeypatch):
    from app.services import external_login

    member = ExternalMember(email="retry@ex.com", login_status="login_failed")
    db.add(member)
    db.commit()
    started = {}

    def start(job_type, worker, *, meta):
        started.update(type=job_type, worker=worker, meta=meta)
        return _FakeJob()

    monkeypatch.setattr(JOBS, "start", start)
    response = client.post("/api/external/members/batch-login", json={"ids": [member.id]})
    assert response.status_code == 200
    assert response.json()["id"] == 999
    assert started == {
        "type": "external_login", "worker": external_login.batch_login_worker,
        "meta": {"member_ids": [member.id], "target": 1, "operator": "tester",
                 "member_emails": {str(member.id): member.email}},
    }
    db.refresh(member)
    assert member.operator == "tester"


def _record_job(jid, ids, *, state="done", actor="operator", job_type="external_login"):
    from app.services.job_manager import Job

    job = Job(jid, job_type, {"member_ids": ids, "target": len(ids), "operator": actor},
              persist_cb=JOBS._persist_job)
    job.status = state
    job.logs = ["test log"]
    job.persist()
    return job


def test_member_history_includes_persisted_old_jobs_and_excludes_deleted(client, db):
    member = ExternalMember(email="history@ex.com")
    db.add(member)
    db.commit()
    _record_job(1, [member.id], actor="alice")
    _record_job(2, [member.id], actor="bob")
    _record_job(3, [member.id], job_type="other")
    for jid in range(4, 40):
        _record_job(jid, [member.id + 1])
    JOBS.delete_many([2])
    listing = client.get("/api/external/members").json()["items"][0]
    assert listing["latest_job"]["id"] == 1
    assert listing["latest_job"]["operator"] == "alice"
    assert listing["latest_job"]["logs"] == []
    assert listing["latest_job"]["log_total"] == 1
    history = client.get(f"/api/external/members/{member.id}/jobs").json()
    assert [j["id"] for j in history] == [1]
    assert "meta" not in history[0]
    detail = client.get("/api/adobe-accounts/jobs/1").json()
    assert detail["logs"] == ["test log"] and detail["operator"] == "alice"
    assert client.get("/api/external/members/999/jobs").status_code == 404


def test_running_login_is_reused_and_overlapping_batch_rejected(client, db, monkeypatch):
    members = [ExternalMember(email=f"running{i}@ex.com", operator="alice") for i in range(2)]
    db.add_all(members)
    db.commit()
    _record_job(1, [members[0].id], state="running", actor="alice")

    def unexpected(*args, **kwargs):
        raise AssertionError("Must not launch duplicate login")

    monkeypatch.setattr(JOBS, "start", unexpected)
    res = client.post("/api/external/members/batch-login", json={"ids": [members[0].id], "operator": "forged"})
    assert res.status_code == 200 and res.json()["id"] == 1
    assert res.json()["operator"] == "alice"
    res = client.post("/api/external/members/batch-login", json={"ids": [m.id for m in members]})
    assert res.status_code == 409
    db.refresh(members[0])
    assert members[0].operator == "alice"


def test_import_overwrite_preserves_import_time_and_reuses_running_job(client, db, monkeypatch):
    from datetime import datetime

    member = ExternalMember(email="overwrite@ex.com", operator="alice", created_at=datetime(2025, 1, 2))
    db.add(member)
    db.commit()
    _record_job(1, [member.id], state="running", actor="alice")

    def unexpected(*args, **kwargs):
        raise AssertionError("Must not launch duplicate import login")

    monkeypatch.setattr(JOBS, "start", unexpected)
    res = client.post("/api/external/members/import", json={
        "content": "overwrite@ex.com----p----11111111-2222-3333-4444-555555555555----M.tok1111111111111111111111111111111111111111111111111111111111",
        "on_duplicate": "overwrite", "operator": "forged",
    })
    assert res.status_code == 200 and res.json()["job_ids"] == [1]
    db.refresh(member)
    assert member.created_at == datetime(2025, 1, 2)
    assert member.operator == "tester"


def test_task_actions_update_inline_history(client, db):
    member = ExternalMember(email="actions@ex.com")
    db.add(member)
    db.commit()
    _record_job(1, [member.id], state="running")
    assert client.post("/api/adobe-accounts/jobs/batch-delete", json={"ids": [1]}).json()["success"] is False
    assert client.post("/api/adobe-accounts/jobs/1/cancel").json()["success"] is True
    assert client.post("/api/adobe-accounts/jobs/1/clear-logs").json()["success"] is True
    history = client.get(f"/api/external/members/{member.id}/jobs").json()
    assert history[0]["status"] == "cancelled" and history[0]["log_total"] == 0
    assert client.post("/api/adobe-accounts/jobs/batch-delete", json={"ids": [1]}).json()["success"] is True
    assert client.get(f"/api/external/members/{member.id}/jobs").json() == []


def test_reused_account_id_does_not_inherit_another_emails_tasks(client, db):
    from datetime import datetime

    member = ExternalMember(email="new-owner@ex.com", created_at=datetime(2026, 1, 1))
    db.add(member)
    db.commit()
    old = _record_job(1, [member.id])
    old.meta["member_emails"] = {str(member.id): "old-owner@ex.com"}
    old.persist()
    legacy = _record_job(2, [member.id])
    legacy.created_at = 1  # A legacy task predating the replacement account.
    legacy.persist()
    assert client.get(f"/api/external/members/{member.id}/jobs").json() == []
    assert client.get("/api/external/members").json()["items"][0]["latest_job"] is None


def test_legacy_single_login_failure_is_visible_in_error_logs(client, db, monkeypatch):
    from app.services import external_login, log_store

    member = ExternalMember(email="legacy@ex.com")
    db.add(member)
    db.commit()
    log_store.STORE.clear()

    def fail(member_id, *, log):
        log("✗ 登录失败:factor_unavailable")
        return {"ok": False, "code": "login_failed", "message": "factor_unavailable"}

    monkeypatch.setattr(external_login, "login_and_store", fail)
    response = client.post(f"/api/external/members/{member.id}/login")
    assert response.status_code == 200 and response.json()["ok"] is False
    logs = client.get("/api/logs", params={"level": "ERROR", "keyword": "external_login"}).json()
    assert any("factor_unavailable" in row["message"] for row in logs["items"])
