"""外部子号的 Adobe 密码:导入行第 5 段优先,没有则首登后存我们设的默认密码。

    邮箱----密码----ClientID----RefreshToken              → adobe_password 留空
    邮箱----密码----ClientID----RefreshToken----Adobe密码  → 第 5 段即 adobe_password
"""

from types import SimpleNamespace

import app.services.external_login as el
from app.crud import external_member as crud
from app.crud.email import _parse_email_line
from app.models.external_member import ExternalMember

CID = "3c5f8a1e-9b2d-4e7a-8c1f-6d0b9e3a2f11"
RT = "M." + "x" * 80


# ---- 解析 ----

def test_parse_four_fields_has_no_adobe_password():
    f = _parse_email_line(f"u@ex.com----mailpwd----{CID}----{RT}")
    assert f["password"] == "mailpwd"
    assert f["adobe_password"] == ""
    assert f["client_id"] == CID and f["refresh_token"] == RT


def test_parse_fifth_field_is_adobe_password():
    f = _parse_email_line(f"u@ex.com----mailpwd----{CID}----{RT}----AdobePwd1!")
    assert f["password"] == "mailpwd"
    assert f["adobe_password"] == "AdobePwd1!"
    assert f["client_id"] == CID and f["refresh_token"] == RT


def test_parse_fifth_field_with_pipe_separator():
    f = _parse_email_line(f"u@ex.com|mailpwd|{CID}|{RT}|AdobePwd1!")
    assert f["adobe_password"] == "AdobePwd1!"


# ---- 导入落库 ----

def test_import_stores_adobe_password(db):
    crud.import_lines(db, f"a@ex.com----mp----{CID}----{RT}----AdobePwd1!")
    row = crud.get_by_email(db, "a@ex.com")
    assert row.mail_password == "mp"
    assert row.adobe_password == "AdobePwd1!"


def test_import_without_fifth_leaves_adobe_password_empty(db):
    crud.import_lines(db, f"b@ex.com----mp----{CID}----{RT}")
    assert crud.get_by_email(db, "b@ex.com").adobe_password == ""


def test_import_overwrite_updates_adobe_password(db):
    crud.import_lines(db, f"c@ex.com----mp----{CID}----{RT}----Old1!")
    crud.import_lines(db, f"c@ex.com----mp----{CID}----{RT}----New2!",
                      on_duplicate="overwrite")
    assert crud.get_by_email(db, "c@ex.com").adobe_password == "New2!"


def test_import_without_fifth_does_not_wipe_existing(db):
    """已经存了密码的号,再用不带第 5 段的行覆盖导入,不能把密码抹掉。"""
    crud.import_lines(db, f"d@ex.com----mp----{CID}----{RT}----Keep1!")
    crud.import_lines(db, f"d@ex.com----mp----{CID}----{RT}",
                      on_duplicate="overwrite")
    assert crud.get_by_email(db, "d@ex.com").adobe_password == "Keep1!"


# ---- 首登自动写入 ----

def _seed(db, **kw):
    m = ExternalMember(email=kw.pop("email"), client_id="cid", refresh_token="M.tok")
    for k, v in kw.items():
        setattr(m, k, v)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _login(monkeypatch, SessionLocal, rec):
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings",
        lambda db: SimpleNamespace(proxy_enabled=False, proxy_url="", concurrency=1),
    )
    monkeypatch.setattr(el.firefly, "register_account", lambda **kw: rec)


_OK = {"access_token": "at", "cookie": "k=v", "credits": 3500.0,
       "credits_total": 4000.0, "expires_at": 1, "display_name": "", "user_id": ""}


def test_first_login_stores_the_password_we_set(db, monkeypatch, SessionLocal):
    """自己补全注册的号:把我们设的密码记下来。"""
    m = _seed(db, email="p1@ex.com")
    _login(monkeypatch, SessionLocal, dict(_OK, set_password="CHANGE_ME_PASSWORD"))
    assert el.login_and_store(m.id)["ok"] is True
    db.refresh(m)
    assert m.adobe_password == "CHANGE_ME_PASSWORD"


def test_first_login_does_not_overwrite_imported_password(db, monkeypatch, SessionLocal):
    """导入行给过密码的,不能被我们设的默认密码盖掉 —— 那才是这个号真正的密码。"""
    m = _seed(db, email="p2@ex.com", adobe_password="Imported9!")
    _login(monkeypatch, SessionLocal, dict(_OK, set_password="CHANGE_ME_PASSWORD"))
    assert el.login_and_store(m.id)["ok"] is True
    db.refresh(m)
    assert m.adobe_password == "Imported9!"


def test_login_of_already_complete_account_stores_nothing(db, monkeypatch, SessionLocal):
    """账号本来就已补全(密码不是我们设的)时 set_password 为空,不能瞎记一个。"""
    m = _seed(db, email="p3@ex.com")
    _login(monkeypatch, SessionLocal, dict(_OK, set_password=""))
    assert el.login_and_store(m.id)["ok"] is True
    db.refresh(m)
    assert m.adobe_password == ""


def test_login_tolerates_rec_without_set_password(db, monkeypatch, SessionLocal):
    """老路径/别的调用方没带这个 key 时不能炸。"""
    m = _seed(db, email="p4@ex.com")
    _login(monkeypatch, SessionLocal, dict(_OK))
    assert el.login_and_store(m.id)["ok"] is True
    db.refresh(m)
    assert m.adobe_password == ""


# ---- 共用解析器不能带崩邮箱池 ----

def test_email_pool_import_survives_extra_parser_field(db):
    """回归:_parse_email_line 多返回 adobe_password 之后,Email(**fields)
    会抛 'invalid keyword argument'。邮箱池导入必须只取自己有的列。"""
    from app.crud import email as email_crud

    res = email_crud.batch_import(db, f"pool@ex.com----mp----{CID}----{RT}----AdobePwd1!")
    assert res.created == 1 and res.failed == 0
    row = email_crud.get_by_email(db, "pool@ex.com")
    assert row is not None and row.password == "mp"
    assert not hasattr(row, "adobe_password")


# ---- 列表只回「有没有」,不回明文 ----

def test_list_reports_has_adobe_password_without_leaking_it(client, db):
    crud.import_lines(db, f"withpw@ex.com----mp----{CID}----{RT}----Secret9!")
    crud.import_lines(db, f"nopw@ex.com----mp----{CID}----{RT}")

    r = client.get("/api/external/members?size=50")
    assert r.status_code == 200
    rows = {x["email"]: x for x in r.json()["items"]}

    assert rows["withpw@ex.com"]["has_adobe_password"] is True
    assert rows["nopw@ex.com"]["has_adobe_password"] is False
    # 明文一个字都不能出现在响应里
    assert "Secret9!" not in r.text
    assert all("adobe_password" not in x for x in rows.values())


def test_blank_password_counts_as_missing(db):
    from app.api.routes.external_member import _to_out

    crud.import_lines(db, f"blank@ex.com----mp----{CID}----{RT}")
    row = crud.get_by_email(db, "blank@ex.com")
    row.adobe_password = "   "
    db.commit()
    assert _to_out(row).has_adobe_password is False
