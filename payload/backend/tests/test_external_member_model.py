from app.models.external_member import ExternalMember


def test_defaults_and_persist(db):
    m = ExternalMember(email="User@Example.com")
    db.add(m)
    db.commit()
    db.refresh(m)
    assert m.id > 0
    assert m.login_status == "never"
    assert m.subscription_ok is False
    assert m.first_login_done is False
    assert m.cookie == ""
    assert m.credits_total is None
