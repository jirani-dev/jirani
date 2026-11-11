from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.auth import RoleChecker, get_current_user
from app.models import Account, RoleEnum
from app.repositories import AuthRepo
from app.schemas import (
    AccountCreateRequest,
    AccountCreateResponse,
    AccountRead,
    BulkCreateRequest,
    BulkCreateResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordChangeResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services import AuthService
from app.services.auth_errors import UserNotFound

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepo(db))


# The handlers below are plain `def` on purpose: bcrypt and the synchronous
# database session block, so FastAPI must run them in its threadpool rather
# than on the event loop, where one slow login would stall every other request.
@router.post("/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    login_data: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user = auth_service.authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = auth_service.create_token_for_user(user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # JS can't read it — mitigates XSS token theft
        secure=False,  # plain http:// on your LAN — set True only if you add TLS
        samesite="strict",  # SPA + API are same-site (localhost) either way —
        # strict costs nothing here and narrows the CSRF surface for when
        # state-changing endpoints start accepting cookie-only auth.
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # same as the JWT's
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username,
        role=user.role,
        first_login=user.first_login,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response) -> dict[str, str]:
    # No auth required: logout's only job is clearing the cookie, and it
    # must still succeed against an already-expired or already-cleared one.
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=False,
        samesite="strict",
    )
    return {"message": "Logged out"}


@router.post(
    "/reset-password",
    response_model=PasswordChangeResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password(
    reset_data: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin])),
) -> PasswordChangeResponse:
    try:
        updated, password = auth_service.reset_password(
            reset_data.account_id, current_user.role
        )
    except UserNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return PasswordChangeResponse(
        message=f"Password reset for {updated.username}", new_password=password
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    change_data: ChangePasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(
        RoleChecker([RoleEnum.student, RoleEnum.teacher, RoleEnum.admin])
    ),
) -> dict[str, str]:
    if not auth_service.verify_password(
        change_data.old_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    try:
        auth_service.validate_credentials(
            current_user.role, change_data.new_password, context="self_change"
        )
        auth_service.change_password(current_user.username, change_data.new_password)
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: AccountCreateRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin])),
) -> AccountCreateResponse:
    try:
        new_user, credential = auth_service.create_user(user_data, current_user.role)
        return AccountCreateResponse(username=new_user.username, credential=credential)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except IntegrityError:
        raise HTTPException(
            status_code=400, detail="Username conflict - please retry."
        ) from None


@router.post("/users/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_users(
    bulk_data: BulkCreateRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin])),
) -> BulkCreateResponse:
    try:
        return auth_service.bulk_create_users(bulk_data, current_user.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except IntegrityError:
        raise HTTPException(
            status_code=400, detail="Username conflict - please retry."
        ) from None


@router.get("/users", status_code=status.HTTP_200_OK)
def list_users(
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin])),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[AccountRead]:
    try:
        return auth_service.get_all_users(current_user.role)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(
    current_user: Account = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AccountRead:
    try:
        return auth_service.get_user_by_id(current_user.id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
