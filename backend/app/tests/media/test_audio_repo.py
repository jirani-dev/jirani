from datetime import UTC, datetime, timedelta

import pytest

from app.models.audio import Audio
from app.repositories.audio_repo import Audio_Repo
from app.schemas.audio_schema import Audio_Create


def _seed_audio(
    db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3"
) -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_create_audio_persists(db):
    track = Audio_Repo(db).create_audio(
        Audio_Create(
            title="song", description="first", file_path="/tmp/nonexistent.mp3"
        )
    )
    assert track.id is not None
    assert track.title == "song"
    assert track.description == "first"
    assert track.file_path == "/tmp/nonexistent.mp3"
    assert track.deleted_at is None


def test_delete_audio_soft_deletes(db):
    track = _seed_audio(db)
    before = datetime.now(UTC).replace(tzinfo=None)
    Audio_Repo(db).delete_audio(track.id)
    after = datetime.now(UTC).replace(tzinfo=None)
    db.expire_all()
    row = db.query(Audio).filter(Audio.id == track.id).first()
    assert row is not None  # soft delete keeps the row
    assert row.deleted_at is not None
    assert (
        before - timedelta(seconds=5) <= row.deleted_at <= after + timedelta(seconds=5)
    )


def test_delete_audio_missing_id_raises(db):
    # Bug pin: legacy delete_audio dereferences None.deleted_at for missing ids.
    with pytest.raises(AttributeError):
        Audio_Repo(db).delete_audio(999999)
