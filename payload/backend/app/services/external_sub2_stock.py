"""Read current Sub2 inventory independently of external Cookie sync history.

Only email identities, remote IDs, availability counts and allowlisted health are cached. Reading inventory never links
accounts, sends cookies, or changes their login/synchronization history.
"""
from datetime import datetime, timezone
import hashlib
from threading import Lock
from time import monotonic

from sqlalchemy import select

from app.models.external_member import ExternalMember
from app.services import external_sub2, sub2_account_health

_lock = Lock()
_cache = {}
TTL = 30


def _read(cfg):
    by_email = {}
    health_by_email = {}
    live = set()
    if cfg.get('enabled') and cfg.get('integration_key'):
        from app.services import reliable_integration as link
        for account in link.inventory(cfg):
            if account.get('status') == 'active' and account.get('schedulable') is True:
                live.add(account['id'])
            email = str(account.get('email') or '').strip().lower()
            imported = str(account.get('imported_email') or '').strip().lower()
            if imported and imported != email:
                continue
            if '@' in email:
                by_email.setdefault(email, set()).add(account['id'])
                health_by_email.setdefault(email, []).append({'account_health': sub2_account_health.project(account)})
        return {email: sorted(ids) for email, ids in by_email.items()}, len(live), health_by_email
    fetched = 0
    for page in range(1, 201):
        data = external_sub2._request(
            cfg, 'GET', f'/admin/accounts?page={page}&page_size=200&platform=adobe')
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
                health_by_email.setdefault(email, []).append({'account_health': sub2_account_health.project(account)})
                if account.get('status') == 'active' and account.get('schedulable') is True:
                    live.add(account['id'])
        fetched += len(items)
        if fetched >= data['total']:
            return {email: sorted(ids) for email, ids in by_email.items()}, len(live), health_by_email
        if not items:
            break
    raise external_sub2.SyncError('Sub2 账号列表不完整，暂时无法确认库存')


def _snapshot(cfg, refresh=False):
    credential = cfg.get('integration_key') if cfg.get('enabled') and cfg.get('integration_key') else cfg.get('admin_token', '')
    key = (external_sub2.destination(cfg), cfg.get('site_id'), hashlib.sha256(credential.encode()).hexdigest())
    with _lock:
        if not refresh and _cache.get('key') == key and monotonic() - _cache['at'] < TTL:
            return _cache['result']
        try:
            by_email, live, health_by_email = _read(cfg)
            result = {'ok': True, 'by_email': by_email, 'live': live, 'message': '',
                      'health_by_email': {email: sub2_account_health.combine(accounts)
                                          for email, accounts in health_by_email.items()}}
        except external_sub2.SyncError as exc:
            result = {'ok': False, 'by_email': {}, 'message': str(exc)}
        except Exception:
            result = {'ok': False, 'by_email': {}, 'message': 'Sub2 库存暂不可用，请检查连接后重试'}
        result['checked_at'] = datetime.now(timezone.utc).isoformat()
        _cache.update(key=key, at=monotonic(), result=result)
        return result


def membership(db, refresh=False):
    cfg = external_sub2.config(db)
    if not cfg.get('base_url') or not (cfg.get('admin_token') or (cfg.get('enabled') and cfg.get('integration_key'))):
        return {'ok': False, 'configured': False, 'items': {},
                'message': '请先在 Sub2 管理配置地址和管理员密钥'}
    result = _snapshot(cfg, refresh)
    # Query local identities after the network request, so a newly added or
    # renamed external account is compared with its current complete email.
    items = {}
    if result['ok']:
        for mid, email in db.execute(select(ExternalMember.id, ExternalMember.email)):
            ids = result['by_email'].get((email or '').strip().lower(), [])
            items[mid] = {'email': email, 'in_stock': bool(ids), 'account_ids': ids,
                          'account_health': result.get('health_by_email', {}).get((email or '').strip().lower(),
                              {'state': 'unknown', 'codes': [], 'errors': []})}
    return {'ok': result['ok'], 'configured': True, 'items': items,
            'checked_at': result['checked_at'], 'message': result['message']}


def capacity_detail(db, member):
    """Confirm a capacity shortage on demand; never infer it from proxy_pending alone."""
    unknown = {'confirmed': False}
    cfg = external_sub2.config(db)
    link = (member.sub2_links or {}).get(external_sub2.destination(cfg), {})
    aid = link.get('account_id')
    if (link.get('status') != 'pending' or type(aid) is not int or aid <= 0
            or not cfg.get('base_url') or not cfg.get('admin_token')):
        return unknown
    try:
        account = external_sub2._request(cfg, 'GET', f'/admin/accounts/{aid}')
        if (account.get('id') != aid or not external_sub2._matches(account, member.email)
                or 'proxy_id' not in account or account['proxy_id'] is not None
                or (account.get('extra', {}).get('okad') or {}).get('verification') != 'proxy_pending'):
            return unknown
        allocation = external_sub2._request(cfg, 'GET', '/admin/accounts/proxy-allocation')
        nodes, per_node, total = allocation.get('nodes'), allocation.get('accounts_per_proxy'), allocation.get('accounts')
        if (allocation.get('enabled') is not True or type(per_node) is not int or per_node <= 0
                or type(total) is not int or total < 0 or not isinstance(nodes, list)
                or any(not isinstance(n, dict) or type(n.get('id')) is not int for n in nodes)
                or len({n['id'] for n in nodes}) != len(nodes)
                or type(allocation.get('available_slots')) is not int or allocation['available_slots'] != 0):
            return unknown
        capacity = len(nodes) * per_node
        # Count every configured node, even unhealthy ones. A temporary health
        # failure alone must not be labelled as exceeding the node count limit.
        if total <= capacity:
            return unknown
        return {'confirmed': True, 'account_id': aid, 'accounts': total,
                'nodes': len(nodes), 'per_node': per_node, 'capacity': capacity,
                'checked_at': datetime.now(timezone.utc).isoformat()}
    except Exception:
        return unknown  # No credentials or upstream errors in the public result.
