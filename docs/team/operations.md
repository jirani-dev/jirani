# Operations — running Jirani

The runbook: containers, schema, media, deploy, and what to do when it
misbehaves. For the project overview and mission, read the `README.md`;
for the workflow rules, `AGENTS.md`.

## Run with Docker

```bash
docker compose up -d --build    # nginx on :80 (the only published HTTP port), API at /api/*, Postgres on :5432
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

If you're also running the frontend dev server (`cd frontend && npm run
dev`) against this mode, set `VITE_API_BASE=http://localhost:8000` (see
`frontend/.env.example`) — the frontend's default assumes the nginx-fronted
"Run with Docker" setup above. Protected media (book/audio/video streaming)
needs nginx's X-Accel-Redirect regardless, so it won't stream in this mode
either way; everything else works fine once the base URL is corrected.

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
