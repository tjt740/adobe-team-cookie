from sqlalchemy import create_engine, text

from app.models.external_member import ExternalMember
from app.services import external_login


def test_query_failure_survives_api_and_login_failure_then_clears_on_recovery(db, client, monkeypatch, SessionLocal):
    member = ExternalMember(email='credits@example.test')
    db.add(member); db.commit()
    monkeypatch.setattr(external_login, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(external_login, '_login_with_proxy_retry', lambda **kw: ({
        'cookie': 'private-cookie', 'access_token': 'private-token',
        'credits_error': 'Adobe 拒绝查询（HTTP 451 / 10009）',
    }, None))
    result = external_login.login_and_store(member.id, sync_to_sub2=False)
    assert result['ok'] is True
    row = client.get('/api/external/members').json()['items'][0]
    assert row['login_status'] == 'ok' and row['has_cookie']
    assert row['credits_available'] is None and row['credits_total'] is None
    assert row['credits_error'] == 'Adobe 拒绝查询（HTTP 451 / 10009）'
    assert 'private-' not in str(row)
    external_login._save_failure(member.id, 'login_failed', 'login failed')
    assert client.get('/api/external/members').json()['items'][0]['credits_error'] == row['credits_error']
    external_login._save_success(member.id, {'cookie': 'new', 'credits': 0, 'credits_total': 4000,
                                            'credits_error': row['credits_error']}, True)
    row = client.get('/api/external/members').json()['items'][0]
    assert row['credits_error'] == '' and row['subscription_ok'] is True
    assert row['credits_available'] == 0


def test_legacy_rows_keep_unknown_error_and_additive_migration_preserves_data(tmp_path, monkeypatch):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT, cookie TEXT)'))
        conn.execute(text("INSERT INTO external_members VALUES (1, 'legacy@example.test', 'keep-cookie')"))
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations(); init_db._run_migrations()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT cookie, credits_error FROM external_members')).fetchone() == ('keep-cookie', '')
    engine.dispose()
