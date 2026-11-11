import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagBase(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class TagRead(TagBase):
    id: int


class TagCreate(TagBase):
    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        # Runs after the strip and length checks above, so v is never blank.
        v = " ".join(v.split())

        # Allowed characters: letters, numbers, spaces, hyphens, underscores
        if not re.match(r"^[\w\s-]+$", v):
            raise ValueError(
                "Tag name can only contain letters, numbers, "
                "spaces, hyphens, and underscores"
            )

        return v
