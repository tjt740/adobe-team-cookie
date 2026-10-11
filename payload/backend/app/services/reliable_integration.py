"""Versioned Sub2 delivery and recoverable login jobs.

Source Cookie + outbox update share one transaction. Delivery retries never log
in. Login requests have durable IDs, and interrupted logins are never replayed.
"""
import hashlib
import threading
import time
import uuid
import contextvars
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests
from sqlalchemy import select, update, func, text
from app.db.session import SessionLocal
from app.models.integration import CredentialState, CredentialDelivery, RecoveryJob, LoginLease
from app.models.external_member import ExternalMember
from app.models.adobe_member import AdobeMember
from app.models.setting import Setting

_login_destination = contextvars.ContextVar('integration_destination', default=None)


@contextmanager
def login_destination(cfg):
    """Freeze the destination before login, including manual/batch entry points."""
    previous = _login_destination.get()
    token = _login_destination.set(previous if previous is not None else dict(cfg))
    try:
        yield
    finally:
        _login_destination.reset(token)

class IntegrationError(Exception):
    def __init__(self, code, message, retryable=False):
        super().__init__(message)
        self.code, self.retryable = code, retryable


def settings(db):
    from app.api.routes.sub2 import _get_config, _dec
    rows = {r.key: r.value for r in db.scalars(select(Setting))}
    cfg = _get_config(db)
    cfg.update(enabled=rows.get('sub2_reliable_enabled') == 'true',
               integration_key=_dec(rows.get('sub2_integration_key', '')),
               site_id=rows.get('sub2_site_id', ''),
               issuer=rows.get('okad_instance_id', ''),
               base_url=rows.get('sub2_reliable_url') or cfg.get('base_url', ''))
    return cfg


def target(cfg):
    from app.services.sub2_client import api_base
    return api_base(cfg.get('base_url', '')).rstrip('/')


def request(cfg, method, path, body=None):
    if not cfg.get('integration_key'):
        raise IntegrationError('configuration', '未配置 Sub2 专用联动密钥')
    address = target(cfg)
    parsed = urlsplit(address)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or not parsed.hostname:
        raise IntegrationError('configuration', 'Sub2 地址无效')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1') and '.' in parsed.hostname:
        import ipaddress
        try:
            if not ipaddress.ip_address(parsed.hostname).is_private:
                raise ValueError()
        except ValueError:
            raise IntegrationError('configuration', '跨主机公网联动请使用 HTTPS') from None
    try:
        with requests.Session() as client:
            client.trust_env = False
            response = client.request(method, address+'/integrations/okad'+path,
                headers={'X-Integration-Key': cfg['integration_key']}, json=body,
                timeout=(5, 70), allow_redirects=False)
    except requests.RequestException:
        raise IntegrationError('transport', '联动连接暂不可用，保留 Cookie 后重试', True) from None
    if response.status_code == 409:
        raise IntegrationError('conflict', '版本、来源或账号状态已变化，未覆盖，请核对关联')
    if response.status_code in (401, 403):
        raise IntegrationError('configuration', '联动密钥无效或无权操作，请检查配置')
    if response.status_code == 404:
        raise IntegrationError('not_found', '远端账号或联动接口不存在，不自动重建')
    if response.status_code >= 500 or response.status_code == 429:
        raise IntegrationError('unavailable', 'Sub2 暂不可用，等待重试同步', True)
    if response.status_code != 200:
        raise IntegrationError('protocol', 'Sub2 联动协议不兼容，请核对两边版本')
    try:
        data = response.json()['data']
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, KeyError):
        raise IntegrationError('protocol', 'Sub2 返回格式不兼容') from None


def source(db, key):
    try:
        kind, identifier = key.split(':')
        model = {'external': ExternalMember, 'pool': AdobeMember}[kind]
        row = db.get(model, int(identifier))
    except (ValueError, KeyError):
        row = None
    if not row or (kind == 'pool' and row.is_admin):
        raise IntegrationError('not_registered', '恢复资料不存在，请补充关联')
    return row


