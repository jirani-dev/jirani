from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.tag import Tag
from app.models.video import Video
from app.repositories.tag_repo import TagRepo
from app.schemas.video_schema import VideoCreate
from app.services.media_errors import MediaNotFound


class VideoRepo:
    def __init__(self, db_session: Session) -> None:
        self.db_session = db_session

    def create(
        self,
        video_create: VideoCreate,
        *,
        tags: list[Tag] | None = None,
        poster_path: str | None = None,
    ) -> Video:
        new_video = Video(**video_create.model_dump(), poster_path=poster_path)
        if tags:
            new_video.tags = tags
        self.db_session.add(new_video)
        self.db_session.commit()
        self.db_session.refresh(new_video)
        return new_video

    def get_by_id(self, video_id: int) -> Video | None:
        stmt = (
            select(Video).options(selectinload(Video.tags)).where(Video.id == video_id)
        )
        return self.db_session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Video]:
        # Explicit order: without ORDER BY the row order is unspecified and
        # changes after an UPDATE, which would reshuffle the grid on every edit.
        stmt = select(Video).options(selectinload(Video.tags)).order_by(Video.id)
        return list(self.db_session.scalars(stmt).all())

    def delete(self, video_id: int) -> None:
        video = self.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        try:
            self.db_session.delete(video)
            self.db_session.flush()
            TagRepo(self.db_session).delete_orphans()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
