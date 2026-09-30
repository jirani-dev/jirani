# Onboarding

Jirani is an offline digital library for schools: books, audio, and video served over a school's local network from one modest machine, with no cloud in the path. The backend is FastAPI + PostgreSQL behind nginx; the frontend is a React SPA in `frontend/`. The mission and goals are in `README.md`.

This is the one guide: setup, running, the workflow, and a tour of the code. The rules live in the `AGENTS.md` files, and they win wherever this guide and they differ.

## Setup

Tools: Python via `uv`, Docker (daemon), `node` and `npm`, `graphify`, `opencode`, `gh`.

```bash
cd backend && uv sync                              # creates backend/.venv (VS Code auto-discovers it)
cd ..
docker compose up -d db                            # development Postgres
uv tool install pre-commit && pre-commit install   # installs the pre-commit AND commit-msg hooks
graphify update .                                  # builds graphify-out/ (gitignored — every clone generates its own)
cd frontend && npm install                         # frontend dependencies
```

Install opencode with `npm i -g opencode-ai` (or see opencode.ai) and launch it in the repo root — it picks up `.opencode/opencode.jsonc` automatically.

Why `uv tool install` and not `uvx`: the hook script pre-commit writes records the path of the Python that installed it. Under `uvx` that is an ephemeral cache environment, and a `uv cache clean` leaves you with a dead hook.

Works on macOS, Linux (WSL), and Windows. Tests need a running Docker daemon — testcontainers starts its own Postgres, so you never create a database by hand. Machine-specific opencode overrides go in `~/.config/opencode/opencode.json`, never in the shared project file.

## Run with Docker

```bash
docker compose up -d --build    # nginx on :80 (the only published HTTP port), API at /api/*, Postgres on :5432
docker compose down             # stop
docker compose down -v          # stop and remove the database volume
```

The backend image is **baked** — only `./uploads` is bind-mounted. After code changes: `docker compose build backend && docker compose up -d backend`.

## Run locally (without the backend container)

```bash
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```

To run the frontend dev server (`cd frontend && npm run dev`) against this mode, set `VITE_API_BASE=http://localhost:8000` (see `frontend/.env.example`) — the default assumes the nginx-fronted "Run with Docker" setup. Protected media (book, audio, and video streaming) needs nginx's X-Accel-Redirect, so it won't stream in this mode either way; everything else works once the base URL is set.

## Where the rules are

| File | Covers |
|---|---|
| `AGENTS.md` | All work: how the agent works with you, permissions, the review gate |
| `backend/AGENTS.md` | Backend invariants (layering, error mapping, paths, SQLAlchemy 2.0, tests on PostgreSQL, naming, the frozen API contract), structure, and the backend Definition of Done |
| `frontend/AGENTS.md` | Frontend invariants F1–F6, backend integration, naming, and the frontend Definition of Done |

OpenCode loads the backend or frontend file as soon as it reads code in that folder. Some rules are enforced by tooling rather than prose: ruff `N801` checks class names, the commit format is a commit-msg hook, and merging into `master` requires green checks and one approval.

Query the knowledge graph before reading code. `graphify-out/` is generated, not shipped: `graphify update .` in Setup creates it, and you re-run it after code changes (local AST only, no API cost).

```bash
graphify query "how does book upload validation work"    # scoped subgraph first
graphify path "book_router" "BookFileStorage"            # relationships
graphify explain "X-Accel"                               # focused concepts
```

What's in `.opencode/`:

| Path | What it is |
|---|---|
| `opencode.jsonc` | Shared config: the superpowers plugin (pinned), MCP servers, and the permission rules — edits to `backend/app/**` and `frontend/src/**` ask first; dependencies, packaging, schema, and destructive git commands are denied or ask |
| `agents/review.md` | The review gate — runs the Definitions of Done and audits the diff against the invariants, one combined verdict |
| `agents/executor.md` | Implements one exhaustive task brief end to end and reports back |
| `commands/done.md` | `/done` — runs the review gate on demand |
| `skills/` | Vendored skills: `grill-me`, `grilling`, `grill-with-docs`, `domain-modeling` (provenance in `skills/PROVENANCE.md`) |

## How work flows

There is no mandated workflow. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green.

