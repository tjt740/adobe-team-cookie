from types import SimpleNamespace

import pytest

from app.services.adobe_protocol import http_client


@pytest.mark.parametrize("major", [124, 131, 136, 146])
def test_http_headers_describe_the_selected_tls_browser(monkeypatch, major):
    sessions = []

    def make_session(**kwargs):
        sessions.append(kwargs)
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(http_client, "_HAS_CURL_CFFI", True)
    monkeypatch.setattr(http_client, "IMPERSONATE_TARGET", f"chrome{major}")
    monkeypatch.setattr(http_client, "_requests", SimpleNamespace(Session=make_session))
    client = http_client.HttpClient()
    headers = client._base_headers()
    assert sessions == [{"impersonate": f"chrome{major}"}]
    assert f"Chrome/{major}.0.0.0" in headers["User-Agent"]
    assert f'"Chromium";v="{major}"' in headers["sec-ch-ua"]
    assert f'"Google Chrome";v="{major}"' in headers["sec-ch-ua"]
    assert headers["sec-ch-ua-platform"] == '"Windows"'


def test_profile_initialization_failure_does_not_silently_change_transport(monkeypatch):
    calls = []

    def unavailable(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("profile unavailable")

    monkeypatch.setattr(http_client, "_HAS_CURL_CFFI", True)
    monkeypatch.setattr(http_client, "IMPERSONATE_TARGET", "chrome124")
    monkeypatch.setattr(http_client, "_requests", SimpleNamespace(Session=unavailable))
    with pytest.raises(RuntimeError, match="profile unavailable"):
        http_client.HttpClient()
    assert calls == [{"impersonate": "chrome124"}]


def test_non_chrome_fallback_cannot_claim_a_chrome_identity(monkeypatch):
    monkeypatch.setattr(http_client, "IMPERSONATE_TARGET", "safari17_0")
    with pytest.raises(ValueError, match="desktop Chrome"):
        http_client.HttpClient()
