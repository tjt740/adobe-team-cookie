from threading import Lock

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import capture_job_request, get_current_user
from app.crud import external_member as crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.adobe_account import JobStatusOut
from app.schemas.common import BatchIds, MessageResult, Page
from app.schemas.external_member import ExternalImportRequest, ExternalLoginFilter, ExternalMemberOut, ExternalProfilePreferenceUpdate
from app.services import external_login, external_sub2, external_sub2_stock
from app.services.job_manager import JOBS

router = APIRouter(
    prefix="/external",
    tags=["外部子号"],
    dependencies=[Depends(capture_job_request)],
)
_login_lock = Lock()


def _to_out(m, latest_job=None, sub2_target="") -> ExternalMemberOut:
    return ExternalMemberOut(
        id=m.id, email=m.email,
        credits_available=m.credits_available, credits_total=m.credits_total,
        account_profile=m.account_profile,
        profile_preference=m.profile_preference,
        login_status=m.login_status, subscription_ok=m.subscription_ok,
        first_login_done=m.first_login_done, has_cookie=bool(m.cookie),
        has_adobe_password=bool((m.adobe_password or "").strip()),
        last_login_at=m.last_login_at, message=m.message, created_at=m.created_at,
        operator=m.operator or "", latest_job=latest_job,
        **external_sub2.summary(m, sub2_target),
    )


def _start_login(members, db, operator):
    for member in members:
        member.operator = operator
    db.commit()
    return JOBS.start(
        "external_login", external_login.batch_login_worker,
        meta={"member_ids": [m.id for m in members], "target": len(members), "operator": operator,
              "member_emails": {str(m.id): m.email for m in members},
              "member_profile_preferences": {str(m.id): m.profile_preference for m in members}},
    )


def _active_jobs(ids):
    return {mid: jobs[0] for mid, jobs in JOBS.external_member_jobs(ids).items()
            if jobs[0]["status"] in {"running", "pausing", "paused", "cancelling"}}


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
    jobs = JOBS.external_member_jobs([m.id for m in items])
    target = external_sub2.destination(external_sub2.config(db))
    return Page(items=[_to_out(m, (jobs.get(m.id) or [None])[0], target) for m in items], total=total, page=page, size=size)


@router.get("/members/sub2-stock", summary="按邮箱核对外部子号在 Sub2 的实时库存")
def sub2_stock(refresh: bool = False, db: Session = Depends(get_db)) -> dict:
    return external_sub2_stock.membership(db, refresh=refresh)


@router.patch("/members/{member_id}/login-profile", summary="保存账号下次登录使用的配置")
def update_login_profile(member_id: int, payload: ExternalProfilePreferenceUpdate,
                         db: Session = Depends(get_db)) -> dict:
    with _login_lock:
        member = crud.get(db, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="条目不存在")
        if _active_jobs([member_id]):
            raise HTTPException(status_code=409, detail="账号登录任务尚未结束，请完成或终止后修改登录配置")
        member.profile_preference = payload.profile_preference
        db.commit()
    return {"profile_preference": member.profile_preference, "message": "已保存，下次登录生效"}


