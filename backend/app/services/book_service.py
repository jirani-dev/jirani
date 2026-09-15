import uuid
from pathlib import Path

from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.repositories.tag_repo import TagRepo
from app.schemas import BookCreate, BookRead, BookUpload, TagCreate
from app.schemas.book_schema import BookSearchCriteria, BookUpdate, Page
from app.services.book_errors import BookAlreadyExists, BookNotFound
from app.services.book_file_storage import BookFileStorage
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_converter import EpubConverter
from app.services.epub_metadata_reader import EpubMetadataReader
from app.services.image_validator import ImageValidator

MEDIA_TYPES = {"pdf": "application/pdf", "epub": "application/epub+zip"}


class BookService:
    def __init__(
        self,
        book_repo: BookRepo,
        validator: ContentValidator,
        storage: BookFileStorage,
        epub_reader: EpubMetadataReader,
        cover_generator: CoverGenerator,
        author_repo: AuthorRepo,
        level_repo: LevelRepo,
        genre_repo: GenreRepo,
        tag_repo: TagRepo | None = None,
        image_validator: ImageValidator | None = None,
        epub_converter: EpubConverter | None = None,
    ) -> None:
        self.book_repo = book_repo
        self.validator = validator
        self.storage = storage
        self.epub_reader = epub_reader
        self.cover_generator = cover_generator
        self.author_repo = author_repo
        self.level_repo = level_repo
        self.genre_repo = genre_repo
        self.tag_repo = (
            tag_repo if tag_repo is not None else TagRepo(self.book_repo.db_session)
        )
        self.image_validator = (
            image_validator if image_validator is not None else ImageValidator()
        )
        self.epub_converter = (
            epub_converter if epub_converter is not None else EpubConverter()
        )

    def get_book_by_uid(self, book_uid: str) -> BookRead | None:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            return None
        return BookRead.model_validate(book)

    def search(
        self,
        book_search_criteria: BookSearchCriteria,
        *,
        limit: int,
        offset: int,
    ) -> Page[BookRead]:
        rows, total = self.book_repo.search(
            book_search_criteria, limit=limit, offset=offset
        )
        items = [BookRead.model_validate(row) for row in rows]
        return Page[BookRead](items=items, total=total, limit=limit, offset=offset)

    def resolve_stream(self, book_uid: str) -> tuple[Path, str]:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        media_path = self.storage.resolve(book.file_path)
        media_type = MEDIA_TYPES.get(media_path.suffix.lstrip("."))
        if media_type is None:
            raise BookNotFound(
                f"Book with UID {book_uid} has an unsupported media type"
            )
        return media_path, media_type

    def read_book(self, book_uid: str) -> tuple[Path, str]:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        media_path = self.storage.resolve(book.file_path)
        if media_path.suffix.lstrip(".").lower() == "pdf":
            return media_path, "application/pdf"
        dest_dir = self.storage.upload_dir
        dest = dest_dir / f"{media_path.stem}.read.pdf"
        if not dest.is_file():
            converted = self.epub_converter.convert(media_path, dest_dir)
            if converted is None:
                raise BookNotFound("Book not readable")
        return dest, "application/pdf"

    def get_book_file(self, book_uid: str) -> Path:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        return self.storage.resolve(book.file_path)

    def update_book(
        self,
        book_uid: str,
        data: BookUpdate,
        *,
        cover: bytes | None = None,
        cover_filename: str | None = None,
    ) -> BookRead:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")

        ext: str | None = None
        if cover is not None:
            ext = self.image_validator.validate(cover, cover_filename or "")

        old_author_name = book.author.name if book.author else None
        old_level_name = book.level.name if book.level else None
        old_genre_name = book.genre.name if book.genre else None

        author_id = (
            self.author_repo.get_or_create_by_name(data.author).id
            if data.author
            else book.author_id
        )
        level_id = (
            self.level_repo.get_or_create_by_name(data.level).id
            if data.level
            else book.level_id
        )
        genre_id = (
            self.genre_repo.get_or_create_by_name(data.genre).id
            if data.genre
            else book.genre_id
        )

        book_update = BookCreate(
            uid=book.uid,
            title=data.title if data.title and data.title.strip() else book.title,
            language=data.language if data.language is not None else book.language,
            extension=book.extension,
            author_id=author_id,
            level_id=level_id,
            genre_id=genre_id,
            file_path=book.file_path,
            cover_path=book.cover_path,
            tags=(
                data.tags
                if data.tags is not None
                else [TagCreate(name=t.name) for t in book.tags]
            ),
        )
        updated = self.book_repo.update_book(book_uid, book_update)

        if data.author is not None and data.author.strip().lower() != old_author_name:
            self.author_repo.delete_orphans()
        if data.level is not None and data.level.strip().lower() != old_level_name:
            self.level_repo.delete_orphans()
        if data.genre is not None and data.genre.strip().lower() != old_genre_name:
            self.genre_repo.delete_orphans()
        if data.tags is not None:
            self.tag_repo.delete_orphans()

        if cover is not None and ext is not None:
            old_cover = book.cover_path
            new_cover = self.storage.save_cover(book.uid, cover, ext)
            if old_cover:
                self.storage.delete_cover(old_cover)
            updated.cover_path = new_cover
            self.book_repo.db_session.commit()
            self.book_repo.db_session.refresh(updated)

        return BookRead.model_validate(updated)

    def delete_book(self, book_uid: str) -> None:
        book = self.book_repo.get_book_by_uid(book_uid)
        if not book:
            raise BookNotFound(f"Book with UID {book_uid} does not exist")
        self.storage.delete(book.file_path)
        if book.cover_path:
            self.storage.delete_cover(book.cover_path)
        self.book_repo.delete_book(book_uid)
        self.tag_repo.delete_orphans()
        self.author_repo.delete_orphans()
        self.level_repo.delete_orphans()
        self.genre_repo.delete_orphans()

    def create_from_upload(
        self,
        metadata: BookUpload,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> BookRead:
        extension = self.validator.validate(data, filename)
        title = metadata.title or Path(filename).stem.strip()

        uid = str(uuid.uuid4())
        rel_path = self.storage.save(data, filename, uid)
        abs_path = self.storage.resolve(rel_path)

        author = metadata.author
        language = metadata.language
        tags = list(metadata.tags)

        epub_meta = self.epub_reader.read(abs_path)
        if epub_meta is not None:
            author = author or epub_meta.author
            language = language or epub_meta.language
            existing = {t.name.strip().lower() for t in tags}
            for name in epub_meta.tags:
                if name.strip().lower() not in existing:
                    tags.append(TagCreate(name=name))

        author_id = (
            self.author_repo.get_or_create_by_name(author).id if author else None
        )
        level_id = (
            self.level_repo.get_or_create_by_name(metadata.level).id
            if metadata.level
            else None
        )
        genre_id = (
            self.genre_repo.get_or_create_by_name(metadata.genre).id
            if metadata.genre
            else None
        )

        cover_name: str | None = None
        if self.cover_generator.generate(abs_path, self.storage.cover_dir):
            cover_name = f"{abs_path.stem}.png"

        book_create = BookCreate(
            uid=uid,
            title=title,
            language=language,
            extension=extension,
            author_id=author_id,
            level_id=level_id,
            genre_id=genre_id,
            file_path=rel_path,
            cover_path=cover_name,
            tags=tags,
        )
        try:
            book = self.book_repo.create_book(book_create)
        except ValueError as err:
            self.storage.delete(rel_path)
            raise BookAlreadyExists(f"Book with UID {uid} already exists") from err

        return BookRead.model_validate(book)
