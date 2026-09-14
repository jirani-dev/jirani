import pytest
from sqlalchemy import select

from app.models.tag import Tag
from app.models.video import Video
from app.repositories.video_repo import VideoRepo
from app.schemas.video_schema import VideoCreate
from app.services.media_errors import MediaNotFound


def _seed_video(
    db, *, title: str = "clip", file_path: str = "/tmp/nonexistent.mp4"
) -> Video:
    vid = Video(title=title, description=None, file_path=file_path)
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


def test_create_video_persists(db):
    video = VideoRepo(db).create(
        VideoCreate(
            title="Intro", description="first", file_path="/tmp/nonexistent.mp4"
        )
    )
    assert video.id is not None
    assert video.title == "Intro"
    assert video.description == "first"
    assert video.file_path == "/tmp/nonexistent.mp4"


def test_video_timestamps_populated_on_create(db):
    video = VideoRepo(db).create(
        VideoCreate(
            title="Intro", description="first", file_path="/tmp/nonexistent.mp4"
        )
    )
    assert video.created_at is not None
    assert video.updated_at is not None


def test_delete_video_deletes_row(db):
    vid = _seed_video(db)
    tag = Tag(name="lesson")
    db.add(tag)
    db.flush()
    vid.tags.append(tag)
    db.commit()
    tag_id = tag.id
    VideoRepo(db).delete(vid.id)
    assert VideoRepo(db).get_by_id(vid.id) is None
    assert (
        db.scalars(select(Tag).where(Tag.id == tag_id)).first() is None
    )  # orphan sweep


def test_delete_video_missing_id_raises(db):
    with pytest.raises(MediaNotFound):
        VideoRepo(db).delete(999999)
