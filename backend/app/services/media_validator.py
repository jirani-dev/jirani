from pathlib import Path

from app.services.media_errors import InvalidMediaFile

ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {"mp4", "mov", "avi", "mkv", "webm", "m4v", "ogv", "wmv"}
)


def validate_media(filename: str, *, allowed: frozenset[str]) -> str:
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in allowed:
        raise InvalidMediaFile(f"File type .{ext} not allowed")
    return ext
