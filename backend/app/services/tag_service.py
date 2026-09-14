from sqlalchemy.orm import Session

from app.repositories.tag_repo import TagRepo
from app.schemas.tag_schema import TagRead


class TagService:
    def __init__(self, db: Session):
        self.db = db

    def list_tags(self) -> list[TagRead]:
        return [TagRead.model_validate(tag) for tag in TagRepo(self.db).get_all_tags()]
