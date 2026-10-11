"""Operator dashboard and the versioned machine recovery protocol."""
import hmac
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.orm import load_only
from pydantic import BaseModel, Field
from app.api.deps import get_current_user
from app.db.session import get_db
from app.crud import setting as setting_crud
from app.models.integration import CredentialState, CredentialDelivery, RecoveryJob
from app.services import reliable_integration as link

router=APIRouter(prefix='/api/integration',dependencies=[Depends(get_current_user)])
external=APIRouter(prefix='/api/v1/adobe')


def machine_key(x_api_key: str=Header(default='',alias='X-API-Key'),db=Depends(get_db)):
    expected=(setting_crud.get_settings(db).external_api_key or '').strip()
    if not expected or not hmac.compare_digest(expected.encode(),x_api_key.encode()):
        raise HTTPException(401,'invalid api key')


def failure(exc):
    return {'ok':False,'code':exc.code,'message':str(exc),'managed':True}


@external.get('/cookie/capability',dependencies=[Depends(machine_key)])
def capability(email: str,source_key: str='',cookie_hash: str='',db=Depends(get_db)):
    try:
        key,row=link.resolve(db,email,source_key)
        cfg=link.settings(db)
        if not cfg['enabled'] or not cfg['site_id'] or not cfg['integration_key']:
            raise link.IntegrationError('configuration','请先启用并测试可靠联动')
        import hashlib
        if cookie_hash and row.cookie and hashlib.sha256(row.cookie.encode()).hexdigest()!=cookie_hash:
            link.queue_source(db,key)
            return {'ok': False, 'code': 'awaiting_sync', 'message': 'Okad 已有不同版本凭据，先同步验证，不重新登录'}
        link.check_capability(db,key,row,cfg)
        return {'ok':True,'email':row.email,'source_key':key,'protocol':2}
    except link.IntegrationError as exc:return failure(exc)


@external.get('/cookie/jobs/{job_id}',dependencies=[Depends(machine_key)])
def job_status(job_id: str,db=Depends(get_db)):
    job=db.get(RecoveryJob,job_id)
    if not job:raise HTTPException(404,'任务不存在')
    return link.job_result(job)


class ConfigIn(BaseModel):
    enabled: bool=True
    base_url: str=Field(max_length=1024)
    integration_key: str=Field(default='',max_length=512)


@router.get('/config')
def configuration(db=Depends(get_db)):
    cfg=link.settings(db)
    return {k:cfg[k] for k in ('enabled','base_url','site_id','issuer')} | {'key_configured':bool(cfg['integration_key'])}


@router.put('/config')
def configure(body: ConfigIn,db=Depends(get_db)):
    from app.api.routes.sub2 import _set,_enc
    cfg=link.settings(db)
    cfg['base_url']=body.base_url.strip()
    if body.integration_key:cfg['integration_key']=body.integration_key.strip()
    try:remote=link.request(cfg,'GET','/capabilities',timeout=(5,12)) if body.enabled else None
    except link.IntegrationError as exc:raise HTTPException(400,str(exc)) from None
    if remote and (remote.get('protocol')!=2 or not remote.get('site_id')):
        raise HTTPException(400,'对方不支持联动协议 v2')
    _set(db,'sub2_reliable_enabled','true' if body.enabled else 'false')
    _set(db,'sub2_reliable_url',cfg['base_url'])
    if body.integration_key:_set(db,'sub2_integration_key',_enc(body.integration_key.strip()))
    if not cfg['issuer']:_set(db,'okad_instance_id',uuid.uuid4().hex)
    if remote:_set(db,'sub2_site_id',remote['site_id'])
    db.commit()
    return configuration(db)


@router.get('/status')
def status(db=Depends(get_db)):
    cfg=link.settings(db)
    counts=dict(db.execute(select(CredentialDelivery.state,func.count()).where(CredentialDelivery.site_id==cfg['site_id']).group_by(CredentialDelivery.state)).all())
    active_jobs=db.scalar(select(func.count()).select_from(RecoveryJob).where(RecoveryJob.state.in_(['queued','running'])))
    jobs=[link.job_result(j)|{'created_at':j.created_at,'updated_at':j.updated_at} for j in db.scalars(select(RecoveryJob).order_by(RecoveryJob.created_at.desc()).limit(100))]
    deliveries=[]
    recent=db.execute(select(CredentialDelivery,CredentialState.email).outerjoin(CredentialState,CredentialState.source_key==CredentialDelivery.source_key).where(CredentialDelivery.site_id==cfg['site_id']).order_by(CredentialDelivery.updated_at.desc()).limit(100))
    for d,email in recent:
        deliveries.append({'key':d.key,'source_key':d.source_key,'email':email or '',
            'version':d.version,'account_id':d.account_id,'state':d.state,'message':d.message,
            'attempts':d.attempts,'next_at':d.next_at,'updated_at':d.updated_at,'receipt':d.receipt})
    return {'config':configuration(db),'jobs':jobs,'deliveries':deliveries,'counts':counts,'active_jobs':active_jobs,'checked_at':time.time()}


