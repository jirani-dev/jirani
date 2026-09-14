from pydantic import BaseModel, ConfigDict, computed_field

from app.schemas.tag_schema import TagRead


class VideoCreate(BaseModel):
    title: str
    description: str | None = None
    file_path: str


class VideoView(BaseModel):
    id: int
    title: str
    description: str | None = None
    poster_path: str | None = None
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def video_url(self) -> str:
        return f"/videos/stream/{self.id}"

    @computed_field
    def poster_url(self) -> str | None:
        if not self.poster_path:
            return None
        return f"/static/covers/{self.poster_path}"
