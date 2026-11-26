import json
from pathlib import Path

import pytest

from app.config import settings
from app.services import openapi_snapshot


def test_committed_snapshot_matches_the_app() -> None:
    # The frontend client is generated from this file. If this fails, a route
    # or schema changed: run `npm run generate-api` in frontend/ and commit
    # the result.
    assert settings.OPENAPI_SNAPSHOT.read_text(encoding="utf-8") == (
        openapi_snapshot.render()
    )


def test_render_is_stable_and_sorted() -> None:
    first = openapi_snapshot.render()

    assert first == openapi_snapshot.render()
    assert first.endswith("}\n")
    assert first == json.dumps(json.loads(first), indent=2, sort_keys=True) + "\n"


def test_write_creates_the_target_and_its_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "openapi.json"

    written = openapi_snapshot.write(target)

    assert written == target
    assert target.read_text(encoding="utf-8") == openapi_snapshot.render()


def test_write_defaults_to_the_configured_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "openapi.json"
    monkeypatch.setattr(settings, "OPENAPI_SNAPSHOT", target)

    assert openapi_snapshot.write() == target
    assert target.exists()


def test_snapshot_path_is_anchored_to_the_repository() -> None:
    assert settings.OPENAPI_SNAPSHOT.is_absolute()
    assert settings.OPENAPI_SNAPSHOT.parts[-5:] == (
        "frontend",
        "src",
        "api",
        "generated",
        "openapi.json",
    )


def test_login_role_is_typed_as_the_role_enum() -> None:
    schemas = json.loads(openapi_snapshot.render())["components"]["schemas"]

    assert schemas["TokenResponse"]["properties"]["role"] == {
        "$ref": "#/components/schemas/RoleEnum"
    }
    assert schemas["RoleEnum"]["enum"] == ["admin", "student", "teacher"]
