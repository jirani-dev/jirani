class BookError(Exception):
    default_detail: str = "Book error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail if detail is not None else self.default_detail
        super().__init__(self.detail)


class BookNotFound(BookError):
    default_detail = "Book not found"


class InvalidBookFile(BookError):
    default_detail = "Invalid book file"


class BookAlreadyExists(BookError):
    default_detail = "Book already exists"


class CoverGenerationFailed(BookError):
    default_detail = "Cover generation failed"


class InvalidImageError(BookError):
    default_detail = "Invalid image file"
