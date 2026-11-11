from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.level import Level


class LevelRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_orphans(self) -> int:
        orphan_ids = list(
            self.db.scalars(select(Level.id).where(~Level.books.any())).all()
        )
        if not orphan_ids:
            return 0
        self.db.execute(delete(Level).where(Level.id.in_(orphan_ids)))
        self.db.commit()
        return len(orphan_ids)

    def get_by_name(self, name: str) -> Level | None:
        # Case-insensitive lookup that returns the row as stored and never
        # creates one: book search turns a miss into "no results".
        return self.db.execute(
            select(Level).where(func.lower(Level.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Level:
        # Reuse an existing row whatever case it was stored in; a new row is
        # stored lowercased.
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        entity = Level(name=name.strip().lower())
        self.db.add(entity)
        self.db.commit()  # commit-stays-in-repo (legacy convention)
        self.db.refresh(entity)
        return entity

    def list_all(self) -> list[Level]:
        return list(self.db.scalars(select(Level).order_by(Level.name)).all())
