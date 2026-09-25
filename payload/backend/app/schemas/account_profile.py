from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileItem(BaseModel):
    profile_id: str = ""
    name: str = ""
    kind: Literal["personal", "organization", "unknown"] = "unknown"
    org_id: str = ""
    status: str = ""


class SubscriptionOwner(BaseModel):
    owner_id: str
    status: str = ""


class AccountProfile(BaseModel):
    current_kind: Literal["personal", "organization", "unknown"] = "unknown"
    account_type: str = ""
    current_profile_id: str = ""
    current_profile_name: str = ""
    current_org_id: str = ""
    credits_account_id: str = ""
    profiles: list[ProfileItem] = Field(default_factory=list)
    profiles_complete: bool = False
    subscription_owners: list[SubscriptionOwner] = Field(default_factory=list)
    fetched_at: datetime
