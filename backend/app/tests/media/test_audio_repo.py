import pytest

from app.models.audio import Audio
from app.repositories.audio_repo import AudioRepo
from app.schemas.audio_schema import AudioCreate
from app.services.media_errors import MediaError


def _seed_audio(
    db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3"
) -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_create_persists(db):
    track = AudioRepo(db).create(
        AudioCreate(title="song", description="first", file_path="/tmp/nonexistent.mp3")
    )
    assert track.id is not None
    assert track.title == "song"
    assert track.description == "first"
    assert track.file_path == "/tmp/nonexistent.mp3"
    assert track.created_at is not None  # hard-delete world: no deleted_at column


def test_delete_hard_deletes(db):
    track = _seed_audio(db)
    AudioRepo(db).delete(track.id)
    db.expire_all()
    assert db.query(Audio).filter(Audio.id == track.id).first() is None
    assert db.query(Audio).count() == 0  # row GONE, not soft-deleted


def test_delete_missing_id_raises(db):
    # Flip of the legacy AttributeError pin: the rewritten repo raises the
    # domain exception the service layer maps to 404.
    with pytest.raises(MediaError, match="Audio not found"):
        AudioRepo(db).delete(999999)