def resolve(db, email, key=''):
    email = email.strip().lower()
    if key:
        row = source(db, key)
        if row.email.strip().lower() != email:
            raise IntegrationError('identity_mismatch', '账号来源与邮箱不一致')
        return key, row
    matches = [('external:'+str(m.id), m) for m in db.scalars(select(ExternalMember).where(func.lower(ExternalMember.email)==email))]
    matches += [('pool:'+str(m.id), m) for m in db.scalars(select(AdobeMember).where(func.lower(AdobeMember.email)==email, AdobeMember.is_admin.is_(False)))]
    if len(matches) != 1:
        raise IntegrationError('ambiguous' if matches else 'not_registered', '同邮箱有多个来源，请明确关联' if matches else '未登记恢复资料')
    return matches[0]


def capability(db, email, key='', automatic=True):
    key, row = resolve(db, email, key)
    cfg = settings(db)
    check_capability(db,key,row,cfg,automatic=automatic)
    return key,row


def check_capability(db,key,row,cfg,automatic=True,supply_available=None):
    if not cfg['enabled'] or not cfg['site_id'] or not cfg['integration_key']:
        raise IntegrationError('configuration', '请先启用并测试可靠联动')
    if key.startswith('external:'):
        if row.otp_mode == 'manual' and automatic:
            raise IntegrationError('needs_manual', '此账号需要手动验证码，请到 Okad 发起登录')
        from app.services.supply_mail import get_token
        if supply_available is None:supply_available=bool(get_token(db))
        if row.otp_mode != 'manual' and not (row.mail_url or (row.refresh_token and row.client_id) or supply_available):
            raise IntegrationError('missing_mail', '缺少取信配置，请补充后恢复')
    else:
        from app.services.pool_login import _resolve_creds
        rt, cid, mail_url = _resolve_creds(db, row,persist=False)
        if not ((rt and cid) or mail_url):
            raise IntegrationError('missing_mail', '号池缺少取信资料')


def record_cookie(db, key, email, cookie, *, allow_create=False, account_id=None):
    """Caller commits once with the source cookie. No HTTP or executor here."""
    if not cookie:
        return None
    from app.services.login_coordinator import assert_owner
    assert_owner(db)
    # Serialize both first insertion and revision increment on the source row.
    # This also works across processes; a Python mutex cannot protect SQLite
    # workers or a PostgreSQL deployment from concurrent manual sync requests.
    kind, identifier = key.split(':')
    table = {'external': 'external_members', 'pool': 'adobe_members'}[kind]
    with db.no_autoflush:
        locked = db.execute(text(f'UPDATE {table} SET id=id WHERE id=:id'), {'id':int(identifier)}).rowcount
    if not locked:
        raise IntegrationError('not_registered','恢复资料不存在，请补充关联')
    db.flush()
    digest = hashlib.sha256(cookie.encode()).hexdigest()
    state = db.get(CredentialState, key, populate_existing=True)
    if not state:
        state = CredentialState(source_key=key, email=email, cookie_hash=digest, version=1, updated_at=time.time())
        db.add(state)
    elif state.cookie_hash != digest:
        state.version += 1
        state.cookie_hash, state.email, state.updated_at = digest, email, time.time()
    cfg = _login_destination.get() or settings(db)
    if not cfg['enabled'] or not cfg['site_id']:
        return state
    if key.startswith('external:'):
        from app.services.external_sub2 import destination
        member=source(db,key)
        dest=destination(cfg)
        old=(member.sub2_links or {}).get(dest,{})
        member.sub2_links={**(member.sub2_links or {}),dest:{**old,'status':'pending','message':'Cookie 已保存，等待同步与验证'}}
    dkey = cfg['site_id']+'/'+key
    delivery = db.get(CredentialDelivery, dkey, populate_existing=True)
    if not delivery:
        if not account_id and key.startswith('external:'):
            from app.services.external_sub2 import destination
            member=source(db,key)
            account_id=((member.sub2_links or {}).get(destination(cfg)) or {}).get('account_id')
        delivery = CredentialDelivery(key=dkey, source_key=key, site_id=cfg['site_id'], target=target(cfg),
                                      version=state.version, account_id=account_id, updated_at=time.time())
        db.add(delivery)
    if delivery.target != target(cfg):
        delivery.target = target(cfg)  # Same tested site identity; endpoint can move.
    if delivery.version == state.version and delivery.state in ('pending', 'retry'):
        if allow_create: delivery.allow_create = 1
        if account_id: delivery.account_id = account_id
        return state
    delivery.version, delivery.state = state.version, 'pending'
    delivery.attempts = 0
    delivery.receipt = None
    delivery.next_at, delivery.message, delivery.updated_at = 0, 'Cookie 已保存，等待同步', time.time()
    delivery.allow_create = int(allow_create or delivery.allow_create or False)
    if account_id:
        delivery.account_id = account_id
    return state


