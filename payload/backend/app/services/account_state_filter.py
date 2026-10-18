"""Match the account-status chips before pagination, export and batch login.

Only booleans and compact task summaries are read; credentials and task logs are
never loaded for this filter. Selected statuses are ORed; other filters AND them.
"""
from sqlalchemy import func, select, text
from app.models.external_member import ExternalMember
from app.services import manual_otp, sub2_account_health
from app.services.job_manager import ACTIVE_STATUSES, JOBS


def task_phases(db):
    JOBS._ensure_storage()
    rows = db.execute(text("""
        WITH ranked AS MATERIALIZED (
            SELECT j.id, e.id AS member_id,
                   ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY j.id DESC) AS position
            FROM job_records j, json_each(j.meta_json, '$.member_ids') m
            JOIN external_members e ON e.id=m.value
            WHERE j.deleted=0 AND j.type='external_login'
              AND j.created_at >= CAST(strftime('%s', e.created_at) AS INTEGER)
              AND (json_type(j.meta_json, '$.member_emails') IS NULL
                   OR json_extract(j.meta_json, '$.member_emails."' || e.id || '"')=e.email)
        ), latest AS MATERIALIZED (SELECT id, member_id FROM ranked WHERE position=1)
        SELECT l.member_id, j.status,
               (SELECT json_extract(i.value, '$.status') FROM json_each(j.extra_json, '$.items') i
                WHERE json_extract(i.value, '$.id')=l.member_id LIMIT 1) AS item_status
        FROM latest l JOIN job_records j ON j.id=l.id
    """)).mappings()
    out = {}
    for row in rows:
        phase, status = row['item_status'], row['status']
        if manual_otp.BROKER.status(row['member_id']):
            phase = 'otp'
        elif status in ACTIVE_STATUSES and (not phase or phase in ('pending', 'running')):
            phase = status if status in ('paused', 'pausing', 'cancelling') else (phase or 'running')
        elif status not in ACTIVE_STATUSES and phase in ('pending', 'running'):
            phase = 'cancelled' if status == 'cancelled' else 'failed' if status == 'error' else 'interrupted'
        out[row['member_id']] = phase
    return out


def match_ids(db, selected, stock=None):
    selected = set(selected)
    phases = task_phases(db) if any(s.startswith('task_') for s in selected) else {}
    rows = db.execute(select(ExternalMember.id, ExternalMember.login_status,
        (func.coalesce(ExternalMember.cookie, '') != '').label('cookie'),
        (func.trim(func.coalesce(ExternalMember.adobe_password, '')) != '').label('password')))
    matched = set()
    for row in rows:
        statuses = {row.login_status, 'has_cookie' if row.cookie else 'no_cookie',
                    'has_password' if row.password else 'no_password'}
        phase = ('otp' if any(s.startswith('task_') for s in selected) and manual_otp.BROKER.status(row.id)
                 else phases.get(row.id))
        if phase:
            statuses.add('task_' + phase)
        item = ((stock or {}).get('items') or {}).get(str(row.id)) or ((stock or {}).get('items') or {}).get(row.id) or {}
        if selected.intersection(statuses) or (item.get('in_stock') is True and any(
                value.startswith('sub2_') and sub2_account_health.matches(item.get('account_health'), value[5:])
                for value in selected)):
            matched.add(row.id)
    return matched
