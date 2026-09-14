from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Tag


class TagRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_all_tags(self) -> list[Tag]:
        return list(self.db_session.scalars(select(Tag)).all())

    def get_or_create_by_names(self, names: list[str]) -> list[Tag]:
        cleaned = [name.strip() for name in names if name.strip()]
        result: list[Tag] = []
        seen: set[str] = set()
        if not cleaned:
            return result
        matched = self.db_session.scalars(
            select(Tag).where(func.lower(Tag.name).in_({n.lower() for n in cleaned}))
        ).all()
        by_lower = {tag.name.lower(): tag for tag in matched}
        for name in cleaned:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            tag = by_lower.get(key)
            if tag is None:
                tag = Tag(name=key)
                self.db_session.add(tag)
                self.db_session.flush()
            result.append(tag)
        self.db_session.commit()
        return result
