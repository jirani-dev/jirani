import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Author, Book, Genre, Level, Tag, Video
from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.repositories.tag_repo import TagRepo
from app.schemas.book_schema import BookCreate, BookSearchCriteria
from app.schemas.tag_schema import TagCreate
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader
from app.services.video_service import VideoService

_EntityModel = type[Author] | type[Level] | type[Genre] | type[Tag]


def _make_book_service(db: Session) -> BookService:
    return BookService(
        book_repo=BookRepo(db),
        validator=ContentValidator(),
        storage=BookFileStorage(),
        epub_reader=EpubMetadataReader(),
        cover_generator=CoverGenerator(),
        author_repo=AuthorRepo(db),
        level_repo=LevelRepo(db),
        genre_repo=GenreRepo(db),
    )


def _create_book(
    db: Session,
    *,
    title: str,
    author_id: int | None = None,
    level_id: int | None = None,
    genre_id: int | None = None,
    tags: list[str] | None = None,
) -> Book:
    return BookRepo(db).create_book(
        BookCreate(
            uid=str(uuid.uuid4()),
            title=title,
            extension="pdf",
            file_path=f"{title}.pdf",
            author_id=author_id,
            level_id=level_id,
            genre_id=genre_id,
            tags=[TagCreate(name=t) for t in tags] if tags else [],
        )
    )


def _count_by_name(db: Session, model: _EntityModel, name: str) -> int:
    count = db.scalar(select(func.count()).select_from(model).where(model.name == name))
    return count if count is not None else 0


def _table_count(db: Session, model: _EntityModel) -> int:
    count = db.scalar(select(func.count()).select_from(model))
    return count if count is not None else 0


def test_delete_book_orphans_tag_single(db: Session) -> None:
    TagRepo(db).get_or_create_by_names(["math"])
    book = _create_book(db, title="One", tags=["math"])
    _make_book_service(db).delete_book(book.uid)
    db.expire_all()
    assert _count_by_name(db, Tag, "math") == 0


def test_delete_book_orphans_tag_shared(db: Session) -> None:
    TagRepo(db).get_or_create_by_names(["shared"])
    b1 = _create_book(db, title="A", tags=["shared"])
    b2 = _create_book(db, title="B", tags=["shared"])
    svc = _make_book_service(db)
    svc.delete_book(b1.uid)
    db.expire_all()
    assert _count_by_name(db, Tag, "shared") == 1
    svc.delete_book(b2.uid)
    db.expire_all()
    assert _count_by_name(db, Tag, "shared") == 0


def test_delete_video_orphans_tag(db: Session) -> None:
    tag = TagRepo(db).get_or_create_by_names(["clip"])[0]
    video = Video(title="clip", description=None, file_path="/tmp/nonexistent.mp4")
    db.add(video)
    db.flush()
    video.tags.append(tag)
    db.commit()
    db.refresh(video)
    VideoService(db).delete(video.id)
    db.expire_all()
    assert _count_by_name(db, Tag, "clip") == 0


def test_delete_book_orphans_author(db: Session) -> None:
    author_repo = AuthorRepo(db)
    solo = author_repo.get_or_create_by_name("Solo Author")
    book = _create_book(db, title="Solo", author_id=solo.id)
    _make_book_service(db).delete_book(book.uid)
    db.expire_all()
    assert _count_by_name(db, Author, "solo author") == 0

    shared = author_repo.get_or_create_by_name("Shared Author")
    b1 = _create_book(db, title="S1", author_id=shared.id)
    b2 = _create_book(db, title="S2", author_id=shared.id)
    svc = _make_book_service(db)
    svc.delete_book(b1.uid)
    db.expire_all()
    assert _count_by_name(db, Author, "shared author") == 1
    svc.delete_book(b2.uid)
    db.expire_all()
    assert _count_by_name(db, Author, "shared author") == 0


def test_delete_book_orphans_genre(db: Session) -> None:
    genre_repo = GenreRepo(db)
    solo = genre_repo.get_or_create_by_name("Solo Genre")
    book = _create_book(db, title="SoloG", genre_id=solo.id)
    _make_book_service(db).delete_book(book.uid)
    db.expire_all()
    assert _count_by_name(db, Genre, "solo genre") == 0

    shared = genre_repo.get_or_create_by_name("Shared Genre")
    b1 = _create_book(db, title="G1", genre_id=shared.id)
    b2 = _create_book(db, title="G2", genre_id=shared.id)
    svc = _make_book_service(db)
    svc.delete_book(b1.uid)
    db.expire_all()
    assert _count_by_name(db, Genre, "shared genre") == 1
    svc.delete_book(b2.uid)
    db.expire_all()
    assert _count_by_name(db, Genre, "shared genre") == 0


def test_search_purity_guard(db: Session) -> None:
    author_repo = AuthorRepo(db)
    author = author_repo.get_or_create_by_name("Guard Author")
    book = _create_book(db, title="Guard", author_id=author.id)
    _make_book_service(db).delete_book(book.uid)
    db.expire_all()

    counts_before = (
        _table_count(db, Author),
        _table_count(db, Level),
        _table_count(db, Genre),
    )
    page = BookRepo(db).search(BookSearchCriteria(author="nobody"), limit=10, offset=0)
    assert page.total == 0
    assert page.items == []
    counts_after = (
        _table_count(db, Author),
        _table_count(db, Level),
        _table_count(db, Genre),
    )
    assert counts_after == counts_before
