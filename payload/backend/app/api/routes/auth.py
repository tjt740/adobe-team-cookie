from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResult, Token, UserOut
from app.services import login_hints

router = APIRouter(prefix="/auth", tags=["认证"])
_optional_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login/oauth", auto_error=False)


@router.get("/login-hints", summary="展开已登记的本地与线上登录密码")
def credential_hints(request: Request, token: str | None = Depends(_optional_bearer),
                     db: Session = Depends(get_db)) -> JSONResponse:
    config = login_hints.read_config()
    if not login_hints.public_local_request(request, config):
        if not token:
            raise HTTPException(status_code=401, detail="请先登录管理员账号后查看登录密码")
        user = get_current_user(token=token, db=db)
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="仅管理员可以查看登录密码")
    data = login_hints.entries(db, config)
    if not data:
        raise HTTPException(status_code=404, detail="尚未登记登录密码")
    return JSONResponse({"entries": data}, headers={"Cache-Control": "private, no-store"})


@router.post("/login", response_model=LoginResult, summary="账号密码登录")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResult:
    user = user_crud.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = Token(access_token=create_access_token(user.id, token_version=user.token_version))
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
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return Token(access_token=create_access_token(user.id, token_version=user.token_version))


@router.get("/me", response_model=UserOut, summary="获取当前登录用户")
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
