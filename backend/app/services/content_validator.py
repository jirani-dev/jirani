from pathlib import Path

from app.config import settings
from app.services.book_errors import InvalidBookFile


class ContentValidator:
    _MAGIC_BYTES: dict[str, bytes] = {"pdf": b"%PDF-", "epub": b"PK\x03\x04"}

    def validate(self, file_bytes: bytes, filename: str) -> str:
        if not file_bytes:
            raise InvalidBookFile("File is empty")

        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise InvalidBookFile(
                f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE} bytes"
            )

        extension = Path(filename).suffix.lstrip(".").lower()
        if extension not in settings.ALLOWED_EXTENSIONS:
            raise InvalidBookFile(f"File extension not allowed: {extension}")

        magic = self._MAGIC_BYTES[extension]
        if not file_bytes.startswith(magic):
            raise InvalidBookFile(f"File content does not match extension: {extension}")

        return extension
