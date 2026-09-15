class MediaError(Exception):
    default_detail: str = "Media error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail if detail is not None else self.default_detail
        super().__init__(self.detail)


class MediaNotFound(MediaError):
    default_detail = "Media not found"


class InvalidMediaFile(MediaError):
    default_detail = "Invalid media file"
