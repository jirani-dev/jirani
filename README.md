# Jirani Offline Library Backend

FastAPI + PostgreSQL behind nginx. New here? `ONBOARDING.md` is the guided
tour, `CONTRIBUTING.md` has the PR rules, `AGENTS.md` is the rulebook.

## Run with Docker

```bash
docker compose up -d --build    # nginx on :80 (the only published port), API at /api/*, Postgres on :5432
docker compose down             # stop
docker compose down -v          # stop and remove the database volume
```

The backend image is **baked** — only `./uploads` is bind-mounted. After code
changes: `docker compose build backend && docker compose up -d backend`.

## Run locally (without the backend container)

```bash
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```

## Schema

Managed by Alembic and applied at container startup (`alembic upgrade head`
in `docker/entrypoint.sh`). To change it: edit the model, then
`uv run alembic revision --autogenerate -m "describe change"`, **review the
generated file** (autogenerate cannot see renames — it emits a drop plus an
add, which destroys data), then `uv run alembic upgrade head`.

## Media

Served by nginx. Protected streams use nginx's internal X-Accel mechanism —
never expose `/media/` publicly. Uploads are written to `settings.AUDIO_DIR` /
`UPLOAD_DIR` / `COVER_DIR` / `VIDEO_DIR`, all anchored to `backend/`.

## Deploy

Manual, after merge: `docker compose up -d --build` on the machine. The
pipeline deliberately does not deploy for you.

## Troubleshooting

- API returns 502 after a `backend` container restart → `docker compose
  restart nginx` (nginx caches the upstream IP at startup).
- nginx serves 404 for a file the backend can see → `docker compose up -d
  --force-recreate nginx` (a restart does not re-resolve a bind-mounted
  directory whose inode changed).

Tests, dependencies, and the Definition of Done: `AGENTS.md` § Build & Test
Commands. Setup: `ONBOARDING.md` §1.
