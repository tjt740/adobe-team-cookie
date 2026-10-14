"""Company classification shared by the Okad tag and Sub2 metadata sync.

No login, mailbox, Adobe, credential-delivery or verification calls belong here.
"""
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember


def uses_supply_mail(member):
    return bool(member.otp_mode != "manual" and not member.mail_url
                and not (member.refresh_token and member.client_id))


def account_metadata(source_key, member, issuer):
    if not issuer:
        return None
    return {"issuer": issuer, "source_key": source_key,
            "email": member.email.strip().lower(),
            "is_company": source_key.startswith("external:") and uses_supply_mail(member)}


def sync_inventory_metadata(cfg, inventory):
    """Backfill/update existing imports without pushing their Cookie again.

    Versioned owners must match. Old imports must carry the import marker and
    resolve to exactly one local source; same-email ambiguity is left unknown.
    Only changed records are written, in bounded batches.
    """
    from app.services import reliable_integration as link
    if not inventory or not cfg.get("issuer"):
        return
    by_source = {}
    by_email = defaultdict(list)
    with link.SessionLocal() as db:
        external = db.scalars(select(ExternalMember).options(load_only(
            ExternalMember.id, ExternalMember.email, ExternalMember.otp_mode,
            ExternalMember.mail_url, ExternalMember.refresh_token, ExternalMember.client_id)))
        pool = db.scalars(select(AdobeMember).where(AdobeMember.is_admin == 0).options(
            load_only(AdobeMember.id, AdobeMember.email)))
        for prefix, members in (("external", external), ("pool", pool)):
            for member in members:
                metadata = account_metadata(f"{prefix}:{member.id}", member, cfg["issuer"])
                by_source[metadata["source_key"]] = metadata
                by_email[metadata["email"]].append(metadata)
    updates = []
    for remote in inventory:
        email = (remote.get("email") or "").strip().lower()
        owner = remote.get("integration") or {}
        old = remote.get("account_metadata") or {}
        if owner.get("issuer"):
            if owner["issuer"] != cfg["issuer"]:
                continue
            metadata = by_source.get(owner.get("source_key"))
        else:
            candidates = by_email.get(email, [])
            if (remote.get("imported_email") or "").strip().lower() != email or len(candidates) != 1:
                continue
            metadata = candidates[0]
        if not metadata or metadata["email"] != email:
            continue
        if not owner.get("issuer") and old.get("issuer") and (old["issuer"] != cfg["issuer"] or old.get("source_key") != metadata["source_key"]):
            continue
        if old != metadata:
            updates.append({"id": remote["id"], **metadata})
    for offset in range(0, len(updates), 200):
        link.request(cfg, "POST", "/account-metadata", {"items": updates[offset:offset+200]})
