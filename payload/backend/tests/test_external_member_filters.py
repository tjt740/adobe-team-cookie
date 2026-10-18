from datetime import datetime

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2, external_sub2_stock
from app.services.job_manager import JOBS


@pytest.fixture
def members(db, monkeypatch):
    # Shanghai Oct 12 is [Oct 11 16:00 UTC, Oct 12 16:00 UTC).
    timestamps = ["2026-10-11T15:59:59.999999", "2026-10-11T16:00:00",
                  "2026-10-12T15:59:59.999999", "2026-10-12T16:00:00",
                  "2026-10-12T00:00:00", "2026-10-12T00:00:00"]
    rows = [ExternalMember(email=f"filter{i}@example.test", cookie=f"cookie={i}",
                           created_at=datetime.fromisoformat(timestamp),
                           login_status="ok" if i != 5 else "never", subscription_ok=True)
            for i, timestamp in enumerate(timestamps)]
    db.add_all(rows)
    db.commit()
    monkeypatch.setattr(external_sub2_stock, "membership", lambda db: {
        "ok": True, "configured": True,
        "items": {row.id: {"in_stock": i == 4} for i, row in enumerate(rows)},
    })
    return rows


FILTERS = dict(in_stock=False, imported_from="2026-10-12T00:00:00+08:00",
               imported_before="2026-10-13T00:00:00+08:00", login_status="ok",
               subscription_ok=True, keyword="filter")


def test_filters_apply_before_pagination_and_share_export_scope(client, members):
    for page, row in [(1, members[2]), (2, members[1])]:
        response = client.get("/api/external/members", params=dict(FILTERS, page=page, size=1))
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert [item["id"] for item in response.json()["items"]] == [row.id]
    response = client.get("/api/external/members/export", params=FILTERS)
    assert response.status_code == 200
    assert response.json() == [{"cookie": members[2].cookie}, {"cookie": members[1].cookie}]
    response = client.get("/api/external/members", params=dict(FILTERS, in_stock=True))
    assert [item["id"] for item in response.json()["items"]] == [members[4].id]


def test_bulk_login_uses_same_stock_and_date_scope(client, members, monkeypatch):
    started = []

    class Job:
        def to_dict(self):
            return dict(id=999, type="external_login", status="running", target=2,
                        success=0, fail=0, logs=[])

    def start(kind, worker, *, meta):
        started.extend(meta["member_ids"])
        return Job()

    monkeypatch.setattr(JOBS, "start", start)
    response = client.post("/api/external/members/batch-login-filter", json=FILTERS)
    assert response.status_code == 200
    assert response.json()["queued"] == response.json()["total"] == 2
    assert set(started) == {members[1].id, members[2].id}


def test_open_date_ranges_and_empty_inventory_matches(client, members):
    for params, total in [({"imported_before": FILTERS["imported_from"]}, 1),
                          ({"imported_from": FILTERS["imported_before"]}, 1),
                          (dict(FILTERS, keyword="missing"), 0)]:
        response = client.get("/api/external/members", params=params)
        assert response.status_code == 200
        assert response.json()["total"] == total


@pytest.mark.parametrize("configured", [True, False])
def test_unavailable_stock_cannot_be_treated_as_absent(client, members, monkeypatch, configured):
    monkeypatch.setattr(external_sub2_stock, "membership", lambda db: {
        "ok": False, "configured": configured, "items": {}, "message": "库存暂不可用",
    })
    for path in ("/api/external/members", "/api/external/members/export"):
        response = client.get(path, params={"in_stock": False})
        assert response.status_code == 503
        assert response.json()["detail"] == "库存暂不可用"
        assert client.get(path).status_code == 200
    assert client.post("/api/external/members/batch-login-filter", json={"in_stock": False}).status_code == 503


@pytest.mark.parametrize("end", ["2026-10-11T00:00:00Z", "2026-10-11T16:00:00Z"])
def test_invalid_ranges_are_rejected_for_all_scopes(client, end):
    filters = dict(imported_from=FILTERS["imported_from"], imported_before=end)
    for path in ("/api/external/members", "/api/external/members/export"):
        assert client.get(path, params=filters).status_code == 422
    assert client.post("/api/external/members/batch-login-filter", json=filters).status_code == 422


