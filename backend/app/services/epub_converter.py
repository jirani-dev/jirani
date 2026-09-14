import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


class EpubConverter:
    def convert(self, source: Path, dest_dir: Path) -> Path | None:
        dest = dest_dir / f"{source.stem}.read.pdf"
        try:
            doc = pymupdf.open(str(source))  # type: ignore[no-untyped-call]
            pdf_bytes = doc.convert_to_pdf()  # type: ignore[no-untyped-call]
            doc.close()  # type: ignore[no-untyped-call]
            if not pdf_bytes:
                return None
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pdf_bytes)
        except Exception:
            logger.warning(
                "EPUB to PDF conversion failed for %s", source, exc_info=True
            )
            return None
        return dest
