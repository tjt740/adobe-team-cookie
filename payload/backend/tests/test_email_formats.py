from datetime import datetime

import pytest
from app.models.email import Email


def add_email(db, **values):
    row = Email(email='history@example.com', password='Synthetic<&Password',
                client_id='11111111-2222-3333-4444-555555555555',
                refresh_token='M.'+'synthetic-token-'*600, **values)
    db.add(row)
    db.commit()
    return row


def test_complete_legacy_credentials_and_both_formats(client, db):
    row = add_email(db, mail_url='https://mail.example.test/read?key=synthetic&email_id=abc',
                    import_batch=None, imported_at=datetime(2026, 10, 1))
    before = {col.name: getattr(row, col.name) for col in Email.__table__.columns}
    for style, fields, separator in (
        ('standard', [row.email, row.password, row.client_id, row.refresh_token, row.mail_url], '----'),
        ('pipe', [row.email, row.password, row.refresh_token, row.client_id, row.mail_url], '|'),
    ):
        response = client.post('/api/emails/formats', json={'ids': [row.id], 'format': style})
        assert response.status_code == 200
        assert response.json() == dict(total=1, content=separator.join(fields))
    db.refresh(row)
    assert {col.name: getattr(row, col.name) for col in Email.__table__.columns} == before


def test_all_matching_records_and_combined_filters(client, db):
    db.add_all([Email(email=f'old{i}@example.test', import_batch='20261024', is_used=True,
                      remark='历史批次') for i in range(225)])
    db.add_all([Email(email='other-batch@example.test', import_batch='20261025', is_used=True),
                Email(email='unused@example.test', import_batch='20261024', is_used=False)])
    db.commit()
    result = client.post('/api/emails/formats', json={
        'keyword': ' 历史批次 ', 'import_batch': '20261024', 'is_used': True}).json()
    assert result['total'] == 225
    lines = result['content'].splitlines()
    assert len(lines) == 225
    assert lines[0] == 'old224@example.test'+'----'*3
    assert lines[-1] == 'old0@example.test'+'----'*3
    assert client.post('/api/emails/formats', json={'is_used': False}).json()['total'] == 1
    assert client.post('/api/emails/formats', json={'keyword': 'does-not-exist'}).json() == dict(content='', total=0)


def test_selection_never_expands_to_all_and_supports_mail_links(client, db):
    first = add_email(db, mail_url='moemail://edu6.site?api_key=mk_synthetic&email_id=17')
    second = Email(email='only-email@example.test')
    db.add(second)
    db.commit()
    assert client.post('/api/emails/formats', json={'ids': []}).json() == dict(content='', total=0)
    assert client.post('/api/emails/formats', json={'ids': [99999]}).json()['total'] == 0
    result = client.post('/api/emails/formats', json={'ids': [first.id, first.id]}).json()
    assert result['total'] == 1 and result['content'].endswith('----'+first.mail_url)
    result = client.post('/api/emails/formats', json={'ids': [second.id], 'format': 'pipe'}).json()
    assert result == dict(content='only-email@example.test|||', total=1)
    assert client.post('/api/emails/formats', json={}).json()['total'] == 2


@pytest.mark.parametrize('payload', [{'format': 'invalid'}, {'import_batch': '20260230'}, {'ids': ['invalid']}])
def test_invalid_requests(client, payload):
    assert client.post('/api/emails/formats', json=payload).status_code == 422


def test_requires_authenticated_user(client):
    from app.api.deps import get_current_user
    from app.main import app
    app.dependency_overrides.pop(get_current_user)
    assert client.post('/api/emails/formats', json={}).status_code == 401
