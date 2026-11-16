from sqlalchemy import false, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Book, Tag
from app.repositories.author_repo import AuthorRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.repositories.tag_repo import TagRepo
from app.schemas.book_schema import BookCreate, BookSearchCriteria
from app.schemas.tag_schema import TagCreate
from app.services.book_errors import BookAlreadyExists, BookNotFound


class BookRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_book_by_uid(self, book_uid: str) -> Book | None:
        stmt = (
            select(Book)
            .options(
                selectinload(Book.author),
                selectinload(Book.level),
                selectinload(Book.genre),
                selectinload(Book.tags),
            )
            .where(Book.uid == book_uid)
        )
        return self.db_session.execute(stmt).scalar_one_or_none()

    def create_book(self, book_create: BookCreate) -> Book:
        if self.get_book_by_uid(book_create.uid):
            raise BookAlreadyExists(f"Book with UID {book_create.uid} already exists")

        new_book = Book(**book_create.model_dump(exclude={"tags"}))
        try:
            new_book.tags = self._resolve_tags(book_create.tags)
            self.db_session.add(new_book)
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
        self.db_session.refresh(new_book)
        return new_book

    def cleanup_orphan_tags(self) -> None:
        try:
            TagRepo(self.db_session).delete_orphans()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise

    def delete_book(self, book_uid: str) -> None:
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        try:
            self.db_session.delete(book)
            self.db_session.flush()
            TagRepo(self.db_session).delete_orphans()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise

    def update_book(
        self, book_uid: str, book_update: BookCreate, *, replace_tags: bool = True
    ) -> Book:
        """Overwrite the book's columns; its tags only when replace_tags is set."""
        book = self.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")

        try:
            # Resolve tags before touching the book: the lookup may flush.
            tags = self._resolve_tags(book_update.tags) if replace_tags else None
            for key, value in book_update.model_dump(exclude={"tags"}).items():
                setattr(book, key, value)
            if tags is not None:
                book.tags = tags
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
        self.db_session.refresh(book)
        if replace_tags:
            self.cleanup_orphan_tags()
        return book

    def set_cover(self, book: Book, cover_path: str) -> Book:
        book.cover_path = cover_path
        self.db_session.commit()
        self.db_session.refresh(book)
        return book

    def search(
        self, criteria: BookSearchCriteria, *, limit: int, offset: int
    ) -> tuple[list[Book], int]:
        stmt = select(Book).options(
            selectinload(Book.tags),
            selectinload(Book.author),
            selectinload(Book.level),
            selectinload(Book.genre),
        )

        if criteria.title is not None:
            # autoescape: "%" and "_" typed into the search box are literals.
            stmt = stmt.where(Book.title.icontains(criteria.title, autoescape=True))
        if criteria.language is not None:
            stmt = stmt.where(Book.language == criteria.language)
        if criteria.extension is not None:
            stmt = stmt.where(Book.extension == criteria.extension)
        if criteria.tags:
            # Stored names keep the case they were first created with.
            names = [t.lower() for t in criteria.tags]
            stmt = stmt.where(Book.tags.any(func.lower(Tag.name).in_(names)))
        if criteria.metadata_:
            stmt = stmt.where(Book.metadata_.contains(criteria.metadata_))

        for repo, value, column in (
            (AuthorRepo, criteria.author, Book.author_id),
            (LevelRepo, criteria.level, Book.level_id),
            (GenreRepo, criteria.genre, Book.genre_id),
        ):
            if value is not None:
                entity = repo(self.db_session).get_by_name(value)
                stmt = stmt.where(column == entity.id if entity else false())

        total = self.db_session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Book.created_at.desc(), Book.id.desc())
            .limit(limit)
            .offset(offset)
        )
        books = list(self.db_session.execute(stmt).scalars().all())
        return books, total

    def _resolve_tags(self, tags: list[TagCreate]) -> list[Tag]:
        # Stays in the caller's transaction (commit=False), so a failed book
        # write does not leave freshly created tags behind.
        return TagRepo(self.db_session).get_or_create_by_names(
            [tag.name for tag in tags], commit=False
        )
