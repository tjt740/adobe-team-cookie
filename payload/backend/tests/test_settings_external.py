from app.crud import setting as crud
from app.schemas.setting import SettingsUpdate


def test_external_defaults(db):
    s = crud.get_settings(db)
    assert s.external_api_key == ""


def test_external_update_roundtrip(db):
    crud.update_settings(db, SettingsUpdate(external_api_key="secret-key"))
    s = crud.get_settings(db)
    assert s.external_api_key == "secret-key"


def test_captcha_settings_roundtrip(db):
    s = crud.get_settings(db)
    assert s.captcha_provider == "" and s.captcha_key == ""
    crud.update_settings(db, SettingsUpdate(captcha_provider="2captcha", captcha_key="abc"))
    s = crud.get_settings(db)
    assert s.captcha_provider == "2captcha" and s.captcha_key == "abc"
    crud.update_settings(db, SettingsUpdate(captcha_provider="yescaptcha", captcha_key="yes-key"))
    s = crud.get_settings(db)
    assert s.captcha_provider == "yescaptcha" and s.captcha_key == "yes-key"
