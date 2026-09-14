import pytest

from app.config import settings
from app.services.book_errors import InvalidBookFile
from app.services.content_validator import ContentValidator


def test_empty_file_rejected() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"", "book.pdf")


def test_disallowed_extension_rejected() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"whatever", "malware.exe")


def test_magic_bytes_pdf_mismatch() -> None:
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"not a real pdf", "fake.pdf")


def test_oversized_payload_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)
    with pytest.raises(InvalidBookFile):
        ContentValidator().validate(b"x" * 11, "big.pdf")


def test_valid_pdf_returns_lowercase_extension() -> None:
    result = ContentValidator().validate(b"%PDF-1.4 real stub bytes", "Report.PDF")
    assert result == "pdf"


def test_valid_epub_returns_lowercase_extension() -> None:
    result = ContentValidator().validate(b"PK\x03\x04 epub stub bytes", "book.EPUB")
    assert result == "epub"


def test_no_dot_name_reports_empty_extension() -> None:
    with pytest.raises(InvalidBookFile) as exc:
        ContentValidator().validate(b"%PDF-1.4 stub", "noext")
    assert exc.value.detail == "File extension not allowed: "


def test_dotfile_without_real_extension_rejected() -> None:
    with pytest.raises(InvalidBookFile) as exc:
        ContentValidator().validate(b"%PDF-1.4 real stub bytes", ".pdf")
    assert exc.value.detail == "File extension not allowed: "
