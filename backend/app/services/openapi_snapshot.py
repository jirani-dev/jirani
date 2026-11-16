"""Write the API's OpenAPI document where the frontend generates its client from.

Run from backend/:  uv run python -m app.services.openapi_snapshot
"""

import json
from pathlib import Path

from app.config import settings


def render() -> str:
    # Imported here: building the app registers every router, which this
    # module must not do as a side effect of being imported.
    from app.main import app

    # Sorted keys and a trailing newline keep the file byte-stable, so a diff
    # in it always means the API changed.
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def write(path: Path | None = None) -> Path:
    target = path or settings.OPENAPI_SNAPSHOT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(f"wrote {write()}")
