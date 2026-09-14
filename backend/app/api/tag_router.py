from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.schemas.tag_schema import TagRead
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["tags"])


def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db)


@router.get("/", response_model=list[TagRead])
def get_all_tags(
    tag_service: TagService = Depends(get_tag_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> list[TagRead]:
    return tag_service.list_tags()
