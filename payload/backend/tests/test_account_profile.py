from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text

from app.models.external_member import ExternalMember
from app.services.account_profile import build_profile_snapshot
from app.services import external_login, firefly


def test_personal_identity_with_org_subscription_is_not_org_membership():
    snapshot = build_profile_snapshot({
        'check_account_type': 'type1', 'check_user_id': 'person@AdobeID',
        'abp_subscriptions': [{'owner_id': 'plan@AdobeOrg', 'status': 'ACTIVE', 'token': 'secret'}],
        'available_profiles': [{'profile_id': 'person@AdobeID', 'name': 'Personal Account', 'kind': 'personal'}],
        'token_claims': {'access_token': 'secret'},
    }, 'person@AdobeID')
    assert snapshot['current_kind'] == 'personal'
    assert snapshot['current_org_id'] == ''
    assert snapshot['subscription_owners'] == [{'owner_id': 'plan@AdobeOrg', 'status': 'ACTIVE'}]
    assert 'secret' not in str(snapshot)


def test_current_org_uses_verified_identity_and_preserves_other_profiles():
    snapshot = build_profile_snapshot({
        'check_account_type': 'type2e', 'check_user_id': 'member@org.e', 'check_owner_org': 'org@AdobeOrg',
        'available_profiles': [
            {'profile_id': 'person@AdobeID', 'name': 'Personal Account', 'kind': 'personal'},
            {'profile_id': 'member@org.e', 'name': 'Design Team', 'kind': 'organization'},
            {'profile_id': 'member@other.e', 'name': 'Other Team', 'kind': 'organization'},
        ], 'profiles_complete': True,
    }, 'member@org.e')
    assert snapshot['current_kind'] == 'organization'
    assert snapshot['current_profile_name'] == 'Design Team'
    assert snapshot['current_org_id'] == 'org@AdobeOrg'
    assert len(snapshot['profiles']) == 3
    assert snapshot['credits_account_id'] == 'member@org.e'
    assert snapshot['profiles_complete'] is True


def test_missing_metadata_stays_unknown_and_never_guesses_from_credits():
    snapshot = build_profile_snapshot({'credits_total': 4000}, 'person@AdobeID')
    assert snapshot['current_kind'] == 'unknown'
    assert snapshot['current_org_id'] == ''
    assert snapshot['profiles_complete'] is False


def test_collect_profiles_retains_all_and_does_not_change_selection():
    links = [
        {'entitlementAccountUserId': 'dead.e', 'description': 'Old Deleted', 'status': 'active'},
        {'entitlementAccountUserId': 'live.e', 'description': 'Design Team', 'status': 'active'},
        {'entitlementAccountUserId': 'off.e', 'description': 'Off Team', 'status': 'disabled'},
    ]
    response = SimpleNamespace(status_code=200, json=lambda: {'profileData': {'links': links}})
    auth = SimpleNamespace(client=SimpleNamespace(get=lambda *a, **kw: response), client_id='test', headers=lambda: {})
    result = firefly._pick_enterprise_profile(auth, lambda line: None,
        [{'userId': 'person@AdobeID', 'description': 'Personal Account'}])
    assert result == ('live.e', 'Design Team')
    assert len(auth._available_profiles) == 4
    assert auth._available_profiles[-1]['status'] == 'disabled'
    assert auth._profiles_complete is True


def test_failed_profile_request_is_partial_not_no_organizations():
    def fail(*a, **kw):
        raise RuntimeError('timeout')
    auth = SimpleNamespace(client=SimpleNamespace(get=fail), client_id='test', headers=lambda: {})
    assert firefly._pick_enterprise_profile(auth, lambda line: None, []) == ('', '')
    assert auth._profiles_complete is False


def test_profile_persists_and_list_api_does_not_expose_tokens(db, client, monkeypatch, SessionLocal):
    member = ExternalMember(email='profile@example.test', client_id='cid', refresh_token='mail-secret')
    db.add(member); db.commit()
    monkeypatch.setattr(external_login, 'SessionLocal', SessionLocal)
    profile = build_profile_snapshot({'check_account_type': 'type1', 'check_user_id': 'p@AdobeID'}, 'p@AdobeID')
    profile['access_token'] = 'secret-that-must-not-persist'
    external_login._save_success(member.id, {'cookie': 'private-cookie', 'access_token': 'private-token',
                                           'account_profile': profile}, None)
    db.refresh(member)
    assert member.account_profile['current_kind'] == 'personal'
    assert 'access_token' not in member.account_profile
    body = client.get('/api/external/members').json()
    assert body['items'][0]['account_profile']['current_profile_id'] == 'p@AdobeID'
    assert 'private-token' not in str(body) and 'mail-secret' not in str(body)
    external_login._save_failure(member.id, 'login_failed', 'failure')
    db.refresh(member)
    assert member.account_profile['current_kind'] == 'personal'
    external_login._save_success(member.id, {'cookie': 'new-cookie'}, None)
    db.refresh(member)
    assert member.account_profile is None


def test_existing_database_migration_is_additive_and_repeatable(tmp_path, monkeypatch):
    from app.db import init_db
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE external_members (id INTEGER PRIMARY KEY, email TEXT)'))
        conn.execute(text("INSERT INTO external_members VALUES (1, 'keep@example.test')"))
    monkeypatch.setattr(init_db, 'engine', engine)
    init_db._run_migrations(); init_db._run_migrations()
    assert 'account_profile' in {col['name'] for col in inspect(engine).get_columns('external_members')}
    with engine.connect() as conn:
        assert conn.execute(text('SELECT email, account_profile FROM external_members')).fetchone() == ('keep@example.test', None)
    engine.dispose()