@pytest.fixture
def attribute_members(db, monkeypatch):
    profiles = ["personal", "organization", "organization", "organization", "personal", "unknown", None, "", "organization"]
    available = [0, 3999, 4000, 4000.5, 5000, None, None, 25, 4000]
    totals = [4000, 4000, 5000, 6000, 6000, None, 4000, None, 4000]
    mail = [{}, {"otp_mode": "manual"}, {"client_id": "partial"},
            {"client_id": "client", "refresh_token": "token"}, {"mail_url": "https://mail.example.test"},
            {}, {"refresh_token": "partial"}, {"otp_mode": "manual"}, {}]
    rows = [ExternalMember(
        email=f"attributes{i}@example.test", cookie=f"cookie={i}", login_status="ok", subscription_ok=True,
        created_at=datetime(2026, 10, 12), credits_available=available[i], credits_total=totals[i],
        account_profile=({"fetched_at": "2026-10-12T00:00:00Z", **({"current_kind": kind} if kind else {})}
                         if kind is not None else None),
        profile_preference="personal" if kind == "organization" else "organization", **mail[i],
    ) for i, kind in enumerate(profiles)]
    db.add_all(rows)
    db.commit()
    monkeypatch.setattr(external_sub2_stock, "membership", lambda db: {
        "ok": True, "configured": True,
        "items": {row.id: {"in_stock": i in (2, 4, 8)} for i, row in enumerate(rows)},
    })
    return rows


@pytest.mark.parametrize("filters, indexes", [
    ({"credits_min": 0, "credits_max": 0}, [0]),
    ({"credits_min": 4000, "credits_max": 4000.5}, [2, 3, 8]),
    ({"credits_max": 25}, [0, 7]),
    ({"credits_min": 4000.5}, [3, 4]),
    ({"credits_field": "total", "credits_min": 4000, "credits_max": 4000}, [0, 1, 6, 8]),
    ({"current_profile": "personal"}, [0, 4]),
    ({"current_profile": "organization"}, [1, 2, 3, 8]),
    ({"current_profile": "unknown"}, [5, 6, 7]),
    ({"is_company": True}, [0, 2, 5, 6, 8]),
    ({"is_company": False}, [1, 3, 4, 7]),
    (dict(FILTERS, in_stock=True, keyword="attributes", credits_min=4000, credits_max=4000,
          current_profile="organization", is_company=True), [2, 8]),
    ({"credits_min": 9000, "is_company": False}, []),
])
def test_attribute_filters_share_pagination_export_and_login_scope(client, attribute_members, monkeypatch, filters, indexes):
    expected = [attribute_members[i] for i in reversed(indexes)]
    # Filtering happens before LIMIT/OFFSET and totals count all matches.
    for page in range(1, max(1, len(expected)) + 1):
        response = client.get("/api/external/members", params=dict(filters, page=page, size=1))
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(expected)
        assert [row["id"] for row in response.json()["items"]] == [row.id for row in expected[page - 1:page]]
        if "is_company" in filters:
            assert all(row["uses_supply_mail"] == filters["is_company"] for row in response.json()["items"])
    response = client.get("/api/external/members/export", params=filters)
    assert response.status_code == 200
    assert response.json() == [{"cookie": row.cookie} for row in expected]
    started = []

    class Job:
        def to_dict(self):
            return dict(id=999, type="external_login", status="running", target=len(expected),
                        success=0, fail=0, logs=[])

    def start(kind, worker, *, meta):
        started.extend(meta["member_ids"])
        return Job()

    monkeypatch.setattr(JOBS, "start", start)
    response = client.post("/api/external/members/batch-login-filter", json=filters)
    assert response.status_code == 200, response.text
    assert response.json()["queued"] == response.json()["total"] == len(expected)
    assert started == [row.id for row in expected]


@pytest.mark.parametrize("filters", [
    {"credits_min": 100, "credits_max": 99}, {"credits_min": -1}, {"credits_max": -1},
    {"credits_min": "nan"}, {"credits_max": "inf"}, {"credits_min": "invalid"},
    {"credits_field": "invalid"}, {"current_profile": "invalid"}, {"is_company": "invalid"},
    {"sub2_status": "invalid"},
])
def test_invalid_attribute_filters_are_rejected_for_all_scopes(client, monkeypatch, filters):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid filters must not start a login job")

    monkeypatch.setattr(JOBS, "start", unexpected)
    for path in ("/api/external/members", "/api/external/members/export"):
        assert client.get(path, params=filters).status_code == 422
    assert client.post("/api/external/members/batch-login-filter", json=filters).status_code == 422


