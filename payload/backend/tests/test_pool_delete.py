from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember


def list_all(client):
    response = client.get('/api/pool', params={'pool_type': 'all', 'registered_only': False})
    assert response.status_code == 200
    return response.json()['items']


def test_deleted_mother_mirror_does_not_reappear(client, db):
    mother = AdobeAccount(email='mother@example.com', admin_token='keep-token', org_id='keep-org')
    db.add(mother)
    db.commit()
    rows = list_all(client)
    assert len(rows) == 1 and rows[0]['is_admin']
    response = client.post('/api/pool/batch-delete', json={'ids': [rows[0]['id']]})
    assert response.status_code == 200 and response.json()['success']
    assert list_all(client) == []
    assert list_all(client) == []  # Reopening / refreshing is also stable.
    db.expire_all()
    assert db.get(AdobeAccount, mother.id).admin_token == 'keep-token'
    assert db.get(AdobeAccount, mother.id).org_id == 'keep-org'


def test_delete_only_selected_imported_accounts(client, db):
    members = [AdobeMember(admin_id=0, email=f'import{i}@example.com', is_imported=True,
                           registered=True, credits=4000, cookie='keep-unselected') for i in range(3)]
    db.add_all(members)
    db.commit()
    ids = [m.id for m in members]
    response = client.post('/api/pool/batch-delete', json={'ids': ids[:2]})
    assert response.json()['success']
    assert [r['id'] for r in list_all(client)] == ids[2:]
    db.expire_all()
    assert db.get(AdobeMember, ids[2]).cookie == 'keep-unselected'
    assert client.get('/api/dashboard/overview').json()['members']['registered'] == 1


def test_mixed_delete_keeps_mother_and_updates_child_count(client, db, monkeypatch):
    from app.api.routes import pool
    calls = []
    monkeypatch.setattr(pool.adobe_admin, 'remove_member', lambda **kwargs: calls.append(kwargs) or {'ok': True})
    mother = AdobeAccount(email='mother@example.com', admin_token='token', org_id='org', member_count=2)
    db.add(mother)
    db.flush()
    children = [AdobeMember(admin_id=mother.id, email=f'child{i}@example.com', member_id=f'c{i}') for i in range(2)]
    db.add_all(children)
    db.commit()
    rows = list_all(client)
    mirror = next(r for r in rows if r['is_admin'])
    response = client.post('/api/pool/batch-delete', json={'ids': [mirror['id'], children[0].id]})
    assert response.json()['success']
    assert [r['id'] for r in list_all(client)] == [children[1].id]
    db.expire_all()
    assert mother.member_count == 1
    assert len(calls) == 1 and calls[0]['member_id'] == 'c0'


def test_empty_delete_does_not_change_pool(client, db):
    mother = AdobeAccount(email='mother@example.com')
    db.add(mother)
    db.commit()
    before = list_all(client)
    response = client.post('/api/pool/batch-delete', json={'ids': []})
    assert response.status_code == 200
    assert list_all(client) == before


def test_other_mothers_still_get_pool_mirrors(client, db):
    first = AdobeAccount(email='first@example.com')
    db.add(first)
    db.commit()
    mirror = list_all(client)[0]
    client.post('/api/pool/batch-delete', json={'ids': [mirror['id']]})
    db.add(AdobeAccount(email='second@example.com'))
    db.commit()
    assert [r['email'] for r in list_all(client)] == ['second@example.com']


def test_existing_database_migration_preserves_mother_visibility(engine, db, monkeypatch):
    from sqlalchemy import text
    from app.db import init_db
    db.add(AdobeAccount(email='old@example.com'))
    db.commit()
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE adobe_accounts DROP COLUMN pool_hidden'))
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT pool_hidden FROM adobe_accounts')).scalar() == 0
