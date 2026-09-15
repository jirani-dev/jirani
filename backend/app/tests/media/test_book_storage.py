from pathlib import Path

import pytest

from app.config import settings
from app.services.book_errors import BookNotFound
from app.services.book_file_storage import BookFileStorage


@pytest.fixture()
def storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BookFileStorage:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "books")
    monkeypatch.setattr(settings, "COVER_DIR", tmp_path / "covers")
    return BookFileStorage()


def test_resolve_rejects_traversal(storage: BookFileStorage) -> None:
    with pytest.raises(BookNotFound):
        storage.resolve("../../../../etc/passwd")


def test_resolve_returns_path_inside_upload_dir(
    storage: BookFileStorage, tmp_path: Path
) -> None:
    rel = storage.save(b"data", "My Book.pdf", "bk0001")
    resolved = storage.resolve(rel)
    assert resolved == storage.upload_dir / rel
    assert Path(rel).parent == Path(".")
    assert resolved.read_bytes() == b"data"
    assert resolved.is_relative_to(tmp_path / "books")


def test_save_returns_relative_single_component_name(
    storage: BookFileStorage,
) -> None:
    name = storage.save(b"data", "My Book.pdf", "bk0001")
    assert "bk0001" in name
    assert name.endswith(".pdf")
    assert "/" not in name
    assert "\\" not in name


def test_hostile_filename_sanitized(storage: BookFileStorage) -> None:
    name = storage.save(b"x", "../../etc/evil; rm -rf.pdf", "bk0002")
    assert ".." not in name
    assert "/" not in name
    assert "\\" not in name
    assert " " not in name
    assert (storage.upload_dir / name).is_file()


def test_delete_missing_is_silent(storage: BookFileStorage) -> None:
    storage.delete("nope.pdf")


def test_delete_cover_missing_is_silent(storage: BookFileStorage) -> None:
    storage.delete_cover("nope.png")


def test_cover_dir_accessor(storage: BookFileStorage, tmp_path: Path) -> None:
    assert storage.cover_dir == tmp_path / "covers"
