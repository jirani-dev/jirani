import secrets
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SECRET_FILE = DATA_DIR / ".secret"


def get_secret_key() -> str:
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    key = secrets.token_urlsafe(32)
    SECRET_FILE.write_text(key)
    return key


class Settings(BaseSettings):
    # App metadata
    APP_NAME: str = "Jirani Offline Library"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Offline library management system"

    # App settings
    # DEBUG echoes every SQL statement to the log (see database.py), which is
    # noise and I/O a production server does not need: opt-in.
    DEBUG: bool = False

    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/jirani_library"

    # Security settings
    # Empty means "not supplied by the environment": __init__ then loads (or
    # creates) the key file. Resolving it here instead would write the file on
    # import even when SECRET_KEY is set.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # Lifetime of both the JWT and the access_token cookie that carries it.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # File upload settings
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "uploads" / "books"
    COVER_DIR: Path = BASE_DIR / "uploads" / "covers"
    AUDIO_DIR: Path = BASE_DIR / "uploads" / "audio"
    VIDEO_DIR: Path = BASE_DIR / "uploads" / "videos"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_COVER_SIZE: int = 5 * 1024 * 1024  # 5MB

    # The OpenAPI document the frontend client is generated from. It lives in
    # the frontend tree so the generated types and their input are reviewed
    # together; services/openapi_snapshot.py writes it.
    OPENAPI_SNAPSHOT: Path = (
        BASE_DIR.parent / "frontend" / "src" / "api" / "generated" / "openapi.json"
    )

    # Default credentials
    STUDENT_DEFAULT_PASSWORD: str = "student123"
    TEACHER_DEFAULT_PASSWORD: str = "teacher123"

    @property
    def ALLOWED_EXTENSIONS(self) -> set[str]:
        return {"pdf", "epub"}

    @property
    def ALLOWED_IMAGE_EXTENSIONS(self) -> set[str]:
        return {"jpg", "jpeg", "png", "webp"}

    model_config = SettingsConfigDict(case_sensitive=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            self.SECRET_KEY = get_secret_key()


settings = Settings()
