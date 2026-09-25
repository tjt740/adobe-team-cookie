"""Read current Sub2 inventory independently of external Cookie sync history.

Only email identities and remote IDs are cached. Reading inventory never links
accounts, sends cookies, or changes their login/synchronization history.
"""
from datetime import datetime, timezone
import hashlib
from threading import Lock
from time import monotonic

from sqlalchemy import select

from app.models.external_member import ExternalMember
from app.services import external_sub2

_lock = Lock()
_cache = {}
TTL = 2


def _read(cfg):
    by_email = {}
    fetched = 0
    for page in range(1, 201):
        data = external_sub2._request(
            cfg, 'GET', f'/admin/accounts?page={page}&page_size=100&platform=adobe')
        if (not isinstance(data, dict) or not isinstance(data.get('items'), list)
                or type(data.get('total')) is not int or data['total'] < 0):
            raise external_sub2.SyncError('Sub2 账号列表不完整，暂时无法确认库存')
        items = data['items']
        for account in items:
            if not isinstance(account, dict) or type(account.get('id')) is not int:
                raise external_sub2.SyncError('Sub2 账号列表格式异常，暂时无法确认库存')
            extra, creds = account.get('extra') or {}, account.get('credentials') or {}
            email = str(creds.get('email') or extra.get('adobeteam_external_email')
                        or account.get('name') or '').strip().lower()
            if '@' in email and external_sub2._matches(account, email):
                by_email.setdefault(email, set()).add(account['id'])
        fetched += len(items)
        if fetched >= data['total']:
            return {email: sorted(ids) for email, ids in by_email.items()}
        if not items:
            break
    raise external_sub2.SyncError('Sub2 账号列表不完整，暂时无法确认库存')


def _snapshot(cfg, refresh=False):
    key = (external_sub2.destination(cfg), hashlib.sha256(cfg['admin_token'].encode()).hexdigest())
    with _lock:
        if not refresh and _cache.get('key') == key and monotonic() - _cache['at'] < TTL:
            return _cache['result']
        try:
            result = {'ok': True, 'by_email': _read(cfg), 'message': ''}
        except external_sub2.SyncError as exc:
            result = {'ok': False, 'by_email': {}, 'message': str(exc)}
        except Exception:
            result = {'ok': False, 'by_email': {}, 'message': 'Sub2 库存暂不可用，请检查连接后重试'}
        result['checked_at'] = datetime.now(timezone.utc).isoformat()
        _cache.update(key=key, at=monotonic(), result=result)
        return result


def membership(db, refresh=False):
    cfg = external_sub2.config(db)
    if not cfg.get('base_url') or not cfg.get('admin_token'):
        return {'ok': False, 'configured': False, 'items': {},
                'message': '请先在 Sub2 管理配置地址和管理员密钥'}
    result = _snapshot(cfg, refresh)
    # Query local identities after the network request, so a newly added or
    # renamed external account is compared with its current complete email.
    items = {}
    if result['ok']:
        for mid, email in db.execute(select(ExternalMember.id, ExternalMember.email)):
            ids = result['by_email'].get((email or '').strip().lower(), [])
            items[mid] = {'email': email, 'in_stock': bool(ids), 'account_ids': ids}
    return {'ok': result['ok'], 'configured': True, 'items': items,
            'checked_at': result['checked_at'], 'message': result['message']}
