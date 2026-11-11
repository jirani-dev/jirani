import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.tag_schema import TagCreate, TagRead

MAX_TAGS_PER_BOOK = 20


def _reject_duplicate_tags(tags: list[TagCreate]) -> list[TagCreate]:
    names = [tag.name.lower() for tag in tags]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate tags are not allowed")
    return tags


class BookBase(BaseModel):
    uid: str
    title: str
    language: str | None = None
    extension: str
    cover_path: str | None = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class BookCreate(BookBase):
    author_id: int | None = None
    level_id: int | None = None
    genre_id: int | None = None
    file_path: str
    tags: list[TagCreate] = []


class BookRead(BookBase):
    id: int
    author: str | None = Field(default=None, alias="author_name")
    level: str | None = Field(default=None, alias="level_name")
    genre: str | None = Field(default=None, alias="genre_name")
    created_at: datetime
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    # The book cards, the edit form and the tag filter are all built from this.
    tags: list[TagRead] = []

    @computed_field
    def cover_url(self) -> str | None:
        if not self.cover_path:
            return None
        return f"/static/covers/{self.cover_path}"


class BookUpdate(BaseModel):
    # Same bounds as BookUpload: without them an over-long value reaches the
    # database and fails there as an unmapped DataError (a 500).
    title: str | None = Field(None, max_length=255)
    author: str | None = Field(None, max_length=255)
    level: str | None = Field(None, max_length=50)
    genre: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=50)
    # None leaves the book's tags alone; an empty list removes them all.
    tags: list[TagCreate] | None = Field(None, max_length=MAX_TAGS_PER_BOOK)
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[TagCreate] | None) -> list[TagCreate] | None:
        return v if v is None else _reject_duplicate_tags(v)


class BookUpload(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    author: str | None = Field(None, max_length=255)
    level: str | None = Field(None, max_length=50)
    genre: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=50)
    tags: list[TagCreate] = Field(default_factory=list, max_length=MAX_TAGS_PER_BOOK)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = " ".join(v.split())
        if re.search(r'[<>:"/\\|?*]', v):
            raise ValueError("Title contains invalid characters")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[TagCreate]) -> list[TagCreate]:
        return _reject_duplicate_tags(v)


class BookSearchCriteria(BaseModel):
    title: str | None = None
    author: str | None = None
    level: str | None = None
    genre: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    extension: str | None = None
    metadata_: dict[str, Any] | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
