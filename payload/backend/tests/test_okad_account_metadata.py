from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember
from app.models.integration import CredentialDelivery, RecoveryJob
from app.services import reliable_integration as link, external_sub2
from app.services.okad_account_metadata import uses_supply_mail, account_metadata, sync_inventory_metadata
from tests.test_reliable_integration import CFG, setup


@pytest.mark.parametrize('mode,url,token,client,company', [
    ('auto', '', '', '', True), ('manual', '', '', '', False),
    ('auto', 'https://mail.test', '', '', False),
    ('auto', '', 'private-token', 'private-client', False),
    ('auto', '', 'private-token', '', True),
    ('auto', '', '', 'private-client', True),
])
def test_definition_matches_okad_tag(mode, url, token, client, company):
    row = SimpleNamespace(email='User@Outlook.com', otp_mode=mode, mail_url=url,
                          refresh_token=token, client_id=client)
    assert uses_supply_mail(row) is company
    assert account_metadata('external:7', row, 'site')['is_company'] is company
    assert account_metadata('pool:7', row, 'site')['is_company'] is False


def test_backfill_is_metadata_only_and_skips_ambiguous_or_foreign_sources(db, setup, monkeypatch):
    company = ExternalMember(email='Company@outlook.com', cookie='private-cookie')
    other = ExternalMember(email='other@outlook.com', mail_url='https://mail.test')
    duplicate = ExternalMember(email='duplicate@outlook.com')
    pool = AdobeMember(admin_id=0, email='duplicate@outlook.com')
    db.add_all([company, other, duplicate, pool]); db.commit()
    key = f'external:{company.id}'
    expected = account_metadata(key, company, CFG['issuer'])
    rows = [
        {'id': 1, 'email': company.email, 'imported_email': company.email},
        {'id': 2, 'email': other.email, 'imported_email': other.email},
        {'id': 3, 'email': duplicate.email, 'imported_email': duplicate.email},
        {'id': 4, 'email': company.email}, # email-only match is not an import
        {'id': 5, 'email': company.email, 'integration': {'issuer':'foreign','source_key':key}},
        {'id': 6, 'email': 'mismatch@outlook.com', 'integration': {'issuer':CFG['issuer'],'source_key':key}},
        {'id': 7, 'email': company.email, 'imported_email':company.email, 'account_metadata': expected},
        {'id': 8, 'email': company.email, 'imported_email':company.email, 'account_metadata': {**expected, 'issuer':'foreign'}},
        {'id': 9, 'email': pool.email, 'integration': {'issuer':CFG['issuer'],'source_key':f'pool:{pool.id}'}},
    ]
    original = deepcopy(rows)
    calls = []
    monkeypatch.setattr(link, 'request', lambda cfg, method, path, body: calls.append((method,path,body)))
    sync_inventory_metadata(CFG, rows)
    assert len(calls) == 1 and calls[0][:2] == ('POST', '/account-metadata')
    items = calls[0][2]['items']
    assert [r['id'] for r in items] == [1,2,9]
    assert [r['is_company'] for r in items] == [True,False,False]
    assert all(set(r) == {'id','issuer','source_key','email','is_company'} for r in items)
    assert rows == original
    assert company.cookie == 'private-cookie'
    assert not list(db.scalars(select(CredentialDelivery)))
    assert not list(db.scalars(select(RecoveryJob)))
    # Subsequent unchanged polls do not write anything.
    sync_inventory_metadata(CFG, [{'id':1,'email':company.email,'imported_email':company.email,'account_metadata':expected}])
    assert len(calls) == 1
    company.otp_mode = 'manual'; db.commit()
    sync_inventory_metadata(CFG, [{'id':1,'email':company.email,'imported_email':company.email,'account_metadata':expected}])
    assert calls[-1][2]['items'][0]['is_company'] is False


def test_metadata_runs_without_cookie_deliveries_and_respects_capability(db, setup, monkeypatch):
    row = ExternalMember(email='old@outlook.com'); db.add(row); db.commit()
    calls = []
    def request(cfg, method, path, body=None):
        calls.append((method,path))
        if path == '/capabilities': return {'site_id':CFG['site_id'],'account_metadata':True}
        if path.startswith('/accounts?'): return {'items':[{'id':1,'email':row.email,'imported_email':row.email}],'next_cursor':0}
        assert path == '/account-metadata' and method == 'POST'
        return {'updated':1}
    monkeypatch.setattr(link,'request',request)
    link.reconcile_inventory()
    assert calls[-1] == ('POST','/account-metadata')
    assert not list(db.scalars(select(CredentialDelivery)))
    calls.clear()
    monkeypatch.setattr(link,'request',lambda *args,**kwargs: calls.append(args[2]) or {'site_id':CFG['site_id']})
    link.reconcile_inventory()
    assert calls == ['/capabilities']


def test_legacy_sync_sends_metadata_and_preserves_credentials_request(monkeypatch):
    metadata = {'issuer':'site','source_key':'external:3','email':'a@outlook.com','is_company':True}
    monkeypatch.setattr(external_sub2, '_find', lambda *args,**kwargs: {'id':3,'credentials':{'model_mapping':{'a':'b'}}})
    sent = []
    monkeypatch.setattr(external_sub2, '_request', lambda cfg,method,path,body: sent.append((path,body)) or {'id':3})
    assert external_sub2._sync({}, 'a@outlook.com', 'new-cookie', {}, metadata) == 3
    assert sent[0][1]['extra']['okad_account'] == metadata
    assert sent[0][1]['credentials']['model_mapping'] == {'a':'b'}
    assert sent[0][1]['credentials']['cookie'] == 'new-cookie'


def test_metadata_batches_are_bounded(db, setup, monkeypatch):
    members = [ExternalMember(email=f'company-{i}@example.com') for i in range(205)]
    db.add_all(members); db.commit()
    remote = [{'id':i+1,'email':m.email,'imported_email':m.email} for i,m in enumerate(members)]
    calls = []
    monkeypatch.setattr(link,'request',lambda cfg,method,path,body: calls.append(body['items']))
    sync_inventory_metadata(CFG, remote)
    assert [len(batch) for batch in calls] == [200,5]
    assert len({item['id'] for batch in calls for item in batch}) == 205
