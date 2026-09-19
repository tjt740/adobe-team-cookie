from app.services import proxy_pool


def test_random_proxy_empty():
    assert proxy_pool.random_proxy("") == ""


def test_random_proxy_returns_member():
    raw = "\n".join(f"10.0.0.{i}:8080" for i in range(50))
    got = proxy_pool.random_proxy(raw)
    assert got in set(proxy_pool._split(raw))


def test_split_cached_same_object():
    raw = "1.2.3.4:8080\n5.6.7.8:9090"
    a = proxy_pool._split(raw)
    b = proxy_pool._split(raw)
    assert a == b
    assert a is b  # 命中缓存返回同一 list 对象


def test_random_proxy_exclude_avoids_that_exit():
    raw = "\n".join(f"10.8.0.{i}:8080" for i in range(8))
    skip = proxy_pool._split(raw)[0]
    for _ in range(30):
        assert proxy_pool.random_proxy(raw, exclude=skip) != skip


def test_random_proxy_exclude_accepts_unnormalized_form():
    raw = "10.8.1.1:8080\n10.8.1.2:8080"
    # 传入未规范化的写法也要能对上(random_proxy 返回的是规范化后的 URL)
    assert proxy_pool.random_proxy(raw, exclude="10.8.1.1:8080") == "http://10.8.1.2:8080"


def test_random_proxy_exclude_single_proxy_falls_back():
    raw = "10.8.2.1:8080"
    only = proxy_pool._split(raw)[0]
    assert proxy_pool.random_proxy(raw, exclude=only) == only
