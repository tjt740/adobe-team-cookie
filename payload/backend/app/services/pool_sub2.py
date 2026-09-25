"""Selected pool accounts: acquire Adobe web cookies, then create new Sub2 accounts.

Uses AdobeMember throughout; never imports or updates ExternalMember records.
The existing FF-iOS token/device pair remains available for pool operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import threading

from sqlalchemy import select

from app.crud import setting as setting_crud
from app.db.session import SessionLocal
from app.models.adobe_member import AdobeMember
from app.services import firefly, pool_login, proxy_pool, sub2_client
from app.services.job_manager import ACTIVE_STATUSES, JOBS, Job

SUBMIT_LOCK = threading.Lock()


def configuration(db):
    from app.api.routes.sub2 import _get_config
    cfg = _get_config(db)
    if not cfg['base_url'] or not cfg['admin_token']:
        raise ValueError('请先在 Sub2 管理保存地址和管理员密钥')
    if cfg['platform'] != 'adobe':
        raise ValueError('请在 Sub2 管理选择 Adobe Firefly 平台')
    if not cfg['group_ids']:
        raise ValueError('请先在 Sub2 管理选择并保存 Adobe 分组')
    return cfg


def config_identity(cfg):
    return (sub2_client.api_base(cfg['base_url']), cfg['admin_token'],
            cfg['platform'], tuple(sorted(cfg['group_ids'])))


def start(db, ids):
    ids = list(dict.fromkeys(ids))
    if not ids or len(ids) > 500:
        raise ValueError('请勾选 1 至 500 个号池账号')
    cfg = configuration(db)
    members = list(db.scalars(select(AdobeMember).where(AdobeMember.id.in_(ids))))
    if len(members) != len(ids):
        raise ValueError('部分账号已不存在，请刷新号池后重新选择')
    if any(m.is_admin for m in members):
        raise ValueError('请选择子号或导入账号，不能选择母号自身')
    with SUBMIT_LOCK:
        for active in JOBS.list_recent(100):
            if (active.type in ('pool_login', 'pool_cookie_sub2')
                    and active.status in ACTIVE_STATUSES
                    and set(active.meta.get('member_ids') or []) & set(ids)):
                raise ValueError(f'所选账号正在任务 #{active.id} 中处理，请等待完成')
        return JOBS.start('pool_cookie_sub2', lambda job: worker(job, cfg), meta={
            'member_ids': ids, 'target': len(ids),
            'sub2_url': sub2_client.api_base(cfg['base_url']),
            'group_ids': cfg['group_ids'],
        })


def _existing(cfg):
    result = sub2_client.list_existing(cfg, platform='adobe')
    if not result.get('ok'):
        raise ValueError('无法读取 Sub2 账号列表，请检查连接和管理员密钥后重试')
    return result


def _in_stock(member, existing):
    from app.api.routes.sub2 import _member_dedup_keys
    account_ids, email = _member_dedup_keys(member)
    return bool(account_ids & existing['account_ids'] or email in existing['emails'])


def _check_target(cfg):
    with SessionLocal() as db:
        if config_identity(configuration(db)) != config_identity(cfg):
            raise ValueError('Sub2 连接或分组已修改，本次停止推送，请重新提交')


def _save_rotation(mid, email, refresh_token='', **_):
    if not refresh_token:
        return
    with SessionLocal() as db:
        member = db.get(AdobeMember, mid)
        if member and member.email == email:
            member.refresh_token = refresh_token
            member.updated_at = datetime.now(timezone.utc)
            db.commit()


def _login_error(exc):
    # Never persist upstream response bodies: they may contain tokens or cookies.
    detail = str(exc).lower()
    if 'captcha' in detail or 'arkose' in detail:
        return 'Adobe 验证失败，请检查打码配置后重试'
    if 'otp' in detail or '验证码' in detail:
        return '登录验证码获取或验证失败，请检查取信配置后重试'
    if 'invalid_grant' in detail or 'refresh token' in detail:
        return '邮箱授权已失效，请更新邮箱 Refresh Token 后重试'
    if proxy_pool.is_proxy_error(detail):
        return '登录网络或代理连接失败，请检查代理后重试'
    return 'Adobe 登录失败，请检查账号、取信配置和代理后重试'


def _one(job, mid, cfg, report):
    _check_target(cfg)
    existing = _existing(cfg)
    with SessionLocal() as db:
        member = db.get(AdobeMember, mid)
        if not member or member.is_admin:
            raise ValueError('账号已删除或不再是子号')
        email = member.email
        report('checking', '检查 Sub2 库存', email)
        if _in_stock(member, existing):
            return 'existing', '已在库，跳过登录和推送'
        # Failed pushes keep the acquired cookie, so retry need not send another OTP.
        need_cookie = not (member.cookie or '').strip()
        if need_cookie:
            rt, cid, mail_url = pool_login._resolve_creds(db, member)
            if not ((rt and cid) or mail_url):
                raise ValueError('缺少取信配置，请在编辑中补充 Client ID 和 Refresh Token')
            settings = setting_crud.get_settings(db)
            proxy_raw = settings.proxy_url if settings.proxy_enabled else ''
    if need_cookie:
        report('login', '正在登录 Adobe，获取 Cookie', email)
        job.check_cancelled()
        try:
            record = firefly.register_account(
                email=email, refresh_token=rt, client_id=cid, mail_url=mail_url,
                proxy_url=proxy_pool.next_proxy(proxy_raw), otp_timeout=180,
                log=lambda _: job.check_cancelled(),
                on_credentials=lambda **values: _save_rotation(mid, email, **values),
            )
        except Exception as exc:
            raise ValueError(_login_error(exc)) from None
        cookie = (record.get('cookie') or '').strip()
        if not cookie:
            raise ValueError('Adobe 登录未返回 Cookie，未推送')
        with SessionLocal() as db:
            member = db.get(AdobeMember, mid)
            if not member or member.email != email:
                raise ValueError('账号在登录期间被修改或删除，未推送')
            member.cookie = cookie
            # Do not replace the FF-iOS token while keeping its device token.
            if not member.access_token:
                member.access_token = record.get('access_token') or ''
                member.expires_at = record.get('expires_at')
            if record.get('credits') is not None:
                member.credits = record['credits']
            if record.get('rotated_refresh_token'):
                member.refresh_token = record['rotated_refresh_token']
            member.registered = True
            member.status = 'registered'
            member.message = '已获取 Adobe Cookie'
            member.updated_at = datetime.now(timezone.utc)
            db.commit()
    job.check_cancelled()
    _check_target(cfg)
    # Another caller may have imported the account while Adobe login was running.
    existing = _existing(cfg)
    with SessionLocal() as db:
        member = db.get(AdobeMember, mid)
        if not member or member.email != email:
            raise ValueError('账号已修改或删除，未推送')
        if _in_stock(member, existing):
            return 'existing', '已在库，跳过重复推送'
        from app.api.routes.sub2 import REQUIRED_CREDITS, _member_item
        credits = float(member.credits) if member.credits is not None else -1
        if not math.isfinite(credits) or credits < REQUIRED_CREDITS:
            raise ValueError('Cookie 已保存，但积分未知或低于 4000，未推送')
        if not member.registered or not member.access_token or not member.cookie.strip():
            raise ValueError('缺少有效登录结果，未推送')
        item = _member_item(member)
    report('pushing', 'Cookie 已就绪，正在推送 Sub2', email)
    job.check_cancelled()
    try:
        response = sub2_client.import_tokens(cfg, [item])
    except Exception:
        raise ValueError('Cookie 已保存，Sub2 推送请求失败；可重新点击按钮重试') from None
    result = response.get('result') or {}
    if not any(r.get('index') == 0 and r.get('status') == 'created'
               for r in result.get('items', [])):
        raise ValueError('Cookie 已保存，Sub2 未确认创建成功；请检查连接或分组后重试')
    # Save completion even when cancellation arrives after the remote write.
    with SessionLocal() as db:
        member = db.get(AdobeMember, mid)
        if member and member.email == email and member.cookie == item['cookie']:
            member.sub2_pushed_at = datetime.now(timezone.utc)
            db.commit()
    return 'pushed', '已推送，在库 Sub2'


def worker(job: Job, cfg):
    ids = job.meta['member_ids']
    items = {mid: {'id': mid, 'email': '', 'status': 'pending', 'message': '等待处理'} for mid in ids}
    job.set_extra('items', list(items.values()))
    groups = sub2_client.list_groups(cfg)
    valid = {g['id'] for g in groups.get('groups', []) if g.get('platform') == 'adobe'}
    if not groups.get('ok') or not set(cfg['group_ids']).issubset(valid):
        raise ValueError('无法确认目标 Adobe 分组，请在 Sub2 管理重新加载并保存分组')
    _existing(cfg)  # Do not log into any Adobe account when Sub2 is unavailable.
    for mid in ids:
        job.check_cancelled()

        def report(state, message, email=''):
            items[mid].update(status=state, message=message)
            if email:
                items[mid]['email'] = email
            job.set_extra('items', list(items.values()))

        try:
            state, message = _one(job, mid, cfg, report)
            report(state, message)
            job.bump(success=1)
        except ValueError as exc:
            report('failed', str(exc))
            job.bump(fail=1)
        except Exception:
            report('failed', '处理失败，已保存的 Cookie 保留，请刷新后重试')
            job.bump(fail=1)
        job.log(f"[{items[mid]['email'] or mid}] {items[mid]['message']}")
    job.result = {'items': list(items.values()),
                  'pushed': sum(i['status'] == 'pushed' for i in items.values()),
                  'existing': sum(i['status'] == 'existing' for i in items.values()),
                  'failed': job.fail}
    job.persist()
