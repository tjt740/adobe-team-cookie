"""Small, credential-free snapshots explaining where a background job came from."""
from contextvars import ContextVar
import re

from sqlalchemy import bindparam, text


request_context = ContextVar('job_request_context', default=None)
TYPES = {
    'external_login': ('外部子号登录', '外部子号', 'external', '批量登录', '登录 Adobe，保存 Cookie 并查询账号额度'),
    'pool_login': ('号池账号登录', '号池管理', '/pool', '批量登录', '刷新所选账号的 Token 与额度'),
    'pool_cookie_sub2': ('账号导入 Sub2', '号池管理', '/pool', '导入 Sub2', '获取 Cookie，将符合条件的账号导入 Sub2'),
    'admin_login': ('母号登录', '母号管理', '/adobe', '登录母号', '登录并获取组织管理权限'),
    'build_team': ('创建团队子号', '母号管理', '/adobe', '一键拉号', '为指定母号创建并注册团队子号'),
    'build_team_batch': ('批量创建团队子号', '母号管理', '/adobe', '批量拉号', '为多个母号创建并注册团队子号'),
    '子号清退': ('清退团队子号', '母号管理', '/adobe', '清退子号', '按所选范围清理组织中的子号'),
    '批量更新号池': ('同步成员到号池', '母号管理', '/adobe', '更新号池', '读取所选母号的成员并更新本地号池'),
}
FILTERS = ('keyword', 'registered_only', 'pool_type', 'has_token', 'credit_status',
           'credit_value', 'status_filter', 'export_status')


def capture_meta(job_type, meta):
    """Runs in the request thread, before the worker starts. Never retain a session."""
    out = dict(meta or {})
    ctx = request_context.get()
    if not ctx:
        return out
    out['operator'] = ctx['operator']
    definition = TYPES.get(job_type)
    if definition:
        _, label, path, action, _ = definition
        endpoint = ctx['endpoint']
        if endpoint.endswith('/batch-login-filter'):
            action = '登录筛选结果'
        elif '/batch-login-retry/' in endpoint:
            label, path, action = '任务列表', '/jobs', '重试未拿到 Token 的账号'
        elif endpoint.endswith('/external/members/import'):
            action = '导入邮箱后登录'
        elif re.search(r'/external/members/\d+/login$', endpoint):
            action = '账号重新登录'
        out['source'] = {'label': label, 'path': path, 'action': action, 'recorded': True}
    if ctx.get('filters'):
        out['filters'] = ctx['filters']
    if job_type in ('external_login', 'pool_login', 'pool_cookie_sub2'):
        ids, key = out.get('member_ids') or [], 'member_emails'
        table = 'external_members' if job_type == 'external_login' else 'adobe_members'
    else:
        ids, key, table = out.get('admin_ids') or [out.get('admin_id')], 'admin_emails', 'adobe_accounts'
    ids = [int(i) for i in ids if i]
    if ids:
        stmt = text(f'SELECT id,email FROM {table} WHERE id IN :ids').bindparams(bindparam('ids', expanding=True))
        out[key] = {str(row.id): row.email for row in ctx['db'].execute(stmt, {'ids': ids})}
    return out


def describe(job_type, meta, extra=None):
    """Old jobs use only recorded IDs/results; never guess identity from today's DB."""
    meta, extra = meta or {}, extra or {}
    title, label, path, action, description = TYPES.get(job_type, (job_type, '历史任务', '', '未记录', '查看本次执行结果与记录'))
    source = meta.get('source') or {'label': label, 'path': path, 'action': action, 'recorded': False}
    kind = 'external' if job_type == 'external_login' else 'pool' if job_type in ('pool_login', 'pool_cookie_sub2') else 'admin'
    ids = meta.get('member_ids') if kind != 'admin' else meta.get('admin_ids') or [meta.get('admin_id')]
    emails = dict(meta.get('member_emails' if kind != 'admin' else 'admin_emails') or {})
    for row in extra.get('items', []) + extra.get('teams', []):
        rid = row.get('id') or row.get('admin_id')
        if rid and row.get('email'):
            emails.setdefault(str(rid), row['email'])
    ids = list(dict.fromkeys([i for i in (ids or []) if i] + [int(i) for i in emails if str(i).isdigit()]))
    return {
        'title': title, 'description': description, 'source': source,
        'operator': meta.get('operator') or '',
        'accounts': [{'id': i, 'email': emails.get(str(i), ''), 'kind': kind} for i in ids],
        'retry_from_job': meta.get('retry_from_job'),
        'filters': {k: v for k, v in (meta.get('filters') or {}).items() if k in FILTERS},
        'destination': {'url': meta.get('sub2_url', ''), 'group_ids': meta.get('group_ids') or []} if job_type == 'pool_cookie_sub2' else None,
        'mode': meta.get('mode', ''), 'count': meta.get('count'),
    }
