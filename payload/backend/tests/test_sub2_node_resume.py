"""Node allocation wakes durable deliveries using synthetic Sub2 responses only."""
import copy
import time

import pytest
from sqlalchemy import select

from app.models.external_member import ExternalMember
from app.models.integration import CredentialDelivery, RecoveryJob
from app.services import external_login, external_sub2, reliable_integration as link


CFG = dict(enabled=True, integration_key='fixture-key', site_id='fixture-site',
           issuer='fixture-okad', base_url='http://127.0.0.1:19999',
           admin_token='fixture-admin', platform='adobe', group_ids=[1])


@pytest.fixture
def waiting(db, SessionLocal, monkeypatch):
    monkeypatch.setattr(link, 'SessionLocal', SessionLocal)
    config = dict(CFG)
    monkeypatch.setattr(link, 'settings', lambda db: dict(config))
    monkeypatch.setattr(link, '_pending', set())
    monkeypatch.setattr(link, '_last_inventory', {})
    monkeypatch.setattr(external_login, 'login_and_store', lambda *a, **k: pytest.fail('node recovery must not log in'))
    monkeypatch.setattr(link, 'login_pool', lambda *a, **k: pytest.fail('node recovery must not log in'))

    class Immediate:
        def submit(self, work):
            work()

    monkeypatch.setattr(link, '_delivery_executor', Immediate())
    row = ExternalMember(email='waiting@example.test', cookie='fixture-cookie', login_status='ok')
    db.add(row)
    db.commit()
    source_key = f'external:{row.id}'
    link.queue_source(db, source_key, account_id=91)
    remote = dict(id=91, email=row.email, proxy_id=None, status='error', schedulable=False,
                  integration=dict(issuer=CFG['issuer'], source_key=source_key, version=1,
                                   verification='proxy_pending'))
    calls = []

    def request(cfg, method, path, body=None):
        calls.append((method, path))
        if path == '/capabilities':
            return dict(site_id=CFG['site_id'], protocol=2)
        if path.startswith('/accounts?'):
            return dict(items=[copy.deepcopy(remote)] if remote else [], next_cursor=0)
        assert method == 'POST' and path in ('/accounts/91/credentials', '/accounts/91/verify')
        if path.endswith('/verify') and remote['proxy_id']:
            remote['integration']['verification'] = 'verified'
            remote.update(status='active', schedulable=True)
        # The real write/verify receipts omit proxy_id; inventory supplies it.
        return {key: copy.deepcopy(remote[key]) for key in ('id', 'status', 'schedulable', 'integration')}

    monkeypatch.setattr(link, 'request', request)
    key = CFG['site_id'] + '/' + source_key
    link.deliver(key)
    db.expire_all()
    delivery = db.get(CredentialDelivery, key)
    assert delivery.state == 'retry'
    shown = external_sub2.summary(row, external_sub2.destination(CFG))
    assert shown['sub2_status'] == 'pending'
    assert shown['sub2_message'] == 'Cookie 已写入，等待 Sub2 代理就绪'
    delivery.next_at = time.time() + 900
    db.commit()
    calls.clear()
    return row, delivery, remote, calls, config


def test_new_node_automatically_wakes_waiting_delivery(db, waiting):
    row, delivery, remote, calls, _ = waiting
    next_at = delivery.next_at
    link.tick()  # Inventory must run even when there are only proxy-waiting jobs.
    db.refresh(delivery)
    assert delivery.state == 'retry' and delivery.next_at == next_at
    assert all(method == 'GET' for method, _ in calls)
    previous = list(calls)
    link.tick()
    assert calls == previous  # The status check is throttled to 30 seconds.

    remote['proxy_id'] = 72  # Sub2's allocator assigns a newly added node.
    for tag in link._last_inventory:
        link._last_inventory[tag] -= link.INVENTORY_INTERVAL
    link.tick()
    db.refresh(delivery)
    assert delivery.next_at == 0 and delivery.state == 'retry'
    assert delivery.receipt['proxy_id'] == 72
    assert all(method == 'GET' for method, _ in calls)
    link.tick()  # Next worker tick picks up the awakened delivery.
    db.expire_all()
    assert delivery.state == 'ready' and delivery.lease_until == 0
    assert delivery.version == 1 and delivery.attempts == 2
    assert calls.count(('POST', '/accounts/91/credentials')) == 1
    assert calls.count(('POST', '/accounts/91/verify')) == 1
    assert row.cookie == 'fixture-cookie'
    assert row.sub2_links[external_sub2.destination(CFG)]['status'] == 'synced'
    assert not list(db.scalars(select(RecoveryJob)))


@pytest.mark.parametrize('proxy', [None, 0, -1, True, '72'])
def test_missing_or_invalid_node_keeps_backoff(db, waiting, proxy):
    _, delivery, remote, calls, _ = waiting
    remote['proxy_id'] = proxy
    before = delivery.next_at
    link.reconcile_inventory()
    db.refresh(delivery)
    assert delivery.state == 'retry' and delivery.next_at == before
    assert all(method == 'GET' for method, _ in calls)


