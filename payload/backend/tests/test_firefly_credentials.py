"""验证码已轮换令牌或补全已设置密码后,后续失败也必须保留新凭据。"""

from types import SimpleNamespace

import pytest

from app.models.external_member import ExternalMember
from app.services import external_login, firefly


@pytest.mark.parametrize("otp_fails", [False, True])
def test_register_persists_credentials_before_later_failure(db, SessionLocal, monkeypatch, otp_fails):
    member = ExternalMember(email="credentials@ex.com", client_id="cid",
                            refresh_token="M.old", adobe_password="Imported1!")
    db.add(member)
    db.commit()
    monkeypatch.setattr(external_login, "SessionLocal", SessionLocal)
    client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(firefly._p, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(firefly, "AdminAuth", lambda *args, **kwargs: SimpleNamespace(
        authorize=lambda *args: None, susi_token="", client=client,
    ))
    monkeypatch.setattr(firefly._adm, "_probe_auth_methods", lambda *args: [])
    holder = SimpleNamespace(rotated=False, refresh_token="M.old")

    def poll(*args, **kwargs):
        holder.refresh_token = "M.new"
        holder.rotated = True
        if otp_fails:
            raise firefly._adm.AdminError("未收到验证码")
        return "123456"

    monkeypatch.setattr(firefly, "make_otp_poller", lambda **kwargs: (poll, holder))

    def otp_login(auth, email, log, *, poll, **kwargs):
        poll(email)
        auth.susi_token = "verified-session"

    monkeypatch.setattr(firefly._adm, "_passwordless_login", otp_login)
    monkeypatch.setattr(firefly._adm, "complete_sub_account", lambda *args, **kwargs: "Generated2!")

    def fail_exchange(*args, **kwargs):
        raise firefly._adm.AdminError("token exchange failed")

    monkeypatch.setattr(firefly, "_acquire_firefly_token", fail_exchange)
    result = external_login.login_and_store(member.id)
    assert result["ok"] is False
    db.refresh(member)
    assert member.refresh_token == "M.new"
    assert member.adobe_password == ("Imported1!" if otp_fails else "Generated2!")
