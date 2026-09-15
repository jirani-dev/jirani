from pathlib import Path
from uuid import uuid4

from app.services.media_errors import MediaNotFound


class MediaFileStorage:
    def __init__(self, save_dir: Path) -> None:
        self.save_dir = save_dir

    def save(self, file_bytes: bytes, filename: str) -> str:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        target = self.save_dir / f"{uuid4()}_{filename}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
        return str(target)

    def resolve(self, path: str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.save_dir / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.save_dir.resolve()):
            raise MediaNotFound(f"Invalid media path: {path!r}")
        if not resolved.is_file():
            raise MediaNotFound(f"Media file not found: {path!r}")
        return resolved

    def delete(self, path: str) -> None:
        try:
            target = self.resolve(path)
        except MediaNotFound:
            return
        target.unlink(missing_ok=True)
