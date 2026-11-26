from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.author import Author


class AuthorRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_orphans(self) -> int:
        orphan_ids = list(
            self.db.scalars(select(Author.id).where(~Author.books.any())).all()
        )
        if not orphan_ids:
            return 0
        self.db.execute(delete(Author).where(Author.id.in_(orphan_ids)))
        self.db.commit()
        return len(orphan_ids)

    def get_by_name(self, name: str) -> Author | None:
        # Case-insensitive lookup that returns the row as stored and never
        # creates one: book search turns a miss into "no results".
        return self.db.execute(
            select(Author).where(func.lower(Author.name) == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_by_name(self, name: str) -> Author:
        # Reuse an existing row whatever case it was stored in; a new row is
        # stored lowercased.
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        entity = Author(name=name.strip().lower())
        self.db.add(entity)
        self.db.commit()  # commit-stays-in-repo (legacy convention)
        self.db.refresh(entity)
        return entity

    def list_all(self) -> list[Author]:
        return list(self.db.scalars(select(Author).order_by(Author.name)).all())
