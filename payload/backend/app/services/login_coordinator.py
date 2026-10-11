"""All login entry points share a database lease per normalized email.

A heartbeat keeps long OTP waits owned. An expired worker is fenced at credential
commit; a duplicate caller joins the current result rather than logging in again.
"""
import contextvars
import threading
import time
import uuid
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.models.integration import LoginLease

_current = contextvars.ContextVar('login_owner', default=None)
_GUARD = threading.RLock()


def assert_owner(db):
    current = _current.get()
    if current:
        email, owner = current
        # A conditional write holds ownership until the credential transaction
        # commits. A SELECT alone leaves a gap in which another worker can claim.
        with db.no_autoflush:
            owned = db.execute(update(LoginLease).where(
                LoginLease.email == email, LoginLease.owner == owner,
                LoginLease.expires_at > time.time()
            ).values(expires_at=time.time()+90)).rowcount
        if not owned:
            raise RuntimeError('登录任务已失去所有权，未保存旧结果')


def run(source_key, email, action, session_factory, read_result, *, requested_at=None, automatic=False):
    email = email.strip().lower()
    requested_at = time.time() if requested_at is None else requested_at
    owner = uuid.uuid4().hex
    joined_owner = None
    deadline = time.monotonic() + 360
    while True:
        with _GUARD, session_factory() as db:
            row = db.get(LoginLease, email)
            now = time.time()
            if row and row.source_key == source_key and row.result is not None and (
                    row.owner == joined_owner or row.expires_at >= requested_at):
                result = dict(row.result)
                if result.get('ok'):
                    result.update(read_result(db))
                return result
            # Every completed login contributes a durable per-email cooldown.
            # Explicit human logins may bypass it; automatic callers may not.
            # Keep successful overlapping callers on the join path above.
            if automatic and row and row.expires_at <= now:
                retry_after = ((row.result or {}).get('retry_after') or
                               row.expires_at + (900 if (row.result or {}).get('ok') else 300))
                if retry_after > now:
                    return {'ok': False, 'cookie': '', 'code': 'login_cooldown',
                            'retry_after': retry_after,
                            'message': f'自动登录冷却中，约 {int(retry_after-now)+1} 秒后可重试'}
            if not row:
                db.add(LoginLease(email=email, owner=owner, source_key=source_key, expires_at=now+90))
                try:
                    db.commit()
                    break
                except IntegrityError:
                    db.rollback()
                    continue
            if row.expires_at <= now:
                # Joining an interrupted task must not silently start another login.
                if joined_owner:
                    return {'ok': False, 'cookie': '', 'code': 'outcome_unknown', 'message': '原登录任务中断，请检查结果后重试'}
                claimed = db.execute(update(LoginLease).where(LoginLease.email==email, LoginLease.expires_at<=now)
                                     .values(owner=owner, source_key=source_key, expires_at=now+90, result=None)).rowcount
                db.commit()
                if claimed:
                    break
            else:
                if row.source_key != source_key:
                    return {'ok': False, 'cookie': '', 'code': 'busy', 'message': '同邮箱的另一来源正在登录，请稍后重试'}
                joined_owner = row.owner
        if time.monotonic() > deadline:
            return {'ok': False, 'cookie': '', 'code': 'busy', 'message': '账号已有登录任务，尚未结束'}
        time.sleep(.2)

    stop = threading.Event()
    def heartbeat():
        while not stop.wait(20):
            try:
                with session_factory() as db:
                    db.execute(update(LoginLease).where(LoginLease.email==email, LoginLease.owner==owner)
                               .values(expires_at=time.time()+90))
                    db.commit()
            except Exception:
                pass  # Loss of the lease will fence the credential write.
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    token = _current.set((email, owner))
    result = {'ok': False, 'code': 'internal', 'message': '登录中断，请检查任务结果'}
    try:
        result = action()
        return result
    finally:
        stop.set()
        _current.reset(token)
        with session_factory() as db:
            safe = {key: result.get(key) for key in ('ok', 'code')}
            safe['message'] = '' if result.get('ok') else '登录未完成，请查看账号任务'
            safe['retry_after'] = time.time() + (900 if result.get('ok') else 300)
            db.execute(update(LoginLease).where(LoginLease.email==email, LoginLease.owner==owner)
                       .values(result=safe, expires_at=time.time()))
            db.commit()
