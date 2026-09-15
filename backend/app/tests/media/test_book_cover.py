import zipfile
from pathlib import Path

import pymupdf
import pytest

from app.config import settings
from app.services.cover_generator import CoverGenerator


def _write_real_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello cover")
    doc.save(str(path))
    doc.close()


def _png_bytes() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2))
    return pix.tobytes("png")


def _write_epub_with_cover(path: Path) -> None:
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'  # noqa: E501
        '<rootfiles><rootfile full-path="OEBPS/content.opf"'
        ' media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<meta name="cover" content="cover-img"/>'
        "<dc:title>Covered</dc:title></metadata>"
        "<manifest>"
        '<item id="cover-img" href="images/cover.png" media-type="image/png"/>'
        '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        "</manifest>"
        '<spine><itemref idref="ch1"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/images/cover.png", _png_bytes())
        z.writestr("OEBPS/ch1.xhtml", "<html><body>hi</body></html>")


def _write_minimal_epub(path: Path) -> None:
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'  # noqa: E501
        '<rootfiles><rootfile full-path="OEBPS/content.opf"'
        ' media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Minimal</dc:title></metadata>"
        '<manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'  # noqa: E501
        '<spine><itemref idref="ch1"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", "<html><body>hi</body></html>")


def test_corrupt_pdf_returns_false(tmp_path: Path) -> None:
    corrupt = tmp_path / "bk0007.pdf"
    corrupt.write_bytes(b"not a pdf")
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(corrupt, dest) is False
    assert list(dest.iterdir()) == []


def test_real_pdf_generates_cover(tmp_path: Path) -> None:
    source = tmp_path / "bk0001.pdf"
    _write_real_pdf(source)
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(source, dest) is True
    cover = dest / "bk0001.png"
    assert cover.exists()
    size = cover.stat().st_size
    assert size >= 1
    assert size <= settings.MAX_COVER_SIZE


def test_epub_with_declared_cover_returns_true(tmp_path: Path) -> None:
    epub = tmp_path / "covered.epub"
    _write_epub_with_cover(epub)
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(epub, dest) is True
    assert (dest / "covered.png").exists()


def test_epub_without_images_returns_false(tmp_path: Path) -> None:
    epub = tmp_path / "plain.epub"
    _write_minimal_epub(epub)
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(epub, dest) is False
    assert list(dest.iterdir()) == []


def test_oversized_cover_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_COVER_SIZE", 1)
    source = tmp_path / "bk0001.pdf"
    _write_real_pdf(source)
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(source, dest) is False
    assert list(dest.iterdir()) == []
