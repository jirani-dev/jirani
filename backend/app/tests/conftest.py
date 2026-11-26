import errno
import json
from collections.abc import Callable, Generator
from pathlib import Path
from types import ModuleType, TracebackType
from typing import IO, Any, cast

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

DBEnv = tuple[FastAPI, ModuleType]


class _HalfWrittenFile:
    """A file that stores half of what it is given and then fails, as on a
    disk that fills up during the write."""

    def __init__(self, file: IO[bytes]) -> None:
        self._file = file

    def write(self, data: bytes) -> int:
        self._file.write(bytes(data)[: len(data) // 2])
        self._file.flush()
        raise OSError(errno.ENOSPC, "No space left on device")

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "_HalfWrittenFile":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


@pytest.fixture()
def fill_disk(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Returns a switch: once called, every file the app writes, through Python
    or through MuPDF's Pixmap.save, gets half its bytes and then fails."""
    real_open = Path.open

    def open_half_written(
        self: Path, mode: str = "r", *args: Any, **kwargs: Any
    ) -> Any:
        file = real_open(self, mode, *args, **kwargs)
        return _HalfWrittenFile(file) if set(mode) & set("wxa") else file

    # CoverGenerator writes through write_new_file today. Failing Pixmap.save
    # too means a return to MuPDF-side writes would still be caught.
    def save_half_written(self: pymupdf.Pixmap, filename: str, *args: Any) -> None:
        with open_half_written(Path(filename), "wb") as file:
            file.write(self.tobytes("png"))

    def switch_on() -> None:
        monkeypatch.setattr(Path, "open", open_half_written)
        monkeypatch.setattr(pymupdf.Pixmap, "save", save_half_written)

    return switch_on


@pytest.fixture(scope="session")
def db_env() -> Generator[DBEnv]:
    import app.main
    import app.services.setup_service as setup_service_module

    yield app.main.app, setup_service_module


@pytest.fixture(autouse=True)
def reset_db(db_env: DBEnv) -> Generator[None]:
    from app.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client(db_env: DBEnv) -> Generator[TestClient]:
    app, _ = db_env
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(db_env: DBEnv) -> Generator[Session]:
    from app.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def setup_paths(db_env: DBEnv, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    _, setup_service_module = db_env
    monkeypatch.setattr(setup_service_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        setup_service_module, "CREDENTIALS_FILE", tmp_path / ".credentials"
    )
    monkeypatch.setattr(
        setup_service_module, "REVEALED_FLAG", tmp_path / ".credentials_revealed"
    )
    return tmp_path


def _read_admin_password(paths: Path) -> str:
    password = json.loads((paths / ".credentials").read_text())["password"]
    assert isinstance(password, str)
    return password


def setup_admin(client: TestClient, paths: Path) -> str:
    response = client.get("/setup")
    assert response.status_code == 200
    return _read_admin_password(paths)


def login(client: TestClient, username: str, password: str) -> dict[str, Any]:
    response = client.post(
        "/auth/token", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
