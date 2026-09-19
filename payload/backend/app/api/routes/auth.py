from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResult, Token, UserOut

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResult, summary="账号密码登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResult:
    user = user_crud.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = Token(access_token=create_access_token(user.id))
    return LoginResult(token=token, user=UserOut.model_validate(user))


@router.post("/login/oauth", response_model=Token, include_in_schema=False)
def login_oauth(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    """兼容 Swagger UI 的 OAuth2 密码模式登录入口。"""
    user = user_crud.authenticate(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut, summary="获取当前登录用户")
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
