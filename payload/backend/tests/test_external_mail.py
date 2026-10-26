from types import SimpleNamespace

import pytest
import requests

from app.api.deps import get_current_user
from app.crud.setting import _set
from app.main import app
from app.models.external_member import ExternalMember
from app.services import external_mail, mail_test, supply_mail


def member(db, **kwargs):
    row = ExternalMember(email='reader@example.test', **kwargs)
    db.add(row)
    db.commit()
    return row


def test_supply_reader_keeps_body_and_closes_connection(client, db, monkeypatch):
    row = member(db)
    _set(db, supply_mail.TOKEN_KEY, 'supply-secret')
    db.commit()
    calls = []

    class Mailbox:
        def __init__(self, token):
            pass

        def messages(self, email):
            calls.append(email)
            return [dict(subject='Adobe 验证码', body='验证码：654321')]

        def close(self):
            calls.append('closed')

    monkeypatch.setattr(supply_mail, 'SupplyMailbox', Mailbox)
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['messages'][0]['body'] == '验证码：654321'
    assert response.json()['source_label'] == 'supply.ink'
    assert calls == [row.email, 'closed']


@pytest.mark.parametrize('source', ['graph', 'imap'])
def test_microsoft_list_and_full_body_use_member_credentials_and_rotate_tokens(client, db, monkeypatch, source):
    row = member(db, refresh_token='old-secret', client_id='client-secret', otp_mode='manual')
    message_id = 'Junk|42' if source == 'imap' else 'message/+=123'

    def inbox(**kwargs):
        assert kwargs['email_addr'] == row.email
        assert kwargs['refresh_token'] == 'old-secret'
        assert kwargs['client_id'] == 'client-secret'
        return mail_test.MailListResult(True, 'ok', source, [
            mail_test.MailSummary(id=message_id, subject='Adobe 验证码', from_addr='adobe@example.test',
                                  date='2026-10-24T04:00:00Z', preview='只包含预览', source=source),
        ], 'rotated-secret')

    def detail(**kwargs):
        assert kwargs['refresh_token'] == 'rotated-secret'
        assert kwargs['message_id'] == message_id and kwargs['source'] == source
        return mail_test.MailDetailResult(True, 'ok', subject='Adobe 验证码', to_addr=row.email,
            body_html='<p>完整正文：654321</p><script>alert(1)</script>', new_refresh_token='detail-secret')

    monkeypatch.setattr(mail_test, 'fetch_inbox', inbox)
    monkeypatch.setattr(mail_test, 'fetch_message', detail)
    monkeypatch.setattr(supply_mail, 'SupplyMailbox', lambda *_: pytest.fail('Must use the saved Microsoft credentials'))
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 200
    mail = response.json()['messages'][0]
    assert mail['id'] == message_id and mail['sender'] == 'adobe@example.test'
    assert 'body' not in mail and mail['preview'] == '只包含预览'
    assert 'secret' not in response.text
    response = client.get(f'/api/external/members/{row.id}/mail/message', params=dict(source=source, message_id=message_id))
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['body'] == '完整正文：654321'
    assert '<script' not in response.text and 'secret' not in response.text
    db.refresh(row)
    assert row.refresh_token == 'detail-secret'


def test_failed_microsoft_read_retains_rotated_token_without_leaking_provider_error(client, db, monkeypatch):
    row = member(db, refresh_token='old-secret', client_id='client-secret')
    monkeypatch.setattr(mail_test, 'fetch_inbox', lambda **_: mail_test.MailListResult(
        False, 'upstream included old-secret', new_refresh_token='new-secret'))
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 400 and '微软邮箱取信失败' in response.text
    assert response.headers['cache-control'] == 'no-store' and 'secret' not in response.text
    db.refresh(row)
    assert row.refresh_token == 'new-secret'


