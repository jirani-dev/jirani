from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.schemas import BookUpload, TagCreate
from app.schemas.book_schema import BookRead, BookSearchCriteria, BookUpdate, Page
from app.services.book_errors import (
    BookAlreadyExists,
    BookNotFound,
    InvalidBookFile,
    InvalidImageError,
)
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_metadata_reader import EpubMetadataReader

router = APIRouter(prefix="/books", tags=["books"])


def get_book_service(db: Session = Depends(get_db)) -> BookService:
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


async def _submitted_form_fields(request: Request) -> frozenset[str]:
    """Names of the form fields the client actually sent.

    FastAPI passes an empty form value to the handler as the parameter
    default, so `tags=""` ("remove every tag") is indistinguishable from an
    omitted field there. The raw form is the only place the difference
    survives.
    """
    form = await request.form()
    return frozenset(form.keys())


def _blank_to_none(value: str | None) -> str | None:
    """A blank query value means "no filter", not "match the empty string"."""
    if value is None or not value.strip():
        return None
    return value.strip()


@router.post("/upload", response_model=BookRead)
def upload_book(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    author: str | None = Form(None),
    level: str | None = Form(None),
    genre: str | None = Form(None),
    language: str | None = Form(None),
    tags: str | None = Form(None),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> BookRead:
    try:
        tag_list = [
            TagCreate(name=t.strip()) for t in (tags or "").split(",") if t.strip()
        ]
        metadata = BookUpload(
            title=title,
            author=author,
            level=level,
            genre=genre,
            language=language,
            tags=tag_list,
        )

        data = file.file.read()
        book_read = svc.create_from_upload(
            metadata, file.filename or "", data, file.content_type or ""
        )
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except InvalidBookFile as exc:
        raise HTTPException(status_code=400, detail="Invalid book file") from exc
    except BookAlreadyExists as exc:
        raise HTTPException(status_code=409, detail="Book already exists") from exc
    except (IntegrityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid book data") from exc
    return book_read


@router.get("/", response_model=Page[BookRead])
def list_books(
    title: str | None = Query(None),
    author: str | None = Query(None),
    level: str | None = Query(None),
    genre: str | None = Query(None),
    language: str | None = Query(None),
    tags: str | None = Query(None),
    extension: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> Page[BookRead]:
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    criteria = BookSearchCriteria(
        title=_blank_to_none(title),
        author=_blank_to_none(author),
        level=_blank_to_none(level),
        genre=_blank_to_none(genre),
        language=_blank_to_none(language),
        tags=tag_list or None,
        extension=_blank_to_none(extension),
    )
    return svc.search(criteria, limit=limit, offset=offset)


@router.get("/{book_uid}/stream")
def stream_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> Response:
    try:
        media_path, media_type = svc.resolve_stream(book_uid)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/books/{quote(media_path.name)}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{book_uid}/read")
def read_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> Response:
    try:
        media_path, _media_type = svc.read_book(book_uid)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/books/{quote(media_path.name)}",
            "Content-Type": "application/pdf",
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{book_uid}", response_model=BookRead)
def get_book_details(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(
        RoleChecker([RoleEnum.admin, RoleEnum.teacher, RoleEnum.student])
    ),
) -> BookRead:
    book = svc.get_book_by_uid(book_uid)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.put("/{book_uid}", response_model=BookRead)
def update_book(
    book_uid: str,
    title: str | None = Form(None),
    author: str | None = Form(None),
    level: str | None = Form(None),
    genre: str | None = Form(None),
    language: str | None = Form(None),
    tags: str | None = Form(None),
    cover: UploadFile | None = File(None),
    submitted: frozenset[str] = Depends(_submitted_form_fields),
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> BookRead:
    try:
        # Present-but-empty clears the tags; absent leaves them untouched.
        tag_list = (
            [TagCreate(name=t.strip()) for t in (tags or "").split(",") if t.strip()]
            if "tags" in submitted
            else None
        )
        metadata = BookUpdate(
            title=title,
            author=author,
            level=level,
            genre=genre,
            language=language,
            tags=tag_list,
        )
        cover_bytes = cover.file.read() if cover is not None else None
        return svc.update_book(
            book_uid,
            metadata,
            cover=cover_bytes,
            cover_filename=cover.filename if cover is not None else None,
        )
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image file") from exc
    except (IntegrityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid book data") from exc


@router.delete("/{book_uid}", status_code=204)
def delete_book(
    book_uid: str,
    svc: BookService = Depends(get_book_service),
    user: Account = Depends(RoleChecker([RoleEnum.admin, RoleEnum.teacher])),
) -> Response:
    try:
        svc.delete_book(book_uid)
    except BookNotFound as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    return Response(status_code=204)
