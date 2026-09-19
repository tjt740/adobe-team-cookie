import app.api.routes.external_cookie as ec
from app.crud import setting as setting_crud
from app.models.external_member import ExternalMember
from app.schemas.setting import SettingsUpdate

URL = "/api/v1/adobe/cookie/refresh"


def _set_key(db, key="secret"):
    setting_crud.update_settings(db, SettingsUpdate(external_api_key=key))


def test_wrong_key_401(client, db):
    _set_key(db)
    r = client.post(URL, json={"email": "a@ex.com"}, headers={"X-API-Key": "wrong"})
    assert r.status_code in (401, 403)


def test_non_ascii_key_401_not_500(client, db):
    """回归测试:非 ASCII 的 X-API-Key(如含中文/latin-1 高位字节)与配置的
    key 不一致时,应按 401 处理,不应因 hmac.compare_digest(str, str) 对
    非 ASCII 输入抛 TypeError 逃逸成 500。

    header value 用 bytes 传(而不是 str),模拟 Starlette 收到原始请求后
    对 header 按 latin-1 解码得到含非 ASCII 字符的 str——httpx 测试客户端
    对 str header 会先按 ascii 编码,如果直接传 "钥匙" 这种 str 会在客户端
    这一层就报 UnicodeEncodeError,测不到服务端的行为。
    """
    _set_key(db)
    r = client.post(URL, json={"email": "a@ex.com"},
                     headers={"X-API-Key": "钥匙".encode("utf-8")})
    assert r.status_code == 401
    r2 = client.post(URL, json={"email": "a@ex.com"},
                      headers={"X-API-Key": "keyÿ".encode("latin-1")})
    assert r2.status_code == 401


def test_missing_email_400(client, db):
    _set_key(db)
    r = client.post(URL, json={}, headers={"X-API-Key": "secret"})
    assert r.status_code == 400


def test_empty_email_400(client, db):
    _set_key(db)
    r = client.post(URL, json={"email": ""}, headers={"X-API-Key": "secret"})
    assert r.status_code == 400


def test_non_string_email_400(client, db):
    """回归测试:email 非字符串(如数字)不应抛 AttributeError 逃逸成 500,应按 400 处理。"""
    _set_key(db)
    r = client.post(URL, json={"email": 123}, headers={"X-API-Key": "secret"})
    assert r.status_code == 400


def test_invalid_json_400(client, db):
    _set_key(db)
    r = client.post(URL, data="not-json", headers={"X-API-Key": "secret", "Content-Type": "application/json"})
    assert r.status_code == 400


def test_unknown_email_200_ok_false(client, db):
    _set_key(db)
    r = client.post(URL, json={"email": "nope@ex.com"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["code"] == "account_disabled" and body["cookie"] == ""
    assert body["email"] == "nope@ex.com"


def test_success_200_ok_true(client, db, monkeypatch):
    _set_key(db)
    db.add(ExternalMember(email="u@ex.com", client_id="c", refresh_token="M.t"))
    db.commit()
    monkeypatch.setattr(ec.external_login, "login_and_store", lambda mid, **k: {
        "ok": True, "cookie": "k=v", "credits_available": 4000.0,
        "credits_total": 4000.0, "code": "", "message": "",
    })
    r = client.post(URL, json={"email": "U@EX.COM", "extra": "ignored"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["cookie"] == "k=v" and body["email"] == "U@EX.COM"


def test_login_failed_200_ok_false(client, db, monkeypatch):
    _set_key(db)
    db.add(ExternalMember(email="f@ex.com", client_id="c", refresh_token="M.t"))
    db.commit()
    monkeypatch.setattr(ec.external_login, "login_and_store", lambda mid, **k: {
        "ok": False, "cookie": "", "credits_available": None,
        "credits_total": None, "code": "login_failed", "message": "pw",
    })
    r = client.post(URL, json={"email": "f@ex.com"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "login_failed"
    assert body["email"] == "f@ex.com"


def test_login_raises_200_ok_false_internal(client, db, monkeypatch):
    """回归测试:login_and_store 之外抛出的异常(如落库 commit 失败)不应逃逸成 500,
    应兜底为 200 + ok=false + code=internal(契约里业务失败一律 200)。"""
    _set_key(db)
    db.add(ExternalMember(email="boom@ex.com", client_id="c", refresh_token="M.t"))
    db.commit()

    def _raise(mid, **k):
        raise RuntimeError("db commit exploded")

    monkeypatch.setattr(ec.external_login, "login_and_store", _raise)
    r = client.post(URL, json={"email": "boom@ex.com"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["code"] == "internal" and body["cookie"] == ""
    assert body["email"] == "boom@ex.com"
