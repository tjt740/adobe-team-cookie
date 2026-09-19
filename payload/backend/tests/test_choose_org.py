"""组织选择:已删组织要排到最后,但绝不能因此一个都选不出来。

组织被 Adobe 删掉之后不会从列表/企业资料链接里消失,status 也仍是 active,
死信号写在名字里("… Deleted") —— prune_dead_orgs.py 判死组织用的就是这个词。
"""

from app.services import adobe_admin as adm
from app.services.adobe_protocol.admin_member_protocol import (
    choose_org,
    looks_deleted_org,
)


# ---- looks_deleted_org ----

def test_looks_deleted_matches_name_fields():
    assert looks_deleted_org({"name": "Acme Team (Deleted)"}) is True
    assert looks_deleted_org({"description": "某某公司 已删除"}) is True
    assert looks_deleted_org("Foo Ltd Deleted") is True


def test_looks_deleted_matches_status_field():
    assert looks_deleted_org({"name": "Acme", "status": "DELETED"}) is True


def test_looks_deleted_ignores_live_org():
    assert looks_deleted_org({"name": "Acme Team", "status": "ACTIVE"}) is False
    assert looks_deleted_org("Acme Team") is False


def test_looks_deleted_does_not_match_unrelated_fields():
    """回归:不能对整个 JSON 做子串匹配。`deletedAt: null` 这类字段
    在活组织上也存在,整串匹配会把活的误判成死的。"""
    live = {"name": "Acme Team", "deletedAt": None, "isDeleted": False,
            "permissions": ["ORG_ADMIN"]}
    assert looks_deleted_org(live) is False


def test_looks_deleted_tolerates_junk():
    assert looks_deleted_org(None) is False
    assert looks_deleted_org(123) is False


# ---- choose_org ----

def _org(oid, name, admin=True, type_="TEAM"):
    o = {"id": oid, "name": name, "type": type_}
    if admin:
        o["roles"] = ["ORG_ADMIN"]
    return o


def test_choose_org_prefers_live_over_deleted():
    """死组织即便带 ORG_ADMIN 也不能赢过活组织 —— 这是本次改动的要点。"""
    orgs = [_org("dead1", "Acme Team Deleted"), _org("live1", "Acme Team")]
    assert choose_org(orgs)["id"] == "live1"


def test_choose_org_live_wins_even_when_listed_last():
    orgs = [_org("dead1", "A Deleted"), _org("dead2", "B Deleted"),
            _org("live1", "C")]
    assert choose_org(orgs)["id"] == "live1"


def test_choose_org_still_returns_when_all_deleted():
    """全是死组织时仍要选出一个:这里抛错会让整条链路断在「没有组织」上,
    比选中一个死组织更难排查。"""
    orgs = [_org("dead1", "A Deleted"), _org("dead2", "B Deleted")]
    assert choose_org(orgs)["id"] in {"dead1", "dead2"}


def test_choose_org_keeps_admin_preference_among_live():
    orgs = [_org("noadmin", "Acme", admin=False), _org("admin", "Beta")]
    assert choose_org(orgs)["id"] == "admin"


# ---- _select_org_profile 的排序 ----

class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class _Client:
    def __init__(self, links):
        self._links = links

    def get(self, url, headers=None, **kw):
        return _Resp(200, {"profileData": {"links": self._links}})

    def put(self, url, headers=None, json=None, **kw):
        return _Resp(200, {})

    def post(self, url, headers=None, json=None, **kw):
        return _Resp(200, {"token": "new.susi"})


class _Auth:
    def __init__(self, links):
        self.client = _Client(links)
        self.susi_token = "old.susi"

    def headers(self):
        return {}


def _pick(links):
    """跑一遍 _select_org_profile,返回它日志里说选了哪个企业资料。"""
    logs = []
    adm._select_org_profile(_Auth(links), logs.append)
    picked = [m for m in logs if m.startswith("选择企业资料:")]
    return (picked[0].split(":", 1)[1] if picked else ""), logs


def test_select_profile_skips_deleted_when_a_live_one_exists():
    links = [
        {"ident": "d1", "status": "active", "description": "Acme Team Deleted"},
        {"ident": "l1", "status": "active", "description": "Acme Team"},
    ]
    picked, logs = _pick(links)
    assert picked == "Acme Team"
    assert any("跳过 1 个已删组织" in m for m in logs)


def test_select_profile_falls_back_when_all_deleted():
    links = [
        {"ident": "d1", "status": "active", "description": "A Deleted"},
        {"ident": "d2", "status": "active", "description": "B Deleted"},
    ]
    picked, logs = _pick(links)
    assert picked == "A Deleted"  # 仍然选得出来
    assert any("全都看着已删" in m for m in logs)


def test_select_profile_keeps_original_order_among_live():
    """稳定排序:活的之间不许乱序,否则每次登录选中的组织会漂。"""
    links = [
        {"ident": "l1", "status": "active", "description": "First"},
        {"ident": "l2", "status": "active", "description": "Second"},
    ]
    picked, _ = _pick(links)
    assert picked == "First"


def test_select_profile_ignores_inactive_links():
    links = [
        {"ident": "x", "status": "inactive", "description": "Acme Team"},
        {"ident": "l1", "status": "active", "description": "Beta Team"},
    ]
    picked, _ = _pick(links)
    assert picked == "Beta Team"
