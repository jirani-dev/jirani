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


def _jpeg_bytes(width: int, height: int) -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    pix.clear_with(128)
    return pix.tobytes("jpeg")


def _write_epub_with_cover(
    path: Path, *, cover: bytes | None = None, href: str = "images/cover.png"
) -> None:
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
        f'<item id="cover-img" href="{href}" media-type="image/png"/>'
        '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        "</manifest>"
        '<spine><itemref idref="ch1"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr(f"OEBPS/{href}", cover if cover is not None else _png_bytes())
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


def test_epub_jpeg_cover_is_stored_as_a_real_downscaled_png(tmp_path: Path) -> None:
    # The cover file is always named .png, and EPUB covers are mostly large
    # JPEGs; the raw bytes used to be written under that name untouched.
    epub = tmp_path / "jpegcover.epub"
    _write_epub_with_cover(epub, cover=_jpeg_bytes(1600, 2400), href="images/c.jpg")
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(epub, dest) is True
    cover = dest / "jpegcover.png"
    assert cover.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    pix = pymupdf.Pixmap(str(cover))
    assert (pix.width, pix.height) == (600, 900)


def test_epub_cover_that_is_not_an_image_returns_false(tmp_path: Path) -> None:
    epub = tmp_path / "svgcover.epub"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    _write_epub_with_cover(epub, cover=svg, href="images/cover.svg")
    dest = tmp_path / "covers"
    assert CoverGenerator().generate(epub, dest) is False
    assert list(dest.iterdir()) == []


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
