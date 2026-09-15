from pathlib import Path

from app.config import settings
from app.services.book_errors import InvalidImageError


class ImageValidator:
    _MAGIC_BYTES: dict[str, bytes] = {
        "jpg": b"\xff\xd8",
        "jpeg": b"\xff\xd8",
        "png": b"\x89PNG\r\n\x1a\n",
        "webp": b"RIFF",
    }

    def validate(self, file_bytes: bytes, filename: str) -> str:
        if not file_bytes:
            raise InvalidImageError("Image file is empty")
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise InvalidImageError(f"Image type .{ext} not allowed")
        if len(file_bytes) > settings.MAX_COVER_SIZE:
            raise InvalidImageError(
                f"Image exceeds maximum cover size of {settings.MAX_COVER_SIZE} bytes"
            )
        if not file_bytes.startswith(self._MAGIC_BYTES[ext]):
            raise InvalidImageError(f"Image content does not match extension: {ext}")
        if ext == "webp" and file_bytes[8:12] != b"WEBP":
            raise InvalidImageError("Image content does not match extension: webp")
        return ext
