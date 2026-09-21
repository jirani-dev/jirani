from urllib.parse import quote

import pytest

from app.config import settings
from app.models.audio import Audio
from app.models.video import Video
from app.services.audio_service import AudioService
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
    assert response.headers["X-Accel-Redirect"] == f"/media/videos/{quote(name)}"
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
    # stream_env's login left an access_token cookie on this client — clear it
    # so the request truly carries no credentials (auth also falls back to
    # that cookie now, for native <audio>/<video> tags that can't send a
    # Bearer header).
    client.cookies.clear()
    response = client.get(f"/videos/stream/{vid.id}")
    assert response.status_code == 401


def test_stream_cookie_only_auth_204(db, client, stream_env):
    # stream_env's login left a valid access_token cookie on this client.
    # A native <video src> request can't send a custom Authorization
    # header, so the cookie alone must be enough — this is the exact
    # codepath the fallback in app/dependencies/auth.py exists for.
    tmp_path, _ = stream_env
    (tmp_path / "clip.mp4").write_bytes(b"mock bytes")
    vid = _seed_video(db, file_path="clip.mp4")
    response = client.get(f"/videos/stream/{vid.id}")
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == "/media/videos/clip.mp4"


def test_stream_spaced_filename_quoted(db, client, stream_env):
    tmp_path, headers = stream_env
    (tmp_path / "my clip.mp4").write_bytes(b"mock bytes")
    vid = _seed_video(db, file_path="my clip.mp4")
    response = client.get(f"/videos/stream/{vid.id}", headers=headers)
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == "/media/videos/my%20clip.mp4"


# --- audio (Task 3): same contract, prefix /media/audio/, legacy media map ---


@pytest.fixture()
def audio_stream_env(client, setup_paths, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "AUDIO_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


@pytest.fixture()
def audio_service(db) -> AudioService:
    # Scaffold for the fused rewrite: forces the module import, so the missing
    # service module is a collection error before Task 3 lands (video parity).
    return AudioService(db)


def _seed_audio(
    db, *, title: str = "song", file_path: str = "nonexistent.mp3"
) -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@pytest.mark.parametrize(
    "name, media_type",
    [
        ("clip.mp3", "audio/mpeg"),
        ("clip.wav", "audio/wav"),
        ("clip.flac", "audio/flac"),
    ],
)
def test_audio_stream_x_accel_204(db, client, audio_stream_env, name, media_type):
    tmp_path, headers = audio_stream_env
    (tmp_path / name).write_bytes(b"mock bytes")
    track = _seed_audio(db, file_path=name)
    response = client.get(f"/audio/stream/{track.id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/audio/{quote(name)}"
    assert response.headers["Content-Type"] == media_type
    assert response.headers["Accept-Ranges"] == "bytes"


def test_audio_stream_missing_id_404(client, audio_stream_env):
    _, headers = audio_stream_env
    response = client.get("/audio/stream/999999", headers=headers)
    assert response.status_code == 404


def test_audio_stream_missing_disk_file_404(db, client, audio_stream_env):
    _, headers = audio_stream_env
    track = _seed_audio(db, file_path="gone.mp3")
    response = client.get(f"/audio/stream/{track.id}", headers=headers)
    assert response.status_code == 404


def test_audio_stream_traversal_file_path_404(db, client, audio_stream_env):
    _, headers = audio_stream_env
    track = _seed_audio(db, file_path="../../../../etc/passwd")
    response = client.get(f"/audio/stream/{track.id}", headers=headers)
    assert response.status_code == 404


def test_audio_stream_unauthenticated_401(db, client, audio_stream_env):
    tmp_path, _ = audio_stream_env
    (tmp_path / "clip.mp3").write_bytes(b"mock bytes")
    track = _seed_audio(db, file_path="clip.mp3")
    # audio_stream_env's login left an access_token cookie on this client —
    # clear it so the request truly carries no credentials (auth also falls
    # back to that cookie now, for native <audio>/<video> tags that can't
    # send a Bearer header).
    client.cookies.clear()
    response = client.get(f"/audio/stream/{track.id}")
    assert response.status_code == 401


def test_audio_stream_cookie_only_auth_204(db, client, audio_stream_env):
    # audio_stream_env's login left a valid access_token cookie on this
    # client. A native <audio src> request can't send a custom
    # Authorization header, so the cookie alone must be enough — this is
    # the exact codepath the fallback in app/dependencies/auth.py exists
    # for.
    tmp_path, _ = audio_stream_env
    (tmp_path / "clip.mp3").write_bytes(b"mock bytes")
    track = _seed_audio(db, file_path="clip.mp3")
    response = client.get(f"/audio/stream/{track.id}")
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == "/media/audio/clip.mp3"


def test_audio_stream_spaced_filename_quoted(db, client, audio_stream_env):
    tmp_path, headers = audio_stream_env
    (tmp_path / "my clip.mp3").write_bytes(b"mock bytes")
    track = _seed_audio(db, file_path="my clip.mp3")
    response = client.get(f"/audio/stream/{track.id}", headers=headers)
    assert response.status_code == 204
    assert response.headers["X-Accel-Redirect"] == "/media/audio/my%20clip.mp3"
