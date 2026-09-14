import mimetypes
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.tag_repo import TagRepo
from app.repositories.video_repo import VideoRepo
from app.schemas.video_schema import VideoCreate, VideoView
from app.services.media_errors import MediaNotFound
from app.services.media_file_storage import MediaFileStorage
from app.services.media_validator import ALLOWED_VIDEO_EXTENSIONS, validate_media
from app.services.video_metadata_reader import VideoMetadataReader


class VideoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.video_repo = VideoRepo(db)
        self.tag_repo = TagRepo(db)
        self.storage = MediaFileStorage(settings.VIDEO_DIR)
        self.metadata_reader = VideoMetadataReader()

    def list_videos(self) -> list[VideoView]:
        return [VideoView.model_validate(v) for v in self.video_repo.list_all()]

    def upload(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        title: str,
        description: str | None,
        tag_names: list[str],
    ) -> VideoView:
        validate_media(filename, allowed=ALLOWED_VIDEO_EXTENSIONS)
        tags = self.tag_repo.get_or_create_by_names(tag_names)
        saved_path = self.storage.save(file_bytes, filename)
        poster_name = self.metadata_reader.poster(Path(saved_path), settings.COVER_DIR)
        video = self.video_repo.create(
            VideoCreate(title=title, description=description, file_path=saved_path)
        )
        video.tags = list(tags)
        video.poster_path = poster_name
        self.db.commit()
        self.db.refresh(video)
        return VideoView.model_validate(video)

    def upload_multiple(self, files: list[tuple[bytes, str]]) -> list[VideoView]:
        for _data, filename in files:
            validate_media(filename, allowed=ALLOWED_VIDEO_EXTENSIONS)
        results: list[VideoView] = []
        for data, filename in files:
            results.append(
                self.upload(
                    data,
                    filename,
                    title=Path(filename).stem,
                    description=None,
                    tag_names=[],
                )
            )
        return results

    def update(
        self,
        video_id: int,
        *,
        title: str | None,
        description: str | None,
        tag_names: list[str] | None,
    ) -> VideoView:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        if title is not None:
            video.title = title
        if description is not None:
            video.description = description
        if tag_names is not None:
            video.tags = list(self.tag_repo.get_or_create_by_names(tag_names))
        self.db.commit()
        self.db.refresh(video)
        if tag_names is not None:
            self.tag_repo.delete_orphans()
        return VideoView.model_validate(video)

    def delete(self, video_id: int) -> None:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        self.storage.delete(video.file_path)
        self.video_repo.delete(video_id)

    def resolve_stream(self, video_id: int) -> tuple[Path, str]:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        media_path = self.storage.resolve(video.file_path)
        media_type = (
            mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
        )
        return media_path, media_type
