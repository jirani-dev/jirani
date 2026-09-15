from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.audio_repo import AudioRepo
from app.repositories.tag_repo import TagRepo
from app.schemas.audio_schema import AudioCreate, AudioView
from app.services.media_errors import MediaNotFound
from app.services.media_file_storage import MediaFileStorage
from app.services.media_validator import ALLOWED_AUDIO_EXTENSIONS, validate_media

AUDIO_MEDIA_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
}


class AudioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audio_repo = AudioRepo(db)
        self.tag_repo = TagRepo(db)
        self.storage = MediaFileStorage(settings.AUDIO_DIR)

    def list_tracks(self) -> list[AudioView]:
        return [AudioView.model_validate(t) for t in self.audio_repo.list_all()]

    def upload(
        self, file_bytes: bytes, filename: str, tag_names: list[str]
    ) -> AudioView:
        validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)
saved_path = self.storage.save(file_bytes, Path(filename).name)
        track = self.audio_repo.create(
            AudioCreate(
                title=Path(filename).stem, description=None, file_path=saved_path
            )
        )
        track.tags = list(self.tag_repo.get_or_create_by_names(tag_names))
        self.db.commit()
        self.db.refresh(track)
        return AudioView.model_validate(track)

    def upload_multiple(self, files: list[tuple[bytes, str]]) -> list[AudioView]:
        for _data, filename in files:
            validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)
        results: list[AudioView] = []
        for data, filename in files:
            results.append(self.upload(data, filename, []))
        return results

    def update(
        self,
        audio_id: int,
        *,
        title: str | None,
        description: str | None,
        tag_names: list[str] | None,
    ) -> AudioView:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        if title is not None:
            track.title = title
        if description is not None:
            track.description = description
        if tag_names is not None:
            track.tags = list(self.tag_repo.get_or_create_by_names(tag_names))
        self.db.commit()
        self.db.refresh(track)
        if tag_names is not None:
            self.tag_repo.delete_orphans()
        return AudioView.model_validate(track)

    def delete(self, audio_id: int) -> None:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        self.storage.delete(track.file_path)
        self.audio_repo.delete(audio_id)

    def resolve_stream(self, audio_id: int) -> tuple[Path, str]:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        media_path = self.storage.resolve(track.file_path)
        media_type = AUDIO_MEDIA_TYPES.get(
            media_path.suffix.lstrip(".").lower(), "audio/mpeg"
        )
        return media_path, media_type