1. **Start** — `git pull --ff-only` on `master`, branch off it, and run the Definition of Done for the area you will touch, so you know the tree was green when you started.
2. **Build** — however you like, with the agent or without. The agent edits application source with your confirmation on every edit.
3. **Gate** — `@review <what you changed>`; fix what it blocks; re-run.
4. **Commit** — the commit-msg hook enforces the format in `docs/CONTRIBUTING.md`.
5. **PR** — the required checks run (`quality`, `docker-build`, `ai-review`, `frontend`); one human approval merges. `docs/CONTRIBUTING.md` explains each check.

### Example — one full cycle

```bash
# 1. make your change (any editor, any order)
#    say you add an "overdue" flag to books

# 2. gate it locally — the reviewer runs the DoD + audits the invariants
@review the overdue flag change in backend/app/models/book.py

# 3. read the report; fix what it blocks, e.g.:
#    "1. Layering VIOLATION — book_router.py:41 computes the overdue bool;
#     move the rule into BookService."
#    re-run @review after fixing

# 4. commit — the hook rejects anything off-format
git commit -m "feat(book): overdue flag"          # good — type, scope, what changed
git commit -m "update stuff"                      # rejected by commit-msg-type

# 5. push, open the PR, watch the checks, request a human review
```

## Codebase tour

What each technology does:

- **FastAPI** — receives HTTP requests and sends responses. In this repo: `backend/app/api/` (the routers).
- **PostgreSQL** — stores the data permanently. Its advanced features (JSONB, GIN indexes) are modeled in `backend/app/models/`.
- **SQLAlchemy** — translates between Python objects and the database, so business code never writes SQL strings by hand.
- **Pydantic** — enforces exact request and response shapes at the app's edges; definitions live in `backend/app/schemas/`.
- **Alembic** — the versioned history of the database structure, stored in `backend/migrations/`.
- **nginx + Docker** — the deployment shell; see `docker-compose.yml` and `nginx/`. nginx receives every request, serves media itself, and proxies `/api/*` to FastAPI.
- **React + Vite + Tailwind** — the SPA in `frontend/src/`; it talks to the backend only through `src/services/api/`.

One request, end to end — `POST /api/auth/token` (login):

router (`api/auth_router.py`: HTTP questions only — status codes, forms) → service (`services/auth_service.py`: business rules, no HTTP, raises domain errors) → repository (`repositories/auth_repo.py`: the only place that talks to the database; returns objects, never raises `HTTPException`) → model (`models/account.py`: what a saved row is).

This four-layer split is backend invariant 1, and the auth module is the reference implementation. Read its files top to bottom before your first task.

A *characterization pin* is a test that asserts whatever the code does today, even its bugs, written before refactoring it. Bugs are pinned deliberately and flipped later, on purpose. Writing pins is the standard first task: it teaches the test harness and the domain with zero production risk.

## Schema changes

Alembic manages the schema, and it is applied at container startup (`alembic upgrade head` in `docker/entrypoint.sh`). Migrations are human-only — the agent may not edit `backend/migrations/**`. To change the schema: edit the model, then `uv run alembic revision --autogenerate -m "describe change"`, **review the generated file** (autogenerate cannot see renames — it emits a drop plus an add, which destroys data), then `uv run alembic upgrade head`.

## Media and deploy

nginx serves media. Protected streams use nginx's internal X-Accel mechanism — never expose `/media/` publicly. Uploads are written to `settings.AUDIO_DIR` / `UPLOAD_DIR` / `COVER_DIR` / `VIDEO_DIR`, all anchored to `backend/`.

Deploy is manual, after merge: `docker compose up -d --build` on the machine. The pipeline deliberately does not deploy for you.

## Troubleshooting

- API returns 502 after a `backend` container restart → `docker compose restart nginx` (nginx caches the upstream IP at startup).
- nginx serves 404 for a file the backend can see → `docker compose up -d --force-recreate nginx` (a restart does not re-resolve a bind-mounted directory whose inode changed).

## Your first week

Read this file → `AGENTS.md` → `backend/AGENTS.md` or `frontend/AGENTS.md` → the auth module → your first assigned task. Stop when any term is unclear and ask — the right ratio of asking to guessing is 90/10 for the first week. Something failing that you don't understand? Ask in the PR — a documented question beats a silent guess.
