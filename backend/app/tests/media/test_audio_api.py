import re
from pathlib import Path

import pytest

import app.api.audio_router as audio_router_module
from app.config import settings
from app.models.audio import Audio
from app.models.tag import Tag
from app.repositories.audio_repo import Audio_Repo


def _seed_audio(
    db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3"
) -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def _patch_audio_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The single upload reads settings.AUDIO_DIR at request time, while
    # upload_multiple reads the AUDIO_DIR constant captured at import time.
    # Patch both; raising=False keeps this green after the rewrite deletes the
    # constant. The subdir keeps pinned file-count asserts clean.
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(audio_router_module, "AUDIO_DIR", audio_dir, raising=False)


def test_get_audio_empty(client):
    response = client.get("/audio/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_audio_excludes_soft_deleted(db, client):
    keep = _seed_audio(db, title="keep")
    gone = _seed_audio(db, title="gone")
    Audio_Repo(db).delete_audio(gone.id)
    response = client.get("/audio/")
    assert response.status_code == 200
    assert {track["id"] for track in response.json()} == {keep.id}


def test_upload_happy(db, client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    file_bytes = b"\xff\xfbID3 mock audio bytes"
    response = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", file_bytes, "audio/mpeg")},
        data={"tags": "math, algebra"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "song"  # filename stem
    assert body["audio_url"] == f"/audio/stream/{body['id']}"
    assert [tag["name"] for tag in body["tags"]] == ["math", "algebra"]
    files_on_disk = [p for p in (tmp_path / "audio").iterdir() if p.is_file()]
    assert len(files_on_disk) == 1
    assert re.fullmatch(r"[0-9a-f-]{36}_song\.mp3", files_on_disk[0].name)
    assert files_on_disk[0].read_bytes() == file_bytes
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == body["id"]).first()
    assert row is not None
    assert row.file_path == str((tmp_path / "audio") / files_on_disk[0].name)


def test_upload_tags_stripped_deduped_lowercased(db, client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"bytes", "audio/mpeg")},
        data={"tags": " math ,, MATH "},
    )
    assert response.status_code == 200
    body = response.json()
    assert [tag["name"] for tag in body["tags"]] == ["math"]
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_reuses_preexisting_tag_case_insensitive(
    db, client, monkeypatch, tmp_path
):
    tag = Tag(name="Math")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"bytes", "audio/mpeg")},
        data={"tags": "MATH"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["id"] == tag.id
    assert body["tags"][0]["name"] == "Math"  # stored case wins
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_txt_rejected_before_disk_write(client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File type .txt not allowed"
    assert list((tmp_path / "audio").iterdir()) == []


def test_upload_extensionless_rejected(client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("song", b"bytes", "audio/mpeg")},
    )
    assert response.status_code == 400
    # Extension extraction returns the whole name; the whitelist rejects it.
    assert response.json()["detail"] == "File type .song not allowed"


def test_upload_multiple_partial_commit_persists_earlier_file(
    db, client, monkeypatch, tmp_path
):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload_multiple",
        files=[
            ("files", ("a.mp3", b"bytes-a", "audio/mpeg")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
    )
    assert response.status_code == 400
    listing = client.get("/audio/")
    assert listing.status_code == 200
    # Flip target for Task 3 (atomic batch): legacy commits the first file
    # before the second fails validation.
    assert [track["title"] for track in listing.json()] == ["a"]


def test_upload_multiple_two_valid(client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload_multiple",
        files=[
            ("files", ("a.mp3", b"bytes-a", "audio/mpeg")),
            ("files", ("b.mp3", b"bytes-b", "audio/mpeg")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert [track["title"] for track in body] == ["a", "b"]  # filename stems
    assert all(track["tags"] == [] for track in body)


def test_patch_replaces_tag_set_old_rows_survive(db, client):
    track = _seed_audio(db, title="song")
    old_tag = Tag(name="old")
    db.add(old_tag)
    db.commit()
    db.refresh(old_tag)
    track.tags.append(old_tag)
    db.commit()
    old_tag_id = old_tag.id
    response = client.patch(
        f"/audio/{track.id}",
        params={"title": "New", "description": "desc", "tags": "bass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["description"] == "desc"
    assert [tag["name"] for tag in body["tags"]] == ["bass"]
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert [tag.name for tag in row.tags] == ["bass"]
    # Flip target for Task 3 (orphan sweep): legacy keeps the detached tag row.
    assert db.query(Tag).filter(Tag.id == old_tag_id).first() is not None


def test_patch_empty_tags_clears_links_only(db, client):
    track = _seed_audio(db, title="song")
    tag = Tag(name="lesson")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    track.tags.append(tag)
    db.commit()
    tag_id = tag.id
    response = client.patch(f"/audio/{track.id}", params={"tags": ""})
    assert response.status_code == 200
    assert response.json()["tags"] == []
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.tags == []
    # Flip target for Task 3 (orphan sweep): the tag row itself survives.
    assert db.query(Tag).filter(Tag.id == tag_id).first() is not None


def test_patch_omitted_tags_untouched(db, client):
    track = _seed_audio(db, title="Keep")
    tag = Tag(name="lesson")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    track.tags.append(tag)
    db.commit()
    response = client.patch(f"/audio/{track.id}", params={"description": "changed"})
    assert response.status_code == 200
    assert response.json()["title"] == "Keep"
    assert [t["name"] for t in response.json()["tags"]] == ["lesson"]
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.title == "Keep"
    assert row.description == "changed"
    assert [tag.name for tag in row.tags] == ["lesson"]


def test_patch_missing_404_no_db_change(db, client):
    track = _seed_audio(db, title="song")
    response = client.patch("/audio/999999", params={"title": "x"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Audio not found"
    db.expire_all()
    assert db.query(Audio).count() == 1
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.title == "song"


def test_delete_returns_raw_serialized_row(db, client):
    track = _seed_audio(db, title="song")
    response = client.delete(f"/audio/{track.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == track.id
    assert body["title"] == "song"
    assert body["description"] is None
    # Legacy has no response_model here, so the raw ORM object is serialized:
    # derived fields are absent. Deviation pin (brief claimed audio_url/tags
    # present; witnessed body has neither) — flips when the rewrite returns
    # Audio_View. file_path/created_at/deleted_at leak but are NOT pinned.
    assert "audio_url" not in body
    assert "tags" not in body
    listing = client.get("/audio/")
    assert listing.status_code == 200
    assert listing.json() == []
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.deleted_at is not None


def test_delete_missing_id_raises_attribute_error(client):
    # Bug pin: the harness re-raises the server exception from the
    # None.deleted_at deref. Flip target for Task 3 (404).
    with pytest.raises(AttributeError):
        client.delete("/audio/999999")


def test_stream_serves_bytes(db, client, monkeypatch, tmp_path):
    _patch_audio_dir(monkeypatch, tmp_path)
    file_bytes = b"\xff\xfbID3" + b"\x00" * 100
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(file_bytes)
    track = _seed_audio(db, file_path=str(audio_file))
    response = client.get(f"/audio/stream/{track.id}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "audio/mpeg"
    assert response.content == file_bytes


def test_stream_missing_404(client):
    response = client.get("/audio/stream/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Audio not found"


def test_stream_soft_deleted_still_streams(db, client, monkeypatch, tmp_path):
    # Quirk pin: the stream query does not filter deleted_at. Dies with the
    # column in Task 3.
    _patch_audio_dir(monkeypatch, tmp_path)
    file_bytes = b"\xff\xfbID3" + b"\x00" * 100
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(file_bytes)
    track = _seed_audio(db, file_path=str(audio_file))
    Audio_Repo(db).delete_audio(track.id)
    response = client.get(f"/audio/stream/{track.id}")
    assert response.status_code == 200
    assert response.content == file_bytes


def test_stream_missing_file_raises(db, client):
    # Bug pin: uncaught open() inside the generator. Flip target for Task 3.
    track = _seed_audio(db, file_path="/tmp/nonexistent-audio-pin.mp3")
    with pytest.raises(FileNotFoundError):
        client.get(f"/audio/stream/{track.id}")
