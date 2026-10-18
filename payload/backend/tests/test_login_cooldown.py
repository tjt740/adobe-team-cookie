"""No Adobe or mail traffic: durable cooldown and duplicate-call regressions."""
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.integration import LoginLease
from app.services import login_coordinator as coordinator


@pytest.fixture
def factory(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path/'cooldown.db'),
                           connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def run(factory, action, source='external:1', email='Same@Example.test', **kw):
    return coordinator.run(source, email, action, factory,
                           lambda db: {'cookie': 'fixture'}, **kw)


def test_concurrent_automatic_calls_join_one_login(factory):
    calls = []
    started = time.time()
    def login():
        calls.append(1)
        time.sleep(.15)
        return {'ok': True, 'cookie': 'fixture'}
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: run(factory, login, automatic=True,
                                              requested_at=started), range(16)))
    assert len(calls) == 1
    assert all(x['ok'] and x['cookie'] == 'fixture' for x in results)
    # A later caller with a new source ID and differently cased email cannot
    # bypass the per-email cooldown, even with another session factory.
    blocked = run(factory, lambda: pytest.fail('must not login again'),
                  source='pool:99', email='same@example.test', automatic=True)
    assert blocked['code'] == 'login_cooldown'
    assert blocked['retry_after']-time.time() > 890


def test_failed_login_cooldown_and_expiry(factory):
    assert not run(factory, lambda: {'ok': False}, automatic=True)['ok']
    result = run(factory, lambda: pytest.fail('failure cooldown'), automatic=True)
    assert result['code'] == 'login_cooldown'
    assert 290 < result['retry_after']-time.time() <= 300
    with factory() as db:
        row = db.get(LoginLease, 'same@example.test')
        row.result = {'ok': False, 'retry_after': time.time()-1}
        row.expires_at = time.time()-301
        db.commit()
    assert run(factory, lambda: {'ok': True}, automatic=True)['ok']


def test_explicit_manual_login_updates_automatic_cooldown(factory):
    assert run(factory, lambda: {'ok': True}, automatic=True)['ok']
    assert run(factory, lambda: {'ok': True}, automatic=False)['ok']
    assert run(factory, lambda: pytest.fail('automatic caller after manual login'), automatic=True)['code'] == 'login_cooldown'


def test_interrupted_owner_does_not_allow_immediate_automatic_retry(factory):
    with factory() as db:
        db.add(LoginLease(email='same@example.test', source_key='external:1',
                         owner='old-process', expires_at=time.time()-1, result=None))
        db.commit()
    assert run(factory, lambda: pytest.fail('interrupted owner'), automatic=True)['code'] == 'login_cooldown'
