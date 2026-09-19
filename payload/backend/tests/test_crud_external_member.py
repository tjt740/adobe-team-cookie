from app.crud import external_member as crud
from app.models.external_member import ExternalMember


def test_import_lines_parses_four_segments(db):
    content = "user@ex.com----pass123----11111111-2222-3333-4444-555555555555----M.longrefreshtoken0000000000000000000000000000000000000000000000000000000000"
    res = crud.import_lines(db, content)
    assert res["created"] == 1
    m = crud.get_by_email(db, "USER@EX.COM")  # 不区分大小写
    assert m is not None
    assert m.mail_password == "pass123"
    assert m.client_id == "11111111-2222-3333-4444-555555555555"
    assert m.refresh_token.startswith("M.")


def test_import_skip_vs_overwrite(db):
    crud.import_lines(db, "a@ex.com----p1----11111111-2222-3333-4444-555555555555----M.tok11111111111111111111111111111111111111111111111111111111111111")
    res_skip = crud.import_lines(db, "a@ex.com----p2----11111111-2222-3333-4444-555555555555----M.tok11111111111111111111111111111111111111111111111111111111111111", on_duplicate="skip")
    assert res_skip["skipped"] == 1
    assert crud.get_by_email(db, "a@ex.com").mail_password == "p1"
    res_ow = crud.import_lines(db, "a@ex.com----p2----11111111-2222-3333-4444-555555555555----M.tok11111111111111111111111111111111111111111111111111111111111111", on_duplicate="overwrite")
    assert res_ow["updated"] == 1
    assert crud.get_by_email(db, "a@ex.com").mail_password == "p2"


def test_list_filters(db):
    db.add(ExternalMember(email="ok@ex.com", login_status="ok", subscription_ok=True))
    db.add(ExternalMember(email="bad@ex.com", login_status="login_failed", subscription_ok=False))
    db.commit()
    items, total = crud.list_members(db, login_status="ok")
    assert total == 1 and items[0].email == "ok@ex.com"
    items2, total2 = crud.list_members(db, subscription_ok=False)
    assert total2 == 1 and items2[0].email == "bad@ex.com"


def test_export_cookies_skips_empty(db):
    db.add(ExternalMember(email="c1@ex.com", cookie="k=v", login_status="ok", subscription_ok=True))
    db.add(ExternalMember(email="c2@ex.com", cookie="", login_status="ok"))
    db.commit()
    out = crud.export_cookies(db)
    assert out == [{"cookie": "k=v"}]


def test_delete_many(db):
    db.add(ExternalMember(email="d@ex.com"))
    db.commit()
    mid = crud.get_by_email(db, "d@ex.com").id
    assert crud.delete_many(db, [mid]) == 1
    assert crud.get(db, mid) is None


def test_import_intra_batch_duplicate_skip(db):
    """同一次 content 内出现重复邮箱(skip 模式):不应抛 IntegrityError,
    第二条重复行计入 skipped,落库数据保留第一行的内容。"""
    content = (
        "dup1@ex.com----pass1----11111111-2222-3333-4444-555555555555----M.tok11111111111111111111111111111111111111111111111111111111111111\n"
        "dup1@ex.com----pass2----11111111-2222-3333-4444-555555555555----M.tok22222222222222222222222222222222222222222222222222222222222222"
    )
    res = crud.import_lines(db, content)
    assert res["created"] == 1
    assert res["skipped"] == 1
    assert res["updated"] == 0
    assert res["failed"] == 0
    m = crud.get_by_email(db, "dup1@ex.com")
    assert m is not None
    assert m.mail_password == "pass1"  # 保留第一行,第二行被跳过


def test_import_intra_batch_duplicate_overwrite(db):
    """同一次 content 内出现重复邮箱(overwrite 模式):不应抛 IntegrityError,
    第二条重复行计入 updated,落库数据是第二行(最后一次)的内容。"""
    content = (
        "dup2@ex.com----passA----11111111-2222-3333-4444-555555555555----M.tok33333333333333333333333333333333333333333333333333333333333333\n"
        "dup2@ex.com----passB----11111111-2222-3333-4444-555555555555----M.tok44444444444444444444444444444444444444444444444444444444444444"
    )
    res = crud.import_lines(db, content, on_duplicate="overwrite")
    assert res["created"] == 1
    assert res["updated"] == 1
    assert res["skipped"] == 0
    assert res["failed"] == 0
    m = crud.get_by_email(db, "dup2@ex.com")
    assert m is not None
    assert m.mail_password == "passB"  # 保留最后一行


def test_import_intra_batch_duplicate_does_not_rollback_valid_rows(db):
    """一批内既有不相关的合法行,也有重复邮箱行:重复行不应导致整批回滚,
    不相关的合法行必须正常落库。"""
    content = (
        "uniq@ex.com----passU----11111111-2222-3333-4444-555555555555----M.tok55555555555555555555555555555555555555555555555555555555555555\n"
        "dup3@ex.com----passC----11111111-2222-3333-4444-555555555555----M.tok66666666666666666666666666666666666666666666666666666666666666\n"
        "dup3@ex.com----passD----11111111-2222-3333-4444-555555555555----M.tok77777777777777777777777777777777777777777777777777777777777777"
    )
    res = crud.import_lines(db, content)  # 默认 skip
    assert res["failed"] == 0
    assert res["created"] == 2  # uniq@ex.com + dup3@ex.com(第一次出现)
    assert res["skipped"] == 1  # dup3@ex.com 第二次出现
    assert crud.get_by_email(db, "uniq@ex.com") is not None
    dup = crud.get_by_email(db, "dup3@ex.com")
    assert dup is not None
    assert dup.mail_password == "passC"
