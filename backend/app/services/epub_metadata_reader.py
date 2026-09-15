import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookMetadata:
    title: str | None
    author: str | None
    language: str | None
    tags: list[str] = field(default_factory=list)


class EpubMetadataReader:
    def read(self, path: Path) -> BookMetadata | None:
        try:
            doc = pymupdf.open(str(path))  # type: ignore[no-untyped-call]
            meta = doc.metadata or {}
            doc.close()  # type: ignore[no-untyped-call]
        except (RuntimeError, ValueError, OSError):
            logger.warning("Failed to read EPUB metadata from %s", path, exc_info=True)
            return None

        title = meta.get("title") or None
        author = meta.get("author") or None
        language = meta.get("language") or None

        subjects = meta.get("subject") or ""
        tags = [t.strip() for t in re.split(r"[,;]+", subjects) if t.strip()]

        return BookMetadata(title=title, author=author, language=language, tags=tags)
