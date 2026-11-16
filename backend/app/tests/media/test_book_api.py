import io
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.author import Author
from app.models.book import Book
from app.models.genre import Genre
from app.models.tag import Tag
from app.repositories.author_repo import AuthorRepo
from app.repositories.book_repo import BookRepo
from app.repositories.genre_repo import GenreRepo
from app.repositories.level_repo import LevelRepo
from app.schemas.book_schema import BookSearchCriteria, BookUpdate
from app.services.book_errors import BookAlreadyExists, BookNotFound
from app.services.book_file_storage import BookFileStorage
from app.services.book_service import BookService
from app.services.content_validator import ContentValidator
from app.services.cover_generator import CoverGenerator
from app.services.epub_converter import EpubConverter
from app.services.epub_metadata_reader import EpubMetadataReader
from app.tests.conftest import auth_headers, login, setup_admin

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _seed_book(db: Session, *, uid: str, **kwargs: Any) -> Book:
    book = Book(
        uid=uid,
        title=kwargs.pop("title", f"Title {uid}"),
        file_path=kwargs.pop("file_path", f"{uid}.pdf"),
        extension=kwargs.pop("extension", "pdf"),
        **kwargs,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def _make_svc(db: Session) -> BookService:
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


def _patch_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    (tmp_path / "books").mkdir()
    (tmp_path / "covers").mkdir()


def _admin_headers(client: TestClient, setup_paths: Path) -> dict[str, str]:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def _make_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data: bytes = doc.tobytes()
    doc.close()
    return data


def _make_epub(path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        zf.writestr(
            "content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
            'version="2.0" unique-identifier="id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>t</dc:title>'
            "<dc:language>en</dc:language>"
            '<dc:identifier id="id">x</dc:identifier></metadata><manifest>'
            '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/></spine></package>',
        )
        zf.writestr(
            "c1.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title>'
            "</head><body><p>hello</p></body></html>",
        )
    path.write_bytes(buf.getvalue())


@pytest.fixture()
def stream_env(
    client: TestClient,
    setup_paths: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, dict[str, str]]:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


@pytest.fixture()
def read_env(
    client: TestClient,
    setup_paths: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, dict[str, str]]:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


def test_update_book_persists_title(db: Session) -> None:
    _seed_book(db, uid="bkupd001")
    updated = _make_svc(db).update_book("bkupd001", BookUpdate(title="Renamed"))
    assert updated.title == "Renamed"
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkupd001")).scalar_one()
    assert row.title == "Renamed"


def test_update_book_missing_raises_book_not_found(db: Session) -> None:
    with pytest.raises(BookNotFound):
        _make_svc(db).update_book("missing1", BookUpdate(title="Renamed"))


def test_delete_book_removes_row_file_and_cover(
    db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(
        db, uid="bkdel0001", file_path="bkdel0001.pdf", cover_path="bkdel0001.jpg"
    )
    (tmp_path / "books" / "bkdel0001.pdf").write_bytes(b"%PDF-1.4 seed")
    (tmp_path / "covers" / "bkdel0001.jpg").write_bytes(b"\xff\xd8\xff seed")

    _make_svc(db).delete_book("bkdel0001")

    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkdel0001")).scalar_one_or_none()
    assert row is None
    assert not (tmp_path / "books" / "bkdel0001.pdf").exists()
    assert not (tmp_path / "covers" / "bkdel0001.jpg").exists()


def test_delete_book_missing_raises_book_not_found(db: Session) -> None:
    with pytest.raises(BookNotFound):
        _make_svc(db).delete_book("missing1")


def test_get_book_file_returns_contained_existing_path(
    db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(db, uid="bkget0001", file_path="bkget0001.pdf")
    (tmp_path / "books" / "bkget0001.pdf").write_bytes(b"%PDF-1.4 seed")

    path = _make_svc(db).get_book_file("bkget0001")

    assert path == (tmp_path / "books" / "bkget0001.pdf").resolve()
    assert path.is_file()


def test_get_book_file_missing_book_raises_book_not_found(db: Session) -> None:
    with pytest.raises(BookNotFound):
        _make_svc(db).get_book_file("missing1")


def test_get_book_file_missing_on_disk_raises_book_not_found(
    db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(db, uid="bkget0002", file_path="bkget0002.pdf")

    with pytest.raises(BookNotFound):
        _make_svc(db).get_book_file("bkget0002")


def test_upload_pdf_happy_path(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Real PDF", "tags": "math, algebra"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert (tmp_path / row.file_path).exists()


def test_upload_bad_magic_400_nothing_on_disk(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        data={"title": "Fake"},
        headers=headers,
    )
    assert response.status_code == 400
    assert not list(tmp_path.glob("*.pdf"))


def test_upload_requires_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Real PDF"},
    )
    assert response.status_code in (401, 403)


def test_upload_genre_form_linked(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Genre Book", "genre": "Sci-Fi"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert row.genre is not None
    assert row.genre.name == "sci-fi"


def test_upload_author_form_stored(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Author Book", "author": "Ada Lovelace"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == body["uid"])).scalar_one()
    assert row.author is not None
    assert row.author.name == "ada lovelace"


def test_upload_overlong_title_400(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "x" * 256},
        headers=headers,
    )
    assert response.status_code == 400
    assert not list(tmp_path.glob("*.pdf"))


def test_search_genre_filter_and_entities(db: Session) -> None:
    author = Author(name="Ada")
    genre = Genre(name="scifi")
    db.add(author)
    db.add(genre)
    db.commit()
    db.refresh(author)
    db.refresh(genre)

    scifi = _seed_book(db, uid="bk0001")
    scifi.genre = genre
    _seed_book(db, uid="bk0002")
    db.commit()

    rows, total = BookRepo(db).search(
        BookSearchCriteria(genre="SCIFI"), limit=10, offset=0
    )
    assert total == 1
    assert [row.uid for row in rows] == ["bk0001"]
    assert rows[0].genre_name == "scifi"


def test_search_unknown_author_matches_nothing(db: Session) -> None:
    _seed_book(db, uid="bk0001")
    _, total = BookRepo(db).search(
        BookSearchCriteria(author="nobody"), limit=10, offset=0
    )
    assert total == 0


def test_search_tags_or_semantics_and_honest_total(db: Session) -> None:
    b1 = _seed_book(db, uid="bk0001")
    b2 = _seed_book(db, uid="bk0002")
    t_math = Tag(name="math")
    t_algebra = Tag(name="algebra")
    db.add_all([t_math, t_algebra])
    db.flush()
    b1.tags.append(t_math)
    b1.tags.append(t_algebra)
    b2.tags.append(t_math)
    db.commit()

    rows, total = BookRepo(db).search(
        BookSearchCriteria(tags=["Math", "ALGEBRA"]), limit=2, offset=0
    )
    assert total == 2
    assert {row.uid for row in rows} == {"bk0001", "bk0002"}


def test_search_metadata_containment(db: Session) -> None:
    _seed_book(db, uid="bk0001", metadata_={"publisher": "Penguin"})
    _seed_book(db, uid="bk0002", metadata_={"publisher": "Puffin"})
    rows, total = BookRepo(db).search(
        BookSearchCriteria(metadata_={"publisher": "Penguin"}), limit=10, offset=0
    )
    assert total == 1
    assert [row.uid for row in rows] == ["bk0001"]


def test_search_pagination_pages_are_disjoint_and_complete(db: Session) -> None:
    for i in range(5):
        _seed_book(db, uid=f"bk{i:04d}")
    pages = [
        BookRepo(db).search(BookSearchCriteria(), limit=2, offset=off)
        for off in (0, 2, 4)
    ]
    uid_sets = [{row.uid for row in rows} for rows, _ in pages]
    assert all(total == 5 for _, total in pages)
    assert all(not (a & b) for a, b in zip(uid_sets, uid_sets[1:], strict=False))
    assert set().union(*uid_sets) == {f"bk{i:04d}" for i in range(5)}


def test_list_books_endpoint_authed_returns_page(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    _seed_book(db, uid="bklist01")
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    response = client.get("/books/", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["uid"] == "bklist01"


def test_book_responses_include_tags(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    # The frontend builds its tag chips, edit form and tag filter from this
    # field; BookRead used to omit it even though every query loads the tags.
    book = _seed_book(db, uid="bktags01")
    book.tags.append(Tag(name="math"))
    db.commit()
    headers = _admin_headers(client, setup_paths)

    listed = client.get("/books/", headers=headers).json()["items"][0]
    detail = client.get("/books/bktags01", headers=headers).json()

    assert [tag["name"] for tag in listed["tags"]] == ["math"]
    assert [tag["name"] for tag in detail["tags"]] == ["math"]
    assert isinstance(detail["tags"][0]["id"], int)


def test_list_books_unauthenticated_401(client: TestClient) -> None:
    response = client.get("/books/")
    assert response.status_code == 401


def test_stream_authed_returns_x_accel_204(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, headers = stream_env
    uid = "abc123"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/stream", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Accept-Ranges"] == "bytes"


def test_stream_missing_book_404(
    client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    _, headers = stream_env
    response = client.get("/books/nonexistent/stream", headers=headers)
    assert response.status_code == 404


def test_stream_poisoned_file_path_404(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    _, headers = stream_env
    _seed_book(db, uid="evil", file_path="../../../../etc/passwd")
    response = client.get("/books/evil/stream", headers=headers)
    assert response.status_code == 404


def test_stream_missing_file_on_disk_404(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    _, headers = stream_env
    _seed_book(db, uid="gone", file_path="gone.pdf")
    response = client.get("/books/gone/stream", headers=headers)
    assert response.status_code == 404


def test_stream_unauthenticated_401(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, _ = stream_env
    uid = "abc123"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    # stream_env's login left an access_token cookie on this client — clear
    # it so the request truly carries no credentials (auth also falls back
    # to that cookie now, for native <audio>/<video> tags that can't send a
    # Bearer header).
    client.cookies.clear()
    response = client.get(f"/books/{uid}/stream")
    assert response.status_code == 401


def test_stream_cookie_only_auth_204(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    # stream_env's login left a valid access_token cookie on this client.
    # A native media tag can't send a custom Authorization header, so the
    # cookie alone must be enough — this is the exact codepath the
    # fallback in app/dependencies/auth.py exists for.
    tmp_path, _ = stream_env
    uid = "cookieauth"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/stream")
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"


def test_stream_epub_content_type(
    db: Session, client: TestClient, stream_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, headers = stream_env
    uid = "epub1"
    (tmp_path / f"{uid}.epub").write_bytes(b"PK\x03\x04 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    response = client.get(f"/books/{uid}/stream", headers=headers)
    assert response.headers["Content-Type"] == "application/epub+zip"


def test_put_replaces_old_cover(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0001", cover_path="bkcov0001.jpg")
    (tmp_path / "covers" / "bkcov0001.jpg").write_bytes(b"\xff\xd8 old cover")

    response = client.put(
        "/books/bkcov0001",
        files={"cover": ("artwork.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkcov0001")).scalar_one()
    # Every upload gets its own file name (see BookFileStorage.save_cover).
    assert row.cover_path is not None
    assert row.cover_path.startswith("bkcov0001_")
    assert row.cover_path.endswith(".png")
    assert response.json()["cover_url"] == f"/static/covers/{row.cover_path}"
    assert not (tmp_path / "covers" / "bkcov0001.jpg").exists()
    assert (tmp_path / "covers" / row.cover_path).read_bytes() == PNG_BYTES


def test_put_cover_twice_with_same_extension_keeps_the_new_file(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    # Regression: the second upload used to be written under the same name as
    # the first and then deleted as "the old cover".
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0006")

    first = client.put(
        "/books/bkcov0006",
        files={"cover": ("one.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=headers,
    )
    second = client.put(
        "/books/bkcov0006",
        files={"cover": ("two.png", io.BytesIO(PNG_BYTES + b"2"), "image/png")},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    # A new URL, so the day-long cache on /static/covers/ cannot serve the old one.
    assert second.json()["cover_url"] != first.json()["cover_url"]
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkcov0006")).scalar_one()
    assert row.cover_path is not None
    covers = list((tmp_path / "covers").iterdir())
    assert [cover.name for cover in covers] == [row.cover_path]
    assert covers[0].read_bytes() == PNG_BYTES + b"2"


def test_put_rejects_executable_magic_400(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0002")

    response = client.put(
        "/books/bkcov0002",
        files={"cover": ("evil.png", io.BytesIO(b"MZ" + b"\x00" * 100), "image/png")},
        headers=headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Invalid image file"
    assert list((tmp_path / "covers").iterdir()) == []


def test_put_without_cover_keeps_cover(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0003", cover_path="bkcov0003.jpg")
    (tmp_path / "covers" / "bkcov0003.jpg").write_bytes(b"\xff\xd8 keep")

    response = client.put(
        "/books/bkcov0003",
        data={"title": "Retitled"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["cover_url"] == "/static/covers/bkcov0003.jpg"
    assert (tmp_path / "covers" / "bkcov0003.jpg").exists()


def test_put_empty_cover_bytes_400(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0004")

    response = client.put(
        "/books/bkcov0004",
        files={"cover": ("empty.png", io.BytesIO(b""), "image/png")},
        headers=headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Invalid image file"
    assert list((tmp_path / "covers").iterdir()) == []


def test_put_oversized_cover_400(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "MAX_COVER_SIZE", 10)
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkcov0005")

    response = client.put(
        "/books/bkcov0005",
        files={"cover": ("big.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Invalid image file"
    assert list((tmp_path / "covers").iterdir()) == []


def _seed_tagged_book(db: Session, *, uid: str, tags: list[str]) -> Book:
    book = _seed_book(db, uid=uid)
    for name in tags:
        book.tags.append(Tag(name=name))
    db.commit()
    return book


def test_put_empty_tags_clears_every_tag(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    # The edit form sends tags="" once the last tag is removed. FastAPI maps an
    # empty form value to None, which used to read as "leave the tags alone".
    headers = _admin_headers(client, setup_paths)
    _seed_tagged_book(db, uid="bktag0001", tags=["math", "algebra"])

    response = client.put("/books/bktag0001", data={"tags": ""}, headers=headers)

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bktag0001")).scalar_one()
    assert row.tags == []
    assert db.scalars(select(Tag)).all() == []  # the orphaned tags were swept


def test_put_without_tags_field_keeps_tags(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    headers = _admin_headers(client, setup_paths)
    _seed_tagged_book(db, uid="bktag0002", tags=["math"])

    response = client.put(
        "/books/bktag0002", data={"title": "Retitled"}, headers=headers
    )

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bktag0002")).scalar_one()
    assert row.title == "Retitled"
    assert [tag.name for tag in row.tags] == ["math"]


def test_put_title_only_does_not_revalidate_existing_tags(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    # "c++" is not a name TagCreate accepts (audio and video tags are not
    # validated); a rename must not trip over a tag it does not touch.
    headers = _admin_headers(client, setup_paths)
    _seed_tagged_book(db, uid="bktag0003", tags=["c++"])

    response = client.put(
        "/books/bktag0003", data={"title": "Retitled"}, headers=headers
    )

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bktag0003")).scalar_one()
    assert [tag.name for tag in row.tags] == ["c++"]


def test_put_tag_with_underscore_does_not_match_a_similar_tag(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    # "_" is a LIKE wildcard: "sci_fi" used to resolve to the existing "sci-fi".
    headers = _admin_headers(client, setup_paths)
    _seed_tagged_book(db, uid="bktag0004", tags=["sci-fi"])
    _seed_book(db, uid="bktag0005")

    response = client.put("/books/bktag0005", data={"tags": "sci_fi"}, headers=headers)

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bktag0005")).scalar_one()
    assert [tag.name for tag in row.tags] == ["sci_fi"]


def test_put_overlong_title_400(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    headers = _admin_headers(client, setup_paths)
    _seed_book(db, uid="bkupd0002", title="Kept")

    response = client.put(
        "/books/bkupd0002", data={"title": "x" * 256}, headers=headers
    )

    assert response.status_code == 400, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkupd0002")).scalar_one()
    assert row.title == "Kept"


def test_upload_survives_unusable_embedded_subjects(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    # The file's own "subject" metadata becomes tags. Real-world subjects are
    # full of characters a tag may not contain, and repeat themselves; neither
    # may fail the upload (it used to answer 400 and leave the file on disk).
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    headers = _admin_headers(client, setup_paths)
    doc = pymupdf.open()
    doc.new_page()
    doc.set_metadata({"subject": "Science & Technology; fiction, Fiction"})
    data: bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/books/upload",
        files={"file": ("subjects.pdf", io.BytesIO(data), "application/pdf")},
        data={"title": "Subjects"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    db.expire_all()
    row = db.execute(select(Book).where(Book.title == "Subjects")).scalar_one()
    assert [tag.name for tag in row.tags] == ["fiction"]


def test_upload_that_fails_to_save_leaves_no_files(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup_paths: Path,
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    headers = _admin_headers(client, setup_paths)

    def refuse(self: BookRepo, book_create: object) -> Book:
        raise BookAlreadyExists("simulated conflict")

    monkeypatch.setattr(BookRepo, "create_book", refuse)

    response = client.post(
        "/books/upload",
        files={"file": ("real.pdf", io.BytesIO(_make_pdf()), "application/pdf")},
        data={"title": "Real PDF"},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert list((tmp_path / "books").iterdir()) == []
    assert list((tmp_path / "covers").iterdir()) == []


def test_delete_epub_book_removes_its_read_copy(
    db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dirs(monkeypatch, tmp_path)
    _seed_book(db, uid="bkdel0002", file_path="bkdel0002.epub", extension="epub")
    _make_epub(tmp_path / "books" / "bkdel0002.epub")
    svc = _make_svc(db)
    read_copy, _ = svc.read_book("bkdel0002")
    assert read_copy.is_file()

    svc.delete_book("bkdel0002")

    assert list((tmp_path / "books").iterdir()) == []


def test_search_title_treats_like_wildcards_literally(db: Session) -> None:
    _seed_book(db, uid="bk0001", title="100% Maths")
    _seed_book(db, uid="bk0002", title="1000 Maths")
    rows, total = BookRepo(db).search(
        BookSearchCriteria(title="100%"), limit=10, offset=0
    )
    assert total == 1
    assert [row.uid for row in rows] == ["bk0001"]


def test_search_tags_match_stored_case_insensitively(db: Session) -> None:
    # Tags keep the case they were first stored with (see test_tag_repo).
    book = _seed_book(db, uid="bk0001")
    book.tags.append(Tag(name="Math"))
    db.commit()
    rows, total = BookRepo(db).search(
        BookSearchCriteria(tags=["math"]), limit=10, offset=0
    )
    assert total == 1
    assert [row.uid for row in rows] == ["bk0001"]


def test_list_books_blank_filters_are_ignored(
    db: Session, client: TestClient, setup_paths: Path
) -> None:
    _seed_book(db, uid="bklist02")
    headers = _admin_headers(client, setup_paths)
    response = client.get(
        "/books/",
        params={"author": "", "level": " ", "genre": "", "language": "", "tags": " , "},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_read_pdf_book_serves_original(
    db: Session, client: TestClient, read_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, headers = read_env
    uid = "pdfbook"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Accept-Ranges"] == "bytes"


def test_read_epub_converts_to_read_pdf(
    db: Session, client: TestClient, read_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, headers = read_env
    uid = "epubbook"
    _make_epub(tmp_path / f"{uid}.epub")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.read.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    converted = tmp_path / f"{uid}.read.pdf"
    assert converted.exists()
    assert converted.read_bytes()[:5] == b"%PDF-"


def test_read_converter_failure_404(
    db: Session,
    client: TestClient,
    read_env: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path, headers = read_env
    uid = "brokencv"
    (tmp_path / f"{uid}.epub").write_bytes(b"PK\x03\x04 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    monkeypatch.setattr(EpubConverter, "convert", lambda self, source, dest_dir: None)
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Book not readable"


def test_read_epub_second_get_uses_cache(
    db: Session,
    client: TestClient,
    read_env: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path, headers = read_env
    uid = "cached"
    _make_epub(tmp_path / f"{uid}.epub")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    calls: list[str] = []
    original = EpubConverter.convert

    def counting(self: EpubConverter, source: Path, dest_dir: Path) -> Path | None:
        calls.append(source.name)
        return original(self, source, dest_dir)

    monkeypatch.setattr(EpubConverter, "convert", counting)
    first = client.get(f"/books/{uid}/read", headers=headers)
    second = client.get(f"/books/{uid}/read", headers=headers)
    assert first.status_code == 204
    assert second.status_code == 204
    assert len(calls) == 1


def test_read_unauthenticated_401(
    db: Session, client: TestClient, read_env: tuple[Path, dict[str, str]]
) -> None:
    tmp_path, _ = read_env
    uid = "noauth"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    # read_env's login left an access_token cookie on this client — clear it
    # so the request truly carries no credentials (auth also falls back to
    # that cookie now, for native <audio>/<video> tags that can't send a
    # Bearer header).
    client.cookies.clear()
    response = client.get(f"/books/{uid}/read")
    assert response.status_code == 401


def test_read_cookie_only_auth_204(
    db: Session, client: TestClient, read_env: tuple[Path, dict[str, str]]
) -> None:
    # read_env's login left a valid access_token cookie on this client.
    # usePdfViewer fetches this endpoint from the browser and must
    # authenticate via that cookie alone when no Bearer header is sent —
    # this is the exact codepath the fallback in app/dependencies/auth.py
    # exists for.
    tmp_path, _ = read_env
    uid = "cookieread"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/read")
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"