def queue_source(db, key, allow_create=False, account_id=None):
    # Acquire before reading the Cookie, otherwise an upload can rotate it while
    # this caller waits for another writer, assigning a new version to stale data.
    try:
        kind, identifier=key.split(':')
        table={'external':'external_members','pool':'adobe_members'}[kind]
        db.execute(text(f'UPDATE {table} SET id=id WHERE id=:id'), {'id':int(identifier)})
    except (ValueError,KeyError):
        raise IntegrationError('not_registered','恢复资料不存在，请补充关联') from None
    row = source(db, key)
    db.refresh(row)
    if not row.cookie:
        raise IntegrationError('no_cookie', '没有 Cookie，请先登录')
    record_cookie(db,key,row.email,row.cookie,allow_create=allow_create,account_id=account_id)
    db.commit()


def inventory(cfg, since=None):
    after, items = 0, []
    while True:
        path = '/accounts?after_id='+str(after)
        if since:
            from urllib.parse import quote
            path += '&since='+quote(since)
        page = request(cfg, 'GET', path)
        items.extend(page['items'])
        cursor = page['next_cursor']
        if not cursor:
            return items
        if cursor <= after:
            raise IntegrationError('protocol', '远端分页无进展，已停止核对')
        after = cursor


def _locate(cfg, delivery, email):
    rows = inventory(cfg)
    if delivery.account_id:
        matches = [r for r in rows if r['id']==delivery.account_id]
        if not matches:
            raise IntegrationError('not_found', '关联账号已删除，自动同步不会重建')
    else:
        matches = [r for r in rows if r['email'].lower()==email.lower()]
    if len(matches)>1:
        raise IntegrationError('ambiguous', 'Sub2 同邮箱账号重复，请先整理')
    if matches:
        row = matches[0]
        if row['email'].lower()!=email.lower():
            raise IntegrationError('identity_mismatch', '远端身份不一致，未覆盖')
        return row['id']
    if not delivery.allow_create:
        raise IntegrationError('not_found', 'Sub2 没有该账号，请先手动推送入库')
    # Creating accounts still requires the existing administrator authorization.
    from app.services import external_sub2
    try:
        external_sub2.validate_config(cfg)
        groups = external_sub2._request(cfg,'GET','/admin/groups/all')
    except external_sub2.SyncError as exc:
        if exc.http_status==423:
            raise IntegrationError('configuration','请先登录 Sub2 完成管理员确认，再重试同步') from None
        if exc.http_status in (None,401,403):
            raise IntegrationError('configuration','首次入库需要在 Sub2 管理中配置本地管理员密钥和 Adobe 分组') from None
        raise IntegrationError('unavailable','首次入库暂不可用，保留 Cookie 后重试',True) from None
    valid={g['id'] for g in groups if g.get('platform')=='adobe' and g.get('status')=='active'}
    if not set(cfg['group_ids']).issubset(valid):
        raise IntegrationError('configuration','请选择有效的 Adobe 分组')
    with SessionLocal() as db:
        row=source(db,delivery.source_key)
        cookie=row.cookie
    result=external_sub2._request(cfg,'POST','/admin/accounts',{
        'name':email,'platform':'adobe','type':'oauth','credentials':{'email':email,'cookie':cookie},
        'group_ids':cfg['group_ids'],'concurrency':cfg.get('concurrency',3),'priority':0,
        'rate_multiplier':external_sub2.sub2_client._safe_float(cfg.get('rate_multiplier'),1),
        'extra':{'adobeteam_external_email':email.lower(),'okad_initial_verification':True}})
    return result['id']


