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
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def video_url(self) -> str:
        return f"/videos/stream/{self.id}"
