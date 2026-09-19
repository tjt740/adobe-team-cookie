import types

from app.services import firefly


class _Resp:
    status_code = 200

    def json(self):
        return {
            "total": {"quota": {"total": 4000, "used": 0, "available": 3500}},
            "credits": {"firefly_plan_credit": {"quota": {"total": 4000, "used": 0, "available": 3500}}},
        }


class _Sess:
    def get(self, *a, **k):
        return _Resp()

    def close(self):
        pass


def test_detail_parses_total_and_available(monkeypatch):
    # 用一个带 exp 的假 token 让 extract_account_id 不至于空;直接传 account_id 更稳
    d = firefly.fetch_credits_detail("tok", account_id="acc@org.e", session=_Sess())
    assert d == {"available": 3500.0, "total": 4000.0}


def test_detail_none_token():
    assert firefly.fetch_credits_detail("") is None
