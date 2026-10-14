"""Allowlisted, read-only account health from the Sub2 inventory protocol."""
import re

FILTER_PATTERN = r"^(error|401|408|other|recovered|unknown|[45][0-9]{2})$"
REASONS = {'auth', 'quota', 'entitlement', 'timeout', 'proxy', 'network', 'upstream',
           'content', 'legacy', 'unknown', 'account_error', 'rate_limit', 'overload'}
SOURCES = {'business', 'test', 'account', 'legacy', 'connection_test'}
STAGES = {'token', 'prepare', 'upload', 'submit', 'poll', 'download'}


def project(account):
    # Older Sub2 versions cannot provide complete unresolved-model evidence.
    raw = account.get('account_health')
    if not isinstance(raw, dict) or raw.get('state') not in {'error', 'recovered', 'unknown'}:
        return {'state': 'unknown', 'codes': [], 'errors': []}
    errors = []
    for item in raw.get('errors') or []:
        if not isinstance(item, dict):
            continue
        code = item.get('code')
        errors.append({
            'code': code if type(code) is int and 400 <= code <= 599 else 0,
            'reason': item.get('reason') if item.get('reason') in REASONS else 'unknown',
            'source': item.get('source') if item.get('source') in SOURCES else 'unknown',
            'stage': item.get('stage') if item.get('stage') in STAGES else '',
        })
    state = 'error' if errors else raw['state']
    return {'state': state, 'codes': sorted({e['code'] for e in errors if e['code']}), 'errors': errors}


def combine(accounts):
    """Duplicate email accounts expose every error; one successful copy cannot hide another."""
    states = [project(a) for a in accounts]
    errors = [e for h in states for e in h['errors']]
    state = ('error' if any(h['state'] == 'error' for h in states) else
             'recovered' if states and all(h['state'] == 'recovered' for h in states) else 'unknown')
    return {'state': state, 'codes': sorted({e['code'] for e in errors if e['code']}), 'errors': errors}


def matches(health, value):
    if not value:
        return True
    if not re.fullmatch(FILTER_PATTERN, value):
        raise ValueError('不支持的 Sub2 账号状态')
    health = health or {}
    if value.isdigit():
        return int(value) in health.get('codes', [])
    if value == 'other':
        return health.get('state') == 'error' and (
            not health.get('errors') or any(e.get('code') not in (401, 408) for e in health['errors']))
    return health.get('state', 'unknown') == value
