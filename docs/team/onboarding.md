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
the reference implementation that does it right.

## 3. The six rules for people who did not write them

For each rule in `AGENTS.md` ("System Design — Binding Invariants"): one
plain sentence, one compliant example (auth module), and where a live
violation exists today, point at it (the media routers — being fixed by the
media refactor). Emphasis: "in flight — read those files, do not imitate
them."

## 4. How a change actually gets made (the recipe)

1. Get a task from a mentor.
2. Write the failing test first (for bugfixes and service logic — see the
   scoped TDD rules in `ONBOARDING.md` §4). Running it fails for the RIGHT
   reason — if it fails on a typo, that is not the red you wanted.
3. Write the minimum code to make it green; run the suite.
4. Cleanup: the DoD commands in `ONBOARDING.md` §6.
5. Commit with the repo style; push; open the PR; watch the three checks —
   they enforce steps 2–4 continuously, which is why step 2 is not optional.

## 5. Tests: what "characterization pin" means

A pin is a test that asserts whatever the code DOES today, even its bugs,
written BEFORE refactoring it. Bugs are pinned deliberately and flipped
later, on purpose. Writing pins is the standard first task for a reason: it
teaches the harness, the TDD convention, and the domain with zero production
risk.

## 6. Reading order (curated)

`ONBOARDING.md` → this file → `AGENTS.md` → auth module (read all five files
top to bottom) → your first assigned task. Stop when any term is unclear and
ask — the correct ratio of asking to guessing is 90/10 for the first week.