def test_unchanged_unhealthy_node_does_not_repeatedly_wake(db, waiting):
    _, delivery, remote, calls, _ = waiting
    remote['proxy_id'] = 72
    delivery.receipt = {**delivery.receipt, 'proxy_id': 72}
    db.commit()
    before = delivery.next_at
    link.reconcile_inventory()
    db.refresh(delivery)
    assert delivery.next_at == before
    remote['proxy_id'] = 73
    link.reconcile_inventory()
    db.refresh(delivery)
    assert delivery.next_at == 0 and delivery.receipt['proxy_id'] == 73
    assert all(method == 'GET' for method, _ in calls)


@pytest.mark.parametrize('change', ['delete', 'issuer', 'source', 'version', 'verified', 'paused'])
def test_remote_changes_are_respected_without_pushing(db, waiting, change):
    row, delivery, remote, calls, _ = waiting
    remote['proxy_id'] = 72
    if change == 'delete':
        remote.clear()
    elif change == 'issuer':
        remote['integration']['issuer'] = 'another-okad'
    elif change == 'source':
        remote['integration']['source_key'] = 'external:999'
    elif change == 'version':
        remote['integration']['version'] = 2
    else:
        remote['integration']['verification'] = 'verified'
        remote.update(status='active', schedulable=change == 'verified')
    link.reconcile_inventory()
    db.expire_all()
    expected = {'delete': 'blocked', 'verified': 'ready', 'paused': 'paused'}.get(change, 'attention')
    assert delivery.state == expected
    status = row.sub2_links[external_sub2.destination(CFG)]['status']
    assert status == ('synced' if expected in ('ready', 'paused') else 'failed')
    assert all(method == 'GET' for method, _ in calls)


@pytest.mark.parametrize('change', ['new_cookie', 'same_version_retry', 'lease', 'disable', 'site', 'target'])
def test_late_inventory_never_overwrites_newer_work(db, waiting, monkeypatch, change):
    row, delivery, remote, _, config = waiting
    remote['proxy_id'] = 72
    original = link.request
    before = delivery.next_at

    def request(cfg, method, path, body=None):
        if path.startswith('/accounts?'):
            if change == 'new_cookie':
                row.cookie = 'new-cookie'
                link.record_cookie(db, delivery.source_key, row.email, row.cookie)
            elif change == 'same_version_retry':
                delivery.updated_at = time.time() + 1
                delivery.next_at = before + 100
            elif change == 'lease':
                delivery.lease_until = time.time() + 180
            elif change == 'disable':
                config['enabled'] = False
            elif change == 'site':
                config['site_id'] = 'another-site'
            else:
                config['base_url'] = 'http://127.0.0.1:29999'
            db.commit()
        return original(cfg, method, path, body)

    monkeypatch.setattr(link, 'request', request)
    link.reconcile_inventory()
    db.refresh(delivery)
    if change == 'new_cookie':
        assert delivery.state == 'pending' and delivery.version == 2 and delivery.receipt is None
    else:
        assert delivery.state == 'retry'
        assert delivery.next_at == (before + 100 if change == 'same_version_retry' else before)
        assert delivery.receipt.get('proxy_id') is None


def test_partial_node_capacity_wakes_only_assigned_account(db, waiting, monkeypatch):
    _, delivery, remote, _, _ = waiting
    other = ExternalMember(email='other@example.test', cookie='other-cookie')
    db.add(other)
    db.commit()
    other_source = f'external:{other.id}'
    link.queue_source(db, other_source, account_id=92)
    second = db.get(CredentialDelivery, CFG['site_id'] + '/' + other_source)
    second.state = 'retry'
    second.next_at = delivery.next_at
    second.receipt = dict(integration=dict(verification='proxy_pending'))
    db.commit()
    before = second.next_at
    original = link.request

    def request(cfg, method, path, body=None):
        result = original(cfg, method, path, body)
        if path.startswith('/accounts?'):
            result['items'].append(dict(id=92, email=other.email, proxy_id=None,
                status='error', schedulable=False, integration=dict(verification='proxy_pending',
                issuer=CFG['issuer'], source_key=other_source, version=1)))
        return result

    monkeypatch.setattr(link, 'request', request)
    remote['proxy_id'] = 72
    link.reconcile_inventory()
    db.expire_all()
    assert delivery.next_at == 0 and delivery.state == 'retry'
    assert second.state == 'retry' and second.next_at == before


@pytest.mark.parametrize('failure', ['offline', 'wrong_site', 'disabled'])
def test_unavailable_connection_preserves_waiting_work(db, waiting, monkeypatch, failure):
    _, delivery, remote, calls, config = waiting
    before = delivery.next_at
    remote['proxy_id'] = 72
    if failure == 'disabled':
        config['enabled'] = False
    else:
        def request(cfg, method, path, body=None):
            assert method == 'GET'
            if failure == 'offline':
                raise link.IntegrationError('transport', 'offline', True)
            assert path == '/capabilities'
            return dict(site_id='another-site')

        monkeypatch.setattr(link, 'request', request)
    link.tick()
    db.refresh(delivery)
    assert delivery.state == 'retry' and delivery.next_at == before
    assert calls == []
    assert not link._pending
