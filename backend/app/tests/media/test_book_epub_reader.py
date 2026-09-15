import zipfile
from pathlib import Path

from app.services.epub_metadata_reader import EpubMetadataReader


def _write_minimal_epub(
    path: Path, *, title: str = "Minimal Title", author: str = "Jane Doe"
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
        f"<dc:title>{title}</dc:title><dc:creator>{author}</dc:creator>"
        "<dc:language>en</dc:language></metadata>"
        '<manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'  # noqa: E501
        '<spine><itemref idref="ch1"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", "<html><body>hi</body></html>")


def test_corrupt_epub_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.epub"
    path.write_bytes(b"not a zip")
    assert EpubMetadataReader().read(path) is None


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert EpubMetadataReader().read(tmp_path / "gone.epub") is None


def test_minimal_epub_returns_metadata(tmp_path: Path) -> None:
    path = tmp_path / "minimal.epub"
    _write_minimal_epub(path)
    meta = EpubMetadataReader().read(path)
    assert meta is not None
    assert meta.title == "Minimal Title"
    assert meta.author == "Jane Doe"
    assert isinstance(meta.language, str | None)
    assert isinstance(meta.tags, list)
