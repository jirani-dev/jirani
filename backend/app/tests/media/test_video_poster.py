import os
import re
import shutil
from pathlib import Path

import pytest

from app.services.video_metadata_reader import VideoMetadataReader

FAKE_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 400
POSTER_NAME_PATTERN = re.compile(r"[0-9a-f-]{36}\.jpg")


def _put_fake_ffmpeg_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    script = tmp_path / "ffmpeg"
    script.write_text(f"#!/bin/sh\n{body}")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])


def test_poster_returns_none_without_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    reader = VideoMetadataReader()
    assert reader.poster(tmp_path / "gone.mp4", tmp_path) is None


def test_poster_extracts_jpg_into_dest_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftypmp42 mock bytes")
    fake_jpg = tmp_path / "fake.jpg"
    fake_jpg.write_bytes(FAKE_JPEG_BYTES)
    dest_dir = tmp_path / "covers"
    dest_dir.mkdir()
    body = f'for last do :; done\ncp "{fake_jpg}" "$last"\n'
    _put_fake_ffmpeg_on_path(tmp_path, monkeypatch, body)
    name = VideoMetadataReader().poster(source, dest_dir)
    assert name is not None
    assert POSTER_NAME_PATTERN.fullmatch(name)
    poster = dest_dir / name
    assert poster.is_file()
    assert poster.read_bytes() == FAKE_JPEG_BYTES


def test_poster_returns_none_when_ffmpeg_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"bytes")
    dest_dir = tmp_path / "covers"
    dest_dir.mkdir()
    _put_fake_ffmpeg_on_path(tmp_path, monkeypatch, "exit 1\n")
    assert VideoMetadataReader().poster(source, dest_dir) is None
