import json
import sys
from pathlib import Path

from app.main import app

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes((json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"wrote {out}")