"""Exercise profile discovery, session switching and final stored identity together."""
import base64
import json
from types import SimpleNamespace

import pytest

from app.models.external_member import ExternalMember
from app.services import external_login, firefly
from app.services.account_profile import build_profile_snapshot

PERSON = "person@AdobeID"
ORG = "member@team.e"


def response(payload=None, status=200):
    return SimpleNamespace(status_code=status, headers={}, text="",
                           json=lambda: payload or {})


def link(name="Design Team", guid=ORG, status="active"):
    return {"entitlementAccountUserId": guid, "description": name, "status": status}


class ProfileClient:
    def __init__(self, links, *, personal=True, reason=1000, profile_status=200):
        self.links = links
        self.fps = [{"userId": PERSON, "description": "Personal Account"}] if personal else []
        self.reason = reason
        self.profile_status = profile_status
        self.selected = None
        self.switches = []
        self.cookies = {}
        self.session = SimpleNamespace(cookies=self.cookies)
        self.mapping_status = 200
        self.wrong_identity = False
        self.fail_personal = False
        self.accounts_status = 200

    def get(self, url, **kwargs):
        if "filtered_profiles" in url:
            return response({"filteredProfiles": self.fps})
        if "/accounts/me" in url:
            return response({"profileData": {"links": self.links}}, self.accounts_status)
        if url == firefly.ABP_PROFILE_URL:
            return response({"commerce_profile": {"subscriptions": [
                {"owner_id": self.selected, "status": "ACTIVE"}]}})
        raise AssertionError(url)

    def put(self, url, **kwargs):
        assert "filterprofilemapping" in url
        self.selected = kwargs["json"]["guid"]
        self.switches.append(self.selected)
        return response(status=403 if self.fail_personal and self.selected == PERSON
                        else self.mapping_status)

    def post(self, url, **kwargs):
        if "/signin/v1/ims/tokens" in url:
            return response({"token": "susi.session.token"})
        if "/check/v6/token" in url:
            # The exchange must use the newly established cookie session.
            assert self.cookies["profile"] == self.selected
            return response({"access_token": "token:" + self.selected,
                             "userId": "stale@team.e" if self.wrong_identity else self.selected,
                             "account_type": "type1" if self.selected == PERSON else "type2e",
                             "ownerOrg": "" if self.selected == PERSON else "team@AdobeOrg"})
        if url == firefly.IMS_VALIDATE_URL:
            return response({"valid": True})
        if url == firefly.ACCESS_PROFILE_URL:
            payload = base64.urlsafe_b64encode(json.dumps({
                "profileStatusReason": 1000 if self.selected == PERSON else self.reason,
            }).encode()).decode()
            return response({"asnp": {"payload": payload}}, self.profile_status)
        raise AssertionError(url)

    def close(self):
        pass


def auth_for(client):
    def from_susi_token(_):
        client.cookies["profile"] = client.selected

    return SimpleNamespace(client=client, client_id="test", susi_token="verified.session.token",
                           headers=lambda: {}, from_susi_token=from_susi_token,
                           authorize=lambda *args: None, auth_state_encrypted="",
                           identity_verification_token="")


def finish(client, *, separate_auth=False, profile_preference=""):
    auth = auth_for(client)
    a2 = auth_for(client) if separate_auth else auth
    logs = []
    token = firefly._finish_firefly_token(auth, a2, "test@example.com", logs.append, lambda r: None,
                                         profile_preference=profile_preference)
    snapshot = build_profile_snapshot(auth._firefly_context, auth._enterprise_account_id)
    return token, snapshot, logs


def test_all_del_orgs_use_personal_and_preserve_orgs_for_display():
    client = ProfileClient([link("DEL-First"), link("DEL-Second", "other@team.e")])
    # Personal is not necessarily the first entry Adobe returns.
    client.fps.insert(0, {"userId": ORG, "description": "DEL-First"})
    token, snapshot, logs = finish(client)
    assert client.switches == [PERSON]
    assert token == "token:" + PERSON
    assert snapshot["current_kind"] == "personal"
    assert snapshot["credits_account_id"] == PERSON
    assert snapshot["current_org_id"] == ""
    assert len(snapshot["profiles"]) == 3
    assert all(p["status"] == "suspected_deleted" for p in snapshot["profiles"] if p["kind"] == "organization")
    assert any("跳过 2 个" in line for line in logs)


def test_explicit_personal_ignores_healthy_org_but_lists_it():
    client = ProfileClient([link()])
    _, snapshot, logs = finish(client, profile_preference="personal")
    assert client.switches == [PERSON]
    assert snapshot["current_kind"] == "personal"
    assert any(p["profile_id"] == ORG for p in snapshot["profiles"])
    assert any("按指定设置使用个人配置" in line for line in logs)


@pytest.mark.parametrize("disabled", [True, False])
def test_explicit_personal_does_not_silently_use_org_if_missing_or_disabled(disabled):
    client = ProfileClient([link()], personal=disabled)
    if disabled:
        client.fps[0]["disabled"] = True
    with pytest.raises(firefly._adm.AdminError, match="指定的个人配置不可用"):
        finish(client, profile_preference="personal")
    assert client.switches == []


