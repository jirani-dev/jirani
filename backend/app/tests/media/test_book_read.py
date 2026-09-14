import io
import zipfile
from pathlib import Path
from urllib.parse import quote

import pytest

from app.config import settings
from app.models.book import Book
from app.services.epub_converter import EpubConverter
from app.tests.conftest import auth_headers, login, setup_admin


@pytest.fixture()
def read_env(client, setup_paths, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    admin_pw = setup_admin(client, setup_paths)
    token = login(client, "admin", admin_pw)["access_token"]
    headers = auth_headers(token)
    return tmp_path, headers


def _seed_book(db, *, uid: str, file_path: str, extension: str = "pdf") -> Book:
    book = Book(
        uid=uid,
        title=f"Title {uid}",
        file_path=file_path,
        extension=extension,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def _make_epub(path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        zf.writestr(
            "content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
            'version="2.0" unique-identifier="id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>t</dc:title>'
            "<dc:language>en</dc:language>"
            '<dc:identifier id="id">x</dc:identifier></metadata><manifest>'
            '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/></spine></package>',
        )
        zf.writestr(
            "c1.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title>'
            "</head><body><p>hello</p></body></html>",
        )
    path.write_bytes(buf.getvalue())


def test_read_pdf_book_serves_original(db, client, read_env):
    tmp_path, headers = read_env
    uid = "pdfbook"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Accept-Ranges"] == "bytes"


def test_read_epub_converts_to_read_pdf(db, client, read_env):
    tmp_path, headers = read_env
    uid = "epubbook"
    _make_epub(tmp_path / f"{uid}.epub")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Accel-Redirect"] == f"/media/books/{quote(uid)}.read.pdf"
    assert response.headers["Content-Type"] == "application/pdf"
    converted = tmp_path / f"{uid}.read.pdf"
    assert converted.exists()
    assert converted.read_bytes()[:5] == b"%PDF-"


def test_read_converter_failure_404(db, client, read_env, monkeypatch):
    tmp_path, headers = read_env
    uid = "brokencv"
    (tmp_path / f"{uid}.epub").write_bytes(b"PK\x03\x04 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    monkeypatch.setattr(EpubConverter, "convert", lambda self, source, dest_dir: None)
    response = client.get(f"/books/{uid}/read", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Book not readable"


def test_read_epub_second_get_uses_cache(db, client, read_env, monkeypatch):
    tmp_path, headers = read_env
    uid = "cached"
    _make_epub(tmp_path / f"{uid}.epub")
    _seed_book(db, uid=uid, file_path=f"{uid}.epub", extension="epub")
    calls: list[str] = []
    original = EpubConverter.convert

    def counting(self, source, dest_dir):
        calls.append(source.name)
        return original(self, source, dest_dir)

    monkeypatch.setattr(EpubConverter, "convert", counting)
    first = client.get(f"/books/{uid}/read", headers=headers)
    second = client.get(f"/books/{uid}/read", headers=headers)
    assert first.status_code == 204
    assert second.status_code == 204
    assert len(calls) == 1


def test_read_unauthenticated_401(db, client, read_env):
    tmp_path, _ = read_env
    uid = "noauth"
    (tmp_path / f"{uid}.pdf").write_bytes(b"%PDF-1.4 mock")
    _seed_book(db, uid=uid, file_path=f"{uid}.pdf")
    response = client.get(f"/books/{uid}/read")
    assert response.status_code == 401
