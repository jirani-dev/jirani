import re
from pathlib import Path
from urllib.parse import quote

import pytest

import app.api.audio_router as audio_router_module
from app.config import settings
from app.models.audio import Audio
from app.models.tag import Tag
from app.tests.conftest import auth_headers, login, setup_admin


def _seed_audio(
    db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3"
) -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def _patch_audio_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The legacy router reads settings.AUDIO_DIR at request time (single
    # upload) and the AUDIO_DIR constant at import time (upload_multiple);
    # the fused router+service read settings.AUDIO_DIR at request time only.
    # Patch both; raising=False keeps this green once the legacy constant is
    # gone. The subdir keeps pinned file-count asserts clean.
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(audio_router_module, "AUDIO_DIR", audio_dir, raising=False)


@pytest.fixture()
def auth(client, setup_paths) -> dict[str, str]:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def test_get_audio_empty(client, auth):
    response = client.get("/audio/", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


def test_get_audio_lists_remaining_track_after_repo_delete(db, client, auth):
    keep = _seed_audio(db, title="keep")
    gone = _seed_audio(db, title="gone")
    # Deferred import: the hard-deleting repo is new in Task 3; a module-level
    # import would break collection of this file against legacy (red-phase).
    from app.repositories.audio_repo import AudioRepo

    AudioRepo(db).delete(gone.id)  # hard delete — the row itself is gone
    response = client.get("/audio/", headers=auth)
    assert response.status_code == 200
    assert {track["id"] for track in response.json()} == {keep.id}
    db.expire_all()
    assert db.query(Audio).count() == 1


def test_upload_happy(db, client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    file_bytes = b"\xff\xfbID3 mock audio bytes"
    response = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", file_bytes, "audio/mpeg")},
        data={"tags": "math, algebra"},
        headers=auth,
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


def test_upload_tags_stripped_deduped_lowercased(
    db, client, monkeypatch, tmp_path, auth
):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"bytes", "audio/mpeg")},
        data={"tags": " math ,, MATH "},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert [tag["name"] for tag in body["tags"]] == ["math"]
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_reuses_preexisting_tag_case_insensitive(
    db, client, monkeypatch, tmp_path, auth
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
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["id"] == tag.id
    assert body["tags"][0]["name"] == "Math"  # stored case wins
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_txt_rejected_before_disk_write(client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File type .txt not allowed"
    assert list((tmp_path / "audio").iterdir()) == []


def test_upload_extensionless_rejected(client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload",
        files={"file": ("song", b"bytes", "audio/mpeg")},
        headers=auth,
    )
    assert response.status_code == 400
    # Deliberate flip (Task 3): the shared validator extracts the suffix via
    # Path(filename).suffix — extensionless yields "", so the detail is
    # "File type . not allowed". Legacy emitted ".song" (witnessed red).
    assert response.json()["detail"] == "File type . not allowed"


def test_upload_multiple_partial_commit_leaves_nothing(
    db, client, monkeypatch, tmp_path, auth
):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload_multiple",
        files=[
            ("files", ("a.mp3", b"bytes-a", "audio/mpeg")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
        headers=auth,
    )
    assert response.status_code == 400
    # Flip target for Task 3 (atomic batch): validate every file before the
    # first byte is written. Legacy persisted the first file before the
    # second failed validation (witnessed red: one row + bytes on disk).
    db.expire_all()
    assert client.get("/audio/", headers=auth).json() == []
    assert list((tmp_path / "audio").iterdir()) == []


def test_upload_multiple_two_valid(client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    response = client.post(
        "/audio/upload_multiple",
        files=[
            ("files", ("a.mp3", b"bytes-a", "audio/mpeg")),
            ("files", ("b.mp3", b"bytes-b", "audio/mpeg")),
        ],
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert [track["title"] for track in body] == ["a", "b"]  # filename stems
    assert all(track["tags"] == [] for track in body)


def test_patch_replaces_tags_and_sweeps_orphans(db, client, auth):
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
        headers=auth,
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
    # Flip target for Task 3 (orphan sweep): the detached tag row is swept.
    # Legacy kept it alive (witnessed red).
    assert db.query(Tag).filter(Tag.id == old_tag_id).first() is None


def test_patch_empty_tags_clears_links_and_sweeps_orphans(db, client, auth):
    track = _seed_audio(db, title="song")
    shared_tag = Tag(name="lesson")
    orphan_tag = Tag(name="orphan")
    db.add_all([shared_tag, orphan_tag])
    db.commit()
    db.refresh(shared_tag)
    db.refresh(orphan_tag)
    track.tags.append(shared_tag)
    track.tags.append(orphan_tag)
    other = _seed_audio(db, title="other")
    other.tags.append(shared_tag)
    db.commit()
    tag_id = orphan_tag.id
    response = client.patch(f"/audio/{track.id}", params={"tags": ""}, headers=auth)
    assert response.status_code == 200
    assert response.json()["tags"] == []
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.tags == []
    # orphan tag: its only link was cleared → row swept (legacy kept it — red)
    assert db.query(Tag).filter(Tag.id == tag_id).first() is None
    # shared tag: still linked to the other track → survives
    assert db.query(Tag).filter(Tag.name == "lesson").first() is not None


def test_patch_omitted_fields_unchanged(db, client, auth):
    track = _seed_audio(db, title="Keep")
    tag = Tag(name="lesson")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    track.tags.append(tag)
    db.commit()
    response = client.patch(
        f"/audio/{track.id}", params={"description": "changed"}, headers=auth
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Keep"
    assert [t["name"] for t in response.json()["tags"]] == ["lesson"]
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.title == "Keep"
    assert row.description == "changed"
    assert [tag.name for tag in row.tags] == ["lesson"]


def test_patch_missing_404_no_db_change(db, client, auth):
    track = _seed_audio(db, title="song")
    response = client.patch("/audio/999999", params={"title": "x"}, headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Audio not found"
    db.expire_all()
    assert db.query(Audio).count() == 1
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None
    assert row.title == "song"


def test_delete_track_deletes_via_api(db, client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(b"\x00\x01\x02\x03" * 100)
    track = _seed_audio(db, file_path=str(audio_file))
    response = client.delete(f"/audio/{track.id}", headers=auth)
    # Flip target for Task 3 (hard delete + 204): legacy returned 200 with the
    # raw serialized row and soft-deleted (witnessed red).
    assert response.status_code == 204
    assert response.content == b""
    db.expire_all()
    assert db.query(Audio).count() == 0
    assert client.get("/audio/", headers=auth).json() == []
    assert not audio_file.exists()


def test_delete_missing_track_404(client, auth):
    # Flip target for Task 3 (404): legacy dereferenced None.deleted_at and the
    # harness re-raised the server AttributeError (witnessed red).
    response = client.delete("/audio/999999", headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Audio not found"


def test_stream_serves_x_accel_204(db, client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    file_bytes = b"\xff\xfbID3" + b"\x00" * 100
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(file_bytes)
    track = _seed_audio(db, file_path=str(audio_file))
    response = client.get(f"/audio/stream/{track.id}", headers=auth)
    # Flip target for Task 3 (X-Accel): legacy streamed the bytes with a 200
    # body (witnessed red).
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/audio/{quote('clip.mp3')}"
    assert response.headers["Content-Type"] == "audio/mpeg"
    assert response.headers["Accept-Ranges"] == "bytes"


def test_stream_missing_track_404(client, auth):
    response = client.get("/audio/stream/999999", headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Audio not found"


def test_stream_deleted_track_404(db, client, monkeypatch, tmp_path, auth):
    # Replaces the soft-deleted-still-streams quirk pin: the column (and the
    # row) die with the rewrite, so a deleted id is simply a missing one.
    _patch_audio_dir(monkeypatch, tmp_path)
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(b"\xff\xfbID3" + b"\x00" * 100)
    track = _seed_audio(db, file_path=str(audio_file))
    client.delete(f"/audio/{track.id}", headers=auth)
    response = client.get(f"/audio/stream/{track.id}", headers=auth)
    assert response.status_code == 404


def test_stream_missing_file_404(db, client, monkeypatch, tmp_path, auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    track = _seed_audio(db, file_path=str(tmp_path / "audio" / "gone.mp3"))
    response = client.get(f"/audio/stream/{track.id}", headers=auth)
    # Flip target for Task 3 (404): legacy open()'d inside the generator and
    # the harness re-raised FileNotFoundError (witnessed red).
    assert response.status_code == 404


@pytest.fixture()
def student_auth(client, setup_paths) -> dict[str, str]:
    admin_pw = setup_admin(client, setup_paths)
    admin_token = login(client, "admin", admin_pw)["access_token"]
    response = client.post(
        "/auth/users/bulk",
        json={"count": 1, "role": "student", "prefix": "stu"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 201, response.text
    accounts = response.json()["accounts"]
    student = accounts[0]
    token = login(client, student["username"], student["password"])["access_token"]
    return auth_headers(token)


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        (
            "post",
            "/audio/upload",
            {
                "files": {"file": ("song.mp3", b"bytes", "audio/mpeg")},
                "data": {"tags": "t"},
            },
        ),
        (
            "post",
            "/audio/upload_multiple",
            {"files": [("files", ("a.mp3", b"bytes", "audio/mpeg"))]},
        ),
        ("patch", "/audio/{id}", {"params": {"title": "x"}}),
        ("delete", "/audio/{id}", {}),
    ],
)
def test_student_write_endpoints_403(
    db, client, monkeypatch, tmp_path, student_auth, method, path, kwargs
):
    _patch_audio_dir(monkeypatch, tmp_path)
    track = _seed_audio(db)
    response = getattr(client, method)(
        path.format(id=track.id), headers=student_auth, **kwargs
    )
    assert response.status_code == 403


def test_student_can_list_tracks(db, client, student_auth):
    _seed_audio(db, title="a")
    response = client.get("/audio/", headers=student_auth)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_student_can_stream_track(db, client, monkeypatch, tmp_path, student_auth):
    _patch_audio_dir(monkeypatch, tmp_path)
    audio_file = tmp_path / "audio" / "clip.mp3"
    audio_file.write_bytes(b"\x00\x01\x02\x03" * 100)
    track = _seed_audio(db, file_path=str(audio_file))
    response = client.get(f"/audio/stream/{track.id}", headers=student_auth)
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == f"/media/audio/{quote('clip.mp3')}"


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/audio/", {}),
        (
            "post",
            "/audio/upload",
            {
                "files": {"file": ("song.mp3", b"bytes", "audio/mpeg")},
                "data": {"tags": "t"},
            },
        ),
        (
            "post",
            "/audio/upload_multiple",
            {"files": [("files", ("a.mp3", b"bytes", "audio/mpeg"))]},
        ),
        ("patch", "/audio/{id}", {"params": {"title": "x"}}),
        ("delete", "/audio/{id}", {}),
        ("get", "/audio/stream/{id}", {}),
    ],
)
def test_all_audio_endpoints_require_auth(
    db, client, monkeypatch, tmp_path, method, path, kwargs
):
    _patch_audio_dir(monkeypatch, tmp_path)
    (tmp_path / "audio" / "clip.mp3").write_bytes(b"\x00\x01\x02\x03" * 100)
    track = _seed_audio(db, file_path=str(tmp_path / "audio" / "clip.mp3"))
    response = getattr(client, method)(path.format(id=track.id), **kwargs)
    assert response.status_code == 401