@pytest.mark.parametrize("separate_auth", [False, True])
@pytest.mark.parametrize("reason", [2000, "2000"])
def test_expired_org_rebuilds_session_for_personal(reason, separate_auth):
    client = ProfileClient([link()], reason=reason)
    token, snapshot, logs = finish(client, separate_auth=separate_auth)
    assert client.switches == [ORG, PERSON]
    assert token == "token:" + PERSON
    assert client.cookies["profile"] == PERSON
    assert snapshot["current_profile_id"] == snapshot["credits_account_id"] == PERSON
    assert snapshot["subscription_owners"] == [{"owner_id": PERSON, "status": "ACTIVE"}]
    assert next(p for p in snapshot["profiles"] if p["profile_id"] == ORG)["status"] == "expired"
    assert any("回退到个人配置" in line for line in logs)


@pytest.mark.parametrize("reason,status", [(1000, 200), (None, 200), (2000, 503), (1003, 200)])
def test_valid_or_unconfirmed_org_is_not_replaced(reason, status):
    client = ProfileClient([link()], reason=reason, profile_status=status)
    token, snapshot, _ = finish(client)
    assert client.switches == [ORG]
    assert snapshot["current_kind"] == "organization"
    assert snapshot["credits_account_id"] == ORG


def test_active_org_wins_over_deleted_and_disabled_orgs():
    client = ProfileClient([link("DEL-Old", "old@team.e"), link("Disabled", "off@team.e"), link()])
    client.fps.append({"userId": "off@team.e", "disabled": True})
    _, snapshot, _ = finish(client)
    assert client.switches == [ORG]
    assert next(p for p in snapshot["profiles"] if p["profile_id"] == "off@team.e")["status"] == "disabled"


def test_no_orgs_keeps_personal_with_organization_subscription(monkeypatch):
    client = ProfileClient([])
    original_get = client.get

    def get(url, **kwargs):
        if url == firefly.ABP_PROFILE_URL:
            return response({"commerce_profile": {"subscriptions": [{"owner_id": "plan@AdobeOrg", "status": "ACTIVE"}]}})
        return original_get(url, **kwargs)

    monkeypatch.setattr(client, "get", get)
    _, snapshot, _ = finish(client)
    assert client.switches == [PERSON]
    assert snapshot["current_kind"] == "personal"
    assert snapshot["subscription_owners"][0]["owner_id"] == "plan@AdobeOrg"


def test_missing_org_metadata_uses_personal_but_marks_list_incomplete():
    client = ProfileClient([link()])
    client.accounts_status = 503
    _, snapshot, _ = finish(client)
    assert client.switches == [PERSON]
    assert snapshot["profiles_complete"] is False


def test_expired_org_without_personal_preserves_expired_status():
    client = ProfileClient([link()], personal=False, reason=2000)
    _, snapshot, _ = finish(client)
    assert client.switches == [ORG]
    assert snapshot["profiles"][0]["status"] == "expired"


def test_disabled_personal_is_not_used_as_fallback():
    client = ProfileClient([link()], reason=2000)
    client.fps[0]["disabled"] = True
    finish(client)
    assert client.switches == [ORG]


def test_all_deleted_without_personal_fails_without_switching():
    client = ProfileClient([link("Old Deleted")], personal=False)
    with pytest.raises(firefly._adm.AdminError, match="未找到可用"):
        finish(client)
    assert client.switches == []


@pytest.mark.parametrize("failure", ["mapping", "identity", "fallback"])
def test_failed_switch_never_publishes_selected_identity(failure):
    client = ProfileClient([link()], reason=2000)
    client.mapping_status = 403 if failure == "mapping" else 200
    client.wrong_identity = failure == "identity"
    client.fail_personal = failure == "fallback"
    auth = auth_for(client)
    with pytest.raises(firefly._adm.AdminError, match="配置切换"):
        firefly._finish_firefly_token(auth, auth, "test@example.com", lambda _: None, lambda r: None)
    assert not hasattr(auth, "_firefly_context")
    assert not hasattr(auth, "_enterprise_account_id")


@pytest.mark.parametrize("reason,preference,expected", [(2000, "organization", PERSON),
                                                     (1000, "organization", ORG), (1000, "personal", PERSON),
                                                     (2000, "", PERSON), (1000, "", ORG)])
def test_register_and_store_keep_cookie_token_profile_and_zero_credits_together(
        db, SessionLocal, monkeypatch, reason, preference, expected):
    client = ProfileClient([link()], reason=reason)
    auth = auth_for(client)
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *args, **kwargs: auth)
    monkeypatch.setattr(firefly, "make_otp_poller", lambda **kwargs: (
        lambda *args, **kwargs: "123456", SimpleNamespace(rotated=False)))
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *args: [])
    monkeypatch.setattr(firefly._adm, "_passwordless_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", lambda *args, **kwargs: "")
    monkeypatch.setattr(firefly._adm, "_session_cookie_str", lambda c: "profile=" + c.cookies["profile"])
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *args, **kwargs: {})

    def credits(token, account_id, *args, session, **kwargs):
        assert account_id == session.cookies["profile"] == expected
        assert token == "token:" + expected
        return {"available": 0, "total": 4000}

    monkeypatch.setattr(firefly, "fetch_credits_detail", credits)
    record = firefly.register_account(email="test@example.com", refresh_token="mail", client_id="mail-client",
                                      profile_preference=preference)
    member = ExternalMember(email="test@example.com")
    db.add(member)
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    external_login._save_success(member.id, record, True)
    db.refresh(member)
    assert member.cookie == "profile=" + expected
    assert member.access_token == "token:" + expected
    assert member.account_profile["current_profile_id"] == expected
    assert member.account_profile["credits_account_id"] == expected
    assert member.credits_available == 0
    assert member.credits_total == 4000
    assert client.switches == ([PERSON] if preference == "personal" else [ORG, PERSON] if reason == 2000 else [ORG])
