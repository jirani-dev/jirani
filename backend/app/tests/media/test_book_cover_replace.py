import io
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.book import Book
from app.tests.conftest import auth_headers, login, setup_admin

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _seed_book(db, *, uid: str, **kwargs) -> Book:
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


def _patch_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    (tmp_path / "books").mkdir()
    (tmp_path / "covers").mkdir()


def _admin_headers(client, setup_paths) -> dict[str, str]:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def test_put_replaces_old_cover(db, client, monkeypatch, tmp_path, setup_paths):
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
    body = response.json()
    assert body["cover_url"] == "/static/covers/bkcov0001.png"
    assert not (tmp_path / "covers" / "bkcov0001.jpg").exists()
    new_cover = tmp_path / "covers" / "bkcov0001.png"
    assert new_cover.read_bytes() == PNG_BYTES
    db.expire_all()
    row = db.execute(select(Book).where(Book.uid == "bkcov0001")).scalar_one()
    assert row.cover_path == "bkcov0001.png"


def test_put_rejects_executable_magic_400(
    db, client, monkeypatch, tmp_path, setup_paths
):
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


def test_put_without_cover_keeps_cover(db, client, monkeypatch, tmp_path, setup_paths):
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


def test_put_empty_cover_bytes_400(db, client, monkeypatch, tmp_path, setup_paths):
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


def test_put_oversized_cover_400(db, client, monkeypatch, tmp_path, setup_paths):
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
