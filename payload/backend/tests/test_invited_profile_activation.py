"""Organization-first login must accept invitations before using a personal fallback."""
import pytest

from app.models.external_member import ExternalMember
from app.services import external_login, firefly
from app.services.job_manager import JobCancelled
from tests.test_firefly_profile_selection import ORG, PERSON, ProfileClient, auth_for, finish, link, response


def invitation(name="NOvA LIMA", guid=ORG, **values):
    return {**link(name, guid, "invited"), "ident": "invite-" + guid, **values}


class InvitationClient(ProfileClient):
    def __init__(self, links, *, activation_status=200, becomes_active=True,
                 activation_error=None, personal=True, reason=1000):
        super().__init__(links, personal=personal, reason=reason)
        self.activation_status = activation_status
        self.becomes_active = becomes_active
        self.activation_error = activation_error
        self.activations = []
        self.needs_login = False
        self.reauthentications = []
        self.mapping_by_guid = {}

    def get(self, url, **kwargs):
        if self.needs_login:
            return response(status=401)
        return super().get(url, **kwargs)

    def put(self, url, **kwargs):
        if self.needs_login:
            return response(status=401)
        result = super().put(url, **kwargs)
        return response(status=self.mapping_by_guid.get(self.selected, result.status_code))

    def post(self, url, **kwargs):
        if "/signin/v2/links/" in url:
            assert kwargs["json"] == {"status": "active"}
            self.activations.append(url)
            if self.activation_error is not None and not isinstance(self.activation_error, TimeoutError):
                raise self.activation_error
            if 200 <= self.activation_status < 300:
                for item in self.links:
                    if url.endswith(item.get("ident", "__missing__")) and self.becomes_active:
                        item["status"] = "active"
                # Adobe may revoke the old session as soon as activation commits.
                self.needs_login = True
            if self.activation_error is not None:
                raise self.activation_error
            return response(status=self.activation_status)
        if "credential=password" in url:
            self.needs_login = False
            self.reauthentications.append("password")
            return response({"token": "new.password.session"})
        return super().post(url, **kwargs)


def register(monkeypatch, remote, *, preference="organization", password_only=False, completion=None):
    logs, saved, sessions = [], [], []
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kw: remote)

    def new_auth(*args, **kwargs):
        auth = auth_for(remote)
        auth.start_email_mfa = lambda email: True
        sessions.append(auth)
        return auth

    def code_login(auth, *args, **kwargs):
        remote.needs_login = False
        remote.reauthentications.append("code")
        auth.susi_token = "new.otp.session"

    monkeypatch.setattr(firefly, "AdminAuth", new_auth)
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *a: ["otp"])
    monkeypatch.setattr(firefly._adm, "_passwordless_login", lambda *a, **kw: None)
    monkeypatch.setattr(firefly._adm, "_browser_code_login", code_login)
    monkeypatch.setattr(firefly, "_try_password_session", lambda *a, **kw: True)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", completion or (lambda *a, **kw: pytest.fail(
        "Accepting a profile invitation must not complete account details or set a password")))
    monkeypatch.setattr(firefly._adm, "_session_cookie_str", lambda c: "profile=" + c.cookies["profile"])
    monkeypatch.setattr(firefly, "fetch_account_info", lambda *a, **kw: {})

    def credits(token, account_id, *args, session, **kwargs):
        assert account_id == session.cookies["profile"]
        assert token == "token:" + account_id
        return {"available": 0, "total": 4000}

    monkeypatch.setattr(firefly, "fetch_credits_detail", credits)
    record = firefly.register_account(
        email="invited@example.test", refresh_token="", client_id="",
        otp_poller=lambda *a, **kw: "123456", profile_preference=preference,
        adobe_password="Known1!" if password_only else "", password_only=password_only,
        log=logs.append, on_credentials=lambda **values: saved.append(values),
    )
    assert saved == [] and record["set_password"] == ""
    return record, logs, sessions


