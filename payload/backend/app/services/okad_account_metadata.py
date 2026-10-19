"""Company classification shared by the Okad tag and Sub2 metadata sync.

No login, mailbox, Adobe, credential-delivery or verification calls belong here.
"""
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember


def uses_supply_mail(member):
    return bool(member.otp_mode == "auto" and not member.mail_url
                and not (member.refresh_token and member.client_id))


def account_metadata(source_key, member, issuer):
    if not issuer:
        return None
    external = source_key.startswith("external:")
    company = external and uses_supply_mail(member)
    group = getattr(member, "group", None) if external else None
    kind = "company" if company else "vietnam" if external and member.otp_mode == "vietnam" else "non_company"
    return {"issuer": issuer, "source_key": source_key,
            "email": member.email.strip().lower(),
            "is_company": company, "account_type": kind,
            "group_id": group.id if group else None, "group_name": group.name if group else ""}


def sync_inventory_metadata(cfg, inventory, *, send=None):
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
            ExternalMember.id, ExternalMember.email, ExternalMember.otp_mode, ExternalMember.group_id,
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
        (send or link.request)(cfg, "POST", "/account-metadata", {"items": updates[offset:offset+200]})


def sync_current_metadata():
    """Propagate edits without logging in or resending credentials, with either connection mode."""
    from app.services import reliable_integration as link, external_sub2, log_store
    try:
        with link.SessionLocal() as db:
            cfg = link.settings(db)
            if not cfg.get("enabled"):
                cfg = {**external_sub2.config(db), "issuer": cfg.get("issuer", "")}
        if not cfg.get("issuer") or not cfg.get("base_url"):
            return
        if cfg.get("enabled") and cfg.get("integration_key"):
            sync_inventory_metadata(cfg, link.inventory(cfg))
            return
        if not cfg.get("admin_token"):
            return
        rows, after = [], 0
        while True:
            page = external_sub2._request(cfg, "GET", "/admin/accounts/okad-inventory?after_id=" + str(after))
            rows.extend(page["items"])
            cursor = page.get("next_cursor", 0)
            if not cursor:
                break
            if cursor <= after:
                raise ValueError("invalid inventory cursor")
            after = cursor
        def send(config, method, path, body):
            return external_sub2._request(config, method, "/admin/accounts/okad-metadata", body)
        sync_inventory_metadata(cfg, rows, send=send)
    except Exception:
        log_store.STORE.add("WARNING", "external_groups", "Sub2 分组和账号类型同步暂未完成，请检查联动连接后重试保存分组")