@pytest.fixture
def sync_members(db, monkeypatch):
    config = {"base_url": "http://localhost:18081/"}
    target = external_sub2.destination(config)
    monkeypatch.setattr(external_sub2, "config", lambda db: config)
    # Current target, old target, and unlinked accounts must stay distinct.
    links = [{target: {"status": state}} for state in ("pending", "pending", "syncing", "synced", "failed")]
    links += [None, {}, {target: {}}, {"https://old.example.test/api/v1": {"status": "pending"}},
              {target: {"status": "synced"}, "https://old.example.test/api/v1": {"status": "pending"}}]
    rows = [ExternalMember(email=f"sync{i}@example.test", cookie=f"sync-cookie={i}", sub2_links=link,
                           login_status="ok", subscription_ok=True, credits_available=i * 100,
                           created_at=datetime(2026, 10, 12)) for i, link in enumerate(links)]
    db.add_all(rows)
    db.commit()
    monkeypatch.setattr(external_sub2_stock, "membership", lambda db: {
        "ok": True, "items": {row.id: {"in_stock": i == 1} for i, row in enumerate(rows)},
    })
    return rows, config


@pytest.mark.parametrize("filters,indexes", [
    ({"sub2_status": "pending"}, [1, 0]),
    ({"sub2_status": "syncing"}, [2]),
    ({"sub2_status": "synced"}, [9, 3]),
    ({"sub2_status": "failed"}, [4]),
    ({"sub2_status": "not_pushed"}, [8, 7, 6, 5]),
    (dict(FILTERS, keyword="sync", sub2_status="pending"), [0]),
    ({"sub2_status": "pending", "credits_min": 100, "in_stock": True}, [1]),
    ({"sub2_status": "pending", "credits_min": 200}, []),
])
def test_sync_filter_scopes(client, sync_members, monkeypatch, filters, indexes):
    rows, _ = sync_members
    expected = [rows[i] for i in indexes]
    for page in range(1, len(expected) + 2):
        response = client.get("/api/external/members", params=dict(filters, page=page, size=1))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == len(expected)
        assert [row["id"] for row in result["items"]] == [row.id for row in expected[page - 1:page]]
        assert all(row["sub2_status"] == filters["sub2_status"] for row in result["items"])
    response = client.get("/api/external/members/export", params=filters)
    assert response.status_code == 200, response.text
    assert response.json() == [{"cookie": row.cookie} for row in expected]
    started = []

    class Job:
        def to_dict(self):
            return dict(id=999, type="external_login", status="running", target=len(expected),
                        success=0, fail=0, logs=[])

    def start(kind, worker, *, meta):
        started.extend(meta["member_ids"])
        return Job()

    monkeypatch.setattr(JOBS, "start", start)
    response = client.post("/api/external/members/batch-login-filter", json=filters)
    assert response.status_code == 200, response.text
    assert response.json()["queued"] == response.json()["total"] == len(expected)
    assert started == [row.id for row in expected]


def test_sync_filter_uses_current_target_and_latest_local_status(client, db, sync_members, monkeypatch):
    rows, config = sync_members

    def unavailable(*args, **kwargs):
        pytest.fail("Filtering local sync status must not depend on remote stock availability")

    monkeypatch.setattr(external_sub2_stock, "membership", unavailable)

    def pending_ids():
        response = client.get("/api/external/members", params={"sub2_status": "pending"})
        assert response.status_code == 200, response.text
        return [row["id"] for row in response.json()["items"]]

    assert pending_ids() == [rows[1].id, rows[0].id]
    target = external_sub2.destination(config)
    rows[1].sub2_links = {target: {"status": "synced"}}
    db.commit()
    assert pending_ids() == [rows[0].id]
    config["base_url"] = "https://old.example.test"
    assert pending_ids() == [rows[9].id, rows[8].id]
    config["base_url"] = ""
    assert pending_ids() == []
    response = client.get("/api/external/members", params={"sub2_status": "not_pushed"})
    assert response.status_code == 200
    assert response.json()["total"] == len(rows)
