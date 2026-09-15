import pytest

from app.services.media_errors import InvalidMediaFile, MediaError, MediaNotFound
from app.services.media_validator import ALLOWED_VIDEO_EXTENSIONS, validate_media


@pytest.mark.parametrize("ext", sorted(ALLOWED_VIDEO_EXTENSIONS))
def test_accepts_each_video_extension_case_folded(ext: str) -> None:
    assert (
        validate_media(f"Clip.{ext.upper()}", allowed=ALLOWED_VIDEO_EXTENSIONS) == ext
    )


def test_rejects_disallowed_extension_exact_detail() -> None:
    with pytest.raises(InvalidMediaFile) as exc:
        validate_media("notes.txt", allowed=ALLOWED_VIDEO_EXTENSIONS)
    assert exc.value.detail == "File type .txt not allowed"


def test_rejects_name_without_dot() -> None:
    with pytest.raises(InvalidMediaFile) as exc:
        validate_media("noext", allowed=ALLOWED_VIDEO_EXTENSIONS)
    assert exc.value.detail == "File type . not allowed"


def test_rejects_dotfile_without_real_extension() -> None:
    with pytest.raises(InvalidMediaFile) as exc:
        validate_media(".mp4", allowed=ALLOWED_VIDEO_EXTENSIONS)
    assert exc.value.detail == "File type . not allowed"


def test_rejects_trailing_dot_name() -> None:
    with pytest.raises(InvalidMediaFile) as exc:
        validate_media("clip.mp4.", allowed=ALLOWED_VIDEO_EXTENSIONS)
    assert exc.value.detail == "File type . not allowed"


def test_error_default_details() -> None:
    assert MediaNotFound("Audio not found").detail == "Audio not found"
    assert MediaNotFound().detail == "Media not found"
    assert InvalidMediaFile().detail == "Invalid media file"
    assert isinstance(MediaNotFound(), MediaError)