def deliver(key):
    now=time.time()
    lease_until=now+180
    with SessionLocal() as db:
        claimed=db.execute(update(CredentialDelivery).where(CredentialDelivery.key==key,CredentialDelivery.lease_until<now)
                           .values(lease_until=lease_until)).rowcount
        db.commit()
        if not claimed:return
        delivery=db.get(CredentialDelivery,key)
        version=delivery.version
        cfg=settings(db)
        source_key=delivery.source_key
        db.expunge(delivery)
    state,message,receipt,aid='blocked','',None,delivery.account_id
    retry=False
    try:
        with SessionLocal() as db:
            row=source(db,source_key)
            credential=db.get(CredentialState,source_key)
            email,cookie=row.email,row.cookie or ''
            if not credential or credential.version!=version or credential.cookie_hash!=hashlib.sha256(cookie.encode()).hexdigest():
                raise IntegrationError('conflict','本地凭据已变化，请重新提交同步')
        if not cfg['enabled'] or cfg['site_id']!=delivery.site_id or target(cfg)!=delivery.target:
            raise IntegrationError('destination_changed','联动目标已改变，任务停止；请在当前目标重新推送')
        capabilities=request(cfg,'GET','/capabilities')
        if capabilities.get('site_id')!=delivery.site_id:
            raise IntegrationError('destination_changed','远端站点身份不一致，未发送凭据')
        aid=_locate(cfg,delivery,email)
        try:
            receipt=request(cfg,'POST',f'/accounts/{aid}/credentials',{
                'email':email,'issuer':cfg['issuer'],'source_key':source_key,'version':version,'cookie':cookie})
        except IntegrationError as exc:
            if exc.code=='conflict':
                # A concurrent status update may invalidate Sub2's snapshot.
                # Retry only if the remote still belongs to us and is older.
                matches=[item for item in inventory(cfg) if item['id']==aid]
                remote=(matches[0].get('integration') or {}) if matches else {}
                same_owner=not remote.get('issuer') or (remote.get('issuer')==cfg['issuer'] and remote.get('source_key')==source_key)
                if matches and same_owner and int(remote.get('version') or 0)<version:
                    exc.retryable=True
            raise
        try:
            receipt=request(cfg,'POST',f'/accounts/{aid}/verify')
        except IntegrationError as exc:
            # Verification may race a manual pause or proxy change. Re-reading
            # and re-verifying is safe; replacing a conflicting source is not.
            if exc.code=='conflict':exc.retryable=True
            raise
        verify=receipt['integration'].get('verification')
        if verify in ('verification_retry','proxy_pending'):
            state,message,retry='retry',('Cookie 已写入，等待 Sub2 代理就绪' if verify=='proxy_pending' else 'Cookie 已写入，等待重新验证'),True
        elif verify=='verified':
            state='ready' if receipt.get('schedulable') and receipt.get('status')=='active' else 'paused'
            message='凭据已验证，可调度；模型尚未验证' if state=='ready' else '凭据已验证，保持暂停或等待代理分配'
        else:
            state,message='attention',receipt['integration'].get('message','需要处理账号权益或凭据')
    except IntegrationError as exc:
        state,message,retry=('retry' if exc.retryable else 'blocked'),str(exc),exc.retryable
    except Exception:
        state,message,retry='retry','同步暂未完成，保留 Cookie 后重试',True
    with SessionLocal() as db:
        # A worker that outlived its lease cannot release/ack its successor.
        owned=db.execute(update(CredentialDelivery).where(CredentialDelivery.key==key,
            CredentialDelivery.lease_until==lease_until).values(lease_until=0)).rowcount
        if not owned:
            db.rollback();return
        current=db.get(CredentialDelivery,key)
        if not current:return
        current.lease_until=0
        # A later cookie owns the outbox; old completions may only release their lease.
        if current.version==version:
            current.state,current.message,current.receipt=state,message,receipt
            current.account_id=aid
            current.attempts=(current.attempts or 0)+1
            delay=min(900,15*2**min(current.attempts,6))+(hash(key)%13)
            current.next_at=time.time()+delay if retry else 0
            current.updated_at=time.time()
            if source_key.startswith('external:'):
                member=db.get(ExternalMember,int(source_key.split(':')[1]))
                if member and aid:
                    from app.services.external_sub2 import destination
                    dest=destination(cfg)
                    link=(member.sub2_links or {}).get(dest,{})
                    member.sub2_links={**(member.sub2_links or {}),dest:{**link,'account_id':aid,
                        'status':('synced' if state in ('ready','paused') else 'pending' if retry else 'failed'),'message':message,
                        **({'synced_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()} if receipt else {})}}
            elif source_key.startswith('pool:') and receipt:
                member=db.get(AdobeMember,int(source_key.split(':')[1]))
                if member:
                    member.sub2_pushed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        db.commit()


def reconcile_inventory():
    """Read Sub2 operator changes without sending credentials or starting login."""
    with SessionLocal() as db:
        cfg=settings(db)
        if not cfg['enabled']:return
        rows=list(db.scalars(select(CredentialDelivery).where(
            CredentialDelivery.site_id==cfg['site_id'],CredentialDelivery.target==target(cfg),
            CredentialDelivery.state.in_(['ready','paused','attention']))))
        snapshots=[(d.key,d.source_key,d.version,d.account_id,d.state,d.message) for d in rows if d.account_id]
    if not snapshots:return
    if request(cfg,'GET','/capabilities').get('site_id')!=cfg['site_id']:return
    remote={item['id']:item for item in inventory(cfg)}
    for key,source_key,version,aid,old_state,old_message in snapshots:
        item=remote.get(aid)
        if not item:
            state,message,receipt='blocked','关联账号已删除，自动同步不会重建',None
        else:
            integration=item.get('integration') or {}
            if (integration.get('issuer')!=cfg['issuer'] or integration.get('source_key')!=source_key
                    or integration.get('version')!=version):
                state,message='attention','Sub2 凭据来源或版本已改变，请核对关联'
            elif integration.get('verification')=='verified':
                state='ready' if item.get('schedulable') and item.get('status')=='active' else 'paused'
                message='凭据已验证，可调度；模型尚未验证' if state=='ready' else '凭据已验证，保持暂停或等待代理分配'
            else:
                state,message='attention',integration.get('message') or 'Sub2 状态已变化，请核对验证结果'
            receipt={k:item[k] for k in ('id','status','schedulable','integration') if k in item}
        if state==old_state and message==old_message:continue
        with SessionLocal() as db:
            # A late inventory response cannot finish or overwrite queued work.
            changed=db.execute(update(CredentialDelivery).where(CredentialDelivery.key==key,
                CredentialDelivery.version==version,CredentialDelivery.account_id==aid,
                CredentialDelivery.target==target(cfg),CredentialDelivery.state.in_(['ready','paused','attention']),
                (CredentialDelivery.state!=state)|(CredentialDelivery.message!=message))
                .values(state=state,message=message,receipt=receipt,updated_at=time.time())).rowcount
            if changed and source_key.startswith('external:'):
                from app.services.external_sub2 import destination
                member=db.get(ExternalMember,int(source_key.split(':')[1]))
                if member:
                    dest=destination(cfg);old=(member.sub2_links or {}).get(dest,{})
                    member.sub2_links={**(member.sub2_links or {}),dest:{**old,'status':'synced' if state in ('ready','paused') else 'failed','message':message}}
            db.commit()


def submit_recovery(db, request_id, email, source_key='', automatic=True):
    if not request_id or len(request_id)>100:
        raise IntegrationError('invalid_request','缺少有效任务编号')
    prior=db.get(RecoveryJob,request_id)
    if prior:
        if prior.email.lower()!=email.strip().lower() or (source_key and prior.source_key!=source_key):
            raise IntegrationError('conflict','任务编号已用于另一账号')
        return prior
    key,row=capability(db,email,source_key,automatic)
    cfg=settings(db)
    now=time.time()
    job=RecoveryJob(id=request_id,source_key=key,email=row.email,
        target=cfg['site_id']+'|'+target(cfg),created_at=now,updated_at=now)
    db.add(job)
    try:db.commit()
    except __import__('sqlalchemy').exc.IntegrityError:
        db.rollback()
        return submit_recovery(db,request_id,email,source_key,automatic)
    return job


def run_recovery(identifier):
    with SessionLocal() as db:
        changed=db.execute(update(RecoveryJob).where(RecoveryJob.id==identifier,RecoveryJob.state=='queued')
                           .values(state='running',updated_at=time.time(),message='正在登录')).rowcount
        db.commit()
        if not changed:return
        job=db.get(RecoveryJob,identifier)
        key,email=job.source_key,job.email
        requested_at=job.created_at
        cfg=settings(db)
        if cfg['site_id']+'|'+target(cfg)!=job.target:
            job.state,job.code,job.message='failed','destination_changed','目标已改变，未登录'
            db.commit();return
    try:
        with login_destination(cfg):
            if key.startswith('external:'):
                from app.services.external_login import login_and_store
                result=login_and_store(int(key.split(':')[1]),request_started_at=requested_at,network_retries=0,sync_to_sub2=False)
            else:
                result=login_pool(int(key.split(':')[1]),request_started_at=requested_at)
        with SessionLocal() as db:
            job=db.get(RecoveryJob,identifier)
            job.state='done' if result.get('ok') else 'failed'
            job.code=result.get('code') or ''
            job.message='登录完成，后续同步独立重试' if result.get('ok') else '登录未完成，请检查账号资料与取信配置'
            job.updated_at=time.time()
            db.commit()
    except Exception:
        with SessionLocal() as db:
            job=db.get(RecoveryJob,identifier)
            job.state,job.code,job.message='failed','outcome_unknown','登录结果未确认，不自动重放此任务'
            job.updated_at=time.time();db.commit()


def login_pool(mid, session_factory=None, *, request_started_at=None):
    session_factory = session_factory or SessionLocal
    from app.services import login_coordinator, pool_login, firefly, proxy_pool
    from app.crud import setting as setting_crud
    with session_factory() as db:
        member=source(db,'pool:'+str(mid));email=member.email
        destination=settings(db)
    def execute():
        with session_factory() as db:
            member=source(db,'pool:'+str(mid))
            rt,cid,mail_url=pool_login._resolve_creds(db,member)
            cfg=setting_crud.get_settings(db)
        def save_rotation(refresh_token='', **_):
            if refresh_token:
                with session_factory() as db:
                    login_coordinator.assert_owner(db)
                    member=source(db,'pool:'+str(mid))
                    if member.email!=email:raise IntegrationError('identity_mismatch','账号已修改')
                    member.refresh_token=refresh_token;db.commit()
        rec=firefly.register_account(email=email,refresh_token=rt,client_id=cid,mail_url=mail_url,
                on_credentials=save_rotation,
                proxy_url=proxy_pool.next_proxy(cfg.proxy_url if cfg.proxy_enabled else ''),otp_timeout=180)
        if not rec.get('cookie'):
            return {'ok':False,'code':'login_failed','cookie':''}
        with session_factory() as db:
            login_coordinator.assert_owner(db)
            member=source(db,'pool:'+str(mid))
            if member.email!=email:raise IntegrationError('identity_mismatch','账号已修改')
            member.cookie=rec['cookie'];member.registered=True
            member.status='registered';member.message='已获取 Adobe Cookie'
            if rec.get('credits') is not None:member.credits=rec['credits']
            if not member.access_token:
                member.access_token=rec.get('access_token') or ''
                member.expires_at=rec.get('expires_at')
            if rec.get('rotated_refresh_token'):member.refresh_token=rec['rotated_refresh_token']
            record_cookie(db,'pool:'+str(mid),email,member.cookie)
            db.commit()
        return {**rec,'ok':True,'cookie':rec['cookie'],'code':''}
    with login_destination(destination):
        return login_coordinator.run('pool:'+str(mid),email,execute,session_factory,
                                     lambda db:{'cookie':source(db,'pool:'+str(mid)).cookie},
                                     requested_at=request_started_at)


def job_result(job):
    return {'job_id':job.id,'email':job.email,'source_key':job.source_key,'state':job.state,
            'ok':job.state=='done','managed':True,'code':job.code,'message':job.message}

_stop=threading.Event()
_thread=None
_login_executor=ThreadPoolExecutor(max_workers=3,thread_name_prefix='recovery-login')
_delivery_executor=ThreadPoolExecutor(max_workers=3,thread_name_prefix='credential-delivery')
_pending=set()
_guard=threading.Lock()
_last_inventory={}


def tick():
    with SessionLocal() as db:
        cfg=settings(db)
        enabled=cfg['enabled']
        now=time.time()
        # A restart never replays a running login. The live lease can belong to
        # another process; only stale ownership is marked as unknown.
        for job in db.scalars(select(RecoveryJob).where(RecoveryJob.state=='running',RecoveryJob.updated_at<now-120)):
            lease=db.get(LoginLease,job.email.lower())
            if not lease or lease.expires_at<now:
                job.state,job.code,job.message='failed','outcome_unknown','登录进程中断，请检查结果后人工重试'
                job.updated_at=now
        db.commit()
        if not enabled:return
        jobs=list(db.scalars(select(RecoveryJob.id).where(RecoveryJob.state=='queued').order_by(RecoveryJob.created_at).limit(12)))
        deliveries=list(db.scalars(select(CredentialDelivery.key).where(CredentialDelivery.state.in_(['pending','retry']),CredentialDelivery.next_at<=now,CredentialDelivery.lease_until<now).order_by(CredentialDelivery.updated_at).limit(12)))
        has_receipts=db.scalar(select(CredentialDelivery.key).where(CredentialDelivery.site_id==cfg['site_id'],CredentialDelivery.state.in_(['ready','paused','attention'])).limit(1))
    for kind,keys,executor,action in [('login',jobs,_login_executor,run_recovery),('delivery',deliveries,_delivery_executor,deliver)]:
        for key in keys:
            tag=(kind,key)
            with _guard:
                if tag in _pending:continue
                _pending.add(tag)
            def work(tag=tag,key=key,action=action):
                try:action(key)
                finally:
                    with _guard:_pending.discard(tag)
            executor.submit(work)
    if not has_receipts:return
    tag=('inventory',cfg['site_id'],target(cfg))
    with _guard:
        if tag in _pending or now-_last_inventory.get(tag,0)<30:return
        _last_inventory[tag]=now
        _pending.add(tag)
    def refresh_inventory():
        try:reconcile_inventory()
        except Exception:pass  # Keep last known state and retry next interval.
        finally:
            with _guard:_pending.discard(tag)
    _delivery_executor.submit(refresh_inventory)


def start():
    global _thread
    if _thread and _thread.is_alive():return
    _stop.clear()
    def loop():
        while not _stop.is_set():
            try:tick()
            except Exception:pass
            _stop.wait(3)
    _thread=threading.Thread(target=loop,daemon=True,name='integration-outbox')
    _thread.start()


def stop():
    _stop.set()
