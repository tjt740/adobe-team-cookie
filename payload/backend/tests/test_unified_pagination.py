import pytest

from app.models.adobe_account import AdobeAccount
from app.models.adobe_member import AdobeMember
from app.models.email import Email
from app.models.external_member import ExternalMember


def test_all_database_lists_accept_presets_and_custom_sizes(client, db):
    account = AdobeAccount(email='owner@example.test')
    db.add(account)
    db.flush()
    for i in range(1207):
        db.add(ExternalMember(email=f'external{i}@example.test'))
        db.add(Email(email=f'email{i}@example.test'))
        db.add(AdobeMember(admin_id=account.id, email=f'child{i}@example.test', is_imported=True))
        if i:
            db.add(AdobeAccount(email=f'owner{i}@example.test'))
    db.commit()
    paths = ['/api/external/members', '/api/adobe-accounts', '/api/emails', '/api/pool',
             f'/api/adobe-accounts/{account.id}/members', '/api/integration/sources']
    for path in paths:
        for size in [100, 200, 300, 400, 500, 1000, 137, 1200]:
            response = client.get(path, params={'page': 1, 'size': size})
            assert response.status_code == 200, (path, size, response.text)
            body = response.json()
            assert body['size'] == size and len(body['items']) == size, (path, size)
        first = client.get(path, params={'page': 1, 'size': 1000}).json()
        second = client.get(path, params={'page': 2, 'size': 1000}).json()
        key = 'source_key' if path.endswith('/sources') else 'id'
        assert not {item[key] for item in first['items']} & {item[key] for item in second['items']}
        assert first['total'] == second['total']
        for size in [0, -1, 1.5, 10001]:
            assert client.get(path, params={'size': size}).status_code == 422, (path, size)


def test_recovery_job_pagination_and_log_limits(client, db):
    from app.models.integration import RecoveryJob
    for i in range(1107):
        db.add(RecoveryJob(id=f'job{i:04d}', source_key=f'external:{i}', email=f'job{i}@example.test',
                           target='', state='done', created_at=i, updated_at=i))
    db.commit()
    first = client.get('/api/integration/status', params={'jobs_size': 1000}).json()
    second = client.get('/api/integration/status', params={'jobs_size': 1000, 'jobs_page': 2}).json()
    assert first['jobs_total'] == second['jobs_total'] == 1107
    assert len(first['jobs']) == 1000 and len(second['jobs']) == 107
    assert not {job['job_id'] for job in first['jobs']} & {job['job_id'] for job in second['jobs']}
    assert client.get('/api/logs', params={'limit': 10000}).status_code == 200
