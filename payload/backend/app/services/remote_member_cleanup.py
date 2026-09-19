from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.crud import adobe_member as member_crud
from app.models.adobe_account import AdobeAccount
from app.services import adobe_admin, proxy_pool

REQUIRED_CREDITS = 4000.0


@dataclass
class RemoteMemberPlan:
    email: str
    member_id: str
    reason: str
    local_id: int | None = None
    local_status: str = ""
    local_credits: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "member_id": self.member_id,
            "reason": self.reason,
            "local_id": self.local_id,
            "local_status": self.local_status,
            "local_credits": self.local_credits,
        }


def credits_ok(value: object) -> bool:
    try:
        return abs(float(value) - REQUIRED_CREDITS) < 0.0001
    except (TypeError, ValueError):
        return False


def analyze_remote_members(
    db: Session,
    account: AdobeAccount,
    *,
    proxy_raw: str = "",
    pages: int = 20,
) -> tuple[list[dict[str, Any]], list[RemoteMemberPlan]]:
    last_exc: Exception | None = None
    remote: list[dict[str, Any]] = []
    for _ in range(5):
        proxy_url = proxy_pool.next_proxy(proxy_raw)
        try:
            remote = adobe_admin.fetch_members(
                token=account.admin_token,
                org_id=account.org_id,
                proxy_url=proxy_url,
                pages=pages,
            )
            proxy_pool.report_success(proxy_url)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            proxy_pool.report_failure(proxy_url, str(exc))
    else:
        raise RuntimeError(f"fetch remote members failed: {last_exc}") from last_exc
    local_rows, _ = member_crud.list_by_admin(db, account.id, page=1, size=5000)
    local_by_email = {m.email.strip().lower(): m for m in local_rows}
    plans: list[RemoteMemberPlan] = []
    for item in remote:
        email = (item.get("email") or "").strip().lower()
        member_id = (item.get("member_id") or "").strip()
        if not email or email == (account.email or "").strip().lower():
            continue
        local = local_by_email.get(email)
        if local is None:
            plans.append(
                RemoteMemberPlan(
                    email=email,
                    member_id=member_id,
                    reason="remote_only",
                )
            )
            continue
        if local.is_admin:
            continue
        if local.registered and local.status == "registered" and credits_ok(local.credits):
            continue
        plans.append(
            RemoteMemberPlan(
                email=email,
                member_id=member_id or local.member_id,
                reason="local_not_qualified",
                local_id=local.id,
                local_status=local.status or "",
                local_credits=local.credits,
            )
        )
    return remote, plans


def cleanup_remote_members(
    db: Session,
    account: AdobeAccount,
    *,
    proxy_raw: str = "",
    pages: int = 20,
    limit: int | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    remote, plans = analyze_remote_members(
        db, account, proxy_raw=proxy_raw, pages=pages
    )
    selected = plans[: max(0, limit)] if limit is not None else plans
    attempted_items = [p.as_dict() for p in selected]
    removed = 0
    removed_items: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for plan in selected:
        if log:
            log(f"remote cleanup removing {plan.email} ({plan.reason})")
        res: dict[str, Any] = {"ok": False, "message": ""}
        for _ in range(3):
            proxy_url = proxy_pool.next_proxy(proxy_raw)
            try:
                res = adobe_admin.remove_member(
                    token=account.admin_token,
                    org_id=account.org_id,
                    member_id=plan.member_id,
                    email=plan.email,
                    proxy_url=proxy_url,
                )
                if res.get("ok"):
                    proxy_pool.report_success(proxy_url)
                else:
                    proxy_pool.report_failure(proxy_url, res.get("message") or "")
                break
            except Exception as exc:  # noqa: BLE001
                proxy_pool.report_failure(proxy_url, str(exc))
                res = {"ok": False, "message": str(exc)[:300]}
        msg = res.get("message") or ""
        if res.get("ok") or "未找到成员" in msg:
            removed += 1
            removed_items.append(plan.as_dict())
            if log:
                log(f"remote cleanup removed {plan.email}")
            if plan.local_id:
                local = member_crud.get(db, plan.local_id)
                if local and not (
                    local.registered
                    and local.status == "registered"
                    and credits_ok(local.credits)
                ):
                    db.delete(local)
        else:
            if log:
                log(f"remote cleanup failed {plan.email}: {msg[:160]}")
            failed.append({**plan.as_dict(), "message": msg})
    db.commit()
    return {
        "remote_total": len(remote),
        "cleanup_candidates": len(plans),
        "attempted": len(selected),
        "attempted_items": attempted_items,
        "removed": removed,
        "removed_items": removed_items,
        "failed": failed,
        "candidates": [p.as_dict() for p in plans],
    }
