from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.crud import external_member as crud
from app.crud.setting import _set
from app.models.integration import CredentialState
from app.models.setting import Setting
from app.services import external_login, external_mail, external_sub2, firefly, reliable_integration
from app.services import supply_mail, supply_mail_health as health, supply_mail_tokens as tokens

CONFIG = '/api/external/mail/config'
TOKENS = '/api/external/mail/tokens'


@pytest.fixture
def provider(monkeypatch, SessionLocal):
    state = SimpleNamespace(libraries={'original': {'a@example.com': 7}, 'second': {'b@example.com': 7}},
                            lookups=[], tests=[], failures=set(), closed=0)

    class Mailbox:
        def __init__(self, token):
            self.token = token
            self.account_ids = {}

        def _account_id(self, email):
            state.lookups.append((self.token, email))
            if self.token in state.failures:
                raise supply_mail.SupplyMailError('supply.ink Token 已失效')
            if email not in state.libraries.get(self.token, {}):
                raise supply_mail.SupplyAccountNotFound('邮箱不在该账号库')
            self.account_ids[email] = state.libraries[self.token][email]
            return self.account_ids[email]

        def messages(self, email, **kwargs):
            assert email in self.account_ids
            if self.token in state.failures:
                raise supply_mail.SupplyMailError('取信失败')
            return [dict(timestamp=time.time(), subject='Adobe verification code 654321',
                         sender='Adobe', body='', recipient=email)]

        def test(self):
            state.tests.append(self.token)
            if self.token in state.failures:
                raise supply_mail.SupplyMailError('supply.ink Token 已失效')
            return {'ok': True, 'total': len(state.libraries.get(self.token, {}))}

        def close(self):
            state.closed += 1

    monkeypatch.setattr(supply_mail, 'SupplyMailbox', Mailbox)
    monkeypatch.setattr(tokens, 'SessionLocal', SessionLocal)
    return state


def add(client, token='second', **values):
    result = client.post(TOKENS, json={'name': '第二组', 'token': token, **values})
    assert result.status_code == 200, result.text
    return result.json()['created_id']


def test_add_preserves_original_token_and_health_and_legacy_form_only_edits_default(client, db, provider):
    client.put(CONFIG, json={'token': 'original'})
    client.post('/api/external/mail/test')
    before = db.scalar(select(Setting.value).where(Setting.key == health.HEALTH_KEY))
    second = add(client)
    saved = client.get(CONFIG)
    assert saved.headers['cache-control'] == 'no-store'
    assert saved.json()['tokens'][0]['id'] == 'default'
    assert saved.json()['tokens'][0]['token'] == 'original'
    assert db.scalar(select(Setting.value).where(Setting.key == health.HEALTH_KEY)) == before
    client.put(CONFIG, json={'token': 'replacement'})
    items = {item['id']: item for item in client.get(CONFIG).json()['tokens']}
    assert items[second]['token'] == 'second' and items['default']['token'] == 'replacement'
    client.put(CONFIG, json={'clear_token': True})
    assert client.get(CONFIG).json()['configured']  # Additional tokens remain usable.
    assert client.post('/api/external/mail/test').json()['token_id'] == second


def test_validation_duplicates_and_independent_clear_disable_remove(client, provider):
    client.put(CONFIG, json={'token': 'original'})
    second = add(client)
    assert client.post(TOKENS, json={'token': 'Bearer original'}).status_code == 400
    bad = client.post(TOKENS, json={'token': 'private-value' * 100})
    assert bad.status_code == 422 and 'private-value' not in bad.text
    client.put(TOKENS + '/' + second, json={'enabled': False})
    data = client.get(CONFIG).json()
    assert data['tokens'][1]['enabled'] is False and data['tokens'][0]['token'] == 'original'
    assert client.delete(TOKENS + '/default').status_code == 400
    assert client.delete(TOKENS + '/' + second).status_code == 200
    assert len(client.get(CONFIG).json()['tokens']) == 1
    assert client.put(TOKENS + '/' + second, json={'token': 'new'}).status_code == 400


def test_each_token_has_its_own_hourly_result_and_failure_does_not_skip_others(client, SessionLocal, monkeypatch, provider):
    client.put(CONFIG, json={'token': 'original'})
    second = add(client)
    monkeypatch.setattr(health, 'SessionLocal', SessionLocal)
    provider.failures.add('original')
    with SessionLocal() as db:
        for item in tokens.entries(db):
            health.reset(db, item.token, token_id=item.id, now=0)
        db.commit()
    health.tick()
    health.tick()
    items = {item['id']: item for item in client.get(CONFIG).json()['tokens']}
    assert items['default']['health']['status'] == 'error'
    assert items[second]['health']['status'] == 'ok'
    assert sorted(provider.tests) == ['original', 'second']
    for item in items.values():
        assert item['health']['next_check_at'] - item['health']['checked_at'] == 3600


def test_slow_check_does_not_block_other_rows_and_stale_result_is_discarded(client, SessionLocal, monkeypatch, provider):
    client.put(CONFIG, json={'token': 'original'})
    second = add(client)
    entered, finish = threading.Event(), threading.Event()
    original = supply_mail.SupplyMailbox

    class SlowMailbox(original):
        def test(self):
            if self.token == 'original':
                entered.set()
                assert finish.wait(5)
            return super().test()

    monkeypatch.setattr(supply_mail, 'SupplyMailbox', SlowMailbox)
    def check():
        with SessionLocal() as db:
            return health.check(db)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(check)
        try:
            assert entered.wait(2)
            assert client.put(TOKENS + '/' + second, json={'name': '独立更新'}).status_code == 200
            assert client.get(CONFIG).status_code == 200
            assert client.put(CONFIG, json={'token': 'replacement'}).status_code == 200
        finally:
            finish.set()
        with pytest.raises(supply_mail.SupplyMailError, match='配置已变更'):
            future.result(timeout=3)
    assert client.get(CONFIG).json()['tokens'][0]['health']['status'] == 'untested'


