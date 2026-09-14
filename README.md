# Jirani Offline Library Backend

## Run With Docker

### 1. Build and start containers

```bash
docker compose up --build
```

This starts:
- API at http://localhost:8000
- PostgreSQL at localhost:5432

### 2. Stop containers

```bash
docker compose down
```

### 3. Stop containers and remove database volume

```bash
docker compose down -v
```

## Notes

- **Schema** is managed by Alembic and applied at container startup
  (`alembic upgrade head` in `docker/entrypoint.sh`). Locally:
  `cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.
- **Schema changes:** edit the model, then
  `uv run alembic revision --autogenerate -m "describe change"`,
  **review the generated file** (autogenerate cannot see renames — it emits a
  drop plus an add, which destroys data), then `uv run alembic upgrade head`.
- **Tests** use a testcontainers Postgres. You need a running Docker daemon,
  but no manual database: `cd backend && uv run pytest -v`.
- **Dependencies** live only in `backend/pyproject.toml`; `backend/uv.lock` is
  generated. Add with `uv add <pkg>` — never hand-edit the lock, and there is
  no `requirements.txt`.
- **Uploads** are written to `settings.AUDIO_DIR` / `UPLOAD_DIR` / `COVER_DIR` /
  `VIDEO_DIR`, all anchored to `backend/`. Never use a relative path for file I/O.
- **Media is served by nginx** — `docker compose up -d --build` brings up the
  stack (nginx:80 is the only published port; API at `/api/*`). Protected media
  streams go through nginx's internal X-Accel mechanism — never expose `/media/`
  publicly. Note: the backend image is baked — rebuild (`docker compose build
  backend`) after code changes, only `./uploads` is bind-mounted.
- **Troubleshooting:** if API calls return 502 after a `backend` container
  restart, `docker compose restart nginx` — nginx caches the upstream's IP at
  startup and must be re-resolved.