@pytest.mark.parametrize("password_only", [False, True])
@pytest.mark.parametrize("personal", [False, True])
def test_invitation_activates_reauthenticates_and_preserves_org_identity(monkeypatch, personal, password_only):
    remote = InvitationClient([invitation()], personal=personal)
    record, logs, sessions = register(monkeypatch, remote, password_only=password_only)
    assert len(remote.activations) == 1 and len(sessions) == 2
    assert remote.reauthentications == ["password" if password_only else "code"]
    assert remote.switches == [ORG]
    assert record["cookie"] == "profile=" + ORG and record["access_token"] == "token:" + ORG
    profile = record["account_profile"]
    assert profile["current_kind"] == "organization"
    assert profile["current_profile_id"] == profile["credits_account_id"] == ORG
    assert profile["requested_preference"] == "organization" and profile["fallback_reason"] == ""
    assert next(p for p in profile["profiles"] if p["profile_id"] == ORG)["status"] == "active"
    assert record["credits"] == 0 and not any("回退到个人" in line for line in logs)


@pytest.mark.parametrize("mode,expected", [("rejected", "HTTP 403"),
                                            ("unchanged", "提交激活后仍为 invited"),
                                            ("missing_ident", "缺少激活编号"),
                                            ("timeout", "未取得响应")])
def test_confirmed_unavailable_invitation_falls_back_once_with_reason(monkeypatch, mode, expected):
    remote = InvitationClient([invitation()], activation_status=403 if mode == "rejected" else 200,
                              becomes_active=False,
                              activation_error=TimeoutError("secret response") if mode == "timeout" else None)
    if mode == "missing_ident":
        remote.links[0].pop("ident")
    record, logs, _ = register(monkeypatch, remote)
    profile = record["account_profile"]
    assert profile["current_kind"] == "personal"
    assert "NOvA LIMA" in profile["fallback_reason"] and expected in profile["fallback_reason"]
    assert "secret" not in str(profile)
    assert remote.switches == [PERSON]
    assert len(remote.activations) == (0 if mode == "missing_ident" else 1)
    assert any(expected in line and "回退到个人" in line for line in logs)


def test_timeout_after_remote_commit_is_verified_without_replaying_activation(monkeypatch):
    remote = InvitationClient([invitation()], activation_error=TimeoutError("response lost"))
    record, _, _ = register(monkeypatch, remote)
    assert len(remote.activations) == 1 and remote.switches == [ORG]
    assert record["account_profile"]["fallback_reason"] == ""


@pytest.mark.parametrize("preference", ["", "personal"])
def test_other_preferences_do_not_activate_invitations(monkeypatch, preference):
    remote = InvitationClient([invitation()])
    record, _, _ = register(monkeypatch, remote, preference=preference)
    assert remote.activations == [] and remote.reauthentications == []
    assert record["account_profile"]["current_kind"] == "personal"


def test_deleted_disabled_and_inactive_orgs_are_explained_without_activation(monkeypatch):
    remote = InvitationClient([invitation("DEL-Old", "deleted.e"),
                               invitation("Disabled", "off.e"),
                               invitation("Inactive", "inactive.e", status="inactive")])
    remote.fps.append({"userId": "off.e", "disabled": True})
    record, _, _ = register(monkeypatch, remote)
    reason = record["account_profile"]["fallback_reason"]
    assert all(text in reason for text in ("疑似已删除", "已停用", "inactive"))
    assert remote.activations == [] and remote.switches == [PERSON]


def test_rejected_active_org_does_not_hide_another_invited_org(monkeypatch):
    remote = InvitationClient([link("Old Team", "old.e"), invitation()])
    remote.mapping_by_guid["old.e"] = 403
    record, _, _ = register(monkeypatch, remote)
    assert len(remote.activations) == 1
    assert remote.switches == ["old.e", ORG]
    assert record["account_profile"]["current_kind"] == "organization"
    assert record["account_profile"]["fallback_reason"] == ""


def test_active_org_is_used_without_activating_unneeded_invitations(monkeypatch):
    remote = InvitationClient([invitation(), link("Active Team", "active.e")])
    record, _, _ = register(monkeypatch, remote)
    assert remote.activations == [] and remote.switches == ["active.e"]
    assert record["account_profile"]["current_profile_id"] == "active.e"


