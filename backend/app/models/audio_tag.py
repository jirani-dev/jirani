from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AudioTag(Base):
    __tablename__ = "audio_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audio.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("audio_id", "tag_id"),)
