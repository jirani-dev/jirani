import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf

from app.config import settings

logger = logging.getLogger(__name__)

_IMG_SRC_RE = re.compile(rb'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2].lower()


class CoverGenerator:
    def generate(self, source_path: Path, dest_dir: Path) -> bool:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            suffix = source_path.suffix.lower()
            if suffix == ".pdf":
                return self._from_pdf(source_path, dest_dir)
            if suffix == ".epub":
                return self._from_epub(source_path, dest_dir)
            logger.warning("Unsupported cover source extension: %s", suffix)
            return False
        except Exception:
            logger.exception("Cover generation failed for %s", source_path)
            return False

    def _from_pdf(self, source_path: Path, dest_dir: Path) -> bool:
        doc = pymupdf.open(str(source_path))  # type: ignore[no-untyped-call]
        page = doc.load_page(0)  # type: ignore[no-untyped-call]
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(0.5, 0.5)  # type: ignore[no-untyped-call]
        )
        dest_file = dest_dir / f"{source_path.stem}.png"
        pix.save(str(dest_file))
        doc.close()  # type: ignore[no-untyped-call]
        return self._keep_if_small_enough(dest_file)

    def _from_epub(self, source_path: Path, dest_dir: Path) -> bool:
        cover_bytes: bytes | None = None

        with zipfile.ZipFile(str(source_path), "r") as z:
            names = z.namelist()

            opf_path: str | None = None
            if "META-INF/container.xml" in names:
                container = ET.fromstring(z.read("META-INF/container.xml"))
                for elem in container.iter():
                    if _local_name(elem.tag) == "rootfile":
                        opf_path = elem.get("full-path")
                        break

            if opf_path and opf_path in names:
                opf_dir = "/".join(opf_path.split("/")[:-1])
                opf = ET.fromstring(z.read(opf_path))

                cover_id: str | None = None
                cover_href: str | None = None

                for meta in opf.iter():
                    if _local_name(meta.tag) == "meta":
                        if meta.get("name", "").lower() == "cover":
                            cover_id = meta.get("content")
                            break

                for item in opf.iter():
                    if _local_name(item.tag) == "item":
                        if cover_id and item.get("id") == cover_id:
                            cover_href = item.get("href")
                            break

                if cover_href:
                    full_cover_path = self._join(opf_dir, cover_href)
                    if full_cover_path in names:
                        content = z.read(full_cover_path)
                        if full_cover_path.endswith((".xhtml", ".html", ".htm")):
                            match = _IMG_SRC_RE.search(content)
                            if match:
                                img_src = match.group(1).decode()
                                xhtml_dir = "/".join(full_cover_path.split("/")[:-1])
                                img_path = self._join(xhtml_dir, img_src)
                                if img_path in names:
                                    cover_bytes = z.read(img_path)
                        else:
                            cover_bytes = content

            if not cover_bytes:
                for name in names:
                    if name.lower().endswith((".xhtml", ".html", ".htm")):
                        content = z.read(name)
                        match = _IMG_SRC_RE.search(content)
                        if match:
                            img_src = match.group(1).decode()
                            xhtml_dir = "/".join(name.split("/")[:-1])
                            img_path = self._join(xhtml_dir, img_src)
                            if img_path in names:
                                cover_bytes = z.read(img_path)
                                break

            if not cover_bytes:
                for name in names:
                    if name.lower().endswith((".jpg", ".jpeg", ".png")):
                        cover_bytes = z.read(name)
                        break

        if cover_bytes:
            dest_file = dest_dir / f"{source_path.stem}.png"
            dest_file.write_bytes(cover_bytes)
            return self._keep_if_small_enough(dest_file)

        return False

    def _keep_if_small_enough(self, dest_file: Path) -> bool:
        if dest_file.stat().st_size > settings.MAX_COVER_SIZE:
            dest_file.unlink(missing_ok=True)
            return False
        return True

    def _join(self, base: str, rel: str) -> str:
        parts = f"{base}/{rel}".split("/")
        resolved: list[str] = []
        for part in parts:
            if part == "..":
                if resolved:
                    resolved.pop()
            elif part in ("", "."):
                continue
            else:
                resolved.append(part)
        return "/".join(resolved)
