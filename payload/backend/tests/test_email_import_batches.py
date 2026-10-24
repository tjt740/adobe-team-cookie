from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

from app.crud import email as crud
from app.services import external_sub2, external_sub2_stock as stock

read_stock = stock.emails_in_stock


@pytest.fixture(autouse=True)
def inventory(monkeypatch):
    calls = []
    def read(db):
        calls.append(True)
        return {'stock@example.com'}
    monkeypatch.setattr(stock, 'emails_in_stock', read)
    return calls


@pytest.mark.parametrize('path,base', [
    ('/api/emails', {'email': 'single@example.com'}),
    ('/api/emails/batch-import', {'content': 'batch@example.com----password'}),
    ('/api/emails/moemail/generate', {'api_key': 'synthetic'}),
])
def test_import_fields_required_and_validated(client, inventory, path, base):
    for extra in ({}, {'import_batch': '20261024'}, {'on_duplicate': 'skip'},
                  {'import_batch': '2026-10-24', 'on_duplicate': 'skip'},
                  {'import_batch': '20260230', 'on_duplicate': 'skip'},
                  {'import_batch': '20261024', 'on_duplicate': ''},
                  {'import_batch': '20261024', 'on_duplicate': 'delete'},
                  {'import_batch': 20261024, 'on_duplicate': 'skip'}):
        assert client.post(path, json={**base, **extra}).status_code == 422
    assert not inventory


def test_batch_metadata_duplicates_and_filtering(client, db, inventory):
    payload = dict(content='stock@example.com----first\nfree@example.com----pass\nstock@example.com----second',
                   import_batch='20261024', on_duplicate='skip')
    result = client.post('/api/emails/batch-import', json=payload).json()
    assert (result['created'], result['skipped'], result['failed']) == (2, 1, 0)
    assert len(inventory) == 1
    used = crud.get_by_email(db, 'stock@example.com')
    free = crud.get_by_email(db, 'free@example.com')
    assert used.is_used and used.used_at and not free.is_used and free.used_at is None
    assert used.password == 'first' and used.import_batch == '20261024'
    assert isinstance(used.import_batch, str)
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - used.imported_at).total_seconds()) < 10
    original = used.imported_at
    created = used.created_at
    result = client.post('/api/emails/batch-import', json={**payload, 'import_batch': '20261025'}).json()
    assert result['skipped'] == 3
    db.refresh(used)
    assert used.import_batch == '20261024' and used.imported_at == original
    assert len(inventory) == 1
    result = client.post('/api/emails/batch-import', json={**payload, 'import_batch': '20261025', 'on_duplicate': 'overwrite'}).json()
    assert result['updated'] == 3
    db.refresh(used)
    assert used.password == 'second' and used.import_batch == '20261025'
    assert used.imported_at > original and used.created_at == created
    assert len(inventory) == 2
    crud.batch_import(db, 'another@example.com', import_batch='20261024')
    assert client.get('/api/emails/import-batches').json() == ['20261025', '20261024']
    response = client.get('/api/emails', params={'import_batch': '20261025', 'is_used': True, 'keyword': 'stock', 'size': 1}).json()
    assert response['total'] == 1 and response['items'][0]['email'] == used.email
    assert response['items'][0]['import_batch'] == '20261025'
    assert response['items'][0]['imported_at']
    assert client.get('/api/emails', params={'import_batch': '20261026'}).json()['total'] == 0
    assert client.get('/api/emails', params={'import_batch': '20261301'}).status_code == 422


def test_single_import_duplicate_policy_and_manual_toggle(client, db, inventory):
    payload = dict(email='stock@example.com', password='first', import_batch='20261024', on_duplicate='skip')
    first = client.post('/api/emails', json=payload).json()
    assert first['is_used'] is True
    changed = {**payload, 'import_batch': '20261025', 'password': 'second'}
    assert client.post('/api/emails', json=changed).json() == first
    assert len(inventory) == 1
    updated = client.post('/api/emails', json={**changed, 'on_duplicate': 'overwrite'}).json()
    assert updated['id'] == first['id'] and updated['password'] == 'second'
    assert updated['import_batch'] == '20261025' and updated['created_at'] == first['created_at']
    assert client.put(f"/api/emails/{first['id']}", json={'is_used': False}).json()['used_at'] is None
    assert client.get('/api/emails').json()['items'][0]['is_used'] is False
    # Editing credentials keeps the import provenance and manually set state.
    edited = client.put(f"/api/emails/{first['id']}", json={'password': 'edited'}).json()
    assert edited['imported_at'] == updated['imported_at'] and edited['import_batch'] == '20261025'
    assert not edited['is_used'] and len(inventory) == 2


def test_moemail_import_includes_batch(client, monkeypatch):
    from app.api.routes import email as routes
    class Response:
        status_code = 201
        def json(self):
            return {'email': 'made@edu6.site', 'id': 'synthetic-id'}
    monkeypatch.setattr(routes.requests, 'post', lambda *a, **kw: Response())
    result = client.post('/api/emails/moemail/generate', json=dict(
        api_key='synthetic', count=1, domain='edu6.site', import_batch='20261025', on_duplicate='skip'))
    assert result.status_code == 200 and result.json()['created'] == 1
    row = client.get('/api/emails').json()['items'][0]
    assert row['import_batch'] == '20261025' and row['imported_at'] and not row['is_used']


@pytest.mark.parametrize('configured,ok', [(False, False), (True, False), (True, True)])
def test_inventory_defaults_only_confirmed_stock(db, monkeypatch, configured, ok):
    # Exercise the real helper, independent of local external-member records.
    monkeypatch.setattr(external_sub2, 'config', lambda db: {
        'base_url': 'https://sub2.example', 'admin_token': 'synthetic' if configured else ''})
    monkeypatch.setattr(stock, '_snapshot', lambda cfg: {'ok': ok, 'by_email': {'stock@example.com': [17]}})
    assert read_stock(db) == ({'stock@example.com'} if configured and ok else set())


def test_legacy_migration_is_repeatable_and_preserves_provenance(monkeypatch, tmp_path):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE emails (id INTEGER PRIMARY KEY, email TEXT, created_at DATETIME, is_used BOOLEAN)'))
        conn.execute(text("INSERT INTO emails VALUES (1, 'legacy@example.com', '2026-10-01 04:05:06', 1)"))
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations()
    init_db._run_migrations()
    with engine.begin() as conn:
        row = conn.execute(text('SELECT * FROM emails')).mappings().one()
        assert row['import_batch'] is None
        assert row['imported_at'] == row['created_at'] == '2026-10-01 04:05:06'
        assert row['is_used'] == 1
    assert 'ix_emails_import_batch' in {i['name'] for i in inspect(engine).get_indexes('emails')}
    engine.dispose()
