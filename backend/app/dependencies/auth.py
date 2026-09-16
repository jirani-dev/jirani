# app/dependencies/auth.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Account, RoleEnum
from app.repositories import AuthRepo

# auto_error=False: the SPA always sends a Bearer header, but native
# <audio>/<video> src requests can't set custom headers at all — they
# only carry cookies. Falling back to the access_token cookie below is
# what lets the audio/video players authenticate; without it, every
# stream request 401s silently (no header, no fallback) and playback
# just never starts.
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Account:
    token = (
        credentials.credentials if credentials else request.cookies.get("access_token")
    )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="couldn't validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        if not isinstance(username, str):
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = AuthRepo(db).get_by_username(username)

    if user is None:
        raise credentials_exception
    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Account = Depends(get_current_user)) -> Account:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
