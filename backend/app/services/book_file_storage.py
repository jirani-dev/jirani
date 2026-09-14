import logging
import re
from pathlib import Path

from app.config import settings
from app.services.book_errors import BookNotFound

logger = logging.getLogger(__name__)


class BookFileStorage:
    @property
    def upload_dir(self) -> Path:
        return settings.UPLOAD_DIR

    @property
    def cover_dir(self) -> Path:
        return settings.COVER_DIR

    def save(self, file_bytes: bytes, filename: str, uid: str) -> str:
        safe_name = self._safe_name(filename, uid)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        (self.upload_dir / safe_name).write_bytes(file_bytes)
        return safe_name

    def save_cover(self, uid: str, data: bytes, ext: str) -> str:
        name = f"{uid}.{ext}"
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        (self.cover_dir / name).write_bytes(data)
        return name

    def delete(self, rel_path: str) -> None:
        try:
            target = self.resolve(rel_path)
            target.unlink()
        except (BookNotFound, OSError):
            logger.warning("Failed to delete book file %r", rel_path, exc_info=True)

    def delete_cover(self, cover_name: str) -> None:
        try:
            (self.cover_dir / cover_name).unlink()
        except (BookNotFound, OSError):
            logger.warning("Failed to delete cover %r", cover_name, exc_info=True)

    def resolve(self, rel_path: str) -> Path:
        base = self.upload_dir.resolve()
        resolved = (base / rel_path).resolve()
        if not resolved.is_relative_to(base):
            raise BookNotFound(f"Invalid book file path: {rel_path!r}")
        if not resolved.is_file():
            raise BookNotFound(f"Book file not found: {rel_path!r}")
        return resolved

    def _safe_name(self, filename: str, uid: str) -> str:
        name = Path(filename).name
        stem, _, ext = name.rpartition(".")
        sanitized_stem = re.sub(r"[^a-z0-9._-]", "", stem.lower())
        clean_ext = re.sub(r"[^a-z0-9]", "", ext.lower())
        return f"{sanitized_stem}_{uid}.{clean_ext}"
