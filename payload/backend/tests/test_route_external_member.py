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
        "meta": {"member_ids": [member.id], "target": 1},
    }


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
