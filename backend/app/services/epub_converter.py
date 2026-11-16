import contextlib
import logging
from pathlib import Path
from uuid import uuid4

import pymupdf

logger = logging.getLogger(__name__)

# Suffix of the PDF rendition cached next to an EPUB the first time it is read.
READ_COPY_SUFFIX = ".read.pdf"


class EpubConverter:
    def convert(self, source: Path, dest_dir: Path) -> Path | None:
        dest = dest_dir / f"{source.stem}{READ_COPY_SUFFIX}"
        # Written under a private name and renamed into place: nginx serves
        # `dest` as soon as it exists, so it must never be half-written.
        partial = dest.with_name(f"{dest.name}.{uuid4().hex}.tmp")
        try:
            with pymupdf.open(str(source)) as doc:  # type: ignore[no-untyped-call]
                pdf_bytes = doc.convert_to_pdf()
            if not pdf_bytes:
                return None
            dest_dir.mkdir(parents=True, exist_ok=True)
            partial.write_bytes(pdf_bytes)
            partial.replace(dest)
        except Exception:
            logger.warning(
                "EPUB to PDF conversion failed for %s", source, exc_info=True
            )
            with contextlib.suppress(OSError):
                partial.unlink(missing_ok=True)
            return None
        return dest
