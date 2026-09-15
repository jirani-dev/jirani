from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import AuthRepo
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService

router = APIRouter(prefix="/setup", tags=["setup"])


def get_setup_service(db: Session = Depends(get_db)) -> SetupService:
    return SetupService(AuthService(AuthRepo(db)))


@router.get("", status_code=status.HTTP_200_OK)
def setup_page(
    setup_service: SetupService = Depends(get_setup_service),
) -> dict[str, str]:
    try:
        credentials = setup_service.get_admin_credentials()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return {
        "message": (
            f"Admin credentials - Username: {credentials['username']}, "
            f"Password: {credentials['password']}. "
            "Please change the password after first login."
        )
    }