class Http:
    def __init__(self, responses):
        self.responses, self.calls, self.closed = iter(responses), [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        payload = next(self.responses)
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(status_code=200, headers={'Content-Type': 'application/json'}, json=lambda: payload)


@pytest.mark.parametrize('url_field', ['mail_url', 'refresh_token'])
def test_http_mail_uses_saved_url_filters_recipient_sorts_and_reads_body(client, db, monkeypatch, url_field):
    row = member(db, **{url_field: 'https://mail.example.test/inbox?key=secret'})
    rows = [dict(id=str(i), subject=f'邮件 {i}', to=row.email, date=f'2026-10-24T04:00:0{i}Z',
                 body={'content': '<p>正文 654321</p><img src=x onerror=alert(1)>'}) for i in range(7)]
    rows.append(dict(to='another@example.test', body='other mailbox'))
    http = Http([dict(data=rows)] * 4)
    monkeypatch.setattr(external_mail.requests, 'Session', lambda: http)
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 200 and http.closed
    data = response.json()
    assert data['source'] == 'external'
    assert len(data['messages']) == 5
    assert data['messages'][0]['subject'] == '邮件 6'
    assert data['messages'][0]['body'] == '正文 654321'
    assert 'other mailbox' not in response.text and 'secret' not in response.text
    assert all(options['allow_redirects'] is False for _, options in http.calls)


def test_moemail_list_and_detail_with_saved_mailbox(client, db, monkeypatch):
    row = member(db, mail_url='moemail://mail.example.test?api_key=secret&email_id=mailbox1')
    http = Http([dict(messages=[dict(id='message/42', subject='Adobe 验证码', content='truncated')]),
                 dict(message=dict(subject='Adobe 验证码', content='<p>完整正文 654321</p>'))])
    monkeypatch.setattr(external_mail.requests, 'Session', lambda: http)
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 200
    assert response.json()['source'] == 'moemail' and 'body' not in response.json()['messages'][0]
    response = client.get(f'/api/external/members/{row.id}/mail/message', params=dict(source='moemail', message_id='message/42'))
    assert response.status_code == 200 and response.json()['body'] == '完整正文 654321'
    assert http.calls[1][0].endswith('/mailbox1/message%2F42')
    assert http.calls[0][1]['headers']['X-API-Key'] == 'secret' and 'secret' not in response.text


def test_provider_connection_error_does_not_echo_credentials(client, db, monkeypatch):
    row = member(db, mail_url='https://mail.example.test?key=secret')
    http = Http([requests.ConnectionError('https://mail.example.test?key=secret')])
    monkeypatch.setattr(external_mail.requests, 'Session', lambda: http)
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 400 and '连接失败' in response.text
    assert 'secret' not in response.text and http.closed


def test_successful_http_folder_is_kept_when_other_folders_fail(client, db, monkeypatch):
    row = member(db, refresh_token='https://mail.example.test?key=secret')
    http = Http([dict(data=[dict(subject='Adobe', body='完整正文', date=1792814400000)]),
                 requests.ConnectionError('secret'), requests.ConnectionError('secret'), requests.ConnectionError('secret')])
    monkeypatch.setattr(external_mail.requests, 'Session', lambda: http)
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 200
    assert response.json()['messages'][0]['body'] == '完整正文'
    assert response.json()['messages'][0]['date'] == '2026-10-24T04:00:00+00:00'


def test_missing_or_invalid_detail_and_vietnam_only_account(client, db):
    assert client.get('/api/external/members/999/mail/message', params=dict(source='imap', message_id='42')).status_code == 404
    row = member(db, otp_mode='vietnam')
    response = client.get(f'/api/external/members/{row.id}/mail')
    assert response.status_code == 400 and '未配置可查看正文' in response.text
    assert client.get(f'/api/external/members/{row.id}/mail/message', params=dict(source='supply', message_id='42')).status_code == 422
    assert client.get(f'/api/external/members/{row.id}/mail/message', params=dict(source='imap', message_id='')).status_code == 422


def test_mail_list_and_body_require_login(client):
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/external/members/1/mail').status_code == 401
    assert client.get('/api/external/members/1/mail/message', params=dict(source='imap', message_id='42')).status_code == 401
