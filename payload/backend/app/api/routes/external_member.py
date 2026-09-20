from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import external_member as crud
from app.db.session import get_db
from app.schemas.adobe_account import JobStatusOut
from app.schemas.common import BatchIds, MessageResult, Page
from app.schemas.external_member import ExternalImportRequest, ExternalMemberOut
from app.services import external_login
from app.services.job_manager import JOBS

router = APIRouter(
    prefix="/external",
    tags=["外部子号"],
    dependencies=[Depends(get_current_user)],
)


def _to_out(m) -> ExternalMemberOut:
    return ExternalMemberOut(
        id=m.id, email=m.email,
        credits_available=m.credits_available, credits_total=m.credits_total,
        login_status=m.login_status, subscription_ok=m.subscription_ok,
        first_login_done=m.first_login_done, has_cookie=bool(m.cookie),
        has_adobe_password=bool((m.adobe_password or "").strip()),
        last_login_at=m.last_login_at, message=m.message, created_at=m.created_at,
    )


@router.get("/members", response_model=Page[ExternalMemberOut], summary="外部子号分页查询")
def list_members(
    page: int = 1, size: int = 20,
    login_status: str | None = None, subscription_ok: bool | None = None,
    keyword: str = "", db: Session = Depends(get_db),
) -> Page[ExternalMemberOut]:
    items, total = crud.list_members(
        db, page=page, size=size, login_status=login_status,
        subscription_ok=subscription_ok, keyword=keyword,
    )
    return Page(items=[_to_out(m) for m in items], total=total, page=page, size=size)


@router.post("/members/import", summary="批量导入外部子号(并自动开批量登录任务)")
def import_members(payload: ExternalImportRequest, db: Session = Depends(get_db)) -> dict:
    result = crud.import_lines(db, payload.content, on_duplicate=payload.on_duplicate)
    ids = result.pop("ids", [])
    # 导入成功后自动开一个批量登录任务(任务列表可见、可看日志)
    if ids:
        job = JOBS.start(
            "external_login", external_login.batch_login_worker,
            meta={"member_ids": ids, "target": len(ids)},
        )
        result["job_id"] = job.id
    return result


@router.post("/members/batch-login", response_model=JobStatusOut, summary="批量登录刷新cookie")
def batch_login(payload: BatchIds, db: Session = Depends(get_db)) -> JobStatusOut:
    members = crud.get_many(db, payload.ids)
    if not members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账号")
    job = JOBS.start(
        "external_login", external_login.batch_login_worker,
        meta={"member_ids": [m.id for m in members], "target": len(members)},
    )
    return JobStatusOut(**job.to_dict())


@router.post("/members/{member_id}/login", summary="单号重登")
def login_one(member_id: int, db: Session = Depends(get_db)) -> dict:
    m = crud.get(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在")
    # 把重登过程写进「日志管理」,失败时能看到具体到哪一步、为什么
    return external_login.login_and_store(
        member_id, log=external_login.log_login
    )


@router.get("/members/export", summary="导出 cookie([{cookie}])")
def export_members(
    login_status: str | None = None, subscription_ok: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    return crud.export_cookies(db, login_status=login_status, subscription_ok=subscription_ok)


@router.delete("/members/batch-delete", response_model=MessageResult, summary="批量删除")
def batch_delete(payload: BatchIds, db: Session = Depends(get_db)) -> MessageResult:
    n = crud.delete_many(db, payload.ids)
    return MessageResult(message=f"已删除 {n} 个")
