# Backend Onboarding — Jirani, for people new to backend development

Read this first, then `AGENTS.md`. This file teaches concepts; `AGENTS.md` is
the rulebook and always wins where they differ. If a command in a file you
read disagrees with `AGENTS.md` or `CONTRIBUTING.md`, trust those and report
the drift.

## 1. What each technology does, in one honest paragraph

- **FastAPI** — the web framework that receives HTTP requests and sends
  responses. In this repo: `backend/app/api/` (the "routers").
- **PostgreSQL** — the database that stores the data permanently. Its
  advanced features (JSONB, GIN indexes) are modeled in `backend/app/models/`.
- **SQLAlchemy** — the translator between Python objects and the database,
  so business code never writes SQL strings by hand.
- **Pydantic** — the validator enforcing exact request/response shapes at
  the app's edges; definitions live in `backend/app/schemas/`.
- **Alembic** — the versioned history of the database structure itself,
  stored in `backend/migrations/`. Schema changes are reviewed, ordered, and
  repeated through migrations — never by editing a database by hand.
- **nginx + Docker** — deployment shells; see `docker-compose.yml` and
  `nginx/`.

## 2. One request traced end to end

Follow `POST /auth/token` (in `auth_router.py`):
router (HTTP questions only: status codes, forms) → service
(`auth_service.py`: business rules, no HTTP, raises domain errors) →
repository (`auth_repo.py`: the only place that speaks to databases, returns
objects, never raises HTTPException) → model (`backend/app/models/account.py`:
what a saved row IS).

This four-layer rule is binding — it is Invariant 1, and the auth module is
the reference implementation that does it right. Concrete contrast:
`auth_router.py:25-26` builds an `AuthService` and never touches the database;
`audio_router.py:40` opens `db.query(...)` directly, which is the shape
being fixed. Read both; imitate the first.

## 3. The six rules for people who did not write them

Each rule from `AGENTS.md` ("System Design — Binding Invariants") in one plain
sentence, with the module that does it right and — where one still exists —
the live violation. Every violation left today is in the **audio** module,
which is waiting for its own refactor plan: read those files, do not imitate
them.

1. **Layering** — a router talks to a service, a service to a repository, a
   repository to the database; nobody skips a layer. Right:
   `auth_router.py:25-26` asks `AuthService(AuthRepo(db))` and never queries.
   Wrong today: `audio_router.py:40` runs `db.query(Audio)` itself.
2. **Error mapping** — services raise plain Python exceptions
   (`ValueError`, `PermissionError`); only the router turns them into HTTP
   statuses, and the same exception always gets the same status. Right:
   `auth_service.py:81` raises `ValueError("Username … already taken")`;
   `auth_router.py:63-66` maps `ValueError`→404 for lookups and
   `PermissionError`→403. No live violation.
3. **No relative paths** — every file path starts from `BASE_DIR` in
   `config.py:7`, so the app works the same wherever it is launched from.
   Right: `config.py:40-42` (`UPLOAD_DIR`, `COVER_DIR`, `AUDIO_DIR`). No live
   violation.
4. **SQLAlchemy 2.0 style** — models declare columns as
   `Mapped[...] = mapped_column(...)` and queries use `select()`. Right:
   `account.py:29-30`, `auth_repo.py:14`. Wrong today: `audio.py:11` uses
   `Column(...)`, `audio_repo.py:21` uses `.query(...)`.
5. **Tests on PostgreSQL** — the suite starts a real `postgres:16-alpine`
   container (`backend/conftest.py:6,14`); never SQLite, never delete a
   failing test. Wrong today: the audio module has no tests at all.
6. **Naming** — classes are `PascalCase` with no underscores, functions and
   modules `snake_case`; ruff's `N801` now checks the class rule. Right:
   `auth_repo.py:8` `class AuthRepo`. Wrong today: `audio_repo.py:9`
   `class Audio_Repo` (listed in `per-file-ignores` until the audio plan).

## 4. How a change actually gets made (the recipe)

1. Get a task from a mentor.
2. Change the code however you like — with the agent (it edits
   `backend/app/**`, you confirm each edit) or without. Tests come with it
   (CI runs the full suite). For bugfixes and service-layer logic, write the
   failing test first: run it, watch it fail for the RIGHT reason (a typo
   failing is not the red you wanted), then fix.
3. Cleanup: the Definition of Done in `AGENTS.md` § Build & Test Commands.
4. Commit in the format `CONTRIBUTING.md` describes (a hook checks it); push;
   open the PR; watch the three checks — `quality`, `docker-build`,
   `ai-review`. What they pass is good enough.

## 5. Tests: what "characterization pin" means

A pin is a test that asserts whatever the code DOES today, even its bugs,
written BEFORE refactoring it. Bugs are pinned deliberately and flipped
later, on purpose. Writing pins is the standard first task for a reason: it
teaches the test harness and the domain with zero production risk.

## 6. Reading order (curated)

`ONBOARDING.md` → this file → `AGENTS.md` → auth module (read all five files
top to bottom) → your first assigned task. Stop when any term is unclear and
ask — the correct ratio of asking to guessing is 90/10 for the first week.
