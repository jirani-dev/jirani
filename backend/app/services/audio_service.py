from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.audio_repo import AudioRepo
from app.repositories.tag_repo import TagRepo
from app.schemas.audio_schema import AudioCreate, AudioRead
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

    def list_tracks(self) -> list[AudioRead]:
        return [AudioRead.model_validate(t) for t in self.audio_repo.list_all()]

    def upload(
        self, file_bytes: bytes, filename: str, tag_names: list[str]
    ) -> AudioRead:
        validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)
        saved_path = self.storage.save(file_bytes, filename)
        try:
            # Tags join the row's transaction (commit=False), so the track and
            # its tags are stored together or not at all.
            tags = self.tag_repo.get_or_create_by_names(tag_names, commit=False)
            track = self.audio_repo.create(
                AudioCreate(
                    title=Path(filename).stem, description=None, file_path=saved_path
                ),
                tags=tags,
            )
        except Exception:
            # A rejected upload must leave nothing behind, in the database or
            # on disk.
            self.db.rollback()
            self.storage.delete(saved_path)
            raise
        return AudioRead.model_validate(track)

    def upload_multiple(self, files: list[tuple[bytes, str]]) -> list[AudioRead]:
        for _data, filename in files:
            validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)
        results: list[AudioRead] = []
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
    ) -> AudioRead:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        # A blank title means "keep the current one": title is required.
        if title is not None and title.strip():
            track.title = title.strip()
        if description is not None:
            track.description = description
        if tag_names is not None:
            track.tags = list(self.tag_repo.get_or_create_by_names(tag_names))
        self.db.commit()
        self.db.refresh(track)
        if tag_names is not None:
            self.tag_repo.delete_orphans()
        return AudioRead.model_validate(track)

    def delete(self, audio_id: int) -> None:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        file_path = track.file_path
        # Row first: if this fails, the record still points at a real file.
        self.audio_repo.delete(audio_id)
        self.storage.delete(file_path)

    def resolve_stream(self, audio_id: int) -> tuple[Path, str]:
        track = self.audio_repo.get_by_id(audio_id)
        if track is None:
            raise MediaNotFound("Audio not found")
        media_path = self.storage.resolve(track.file_path)
        media_type = AUDIO_MEDIA_TYPES.get(
            media_path.suffix.lstrip(".").lower(), "audio/mpeg"
        )
        return media_path, media_type
