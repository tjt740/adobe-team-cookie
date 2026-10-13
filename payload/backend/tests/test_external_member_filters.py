from datetime import datetime

import pytest

from app.models.external_member import ExternalMember
from app.services import external_sub2_stock
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
