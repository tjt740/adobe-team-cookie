from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_superuser
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin_user import AdminCreate, AdminUpdate, PasswordInput
from app.schemas.auth import UserOut
from app.services import log_store

router = APIRouter(prefix="/admin/users", tags=["登录用户管理"])


@contextmanager
def _write(db: Session, actor: User):
    # Serialize changes before rechecking the actor and last administrator.
    # Authentication's read transaction must not become a stale write snapshot.
    actor_id, version = actor.id, actor.token_version
    db.rollback()
    try:
        if db.get_bind().dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        else:
            db.execute(select(User.id).order_by(User.id).with_for_update()).all()
        current = db.get(User, actor_id, populate_existing=True)
        if not current or not current.is_active or not current.is_superuser or current.token_version != version:
            raise HTTPException(401, "登录状态已改变，请重新登录")
        yield current
        db.commit()
    except Exception:
        db.rollback()
        raise


def _target(db: Session, user_id: int) -> User:
    user = db.get(User, user_id, populate_existing=True)
    if not user:
        raise HTTPException(404, "登录用户不存在")
    return user


def _audit(actor: str, action: str, target: str):
    log_store.STORE.add("INFO", "admin_users", f"管理员 {actor} {action}登录用户 {target}")


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), actor: User = Depends(require_superuser)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: AdminCreate, db: Session = Depends(get_db), actor: User = Depends(require_superuser)):
    hashed = hash_password(payload.password.get_secret_value())
    try:
        with _write(db, actor) as current:
            if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
                raise HTTPException(409, "用户名已存在")
            user = User(username=payload.username, nickname=payload.nickname.strip(), hashed_password=hashed,
                        is_active=True, is_superuser=True, token_version=0)
            db.add(user)
            db.flush()
            result, operator = UserOut.model_validate(user), current.username
    except IntegrityError:
        raise HTTPException(409, "用户名已存在") from None
    _audit(operator, "新增", result.username)
    return result


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: AdminUpdate, db: Session = Depends(get_db),
                actor: User = Depends(require_superuser)):
    with _write(db, actor) as current:
        user = _target(db, user_id)
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("is_active") is False:
            if user.id == current.id:
                raise HTTPException(400, "不能停用当前登录账号")
            active_admins = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True), User.is_superuser.is_(True)))
            if user.is_active and user.is_superuser and active_admins <= 1:
                raise HTTPException(400, "必须保留至少一个启用的管理员")
            if user.is_active:
                user.token_version += 1
        if "nickname" in changes:
            user.nickname = changes["nickname"].strip()
        if "is_active" in changes:
            user.is_active = changes["is_active"]
        db.flush()
        result, operator = UserOut.model_validate(user), current.username
    action = "启用" if changes.get("is_active") is True else "停用" if changes.get("is_active") is False else "编辑"
    _audit(operator, action, result.username)
    return result


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(user_id: int, payload: PasswordInput, db: Session = Depends(get_db),
                   actor: User = Depends(require_superuser)):
    hashed = hash_password(payload.password.get_secret_value())
    with _write(db, actor) as current:
        user = _target(db, user_id)
        if user.id == current.id:
            raise HTTPException(400, "请在「管理员密码」中修改自己的密码")
        user.hashed_password = hashed
        user.token_version += 1
        db.flush()
        result, operator = UserOut.model_validate(user), current.username
    _audit(operator, "重置密码：", result.username)
    return result
