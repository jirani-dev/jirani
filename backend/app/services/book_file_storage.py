import logging
import re
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.services.book_errors import BookNotFound

logger = logging.getLogger(__name__)

# Leaves room for "_<uuid>.<ext>" inside the 255-character limit that both
# common filesystems and books.file_path impose on the stored name.
_MAX_STEM_LENGTH = 150


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
        # A new name for every upload. Covers are served with a day-long cache
        # lifetime, so a replacement written under the old name would keep
        # showing the old image; a distinct name also means the previous
        # cover can be deleted without ever touching the new one.
        name = f"{uid}_{uuid4().hex[:8]}.{ext}"
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        (self.cover_dir / name).write_bytes(data)
        return name

    def delete(self, rel_path: str, *, missing_ok: bool = False) -> None:
        try:
            self._contained(rel_path).unlink(missing_ok=missing_ok)
        except (BookNotFound, OSError):
            logger.warning("Failed to delete book file %r", rel_path, exc_info=True)

    def delete_cover(self, cover_name: str) -> None:
        try:
            (self.cover_dir / cover_name).unlink()
        except OSError:
            logger.warning("Failed to delete cover %r", cover_name, exc_info=True)

    def resolve(self, rel_path: str) -> Path:
        resolved = self._contained(rel_path)
        if not resolved.is_file():
            raise BookNotFound(f"Book file not found: {rel_path!r}")
        return resolved

    def _contained(self, rel_path: str) -> Path:
        base = self.upload_dir.resolve()
        resolved = (base / rel_path).resolve()
        if not resolved.is_relative_to(base):
            raise BookNotFound(f"Invalid book file path: {rel_path!r}")
        return resolved

    def _safe_name(self, filename: str, uid: str) -> str:
        name = Path(filename).name
        stem, _, ext = name.rpartition(".")
        sanitized_stem = re.sub(r"[^a-z0-9._-]", "", stem.lower())[:_MAX_STEM_LENGTH]
        clean_ext = re.sub(r"[^a-z0-9]", "", ext.lower())
        return f"{sanitized_stem}_{uid}.{clean_ext}"
