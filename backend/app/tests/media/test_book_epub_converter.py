import zipfile
from pathlib import Path

import pytest

from app.services.epub_converter import READ_COPY_SUFFIX, EpubConverter


def _write_minimal_epub(path: Path) -> None:
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'  # noqa: E501
        '<rootfiles><rootfile full-path="content.opf"'
        ' media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0"'
        ' unique-identifier="id">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>t</dc:title><dc:language>en</dc:language>"
        '<dc:identifier id="id">x</dc:identifier></metadata>'
        '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>'  # noqa: E501
        '<spine><itemref idref="c1"/></spine></package>'
    )
    chapter = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head>'
        "<body><p>hello</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("content.opf", opf)
        z.writestr("c1.xhtml", chapter)


def test_convert_writes_the_read_copy_and_nothing_else(tmp_path: Path) -> None:
    source = tmp_path / "novel.epub"
    _write_minimal_epub(source)

    dest = EpubConverter().convert(source, tmp_path)

    assert dest == tmp_path / f"novel{READ_COPY_SUFFIX}"
    assert dest is not None
    assert dest.read_bytes().startswith(b"%PDF-")
    # The temporary file it is written through must not outlive the call.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["novel.epub", dest.name]


def test_convert_failure_leaves_no_partial_file(tmp_path: Path) -> None:
    source = tmp_path / "broken.epub"
    source.write_bytes(b"PK\x03\x04 not an epub")

    assert EpubConverter().convert(source, tmp_path) is None
    assert [p.name for p in tmp_path.iterdir()] == ["broken.epub"]


def test_convert_never_exposes_a_half_written_read_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # nginx serves the read copy as soon as it exists, so it has to appear
    # complete: at the moment of the rename the final name must not exist yet.
    source = tmp_path / "novel.epub"
    _write_minimal_epub(source)
    final = tmp_path / f"novel{READ_COPY_SUFFIX}"
    seen: list[tuple[bool, bytes]] = []
    real_replace = Path.replace

    def recording_replace(self: Path, target: Path) -> Path:
        seen.append((final.exists(), self.read_bytes()[:5]))
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", recording_replace)

    assert EpubConverter().convert(source, tmp_path) == final
    assert seen == [(False, b"%PDF-")]
