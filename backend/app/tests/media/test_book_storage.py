import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest

from app.config import settings
from app.services import book_file_storage
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


def test_overlong_filename_is_bounded(storage: BookFileStorage) -> None:
    # 255 characters is the limit of both common filesystems and
    # books.file_path; the uid and extension must still fit.
    uid = "0f8fad5b-d9cb-469f-a165-70867728950e"
    name = storage.save(b"x", "a" * 300 + ".pdf", uid)
    assert len(name) < 200
    assert name.endswith(f"_{uid}.pdf")
    assert (storage.upload_dir / name).is_file()


def test_save_cover_never_reuses_a_name(
    storage: BookFileStorage, tmp_path: Path
) -> None:
    first = storage.save_cover("bk0003", b"one", "png")
    second = storage.save_cover("bk0003", b"two", "png")
    assert first != second
    assert first.startswith("bk0003_") and first.endswith(".png")
    assert (tmp_path / "covers" / first).read_bytes() == b"one"
    assert (tmp_path / "covers" / second).read_bytes() == b"two"


def test_delete_missing_is_silent(storage: BookFileStorage) -> None:
    storage.delete("nope.pdf")
    storage.delete("nope.pdf", missing_ok=True)


def test_delete_refuses_to_leave_the_upload_dir(
    storage: BookFileStorage, tmp_path: Path
) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"secret")
    storage.upload_dir.mkdir(parents=True)
    storage.delete("../secret.txt")
    storage.delete("../secret.txt", missing_ok=True)
    assert outside.read_bytes() == b"secret"


def test_delete_cover_missing_is_silent(storage: BookFileStorage) -> None:
    storage.delete_cover("nope.png")


def test_cover_dir_accessor(storage: BookFileStorage, tmp_path: Path) -> None:
    assert storage.cover_dir == tmp_path / "covers"


def test_save_never_overwrites_an_existing_book_file(storage: BookFileStorage) -> None:
    first = storage.save(b"one", "My Book.pdf", "bk0001")
    with pytest.raises(FileExistsError):
        storage.save(b"two", "My Book.pdf", "bk0001")
    assert (storage.upload_dir / first).read_bytes() == b"one"


def test_save_that_fails_part_way_leaves_no_file(
    storage: BookFileStorage, fill_disk: Callable[[], None]
) -> None:
    fill_disk()
    with pytest.raises(OSError):
        storage.save(b"0123456789", "My Book.pdf", "bk0004")
    assert list(storage.upload_dir.iterdir()) == []


def test_save_cover_names_carry_a_whole_uuid(storage: BookFileStorage) -> None:
    name = storage.save_cover("bk0003", b"one", "png")
    assert re.fullmatch(r"bk0003_[0-9a-f]{32}\.png", name)


def test_save_cover_never_overwrites_the_cover_in_use(
    storage: BookFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A clash used to write the new cover under the old name, which the update
    # then deleted as "the old cover", leaving the book pointing at nothing.
    monkeypatch.setattr(book_file_storage, "uuid4", lambda: UUID(int=1))
    first = storage.save_cover("bk0003", b"one", "png")
    with pytest.raises(FileExistsError):
        storage.save_cover("bk0003", b"two", "png")
    assert (storage.cover_dir / first).read_bytes() == b"one"


def test_save_cover_that_fails_part_way_leaves_no_file(
    storage: BookFileStorage, fill_disk: Callable[[], None]
) -> None:
    fill_disk()
    with pytest.raises(OSError):
        storage.save_cover("bk0004", b"0123456789", "png")
    assert list(storage.cover_dir.iterdir()) == []
