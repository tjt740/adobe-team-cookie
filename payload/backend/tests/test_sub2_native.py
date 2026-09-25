import json

import pytest

from app.api.routes import sub2
from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.services import sub2_client as client


CFG = {'base_url': 'https://sub2.example', 'admin_token': 'admin-test',
       'platform': 'adobe', 'group_ids': [7], 'concurrency': 3}


def test_native_cookie_import_shape_and_partial_success(monkeypatch):
    calls = []

    def request(method, url, token, body=None, **kwargs):
        calls.append((method, url, token, body))
        return (201, json.dumps({'data': {'id': 4}})) if len(calls) == 1 else (400, '{}')

    monkeypatch.setattr(client, '_request', request)
    response = client.import_tokens(CFG, [
        {'email': 'first@example.com', 'name': 'Display name', 'cookie': 'ims_sid=test',
         'access_token': 'ios-token-must-not-be-sent', 'arp_session_id': 'arp-test'},
        {'email': 'empty@example.com', 'cookie': ' '},
        {'email': 'failed@example.com', 'cookie': 'ims_sid=other'},
    ])
    assert calls[0][:3] == ('POST', 'https://sub2.example/api/v1/admin/accounts', 'admin-test')
    body = calls[0][3]
    assert body['platform'] == 'adobe' and body['type'] == 'oauth'
    assert body['name'] == 'first@example.com' and body['group_ids'] == [7]
    assert body['credentials'] == {'cookie': 'ims_sid=test', 'email': 'first@example.com', 'arp_session_id': 'arp-test'}
    assert response['code'] == 502
    assert response['result'] == {'created': 1, 'failed': 1, 'skipped': 1, 'items': [
        {'index': 0, 'status': 'created'}, {'index': 1, 'status': 'skipped'}, {'index': 2, 'status': 'failed'},
    ]}


def test_native_cookie_import_requires_group(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('No remote write without a target group')
    monkeypatch.setattr(client, '_request', unexpected)
    assert client.import_tokens({**CFG, 'group_ids': []}, [{'cookie': 'test'}])['code'] == 400


@pytest.mark.parametrize('balance,path,result,ok', [
    (False, '/admin/accounts/batch-refresh', {'success': 1, 'failed': 0}, True),
    (False, '/admin/accounts/batch-refresh', {'success': 0, 'failed': 1}, False),
    (True, '/admin/accounts/usage/batch', {'usage': {'1': {'adobe_credit': {'usage_limit': 4000}}}}, True),
    (True, '/admin/accounts/usage/batch', {'usage': {'1': {'error': 'expired'}}}, False),
    (True, '/admin/accounts/usage/batch', {'usage': {}, 'errors': {'1': 'missing'}}, False),
])
def test_native_refresh(monkeypatch, balance, path, result, ok):
    def request(method, url, token, body=None, **kwargs):
        assert method == 'POST' and url.endswith(path)
        assert body == ({'account_ids': [1], 'force': True} if balance else {'account_ids': [1]})
        return 200, json.dumps({'data': result})
    monkeypatch.setattr(client, '_request', request)
    assert client.batch_refresh(CFG, [1], balance=balance)['ok'] is ok


def test_native_list_counts_accounts_without_exposing_secrets(monkeypatch):
    account = {'id': 5, 'platform': 'adobe', 'name': 'existing@example.com',
               'status': 'active', 'credentials': {'email': 'existing@example.com', 'cookie': 'secret'},
               'credentials_status': {'has_access_token': True}, 'group_ids': [7]}
    def request(method, url, token, **kwargs):
        assert 'platform=adobe' in url
        return 200, json.dumps({'data': {'items': [account], 'total': 1}})
    monkeypatch.setattr(client, '_request', request)
    existing = client.list_existing(CFG, platform='adobe')
    assert existing['ok'] and existing['count'] == 1
    assert existing['emails'] == {'existing@example.com'}
    page = client.list_accounts_page(CFG, platform='adobe')
    assert page['items'][0]['has_token'] is True
    assert 'secret' not in json.dumps(page)
    truncated = client.list_existing(CFG, platform='adobe', max_pages=0)
    assert not truncated['ok'] and truncated['truncated']


def test_native_candidates_include_both_local_platforms_and_mark_success_only(db, monkeypatch):
    monkeypatch.setattr(sub2, '_member_account_id', lambda m: '')
    parents = [AdobeAccount(email=f'parent{i}@example.com', platform=p)
               for i, p in enumerate(['adobe_gemini', 'adobe_gpt'])]
    db.add_all(parents)
    db.flush()
    rows = [AdobeMember(admin_id=a.id, email=f'child{i}@example.com', cookie='test',
                        access_token='test', registered=True, credits=4000)
            for i, a in enumerate(parents)]
    db.add_all(rows)
    db.commit()
    selected, _ = sub2._candidates(db, {'account_ids': set(), 'emails': set()}, None, platform='adobe')
    assert {m.id for m in selected} == {m.id for m in rows}
    assert sub2.mark_pushed(db, selected, {'items': [{'index': 0, 'status': 'created'}, {'index': 1, 'status': 'failed'}]}) == 1
    assert selected[0].sub2_pushed_at and selected[1].sub2_pushed_at is None


def test_legacy_import_still_uses_legacy_endpoint(monkeypatch):
    def request(method, url, token, body=None, **kwargs):
        assert url.endswith('/admin/accounts/adobe/import-cookie')
        assert body['platform'] == 'adobe_gemini'
        return 200, json.dumps({'data': {'created': 1}})
    monkeypatch.setattr(client, '_request', request)
    assert client.import_tokens({**CFG, 'platform': 'adobe_gemini'}, [{'cookie': 'test'}])['code'] == 200