@router.post("/members/push-sub2", summary="推送选中外部子号并开启重登后 Cookie 同步")
def push_sub2(payload: BatchIds, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请先勾选账号")
    try:
        target, queued, skipped = external_sub2.prepare(db, payload.ids)
    except external_sub2.SyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    background.add_task(external_sub2.submit, queued, target)
    return {"queued": len(queued), "skipped": len(skipped),
            "message": f"已提交 {len(queued)} 个账号同步，跳过 {len(skipped)} 个未登录成功或无 Cookie 的账号"}


@router.post("/members/relink-sub2", summary="手动重新关联 Sub2，缺失账号按邮箱去重后重建")
def relink_sub2(payload: BatchIds, background: BackgroundTasks, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> dict:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="请先勾选账号")
    try:
        target, queued, skipped = external_sub2.prepare(db, payload.ids, relink=True, operator=user.username)
    except external_sub2.SyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    background.add_task(external_sub2.submit, queued, target)
    return {"queued": len(queued), "skipped": len(skipped),
            "message": f"已提交 {len(queued)} 个账号重新关联，跳过 {len(skipped)} 个未就绪或正在同步的账号"}


@router.post("/members/import", summary="批量导入外部子号(并自动开批量登录任务)")
def import_members(payload: ExternalImportRequest, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> dict:
    result = crud.import_lines(db, payload.content, on_duplicate=payload.on_duplicate,
                               operator=user.username, profile_preference=payload.profile_preference)
    ids = result.pop("ids", [])
    # 导入成功后自动开一个批量登录任务(任务列表可见、可看日志)
    if ids:
        with _login_lock:
            active = _active_jobs(ids)
            pending = [mid for mid in ids if mid not in active]
            job_ids = list(dict.fromkeys(j["id"] for j in active.values()))
            if pending:
                job = _start_login(crud.get_many(db, pending), db, user.username)
                job_ids.insert(0, job.id)
            result["job_id"] = job_ids[0]
            result["job_ids"] = job_ids
    return result


@router.post("/members/batch-login", response_model=JobStatusOut, summary="批量登录刷新cookie")
def batch_login(payload: BatchIds, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> JobStatusOut:
    members = crud.get_many(db, payload.ids)
    if not members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账号")
    with _login_lock:
        active = _active_jobs([m.id for m in members])
        job_ids = set(j["id"] for j in active.values())
        if len(active) == len(members) and len(job_ids) == 1:
            return JobStatusOut(**JOBS.get(next(iter(job_ids))).to_dict())
        if active:
            raise HTTPException(status_code=409, detail="所选账号已有登录任务运行中,请等待完成后再重试")
        job = _start_login(members, db, user.username)
    return JobStatusOut(**job.to_dict())


@router.post("/members/batch-login-filter", summary="一键重登当前筛选的全部外部子号")
def batch_login_filter(payload: ExternalLoginFilter, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> dict:
    with _login_lock:
        members, total = crud.list_members(db, size=None, **payload.model_dump())
        active = _active_jobs([m.id for m in members]) if members else {}
        pending = [m for m in members if m.id not in active]
        job = _start_login(pending, db, user.username) if pending else None
    if job:
        message = f"已提交 {len(pending)} 个账号重登，跳过 {len(active)} 个任务未结束的账号"
    else:
        message = "当前范围暂无外部子号" if not total else f"当前范围的 {len(active)} 个账号任务未结束，无需重复提交"
    return {"job": JobStatusOut(**job.to_dict()) if job else None,
            "queued": len(pending), "skipped": len(active), "total": total, "message": message}


@router.get("/members/{member_id}/jobs", response_model=list[JobStatusOut], summary="外部子号任务历史")
def member_jobs(member_id: int, limit: int = Query(default=50, ge=1, le=100),
                db: Session = Depends(get_db)) -> list[JobStatusOut]:
    if not crud.get(db, member_id):
        raise HTTPException(status_code=404, detail="条目不存在")
    return [JobStatusOut(**j) for j in JOBS.external_member_jobs([member_id], limit=limit).get(member_id, [])]


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
    keyword: str = "",
    db: Session = Depends(get_db),
) -> list[dict]:
    return crud.export_cookies(db, login_status=login_status, subscription_ok=subscription_ok, keyword=keyword)


@router.post("/members/export", summary="导出选中账号的 Cookie")
def export_selected_members(payload: BatchIds, db: Session = Depends(get_db)) -> list[dict]:
    return crud.export_cookies(db, ids=payload.ids)


@router.delete("/members/batch-delete", response_model=MessageResult, summary="批量删除")
def batch_delete(payload: BatchIds, db: Session = Depends(get_db)) -> MessageResult:
    n = crud.delete_many(db, payload.ids)
    return MessageResult(message=f"已删除 {n} 个")
