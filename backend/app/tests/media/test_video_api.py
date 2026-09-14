import mimetypes
from urllib.parse import quote

import pytest

import app.api.video_router as video_router_module
from app.config import settings
from app.models.tag import Tag
from app.models.video import Video
from app.tests.conftest import auth_headers, login, setup_admin


def _seed_video(
    db, *, title: str = "clip", file_path: str = "/tmp/nonexistent.mp4"
) -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


def _patch_video_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # The legacy router reads VIDS_DIR at import time; the fused router reads
    # settings.VIDEO_DIR at request time. Patch both to a tmp_path subdir so
    # the same location is used before and after the rewrite (raising=False
    # keeps Step 5 green once the legacy VIDS_DIR constant is gone). The subdir
    # keeps the setup flow's .credentials files out of the file-count asserts.
    video_dir = tmp_path / "vids"
    video_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "VIDEO_DIR", video_dir)
    monkeypatch.setattr(video_router_module, "VIDS_DIR", video_dir, raising=False)


@pytest.fixture()
def auth(client, setup_paths) -> dict[str, str]:
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    return auth_headers(token)


def test_get_videos_empty(client, auth):
    response = client.get("/videos/", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


def test_get_videos_lists_all(db, client, auth):
    _seed_video(db, title="a")
    _seed_video(db, title="b")
    response = client.get("/videos/", headers=auth)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_upload_happy(db, client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload",
        files={
            "file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42 mock bytes", "video/mp4")
        },
        data={"title": "Intro", "description": "first", "tags": "lesson"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Intro"
    assert body["description"] == "first"
    assert body["video_url"] == f"/videos/stream/{body['id']}"
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "lesson"
    assert body["tags"][0]["id"] is not None
    files_on_disk = [p for p in (tmp_path / "vids").iterdir() if p.is_file()]
    assert len(files_on_disk) == 1
    assert files_on_disk[0].read_bytes() == b"\x00\x00\x00\x18ftypmp42 mock bytes"
    db.expire_all()
    row = db.query(Video).filter(Video.id == body["id"]).first()
    assert row is not None


def test_upload_missing_title_returns_422(client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        headers=auth,
    )
    assert response.status_code == 422


def test_upload_txt_rejected_400(client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"title": "Notes"},
        headers=auth,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "File type .txt not allowed"


def test_upload_tags_whitespace_first_seen_reused(
    db, client, monkeypatch, tmp_path, auth
):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        data={"title": "T", "tags": " MATH , math "},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "math"
    assert body["tags"][0]["id"] is not None
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_tag_reuses_preexisting_row(db, client, monkeypatch, tmp_path, auth):
    tag = Tag(name="math")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload",
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
        data={"title": "T", "tags": "math"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tags"]) == 1
    assert body["tags"][0]["id"] == tag.id
    assert body["tags"][0]["name"] == "math"
    db.expire_all()
    assert db.query(Tag).count() == 1


def test_upload_multiple_valid_pair(client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload_multiple",
        files=[
            ("files", ("a.mp4", b"bytes-a", "video/mp4")),
            ("files", ("b.mp4", b"bytes-b", "video/mp4")),
        ],
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert [item["title"] for item in body] == ["a", "b"]
    assert all(item["tags"] == [] for item in body)


def test_upload_multiple_partial_commit_leaves_nothing(
    db, client, monkeypatch, tmp_path, auth
):
    _patch_video_dir(monkeypatch, tmp_path)
    response = client.post(
        "/videos/upload_multiple",
        files=[
            ("files", ("a.mp4", b"bytes-a", "video/mp4")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
        headers=auth,
    )
    assert response.status_code == 400
    db.expire_all()
    assert client.get("/videos/", headers=auth).json() == []
    assert list((tmp_path / "vids").iterdir()) == []


def test_patch_title_description_tags_replace(db, client, auth):
    vid = _seed_video(db)
    response = client.patch(
        f"/videos/{vid.id}",
        params={"title": "New", "description": "desc", "tags": "x, y"},
        headers=auth,
    )
    assert response.status_code == 200
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.title == "New"
    assert row.description == "desc"
    assert sorted(tag.name for tag in row.tags) == ["x", "y"]


def test_patch_empty_tags_clears_links_and_sweeps_orphans(db, client, auth):
    vid = _seed_video(db)
    shared_tag = Tag(name="lesson")
    orphan_tag = Tag(name="orphan")
    db.add_all([shared_tag, orphan_tag])
    db.commit()
    db.refresh(shared_tag)
    db.refresh(orphan_tag)
    vid.tags.append(shared_tag)
    vid.tags.append(orphan_tag)
    other = _seed_video(db, title="other")
    other.tags.append(shared_tag)
    db.commit()
    tag_id = orphan_tag.id
    response = client.patch(f"/videos/{vid.id}", params={"tags": ""}, headers=auth)
    assert response.status_code == 200
    assert response.json()["tags"] == []
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.tags == []
    # orphan tag: its only link was cleared → row swept
    assert db.query(Tag).filter(Tag.id == tag_id).first() is None
    # shared tag: still linked to the other video → survives
    assert db.query(Tag).filter(Tag.name == "lesson").first() is not None


def test_patch_omitted_fields_unchanged(db, client, auth):
    vid = _seed_video(db, title="Keep")
    response = client.patch(
        f"/videos/{vid.id}", params={"description": "changed"}, headers=auth
    )
    assert response.status_code == 200
    db.expire_all()
    row = db.query(Video).filter(Video.id == vid.id).first()
    assert row is not None
    assert row.title == "Keep"
    assert row.description == "changed"
    assert row.tags == []


def test_patch_missing_video_404(client, auth):
    response = client.patch("/videos/999999", params={"title": "x"}, headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_delete_video_deletes_via_api(db, client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    video_file = tmp_path / "vids" / "clip.mp4"
    video_file.write_bytes(b"\x00\x01\x02\x03" * 100)
    vid = _seed_video(db, file_path=str(video_file))
    response = client.delete(f"/videos/{vid.id}", headers=auth)
    assert response.status_code == 204
    assert response.content == b""
    db.expire_all()
    assert db.query(Video).count() == 0
    assert client.get("/videos/", headers=auth).json() == []
    assert not video_file.exists()


def test_delete_missing_video_404(client, auth):
    response = client.delete("/videos/999999", headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_stream_serves_x_accel_204(db, client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    file_bytes = b"\x00\x01\x02\x03" * 1000
    video_file = tmp_path / "vids" / "clip.mp4"
    video_file.write_bytes(file_bytes)
    vid = _seed_video(db, file_path=str(video_file))
    response = client.get(f"/videos/stream/{vid.id}", headers=auth)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/videos/{quote('clip.mp4')}"
    assert response.headers["Content-Type"] == mimetypes.guess_type("clip.mp4")[0]
    assert response.headers["Accept-Ranges"] == "bytes"


def test_stream_missing_video_404(client, auth):
    response = client.get("/videos/stream/999999", headers=auth)
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_stream_deleted_video_404(db, client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    file_bytes = b"\x00\x01\x02\x03" * 1000
    video_file = tmp_path / "vids" / "clip.mp4"
    video_file.write_bytes(file_bytes)
    vid = _seed_video(db, file_path=str(video_file))
    client.delete(f"/videos/{vid.id}", headers=auth)
    response = client.get(f"/videos/stream/{vid.id}", headers=auth)
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
            "/videos/upload",
            {
                "files": {"file": ("clip.mp4", b"bytes", "video/mp4")},
                "data": {"title": "T"},
            },
        ),
        (
            "post",
            "/videos/upload_multiple",
            {"files": [("files", ("a.mp4", b"bytes", "video/mp4"))]},
        ),
        ("patch", "/videos/{id}", {"params": {"title": "x"}}),
        ("delete", "/videos/{id}", {}),
    ],
)
def test_student_write_endpoints_403(
    db, client, monkeypatch, tmp_path, student_auth, method, path, kwargs
):
    _patch_video_dir(monkeypatch, tmp_path)
    vid = _seed_video(db)
    response = getattr(client, method)(
        path.format(id=vid.id), headers=student_auth, **kwargs
    )
    assert response.status_code == 403


def test_student_can_list_videos(db, client, student_auth):
    _seed_video(db, title="a")
    response = client.get("/videos/", headers=student_auth)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_student_can_stream_video(db, client, monkeypatch, tmp_path, student_auth):
    _patch_video_dir(monkeypatch, tmp_path)
    video_file = tmp_path / "vids" / "clip.mp4"
    video_file.write_bytes(b"\x00\x01\x02\x03" * 100)
    vid = _seed_video(db, file_path=str(video_file))
    response = client.get(f"/videos/stream/{vid.id}", headers=student_auth)
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == f"/media/videos/{quote('clip.mp4')}"


def test_stream_missing_file_404(db, client, monkeypatch, tmp_path, auth):
    _patch_video_dir(monkeypatch, tmp_path)
    vid = _seed_video(db, file_path=str(tmp_path / "vids" / "gone.mp4"))
    response = client.get(f"/videos/stream/{vid.id}", headers=auth)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/videos/", {}),
        (
            "post",
            "/videos/upload",
            {
                "files": {"file": ("clip.mp4", b"bytes", "video/mp4")},
                "data": {"title": "T"},
            },
        ),
        (
            "post",
            "/videos/upload_multiple",
            {"files": [("files", ("a.mp4", b"bytes", "video/mp4"))]},
        ),
        ("patch", "/videos/{id}", {"params": {"title": "x"}}),
        ("delete", "/videos/{id}", {}),
        ("get", "/videos/stream/{id}", {}),
    ],
)
def test_all_video_endpoints_require_auth(
    db, client, monkeypatch, tmp_path, method, path, kwargs
):
    _patch_video_dir(monkeypatch, tmp_path)
    (tmp_path / "vids" / "clip.mp4").write_bytes(b"\x00\x01\x02\x03" * 100)
    vid = _seed_video(db, file_path=str(tmp_path / "vids" / "clip.mp4"))
    response = getattr(client, method)(path.format(id=vid.id), **kwargs)
    assert response.status_code == 401
