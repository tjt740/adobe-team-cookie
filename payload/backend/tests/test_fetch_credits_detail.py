from types import SimpleNamespace

import pytest

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


def session_for(*responses):
    items = iter(responses)
    def get(*args, **kwargs):
        value = next(items)
        if isinstance(value, Exception):
            raise value
        return value
    return SimpleNamespace(get=get)


def response(status, body):
    return SimpleNamespace(status_code=status, json=lambda: body)


def test_http_error_is_safe_and_cleared_when_retry_succeeds():
    error = {}
    denied = response(451, {'error_code': '10009', 'message': 'private-token'})
    assert firefly.fetch_credits_detail('tok', 'id', session=session_for(denied), error_out=error) is None
    assert error == {'message': 'Adobe 拒绝查询（HTTP 451 / 10009）'}
    assert firefly.fetch_credits_detail('tok', 'id', session=session_for(denied, _Resp()),
                                        attempts=2, error_out=error) == {'available': 3500, 'total': 4000}
    assert error == {}


@pytest.mark.parametrize('body', [{}, {'total': {'quota': {'available': 5}}},
                                 {'total': {'quota': {'available': True, 'total': 4000}}},
                                 {'total': {'quota': {'available': float('nan'), 'total': 4000}}}, []])
def test_invalid_success_response_is_unknown_not_zero(body):
    error = {}
    assert firefly.fetch_credits_detail('tok', 'id', session=session_for(response(200, body)), error_out=error) is None
    assert '数据不完整' in error['message']


def test_zero_balance_is_a_success():
    error = {}
    result = firefly.fetch_credits_detail('tok', 'id', error_out=error,
        session=session_for(response(200, {'total': {'quota': {'available': 0, 'total': 0}}})))
    assert result == {'available': 0, 'total': 0} and error == {}


def test_final_network_failure_does_not_leak_exception_or_keep_previous_http_code():
    error = {}
    session = session_for(response(451, {'error_code': '10009'}), RuntimeError('private-cookie'))
    assert firefly.fetch_credits_detail('tok', 'id', session=session, attempts=2, error_out=error) is None
    assert error == {'message': '积分接口请求失败或超时，请稍后重试'}


@pytest.mark.parametrize('status,phrase', [(401, '凭证已失效'), (403, '拒绝访问'), (429, '过于频繁'), (503, '服务暂时异常')])
def test_http_categories_do_not_persist_arbitrary_error_codes(status, phrase):
    error = {}
    firefly.fetch_credits_detail('tok', 'id', error_out=error,
        session=session_for(response(status, {'error_code': 'private-token', 'message': 'private-cookie'})))
    assert phrase in error['message'] and str(status) in error['message']
    assert 'private' not in error['message']
