"""Explicit external-account push, then refresh its linked Sub2 cookie after login.

The durable per-destination record also acts as a pending queue on restart.
No credentials are stored in job metadata, error text, or the link record.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from threading import RLock
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.external_member import ExternalMember
from app.services import log_store, sub2_client

_lock = RLock()
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='external-sub2')
_queued: set[tuple[int, str]] = set()


class SyncError(Exception):
    """Only deliberately safe, user-readable errors may cross this boundary."""


def config(db):
    # Lazy import: Sub2's existing routes also use external_login.
    from app.api.routes.sub2 import _get_config
    return _get_config(db)


def destination(cfg):
    if not cfg.get('base_url'):
        return ''
    url = urlsplit(sub2_client.api_base(cfg['base_url']))
    host = (url.hostname or '').lower()
    if host == 'localhost':
        host = '127.0.0.1'
    if ':' in host:
        host = '[' + host + ']'
    port = url.port
    if port and (url.scheme, port) not in [('http', 80), ('https', 443)]:
        host += ':' + str(port)
    return urlunsplit((url.scheme.lower(), host, url.path.rstrip('/'), '', ''))


def validate_config(cfg):
    if not cfg.get('base_url') or not cfg.get('admin_token'):
        raise SyncError('请先在 Sub2 管理中配置地址和管理员密钥')
    if cfg.get('platform') != 'adobe':
        raise SyncError('外部子号推送需要选择 Adobe Firefly 平台')
    if not cfg.get('group_ids'):
        raise SyncError('请先在 Sub2 管理中选择 Adobe 分组')


def summary(member, target):
    link = (member.sub2_links or {}).get(target, {})
    return {'sub2_status': link.get('status', 'not_pushed'),
            'sub2_message': link.get('message', ''),
            'sub2_account_id': link.get('account_id'),
            'sub2_synced_at': link.get('synced_at')}


def _store(member, target, link):
    member.sub2_links = {**(member.sub2_links or {}), target: link}


def _hash(cookie):
    return hashlib.sha256(cookie.encode()).hexdigest()


def prepare(db, ids, *, automatic=False):
    cfg = config(db)
    target = destination(cfg)
    queued, skipped = [], []
    if not automatic:
        validate_config(cfg)
    with _lock:
        for mid in dict.fromkeys(ids):
            member = db.get(ExternalMember, mid)
            link = (member.sub2_links or {}).get(target, {}) if member else {}
            if automatic and not link:
                continue  # Never send an unrequested account or switch destinations.
            if not member or member.login_status != 'ok' or not (member.cookie or '').strip():
                skipped.append(mid)
                continue
            _store(member, target, {**link, 'status': 'pending', 'message': '等待同步 Cookie'})
            queued.append(mid)
        db.commit()
    return target, queued, skipped


def submit(ids, target):
    for mid in ids:
        key = (mid, target)
        with _lock:
            if key in _queued:
                continue
            _queued.add(key)
        try:
            _executor.submit(_run, mid, target)
        except Exception:
            with _lock:
                _queued.discard(key)
            raise


def after_login(member_id, session_factory=SessionLocal):
    with session_factory() as db:
        target, ids, _ = prepare(db, [member_id], automatic=True)
    submit(ids, target)


def resume_pending():
    with SessionLocal() as db:
        target = destination(config(db))
        ids = [m.id for m in db.scalars(select(ExternalMember))
               if (m.sub2_links or {}).get(target, {}).get('status') in ('pending', 'syncing')]
    submit(ids, target)


def _request(cfg, method, path, body=None):
    try:
        code, raw = sub2_client._request(method, sub2_client.api_base(cfg['base_url']) + path,
                                        cfg['admin_token'], body=body, timeout=25)
    except Exception:
        raise SyncError('Sub2 请求超时或网络异常，请检查连接后重试') from None
    if code not in (200, 201):
        reason = {401: '管理员密钥无效', 403: '管理员密钥无权操作', 404: '账号或接口不存在'}.get(code, '请求失败')
        raise SyncError(f'Sub2 {reason}（HTTP {code}）')
    try:
        envelope = json.loads(raw)
        data = envelope.get('data')
        if not isinstance(data, (dict, list)):
            raise ValueError()
        return data
    except (ValueError, AttributeError):
        raise SyncError('Sub2 返回格式异常，请检查服务版本') from None


def _matches(account, email):
    if account.get('platform') != 'adobe' or account.get('type') != 'oauth':
        return False
    extra = account.get('extra') or {}
    creds = account.get('credentials') or {}
    identities = [extra.get('adobeteam_external_email'), creds.get('email')]
    recorded = [str(value).strip().lower() for value in identities if value]
    # Never use a name match to override an explicit different identity.
    if recorded:
        return all(value == email.lower() for value in recorded)
    return str(account.get('name', '')).strip().lower() == email.lower()


def _find(cfg, email, account_id):
    if account_id:
        account = _request(cfg, 'GET', f'/admin/accounts/{account_id}')
        if not _matches(account, email):
            raise SyncError('Sub2 关联账号身份不一致，请检查后重试')
        return account
    matches = []
    fetched = 0
    for page in range(1, 201):
        data = _request(cfg, 'GET', f'/admin/accounts?page={page}&page_size=100&platform=adobe')
        if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not isinstance(data.get('total'), int):
            raise SyncError('Sub2 账号列表不完整，已停止推送')
        items = data['items']
        matches.extend(a for a in items if _matches(a, email))
        fetched += len(items)
        if fetched >= data['total']:
            break
        if not items:
            raise SyncError('Sub2 账号列表不完整，已停止推送')
    else:
        raise SyncError('Sub2 账号列表过大，无法完成去重检查')
    if len(matches) > 1:
        raise SyncError('Sub2 存在多个同邮箱账号，请先整理重复账号')
    return matches[0] if matches else None


def _sync(cfg, email, cookie, link):
    account = _find(cfg, email, link.get('account_id'))
    credentials = {'cookie': cookie, 'access_token': '', 'email': email}
    marker = {'adobeteam_external_email': email.lower()}
    if account:
        credentials = {**(account.get('credentials') or {}), **credentials}
        # Native reauthorization merges credentials, preserves groups/proxy/model
        # settings, clears authentication errors and invalidates token caches.
        data = _request(cfg, 'POST', f"/admin/accounts/{account['id']}/apply-oauth-credentials",
                        {'type': 'oauth', 'credentials': credentials, 'extra': marker})
    else:
        groups = _request(cfg, 'GET', '/admin/groups/all')
        valid = {g['id'] for g in groups if g.get('platform') == 'adobe' and g.get('status') == 'active'}
        if not set(cfg['group_ids']).issubset(valid):
            raise SyncError('目标 Adobe 分组不存在或已停用，请重新选择分组')
        data = _request(cfg, 'POST', '/admin/accounts', {
            'name': email, 'platform': 'adobe', 'type': 'oauth', 'credentials': credentials,
            'extra': marker, 'group_ids': cfg['group_ids'],
            'concurrency': cfg.get('concurrency', 10), 'priority': 0,
            'rate_multiplier': sub2_client._safe_float(cfg.get('rate_multiplier'), 1),
        })
    if not isinstance(data.get('id'), int):
        raise SyncError('Sub2 未返回账号编号，请重试并检查账号列表')
    return data['id']


def _run(mid, target):
    try:
        # Coalesce concurrent relogins: always sync the newest committed Cookie.
        while True:
            with _lock, SessionLocal() as db:
                member = db.get(ExternalMember, mid)
                if not member:
                    return
                link = (member.sub2_links or {}).get(target)
                if not link or link.get('status') not in ('pending', 'syncing'):
                    return
                cfg = config(db)
                email, cookie = member.email, member.cookie or ''
                _store(member, target, {**link, 'status': 'syncing', 'message': '正在同步 Cookie'})
                db.commit()
            remote_id, error = None, ''
            try:
                validate_config(cfg)
                if destination(cfg) != target:
                    raise SyncError('Sub2 地址已改变，请在当前目标重新推送')
                if not cookie.strip():
                    raise SyncError('账号没有 Cookie，请先登录')
                remote_id = _sync(cfg, email, cookie, link)
            except SyncError as exc:
                error = str(exc)
            except Exception:
                error = 'Sub2 同步异常，请重试或查看服务状态'
            with _lock, SessionLocal() as db:
                member = db.get(ExternalMember, mid)
                if not member or member.email != email:
                    return
                latest = (member.sub2_links or {}).get(target, {})
                if remote_id:
                    latest = {**latest, 'account_id': remote_id, 'cookie_hash': _hash(cookie),
                              'synced_at': datetime.now(timezone.utc).isoformat()}
                changed = bool(member.cookie) and member.cookie != cookie
                latest = {**latest, 'status': 'pending' if changed else ('failed' if error else 'synced'),
                          'message': '等待同步新 Cookie' if changed else (error or 'Cookie 已同步，重登成功后自动更新')}
                _store(member, target, latest)
                db.commit()
            log_store.STORE.add('WARNING' if error else 'INFO', 'external_sub2',
                                f'外部子号 #{mid} Sub2 ' + (error or 'Cookie 同步成功'))
            if not changed:
                return
    except Exception:
        # Unexpected storage/worker errors must not leave an endless spinner.
        with _lock, SessionLocal() as db:
            member = db.get(ExternalMember, mid)
            if member:
                link = (member.sub2_links or {}).get(target, {})
                _store(member, target, {**link, 'status': 'failed', 'message': 'Sub2 同步未完成，请重新推送'})
                db.commit()
        log_store.STORE.add('WARNING', 'external_sub2', f'外部子号 #{mid} Sub2 同步未完成')
    finally:
        with _lock:
            _queued.discard((mid, target))
            # A login can enqueue between final commit and this cleanup.
            with SessionLocal() as db:
                member = db.get(ExternalMember, mid)
                pending = member and (member.sub2_links or {}).get(target, {}).get('status') == 'pending'
            if pending:
                submit([mid], target)