def test_expired_org_records_reason_and_falls_back_to_verified_personal():
    remote = InvitationClient([link()], reason=2000)
    _, profile, logs = finish(remote, profile_preference="organization")
    assert remote.switches == [ORG, PERSON]
    assert "授权已过期" in profile["fallback_reason"] and "2000" in profile["fallback_reason"]
    assert profile["current_profile_id"] == profile["credits_account_id"] == PERSON
    assert any("2000" in line and "回退" in line for line in logs)


def test_unavailable_org_without_personal_never_publishes_an_expired_session():
    remote = InvitationClient([link()], personal=False, reason=2000)
    auth = auth_for(remote)
    with pytest.raises(firefly._adm.AdminError, match="没有可回退的个人配置"):
        firefly._finish_firefly_token(auth, auth, "test@example.test", lambda _: None,
                                     lambda r: None, profile_preference="organization")
    assert not hasattr(auth, "_firefly_context")


def test_failed_discovery_does_not_misreport_absence_of_organizations():
    remote = InvitationClient([invitation()])
    remote.accounts_status = 503
    with pytest.raises(firefly._adm.AdminError, match="读取组织配置失败.*503"):
        finish(remote, profile_preference="organization")
    assert remote.activations == [] and remote.switches == []


@pytest.mark.parametrize("status", [401, 408, 429, 503])
def test_transient_switch_error_does_not_silently_select_personal(status):
    remote = InvitationClient([link()])
    remote.mapping_by_guid[ORG] = status
    with pytest.raises(firefly._adm.AdminError, match=f"HTTP {status}"):
        finish(remote, profile_preference="organization")
    assert remote.switches == [ORG]


def test_multiple_invitations_are_each_attempted_only_once(monkeypatch):
    remote = InvitationClient([invitation("First Team", "first.e"), invitation()], becomes_active=False)
    record, _, _ = register(monkeypatch, remote)
    assert len(remote.activations) == len(set(remote.activations)) == 2
    assert remote.reauthentications == ["code", "code"]
    reason = record["account_profile"]["fallback_reason"]
    assert "First Team" in reason and "NOvA LIMA" in reason
    assert remote.switches == [PERSON]


def test_cancellation_during_activation_is_not_converted_to_personal_fallback(monkeypatch):
    remote = InvitationClient([invitation()], activation_error=JobCancelled())
    with pytest.raises(JobCancelled):
        register(monkeypatch, remote)
    assert len(remote.activations) == 1 and remote.switches == []


def test_original_login_route_cannot_replay_an_already_submitted_invitation(monkeypatch):
    remote = InvitationClient([invitation()], becomes_active=False)
    remote.fail_personal = True
    completions = []

    def complete(*args, **kwargs):
        completions.append(kwargs)
        assert kwargs['activate_profiles'] is False
        return ""

    with pytest.raises(firefly.LoginRoutesExhausted):
        register(monkeypatch, remote, completion=complete)
    assert len(completions) == len(remote.activations) == 1


def test_malformed_org_list_never_becomes_a_successful_personal_fallback(monkeypatch):
    remote = InvitationClient([invitation()])
    original_get = remote.get

    def get(url, **kwargs):
        if '/accounts/me' in url:
            return response({'profileData': {'links': {'not': 'a list'}}})
        return original_get(url, **kwargs)

    monkeypatch.setattr(remote, 'get', get)
    with pytest.raises(firefly._adm.AdminError, match='无法确认可用组织'):
        finish(remote, profile_preference='organization')
    assert remote.switches == []


def test_fallback_reason_persists_in_public_api_and_next_success_clears_it(
        db, client, SessionLocal, monkeypatch):
    member = ExternalMember(email="invited@example.test", profile_preference="organization")
    db.add(member)
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    record, _, _ = register(monkeypatch, InvitationClient([invitation()], activation_status=403))
    external_login._save_success(member.id, record, True)
    row = client.get("/api/external/members").json()["items"][0]
    assert row["account_profile"]["fallback_reason"] == record["account_profile"]["fallback_reason"]
    assert "HTTP 403" in row["account_profile"]["fallback_reason"]
    assert "token:" not in str(row) and "profile=" not in str(row)
    record, _, _ = register(monkeypatch, InvitationClient([invitation()]))
    external_login._save_success(member.id, record, True)
    profile = client.get("/api/external/members").json()["items"][0]["account_profile"]
    assert profile["current_kind"] == "organization" and profile["fallback_reason"] == ""
