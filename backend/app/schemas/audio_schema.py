from pydantic import BaseModel, ConfigDict, computed_field

from app.schemas.tag_schema import TagRead


class AudioCreate(BaseModel):
    title: str
    description: str | None = None
    file_path: str


class AudioRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def audio_url(self) -> str:
        return f"/audio/stream/{self.id}"
