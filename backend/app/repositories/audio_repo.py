from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.audio import Audio
from app.models.tag import Tag
from app.repositories.tag_repo import TagRepo
from app.schemas.audio_schema import AudioCreate
from app.services.media_errors import MediaNotFound


class AudioRepo:
    def __init__(self, db_session: Session) -> None:
        self.db_session = db_session

    def create(
        self, audio_create: AudioCreate, *, tags: list[Tag] | None = None
    ) -> Audio:
        new_audio = Audio(**audio_create.model_dump())
        if tags:
            new_audio.tags = tags
        self.db_session.add(new_audio)
        self.db_session.commit()
        self.db_session.refresh(new_audio)
        return new_audio

    def get_by_id(self, audio_id: int) -> Audio | None:
        stmt = (
            select(Audio).options(selectinload(Audio.tags)).where(Audio.id == audio_id)
        )
        return self.db_session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Audio]:
        # Explicit order: without ORDER BY the row order is unspecified and
        # changes after an UPDATE, which would reshuffle the grid on every edit.
        stmt = select(Audio).options(selectinload(Audio.tags)).order_by(Audio.id)
        return list(self.db_session.scalars(stmt).all())

    def delete(self, audio_id: int) -> None:
        audio = self.get_by_id(audio_id)
        if audio is None:
            raise MediaNotFound("Audio not found")
        try:
            self.db_session.delete(audio)
            self.db_session.flush()
            TagRepo(self.db_session).delete_orphans()
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
