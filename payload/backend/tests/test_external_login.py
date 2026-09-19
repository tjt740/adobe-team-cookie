from types import SimpleNamespace

import app.services.external_login as el
from app.models.external_member import ExternalMember
from app.services.job_manager import Job


def _seed(db, **kw):
    m = ExternalMember(email=kw.pop("email", "u@ex.com"),
                       client_id="cid", refresh_token="M.tok")
    for k, v in kw.items():
        setattr(m, k, v)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_login_success_stores_cookie(db, monkeypatch, SessionLocal):
    m = _seed(db)
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.proxy_pool, "random_proxy", lambda raw, exclude="": "")
    monkeypatch.setattr(el.firefly, "register_account", lambda **kw: {
        "access_token": "at", "cookie": "k=v", "credits": 3500.0,
        "credits_total": 4000.0, "expires_at": 111, "display_name": "n", "user_id": "u",
    })
    res = el.login_and_store(m.id)
    assert res["ok"] is True and res["cookie"] == "k=v"
    assert res["credits_total"] == 4000.0
    db.refresh(m)
    assert m.cookie == "k=v" and m.login_status == "ok"
    assert m.subscription_ok is True and m.first_login_done is True


def test_login_low_total_marks_unsubscribed(db, monkeypatch, SessionLocal):
    m = _seed(db, email="low@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.proxy_pool, "random_proxy", lambda raw, exclude="": "")
    monkeypatch.setattr(el.firefly, "register_account", lambda **kw: {
        "access_token": "at", "cookie": "k=v", "credits": 10.0,
        "credits_total": 10.0, "expires_at": 1, "display_name": "", "user_id": "",
    })
    res = el.login_and_store(m.id)
    assert res["ok"] is True
    db.refresh(m)
    assert m.subscription_ok is False


def test_login_failure_maps_code_keeps_cookie(db, monkeypatch, SessionLocal):
    m = _seed(db, email="f@ex.com", cookie="old=1")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.proxy_pool, "random_proxy", lambda raw, exclude="": "")
    def _boom(**kw):
        raise RuntimeError("password rejected")
    monkeypatch.setattr(el.firefly, "register_account", _boom)
    res = el.login_and_store(m.id)
    assert res["ok"] is False and res["code"] == "login_failed"
    db.refresh(m)
    assert m.cookie == "old=1"  # 不清空
    assert m.login_status == "login_failed"


def test_login_unknown_member(db, monkeypatch, SessionLocal):
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    res = el.login_and_store(999999)
    assert res["ok"] is False and res["code"] == "account_disabled"


