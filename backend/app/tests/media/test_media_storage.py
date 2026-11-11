import re
from pathlib import Path

import pytest

from app.services.media_errors import MediaNotFound
from app.services.media_file_storage import MediaFileStorage


def test_save_writes_uuid_prefixed_absolute_path(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    saved = storage.save(b"bytes", "song.mp4")
    assert isinstance(saved, str)
    assert Path(saved).is_absolute()
    assert re.fullmatch(r"[0-9a-f-]{36}_song\.mp4", Path(saved).name)
    assert Path(saved).read_bytes() == b"bytes"


@pytest.mark.parametrize(
    ("client_name", "stored_suffix"),
    [
        ("sub/dir.mp4", "_dir.mp4"),
        ("../../../escape.mp4", "_escape.mp4"),
        ("C:\\Users\\me\\clip.mp4", "_clip.mp4"),
        ("..\\..\\evil.mp4", "_evil.mp4"),
    ],
)
def test_save_keeps_only_the_last_component_of_the_client_name(
    tmp_path: Path, client_name: str, stored_suffix: str
) -> None:
    # The name comes straight from the upload. Directories in it used to be
    # created under save_dir (unstreamable: the X-Accel path is the bare file
    # name) and enough "../" wrote outside it altogether.
    save_dir = tmp_path / "media"
    storage = MediaFileStorage(save_dir)
    saved = Path(storage.save(b"b", client_name))
    assert saved.parent == save_dir
    assert saved.name.endswith(stored_suffix)
    assert saved.read_bytes() == b"b"
    assert [p.name for p in tmp_path.iterdir()] == ["media"]
    assert [p.name for p in save_dir.iterdir()] == [saved.name]


def test_resolve_round_trip_returns_saved_bytes(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    saved = storage.save(b"payload", "clip.mp4")
    assert storage.resolve(saved).read_bytes() == b"payload"


def test_resolve_absolute_path_inside_dir(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    target = tmp_path / "legacy.mp4"
    target.write_bytes(b"x")
    assert storage.resolve(str(target)) == target.resolve()


def test_resolve_relative_path_joins_save_dir(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    legacy_dir = tmp_path / "uploads" / "videos"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "u1_x.mp4").write_bytes(b"x")
    assert storage.resolve("uploads/videos/u1_x.mp4").read_bytes() == b"x"


def test_resolve_rejects_absolute_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_bytes(b"secret")
    storage = MediaFileStorage(tmp_path)
    with pytest.raises(MediaNotFound):
        storage.resolve(str(outside))


def test_resolve_rejects_dotdot_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_bytes(b"secret")
    storage = MediaFileStorage(tmp_path)
    with pytest.raises(MediaNotFound):
        storage.resolve(str(tmp_path / ".." / "secret.txt"))


def test_resolve_missing_file_inside_dir(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    with pytest.raises(MediaNotFound):
        storage.resolve(str(tmp_path / "ghost.mp4"))


def test_delete_removes_file_and_is_silent_when_missing(tmp_path: Path) -> None:
    storage = MediaFileStorage(tmp_path)
    saved = storage.save(b"bytes", "song.mp4")
    storage.delete(saved)
    assert not Path(saved).exists()
    storage.delete(saved)
