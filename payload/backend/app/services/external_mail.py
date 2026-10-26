"""Read external members' mail using their saved mailbox configuration."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlparse

import requests

from app.crud import setting as setting_crud
from app.services import mail_test, supply_mail, supply_mail_tokens


class MailReadError(RuntimeError):
    pass


def _rotate_token(db, member, result):
    if result.new_refresh_token and result.new_refresh_token != member.refresh_token:
        member.refresh_token = result.new_refresh_token
        db.commit()


def _address(value):
    if isinstance(value, dict):
        return _address(value.get('emailAddress') or value.get('address') or value.get('email') or '')
    if isinstance(value, list):
        return ', '.join(_address(item) for item in value)
    return str(value or '')


def _message(row):
    body = row.get('body_text') or row.get('body') or row.get('content') or row.get('text') or row.get('body_html') or row.get('html') or ''
    if isinstance(body, dict):
        body = body.get('content') or body.get('text') or ''
    date = row.get('date') or row.get('receivedDateTime') or row.get('received_at') or row.get('receivedAt') or row.get('createTime') or ''
    timestamp = supply_mail.mail_timestamp(date)
    if timestamp is not None:
        try:
            date = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            date = ''
    return {
        'id': str(row.get('id') or ''),
        'subject': supply_mail.text_from_html(row.get('subject') or row.get('title')),
        'sender': _address(row.get('from_addr') or row.get('from_address') or row.get('fromAddress') or row.get('from') or row.get('sender')),
        'recipient': _address(row.get('to_addr') or row.get('to') or row.get('recipient')),
        'date': str(date),
        'body': supply_mail.text_from_html(body),
    }


def _request(http, url, *, timeout, headers=None):
    try:
        response = http.get(url, headers=headers, timeout=timeout, allow_redirects=False)
    except requests.RequestException:
        raise MailReadError('邮箱取信接口连接失败，请稍后刷新重试') from None
    if response.status_code != 200:
        raise MailReadError(f'邮箱取信接口返回 HTTP {response.status_code}，请检查邮箱配置')
    if 'json' in response.headers.get('Content-Type', '').lower():
        try:
            return response.json()
        except ValueError:
            raise MailReadError('邮箱取信接口返回了无法识别的数据') from None
    return response.text


def _external_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, str):
        return [{'body': payload}] if payload.strip() else []
    if isinstance(payload, dict):
        if payload.get('success') is False:
            raise MailReadError('邮箱取信接口查询失败，请检查邮箱配置')
        for key in ('messages', 'list', 'rows', 'data', 'message'):
            if key in payload and isinstance(payload[key], (list, dict)):
                return _external_rows(payload[key])
        if isinstance(payload.get('data'), str):
            return _external_rows(payload['data'])
        if any(key in payload for key in ('subject', 'body', 'body_text', 'body_html', 'content', 'html', 'text')):
            return [payload]
    raise MailReadError('邮箱取信接口未返回邮件内容')


def _moemail_config(member):
    parsed = urlparse(mail_test.normalize_mail_url(member.mail_url or ''))
    if parsed.scheme != 'moemail':
        raise MailReadError('该账号没有 MoeMail 取信配置')
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    key = (params.get('api_key') or params.get('key') or '').strip()
    if not key:
        raise MailReadError('MoeMail 配置缺少 API Key，请更新邮箱取信配置')
    return ('https://' + (parsed.netloc or 'edu6.site'),
            {'X-API-Key': key, 'Accept': 'application/json'},
            (params.get('email_id') or params.get('emailId') or parsed.path.strip('/')).strip())


def _moemail_inbox(http, member, timeout):
    base, headers, email_id = _moemail_config(member)
    if not email_id:
        cursor = ''
        for _ in range(5):
            url = base + '/api/emails' + ('?cursor=' + quote(cursor, safe='') if cursor else '')
            data = _request(http, url, timeout=timeout, headers=headers)
            if not isinstance(data, dict):
                raise MailReadError('MoeMail 返回了无法识别的邮箱列表')
            for item in data.get('emails') or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get('address') or item.get('email') or '').strip().lower() == member.email.strip().lower():
                    email_id = str(item.get('id') or '')
                    break
            cursor = str(data.get('nextCursor') or '')
            if email_id or not cursor:
                break
    if not email_id:
        raise MailReadError('MoeMail 未找到该邮箱，请检查邮箱取信配置')
    return base + '/api/emails/' + quote(email_id, safe=''), headers


def list_messages(db, member):
    timeout = min(setting_crud.get_settings(db).request_timeout, 12)
    mail_url = mail_test.normalize_mail_url(member.mail_url or '')
    if mail_url or mail_test.is_http_mail_url(member.refresh_token or ''):
        with requests.Session() as http:
            if urlparse(mail_url).scheme == 'moemail':
                inbox, headers = _moemail_inbox(http, member, timeout)
                payload = _request(http, inbox, timeout=timeout, headers=headers)
                rows = _external_rows(payload)
                messages = [_message(row) for row in rows if isinstance(row, dict)]
                for message in messages:
                    message.pop('body')  # MoeMail list items are summaries; fetch the full body on expansion.
                source, label = 'moemail', 'MoeMail'
            else:
                urls = mail_test._external_urls(mail_url, member.refresh_token or '', member.client_id or '', member.email)
                messages, seen, failures, successful = [], set(), [], False
                for url in urls:
                    if not mail_test.is_http_mail_url(url):
                        raise MailReadError('邮箱取信地址格式无效，请检查邮箱配置')
                    try:
                        rows = _external_rows(_request(http, url, timeout=timeout))
                    except MailReadError as exc:
                        failures.append(str(exc))
                        continue
                    successful = True
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        message = _message(row)
                        recipient = message['recipient'].lower()
                        if recipient and member.email.lower() not in re.findall(r'[\w.+%\-]+@[\w.\-]+', recipient):
                            continue
                        identity = (message['id'], message['subject'], message['date'], message['body'])
                        if identity not in seen:
                            messages.append(message)
                            seen.add(identity)
                if not successful:
                    raise MailReadError(failures[0] if failures else '邮箱取信接口未返回邮件内容')
                source, label = 'external', '邮箱取信接口'
        messages.sort(key=lambda item: supply_mail.mail_timestamp(item['date']) or 0, reverse=True)
        return dict(email=member.email, source=source, source_label=label, messages=messages[:5])

    if member.refresh_token and member.client_id:
        result = mail_test.fetch_inbox(email_addr=member.email, refresh_token=member.refresh_token,
                                       client_id=member.client_id, proxy_url='', timeout=timeout, top=5)
        _rotate_token(db, member, result)
        if not result.success:
            raise MailReadError('微软邮箱取信失败，请检查该账号的 Refresh Token / Client ID 后重试')
        messages = [dict(id=item.id, subject=item.subject, sender=item.from_addr, date=item.date,
                         preview=item.preview, source=item.source or result.source)
                    for item in result.messages or []]
        return dict(email=member.email, source=result.source, source_label='微软邮箱', messages=messages)

    if member.otp_mode == 'vietnam':
        raise MailReadError('该账号仅配置了越南验证码接收，未配置可查看正文的邮箱取信接口')
    if not supply_mail_tokens.configured(db):
        raise MailReadError('请先在导入外部子号的邮件配置中保存 supply.ink Token，或为该账号提供邮箱取信配置')
    mailbox = supply_mail_tokens.mailbox(db, member.email)
    try:
        return dict(email=member.email, source='supply', source_label='supply.ink', messages=mailbox.messages(member.email))
    except supply_mail.SupplyMailError as exc:
        raise MailReadError(str(exc)) from None
    finally:
        mailbox.close()


def message_detail(db, member, message_id, source):
    timeout = min(setting_crud.get_settings(db).request_timeout, 12)
    if source == 'moemail':
        with requests.Session() as http:
            inbox, headers = _moemail_inbox(http, member, timeout)
            payload = _request(http, inbox + '/' + quote(message_id, safe=''), timeout=timeout, headers=headers)
        rows = _external_rows(payload)
        if not rows or not isinstance(rows[0], dict):
            raise MailReadError('邮件不存在，请刷新邮件列表后重试')
        return _message(rows[0])
    if member.mail_url or not (member.refresh_token and member.client_id) or mail_test.is_http_mail_url(member.refresh_token):
        raise MailReadError('该账号没有微软邮箱取信凭据，请刷新邮件列表后重试')
    result = mail_test.fetch_message(email_addr=member.email, refresh_token=member.refresh_token,
                                     client_id=member.client_id, message_id=message_id, source=source,
                                     proxy_url='', timeout=timeout)
    _rotate_token(db, member, result)
    if not result.success:
        raise MailReadError('邮件正文读取失败，请刷新重试或检查该账号的邮箱授权')
    return dict(subject=result.subject, sender=result.from_addr, recipient=result.to_addr, date=result.date,
                body=result.body_text or supply_mail.text_from_html(result.body_html))
