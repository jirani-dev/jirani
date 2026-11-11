from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.tag_repo import TagRepo
from app.repositories.video_repo import VideoRepo
from app.schemas.video_schema import VideoCreate, VideoRead
from app.services.media_errors import MediaNotFound
from app.services.media_file_storage import MediaFileStorage
from app.services.media_validator import ALLOWED_VIDEO_EXTENSIONS, validate_media
from app.services.video_metadata_reader import VideoMetadataReader

# Explicit rather than mimetypes.guess_type(): that reads the host's
# /etc/mime.types, which the slim container image does not have, and Python's
# built-in table knows neither mkv, m4v, ogv nor wmv. nginx forwards this
# header as-is on X-Accel-Redirect, so a wrong guess reaches the browser.
VIDEO_MEDIA_TYPES: dict[str, str] = {
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "ogv": "video/ogg",
    "mkv": "video/x-matroska",
    "avi": "video/x-msvideo",
    "wmv": "video/x-ms-wmv",
}


class VideoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.video_repo = VideoRepo(db)
        self.tag_repo = TagRepo(db)
        self.storage = MediaFileStorage(settings.VIDEO_DIR)
        self.metadata_reader = VideoMetadataReader()

    def list_videos(self) -> list[VideoRead]:
        return [VideoRead.model_validate(v) for v in self.video_repo.list_all()]

    def upload(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        title: str,
        description: str | None,
        tag_names: list[str],
    ) -> VideoRead:
        validate_media(filename, allowed=ALLOWED_VIDEO_EXTENSIONS)
        saved_path = self.storage.save(file_bytes, filename)
        poster_name: str | None = None
        try:
            poster_name = self.metadata_reader.poster(
                Path(saved_path), settings.COVER_DIR
            )
            # Tags join the row's transaction (commit=False), so the video,
            # its tags and its poster are stored together or not at all.
            tags = self.tag_repo.get_or_create_by_names(tag_names, commit=False)
            video = self.video_repo.create(
                VideoCreate(title=title, description=description, file_path=saved_path),
                tags=tags,
                poster_path=poster_name,
            )
        except Exception:
            # A rejected upload must leave nothing behind, in the database or
            # on disk.
            self.db.rollback()
            self.storage.delete(saved_path)
            self._delete_poster(poster_name)
            raise
        return VideoRead.model_validate(video)

    def upload_multiple(self, files: list[tuple[bytes, str]]) -> list[VideoRead]:
        for _data, filename in files:
            validate_media(filename, allowed=ALLOWED_VIDEO_EXTENSIONS)
        results: list[VideoRead] = []
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
    ) -> VideoRead:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        # A blank title means "keep the current one": title is required.
        if title is not None and title.strip():
            video.title = title.strip()
        if description is not None:
            video.description = description
        if tag_names is not None:
            video.tags = list(self.tag_repo.get_or_create_by_names(tag_names))
        self.db.commit()
        self.db.refresh(video)
        if tag_names is not None:
            self.tag_repo.delete_orphans()
        return VideoRead.model_validate(video)

    def delete(self, video_id: int) -> None:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        file_path, poster_name = video.file_path, video.poster_path
        # Row first: if this fails, the record still points at real files.
        self.video_repo.delete(video_id)
        self.storage.delete(file_path)
        self._delete_poster(poster_name)

    def resolve_stream(self, video_id: int) -> tuple[Path, str]:
        video = self.video_repo.get_by_id(video_id)
        if video is None:
            raise MediaNotFound("Video not found")
        media_path = self.storage.resolve(video.file_path)
        media_type = VIDEO_MEDIA_TYPES.get(
            media_path.suffix.lstrip(".").lower(), "application/octet-stream"
        )
        return media_path, media_type

    @staticmethod
    def _delete_poster(poster_name: str | None) -> None:
        # Posters live beside book covers; Path(...).name keeps the delete
        # inside COVER_DIR whatever the stored value is.
        if poster_name:
            (settings.COVER_DIR / Path(poster_name).name).unlink(missing_ok=True)
