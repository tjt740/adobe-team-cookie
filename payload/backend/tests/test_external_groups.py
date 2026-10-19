from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.crud import external_member as crud
from app.models.external_member import ExternalMember, ExternalMemberGroup
from app.services import okad_account_metadata as metadata
from app.services.job_manager import JOBS


@pytest.fixture(autouse=True)
def no_remote_sync(monkeypatch):
    monkeypatch.setattr(metadata, 'sync_current_metadata', lambda: None)


def group(client, name='客户 A'):
    response = client.post('/api/external/groups', json={'name': name})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_create_validate_duplicates_and_list_empty_groups(client):
    gid = group(client, '  客户 A  ')
    assert client.get('/api/external/groups').json() == [{'id': gid, 'name': '客户 A', 'count': 0}]
    for name in ('', '   ', 'x' * 65):
        assert client.post('/api/external/groups', json={'name': name}).status_code == 422
    assert client.post('/api/external/groups', json={'name': '客户 A'}).status_code == 409
    group(client, 'Team')
    assert client.post('/api/external/groups', json={'name': 'team'}).status_code == 409


def test_import_preserves_or_explicitly_moves_groups(client, db, monkeypatch):
    gid = group(client)
    monkeypatch.setattr(JOBS, 'start', lambda *a, **kw: SimpleNamespace(id=987))
    payload = {'content': 'group@example.com', 'group_id': gid}
    assert client.post('/api/external/members/import', json=payload).status_code == 200
    row = crud.get_by_email(db, 'group@example.com')
    assert row.group_id == gid
    row.cookie = 'saved-cookie'; row.note = 'saved note'; db.commit()
    for values, expected in [({}, gid), ({'group_id': None}, None), ({'group_id': gid}, gid)]:
        response = client.post('/api/external/members/import', json={
            'content': row.email, 'on_duplicate': 'overwrite', **values})
        assert response.status_code == 200, response.text
        db.expire_all()
        assert row.group_id == expected
        assert (row.cookie, row.note) == ('saved-cookie', 'saved note')
    assert client.post('/api/external/members/import', json={**payload, 'group_id': 999}).status_code == 404
    assert client.post('/api/external/members/import', json={**payload, 'group_id': 0}).status_code == 422


def test_groups_and_three_types_filter_before_pagination_export_and_login(client, db, monkeypatch):
    gid = group(client)
    rows = [ExternalMember(email=f'g{i}@example.com', otp_mode=mode, group_id=gid,
                           cookie=f'cookie-{i}', subscription_ok=True)
            for i, mode in enumerate(['auto', 'vietnam', 'manual', 'vietnam'])]
    rows.append(ExternalMember(email='ungrouped@example.com', otp_mode='vietnam', cookie='other-cookie'))
    db.add_all(rows); db.commit()
    filters = {'group_id': gid, 'account_type': 'vietnam', 'subscription_ok': True}
    for page, row in [(1, rows[3]), (2, rows[1])]:
        response = client.get('/api/external/members', params={**filters, 'page': page, 'size': 1})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['total'] == 2
        assert [(r['id'], r['group_id'], r['group_name']) for r in body['items']] == [(row.id, gid, '客户 A')]
    assert client.get('/api/external/members/export', params=filters).json() == [{'cookie': rows[3].cookie}, {'cookie': rows[1].cookie}]
    started = []
    class Job:
        def to_dict(self):
            return dict(id=999, type='external_login', status='running', target=2, success=0, fail=0, logs=[])
    def start(*args, meta):
        started.extend(meta['member_ids'])
        return Job()
    monkeypatch.setattr(JOBS, 'start', start)
    response = client.post('/api/external/members/batch-login-filter', json=filters)
    assert response.status_code == 200, response.text
    assert started == [rows[3].id, rows[1].id]
    for kind, expected in [('company', [rows[0].id]), ('non_company', [rows[2].id])]:
        result = client.get('/api/external/members', params={'group_id': gid, 'account_type': kind}).json()
        assert [r['id'] for r in result['items']] == expected
    assert client.get('/api/external/members', params={'group_id': 0}).json()['items'][0]['id'] == rows[4].id
    assert client.get('/api/external/groups').json()[0]['count'] == 4
    assert client.get('/api/external/members', params={'group_id': -1}).status_code == 422


def test_assign_is_atomic_and_can_clear_without_changing_credentials(client, db, monkeypatch):
    gid = group(client)
    rows = [ExternalMember(email=f'assign{i}@example.com', cookie='private', note='keep') for i in range(2)]
    db.add_all(rows); db.commit()
    calls = []
    monkeypatch.setattr(metadata, 'sync_current_metadata', lambda: calls.append('metadata only'))
    response = client.patch('/api/external/members/group', json={'ids': [r.id for r in rows] + [rows[0].id], 'group_id': gid})
    assert response.status_code == 200 and response.json()['updated'] == 2
    assert calls == ['metadata only']
    db.expire_all()
    assert all(r.group_id == gid and r.cookie == 'private' and r.note == 'keep' for r in rows)
    assert client.patch('/api/external/members/group', json={'ids': [rows[0].id, 999], 'group_id': None}).status_code == 404
    db.expire_all(); assert rows[0].group_id == gid
    assert client.patch('/api/external/members/group', json={'ids': [rows[0].id], 'group_id': None}).status_code == 200
    db.expire_all(); assert rows[0].group_id is None


def test_metadata_has_group_and_vietnam_type_and_clears_group(db):
    g = ExternalMemberGroup(name='越南客户', name_key='越南客户')
    row = ExternalMember(email='vn@example.com', otp_mode='vietnam', group=g)
    db.add(row); db.commit()
    result = metadata.account_metadata(f'external:{row.id}', row, 'site')
    assert (result['account_type'], result['is_company'], result['group_id'], result['group_name']) == ('vietnam', False, g.id, g.name)
    row.group = None; db.commit()
    assert metadata.account_metadata(f'external:{row.id}', row, 'site')['group_id'] is None


def test_existing_database_migration_retains_accounts(tmp_path, monkeypatch):
    from app.db import init_db
    from app.db.session import Base
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT, created_at DATETIME, updated_at DATETIME)'))
        conn.execute(text("INSERT INTO external_members (id,email) VALUES (7,'old@example.com')"))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations()
    init_db._run_migrations()
    assert 'group_id' in {c['name'] for c in inspect(engine).get_columns('external_members')}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT id,email,group_id FROM external_members')).one() == (7, 'old@example.com', None)
    engine.dispose()