@router.get('/inventory')
def inventory(db=Depends(get_db)):
    try:return {'items':link.inventory(link.settings(db))}
    except link.IntegrationError as exc:raise HTTPException(503,str(exc)) from None


class SourceAction(BaseModel):
    source_key: str=Field(max_length=100)


@router.post('/retry-sync')
def retry_sync(body: SourceAction,db=Depends(get_db)):
    try:link.queue_source(db,body.source_key)
    except link.IntegrationError as exc:raise HTTPException(400,str(exc)) from None
    return {'ok':True,'message':'已提交同步与验证，未重新登录'}


@router.post('/login')
def login(body: SourceAction,db=Depends(get_db)):
    try:
        row=link.source(db,body.source_key)
        job=link.submit_recovery(db,uuid.uuid4().hex,row.email,body.source_key,automatic=True)
        return link.job_result(job)
    except link.IntegrationError as exc:raise HTTPException(400,str(exc)) from None

@router.get('/sources')
def sources(page: int=1,db=Depends(get_db)):
    from app.models.external_member import ExternalMember
    from app.models.adobe_member import AdobeMember
    cfg=link.settings(db)
    from app.services.supply_mail import get_token
    supply_available=bool(get_token(db))
    page=max(1,page)
    external_count=db.scalar(select(func.count()).select_from(ExternalMember))
    pool_count=db.scalar(select(func.count()).select_from(AdobeMember).where(AdobeMember.is_admin.is_(False)))
    offset=(page-1)*100
    selected=[]
    if offset<external_count:
        q=select(ExternalMember,func.length(func.coalesce(ExternalMember.cookie,''))>0).options(load_only(
            ExternalMember.id,ExternalMember.email,ExternalMember.otp_mode,ExternalMember.mail_url,ExternalMember.refresh_token,ExternalMember.client_id
        )).order_by(ExternalMember.id).offset(offset).limit(100)
        selected.extend(('external',row,has_cookie) for row,has_cookie in db.execute(q))
    remaining=100-len(selected)
    if remaining:
        q=select(AdobeMember,func.length(func.coalesce(AdobeMember.cookie,''))>0).options(load_only(
            AdobeMember.id,AdobeMember.email,AdobeMember.is_admin,AdobeMember.admin_id,AdobeMember.mail_url,AdobeMember.refresh_token,AdobeMember.client_id
        )).where(AdobeMember.is_admin.is_(False)).order_by(AdobeMember.id).offset(max(0,offset-external_count)).limit(remaining)
        selected.extend(('pool',row,has_cookie) for row,has_cookie in db.execute(q))
    keys=[f'{kind}:{row.id}' for kind,row,_ in selected]
    credentials={c.source_key:c for c in db.scalars(select(CredentialState).where(CredentialState.source_key.in_(keys)))}
    deliveries={d.source_key:d for d in db.scalars(select(CredentialDelivery).where(CredentialDelivery.site_id==cfg['site_id'],CredentialDelivery.source_key.in_(keys)))}
    values=[]
    for prefix,row,has_cookie in selected:
        key=f'{prefix}:{row.id}'
        credential=credentials.get(key)
        delivery=deliveries.get(key)
        reason=''
        reason_code=''
        try:link.check_capability(db,key,row,cfg,supply_available=supply_available)
        except link.IntegrationError as exc:reason=str(exc);reason_code=exc.code
        values.append({'source_key':key,'email':row.email,'source':'外部子号' if prefix=='external' else '号池',
            'has_cookie':bool(has_cookie),'auto_recovery':not reason,'recovery_message':reason,'recovery_code':reason_code,
            'version':credential.version if credential else 0,
            'delivery':{'state':delivery.state,'message':delivery.message,'account_id':delivery.account_id,
                'next_at':delivery.next_at,'updated_at':delivery.updated_at,'receipt':delivery.receipt} if delivery else None})
    return {'items':values,'total':external_count+pool_count,'page':page}


@router.post('/push')
def push(body: SourceAction,db=Depends(get_db)):
    try:link.queue_source(db,body.source_key,allow_create=True)
    except link.IntegrationError as exc:raise HTTPException(400,str(exc)) from None
    return {'ok':True,'message':'已提交入库与验证；已有账号保留关联'}
