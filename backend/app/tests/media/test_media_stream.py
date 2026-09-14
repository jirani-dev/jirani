from urllib.parse import quote

import pytest

from app.config import settings
from app.models.video import Video
from app.services.video_service import VideoService
from app.tests.conftest import auth_headers, login, setup_admin


@pytest.fixture()
def stream_env(client, setup_paths, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "VIDEO_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


@pytest.fixture()
def video_service(db) -> VideoService:
    # Scaffold for the fused rewrite: the module does not exist yet, so this
    # file's import is the collection-error red for Step 2.
    return VideoService(db)


def _seed_video(
    db, *, title: str = "clip", file_path: str = "nonexistent.mp4"
) -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


@pytest.mark.parametrize(
    "name, media_type",
    [
        ("clip.mp4", "video/mp4"),
        ("clip.mov", "video/quicktime"),
        ("clip.webm", "video/webm"),
    ],
)
def test_stream_x_accel_204(db, client, stream_env, name, media_type):
    tmp_path, headers = stream_env
    (tmp_path / name).write_bytes(b"mock bytes")
    vid = _seed_video(db, file_path=name)
    response = client.get(f"/videos/stream/{vid.id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/vids/{quote(name)}"
    assert response.headers["Content-Type"] == media_type
    assert response.headers["Accept-Ranges"] == "bytes"


def test_stream_missing_id_404(client, stream_env):
    _, headers = stream_env
    response = client.get("/videos/stream/999999", headers=headers)
    assert response.status_code == 404


def test_stream_missing_disk_file_404(db, client, stream_env):
    _, headers = stream_env
    vid = _seed_video(db, file_path="gone.mp4")
    response = client.get(f"/videos/stream/{vid.id}", headers=headers)
    assert response.status_code == 404


def test_stream_traversal_file_path_404(db, client, stream_env):
    _, headers = stream_env
    vid = _seed_video(db, file_path="../../../../etc/passwd")
    response = client.get(f"/videos/stream/{vid.id}", headers=headers)
    assert response.status_code == 404


def test_stream_unauthenticated_401(db, client, stream_env):
    tmp_path, _ = stream_env
    (tmp_path / "clip.mp4").write_bytes(b"mock bytes")
    vid = _seed_video(db, file_path="clip.mp4")
    response = client.get(f"/videos/stream/{vid.id}")
    assert response.status_code == 401


def test_stream_spaced_filename_quoted(db, client, stream_env):
    tmp_path, headers = stream_env
    (tmp_path / "my clip.mp4").write_bytes(b"mock bytes")
    vid = _seed_video(db, file_path="my clip.mp4")
    response = client.get(f"/videos/stream/{vid.id}", headers=headers)
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == "/media/vids/my%20clip.mp4"