def test_routing_uses_exact_email_scopes_account_ids_and_remembers_the_successful_token(client, db, provider):
    client.put(CONFIG, json={'token': 'original'})
    second = add(client)
    route = tokens.routing(db, 'B@EXAMPLE.COM')
    box = route.mailbox()
    assert box.messages('b@example.com')[0]['recipient'] == 'b@example.com'
    assert route.pinned.id == second
    box.close()
    assert provider.lookups == [('original', 'b@example.com'), ('second', 'b@example.com')]
    provider.lookups.clear()
    next_box = tokens.mailbox(db, 'b@example.com')
    next_box.messages('b@example.com')
    next_box.close()
    assert provider.lookups == [('second', 'b@example.com')]
    with pytest.raises(supply_mail.SupplyMailError, match='不一致'):
        route.mailbox().messages('a@example.com')


def test_inflight_routing_is_pinned_and_token_changes_do_not_replace_it(client, db, provider):
    client.put(CONFIG, json={'token': 'original'})
    second = add(client)
    route = tokens.routing(db, 'b@example.com')
    box = route.mailbox()
    box.prepare()
    box.close()
    provider.libraries['original']['b@example.com'] = 99
    client.put(TOKENS + '/' + second, json={'token': 'replacement'})
    provider.lookups.clear()
    box = route.mailbox()
    box.messages('b@example.com')
    box.close()
    assert provider.lookups == [('second', 'b@example.com')]
    provider.failures.add('second')
    with pytest.raises(supply_mail.SupplyMailError):
        route.mailbox().prepare()
    assert not any(token == 'original' for token, _ in provider.lookups)


def test_confirmed_miss_and_provider_error_are_distinct_and_new_token_invalidates_miss(client, db, provider):
    client.put(CONFIG, json={'token': 'original'})
    add(client)
    with pytest.raises(supply_mail.SupplyMailError, match='未匹配'):
        tokens.mailbox(db, 'missing@example.com').prepare()
    assert not tokens.available(db, 'missing@example.com')
    cfg = {'enabled': True, 'site_id': 'site', 'integration_key': 'key'}
    row = SimpleNamespace(email='missing@example.com', otp_mode='auto', mail_url='', refresh_token='', client_id='')
    with pytest.raises(reliable_integration.IntegrationError) as error:
        reliable_integration.check_capability(db, 'external:1', row, cfg)
    assert error.value.code == 'missing_mail'
    add(client, 'third')
    assert tokens.available(db, 'missing@example.com')
    provider.failures.add('original')
    with pytest.raises(supply_mail.SupplyMailError, match='暂时无法'):
        tokens.mailbox(db, 'uncertain@example.com').prepare()
    assert tokens.available(db, 'uncertain@example.com')
    # Saving/testing credentials never changes the Sub2 identity or writes a Cookie.
    assert db.scalar(select(CredentialState)) is None


def test_multi_token_login_and_mail_view_keep_existing_sub2_identity(client, db, SessionLocal, monkeypatch, provider):
    client.put(CONFIG, json={'token': 'original'})
    add(client)
    crud.import_lines(db, 'b@example.com')
    member = crud.get_by_email(db, 'b@example.com')
    member.cookie = 'ims_sid=old'
    member.sub2_links = {'https://sub2.test': {'account_id': 123, 'status': 'ok'}}
    db.commit()
    mid = member.id
    synced = []
    monkeypatch.setattr(external_login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(external_sub2, 'after_login', lambda identifier, **kw: synced.append(identifier))
    def register(**kwargs):
        assert kwargs['otp_poller']('b@example.com', timeout=1) == '654321'
        return {'cookie': 'ims_sid=fresh', 'credits': 4000, 'credits_total': 4000}
    monkeypatch.setattr(firefly, 'register_account', register)
    assert external_login.login_and_store(mid)['ok']
    db.refresh(member)
    assert member.id == mid and member.cookie == 'ims_sid=fresh'
    assert member.sub2_links['https://sub2.test']['account_id'] == 123
    assert synced == [mid]
    credential = db.get(CredentialState, 'external:' + str(mid))
    assert credential.email == 'b@example.com'
    assert external_mail.list_messages(db, member)['messages'][0]['recipient'] == 'b@example.com'
    client.put(CONFIG, json={'clear_token': True})
    assert external_login.login_and_store(mid)['ok']  # An extra Token also works without a default Token.
    db.refresh(member)
    assert member.sub2_links['https://sub2.test']['account_id'] == 123
    provider.failures.update({'original', 'second'})
    synced.clear()
    assert not external_login.login_and_store(mid)['ok']
    db.refresh(member)
    assert member.cookie == 'ims_sid=fresh' and member.sub2_links['https://sub2.test']['account_id'] == 123
    assert synced == [] and db.get(CredentialState, 'external:' + str(mid)).version == credential.version


def test_extra_token_routes_require_login(client):
    from app.api.deps import get_current_user
    from app.main import app
    app.dependency_overrides.pop(get_current_user)
    for method, path, body in [('post', TOKENS, {'token': 'secret'}), ('put', TOKENS+'/default', {'token':'secret'}),
                               ('post', TOKENS+'/default/test', None), ('delete', TOKENS+'/x', None)]:
        result = getattr(client, method)(path, **({'json': body} if body else {}))
        assert result.status_code == 401
