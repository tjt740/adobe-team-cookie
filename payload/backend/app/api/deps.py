from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login/oauth")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = user_crud.get_by_id(db, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def capture_job_request(request: Request, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    from app.services.job_provenance import FILTERS, request_context
    filters = {}
    if request.url.path.endswith('/pool/batch-login-filter') and request.method == 'POST':
        body = await request.json()
        if isinstance(body, dict):
            filters = {key: body[key] for key in FILTERS if key in body}
    token = request_context.set({'operator': user.username, 'endpoint': request.url.path,
                                 'filters': filters, 'db': db})
    try:
        yield
    finally:
        request_context.reset(token)
