import json
import secrets
from pathlib import Path

from app.config import DATA_DIR
from app.services.auth_service import AuthService

CREDENTIALS_FILE = Path(DATA_DIR) / ".credentials"
REVEALED_FLAG = Path(DATA_DIR) / ".credentials_revealed"


class SetupService:
    def __init__(self, auth_service: AuthService) -> None:
        self.auth_service = auth_service

    def get_admin_credentials(self) -> dict[str, str]:
        if REVEALED_FLAG.exists():
            raise PermissionError("admin credentials have already been revealed.")
        if CREDENTIALS_FILE.exists():
            credentials: dict[str, str] = json.loads(CREDENTIALS_FILE.read_text())
        else:
            password = secrets.token_urlsafe(8)
            credentials = {"username": "admin", "password": password}
            self.auth_service.setup_admin_account(credentials["password"])
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps(credentials))
        REVEALED_FLAG.touch()
        return credentials