def test_login_success_rotates_refresh_token(db, monkeypatch, SessionLocal):
    m = _seed(db, email="rot@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.proxy_pool, "random_proxy", lambda raw, exclude="": "")
    monkeypatch.setattr(el.firefly, "register_account", lambda **kw: {
        "access_token": "at", "cookie": "k=v", "credits": 3500.0,
        "credits_total": 4000.0, "expires_at": 111, "display_name": "n", "user_id": "u",
        "rotated_refresh_token": "M.newtok",
    })
    res = el.login_and_store(m.id)
    assert res["ok"] is True
    db.refresh(m)
    assert m.refresh_token == "M.newtok"


def test_classify_branches():
    assert el._classify("connection reset by proxy") == "rate_limited"
    assert el._classify("account disabled") == "account_disabled"
    assert el._classify("password rejected") == "login_failed"
    assert el._classify("something weird") == "internal"


def test_batch_login_worker_counts_success_and_fail(db, monkeypatch, SessionLocal):
    m1 = _seed(db, email="b1@ex.com")
    m2 = _seed(db, email="b2@ex.com")
    m3 = _seed(db, email="b3@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.setting_crud, "get_settings", lambda db: SimpleNamespace(concurrency=2))

    def _fake_login(mid, *, log=None):
        ok = mid != m2.id
        return {"ok": ok, "cookie": "k" if ok else "", "credits_available": None,
                "credits_total": None, "code": "" if ok else "login_failed", "message": ""}

    monkeypatch.setattr(el, "login_and_store", _fake_login)

    job = Job(1, "external_login", {"member_ids": [m1.id, m2.id, m3.id]})
    el.batch_login_worker(job)

    assert job.target == 3
    assert job.success == 2
    assert job.fail == 1
    assert job.result == {"total": 3, "success": 2, "fail": 1}


def test_batch_login_worker_survives_raising_member(db, monkeypatch, SessionLocal):
    """回归测试:某个成员的 login_and_store 在 DB 层等处直接抛异常时,
    ThreadPoolExecutor.map 不应把异常传播出去中止整批任务(job 应正常
    完成,而不是被 JobManager 标记为 error),该成员计入失败。"""
    m1 = _seed(db, email="r1@ex.com")
    m2 = _seed(db, email="r2@ex.com")
    m3 = _seed(db, email="r3@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(el.setting_crud, "get_settings", lambda db: SimpleNamespace(concurrency=2))

    def _fake_login(mid, *, log=None):
        if mid == m2.id:
            raise RuntimeError("db commit exploded")
        return {"ok": True, "cookie": "k", "credits_available": None,
                "credits_total": None, "code": "", "message": ""}

    monkeypatch.setattr(el, "login_and_store", _fake_login)

    job = Job(1, "external_login", {"member_ids": [m1.id, m2.id, m3.id]})
    el.batch_login_worker(job)  # 不应抛异常,整批任务应正常完成

    assert job.target == 3
    assert job.success == 2
    assert job.fail == 1
    assert job.result == {"total": 3, "success": 2, "fail": 1}


def test_batch_login_worker_empty_member_ids(monkeypatch, SessionLocal):
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    job = Job(1, "external_login", {"member_ids": []})
    el.batch_login_worker(job)  # 不应抛异常
    assert job.target == 0
    assert job.success == 0 and job.fail == 0
    assert job.result is None


def _proxy_settings(raw: str):
    return lambda db: SimpleNamespace(proxy_enabled=True, proxy_url=raw, concurrency=1)


def test_login_network_error_retries_with_another_proxy(db, monkeypatch, SessionLocal):
    """网络原因失败 → 换一个出口 IP 再试一次,第二次成功即算成功。"""
    m = _seed(db, email="net1@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings", _proxy_settings("10.9.1.1:1\n10.9.1.2:2")
    )
    used: list[str] = []

    def _flaky(**kw):
        used.append(kw["proxy_url"])
        if len(used) == 1:
            raise RuntimeError("('Connection aborted.', ConnectionResetError(54))")
        return {"access_token": "at", "cookie": "k=v", "credits": 3500.0,
                "credits_total": 4000.0, "expires_at": 1, "display_name": "", "user_id": ""}

    monkeypatch.setattr(el.firefly, "register_account", _flaky)
    res = el.login_and_store(m.id)

    assert res["ok"] is True and res["cookie"] == "k=v"
    assert len(used) == 2 and used[0] != used[1]  # 确实换了出口 IP
    db.refresh(m)
    assert m.login_status == "ok"


def test_login_network_error_twice_gives_up(db, monkeypatch, SessionLocal):
    """两次都是网络错 → 只重试一次后放弃,保留原 cookie 并落 rate_limited。"""
    m = _seed(db, email="net2@ex.com", cookie="old=1")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings", _proxy_settings("10.9.2.1:1\n10.9.2.2:2")
    )
    calls: list[str] = []

    def _boom(**kw):
        calls.append(kw["proxy_url"])
        raise RuntimeError("proxy read timeout")

    monkeypatch.setattr(el.firefly, "register_account", _boom)
    res = el.login_and_store(m.id)

    assert res["ok"] is False and res["code"] == "rate_limited"
    assert len(calls) == el.MAX_NETWORK_RETRIES + 1
    db.refresh(m)
    assert m.cookie == "old=1"  # 不清空
    assert m.login_status == "rate_limited"


def test_login_account_error_not_retried(db, monkeypatch, SessionLocal):
    """账号/验证码类错误不重试:换 IP 救不回来,还白耗一次验证码。"""
    m = _seed(db, email="net3@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings", _proxy_settings("10.9.3.1:1\n10.9.3.2:2")
    )
    calls: list[str] = []

    def _boom(**kw):
        calls.append(kw["proxy_url"])
        raise RuntimeError("password rejected")

    monkeypatch.setattr(el.firefly, "register_account", _boom)
    res = el.login_and_store(m.id)

    assert res["ok"] is False and res["code"] == "login_failed"
    assert len(calls) == 1


def test_login_network_error_retries_without_proxy_pool(db, monkeypatch, SessionLocal):
    """没配代理池时也照样多试一次(同一条线路),瞬时网络抖动能救回来。"""
    m = _seed(db, email="net4@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings",
        lambda db: SimpleNamespace(proxy_enabled=False, proxy_url="", concurrency=1),
    )
    calls: list[str] = []

    def _flaky(**kw):
        calls.append(kw["proxy_url"])
        if len(calls) == 1:
            raise RuntimeError("connect timeout")
        return {"access_token": "at", "cookie": "k=v", "credits": 1.0,
                "credits_total": 1.0, "expires_at": 1, "display_name": "", "user_id": ""}

    monkeypatch.setattr(el.firefly, "register_account", _flaky)
    res = el.login_and_store(m.id)

    assert res["ok"] is True
    assert calls == ["", ""]


def test_login_slow_network_error_skips_retry(db, monkeypatch, SessionLocal):
    """网络错但本次已经耗掉大半时间(卡在收码段) → 不再换 IP 重试,
    免得把 /external/cookie 的 5 分钟同步契约拖爆。"""
    m = _seed(db, email="net5@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings", _proxy_settings("10.9.5.1:1\n10.9.5.2:2")
    )
    monkeypatch.setattr(el, "RETRY_MAX_ELAPSED", -1.0)  # 任何耗时都算「太久」
    calls: list[str] = []

    def _boom(**kw):
        calls.append(kw["proxy_url"])
        raise RuntimeError("proxy read timeout")

    monkeypatch.setattr(el.firefly, "register_account", _boom)
    res = el.login_and_store(m.id)

    assert res["ok"] is False and res["code"] == "rate_limited"
    assert len(calls) == 1  # 没有第二次


def test_login_captcha_error_not_retried(db, monkeypatch, SessionLocal):
    """打码失败(arkose.py 的 "captcha timeout" 带 timeout 字样)不能被当成网络问题:
    换出口 IP 救不回来,还会白耗一次验证码。"""
    m = _seed(db, email="net6@ex.com")
    monkeypatch.setattr(el, "SessionLocal", SessionLocal)
    monkeypatch.setattr(
        el.setting_crud, "get_settings", _proxy_settings("10.9.6.1:1\n10.9.6.2:2")
    )
    calls: list[str] = []

    def _boom(**kw):
        calls.append(kw["proxy_url"])
        raise RuntimeError("补全账号 Arkose 失败: captcha timeout")

    monkeypatch.setattr(el.firefly, "register_account", _boom)
    res = el.login_and_store(m.id)

    assert res["ok"] is False
    assert len(calls) == 1
    assert res["code"] == "login_failed"  # 不再误报成 rate_limited(限流)


def test_is_network_error_excludes_captcha():
    assert el._is_network_error("connection reset by proxy") is True
    assert el._is_network_error("补全账号请求异常:Read timed out") is True
    assert el._is_network_error("captcha timeout") is False
    assert el._is_network_error("补全账号 Arkose 失败: captcha timeout") is False
