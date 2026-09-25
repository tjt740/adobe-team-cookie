"""Public account metadata only; never expose raw Adobe responses or tokens."""
from datetime import datetime, timezone

from app.schemas.account_profile import AccountProfile, ProfileItem, SubscriptionOwner


def profile_kind(account_type):
    return {"type1": "personal", "type2e": "organization"}.get(account_type, "unknown")


def build_profile_snapshot(context, credits_account_id):
    account_type = context.get("check_account_type") or ""
    kind = profile_kind(account_type)
    current_id = context.get("check_user_id") or ""
    org_id = context.get("check_owner_org") or ""
    profiles = {}
    for raw in context.get("available_profiles") or []:
        item = ProfileItem.model_validate(raw)
        if item.profile_id:
            profiles[item.profile_id] = item
    current = profiles.get(current_id)
    if current_id:
        # The verified token determines the active identity, not credit count or
        # subscription owners (a personal identity can have organization plans).
        current = ProfileItem(profile_id=current_id, kind=kind, org_id=org_id,
                              name=(current.name if current else "") or ("个人配置" if kind == "personal" else ""),
                              status="active")
        profiles[current_id] = current
    owners = {}
    for raw in context.get("abp_subscriptions") or []:
        owner = raw.get("owner_id") if isinstance(raw, dict) else ""
        if owner:
            owners[owner] = SubscriptionOwner(owner_id=owner, status=raw.get("status") or "")
    return AccountProfile(
        current_kind=kind, account_type=account_type,
        current_profile_id=current_id, current_profile_name=current.name if current else "",
        current_org_id=org_id, credits_account_id=credits_account_id,
        profiles=list(profiles.values()), profiles_complete=bool(context.get("profiles_complete")),
        subscription_owners=list(owners.values()), fetched_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")
