# Backend rules — FastAPI + PostgreSQL

Applies to everything under `backend/`. Cross-cutting rules: the root `AGENTS.md`.

<!-- .github/workflows/ai-review.yml extracts the section below by heading text:
     sed -n '/^## System Design/,/^## Repository Structure/p' backend/AGENTS.md
     Keep this heading and "## Repository Structure" byte-identical. -->
## System Design — Binding Invariants

Breaking one requires explicit approval, and you must say which one you are breaking and why.

| # | Invariant |
|---|---|
| 1 | **Layering:** router → service → repository → model. Routers never open a session or query directly. Repositories never raise `HTTPException`. Business rules live in services. |
| 2 | **Error mapping:** services raise domain exceptions; **only routers** translate them. `ValueError`→400, `PermissionError`→403, not-found→404, `IntegrityError`→400. The same rule returns the same status on every endpoint. |
| 3 | **No CWD-relative file I/O.** Every filesystem path derives from `app/config.py` settings anchored to `BASE_DIR`. Never a bare relative string. |
| 4 | **SQLAlchemy 2.0** (`Mapped[]`, `mapped_column`, `select()`) everywhere. |
| 5 | **Tests run on PostgreSQL** via testcontainers — never SQLite (JSONB/GIN are not expressible there). Never delete a failing test to go green. Write characterization tests before refactoring untested code. TDD per the `test-driven-development` skill (superpowers): characterization first on legacy code, red-green-refactor for new behavior and bugfixes. |
| 6 | **Naming:** `PascalCase` classes with no underscores (ruff `N801`); `snake_case` for functions and modules. The full convention is the Naming table under Repository Structure. |
| 7 | **Frozen API contract:** response shapes may gain fields, never lose or rename them. Removing or renaming anything pinned below needs explicit approval and a frontend impact note in the same PR. |

**Pinned surface (invariant 7):**

- Schemas: `BookRead` (incl. `cover_url`), `VideoRead`, `AudioRead`, `TagRead`, `AuthorRead`, `LevelRead`, `GenreRead`, `TokenResponse`, `Page[T]`.
- Error body: `{"detail": str}`.
- Auth: Bearer JWT with a role claim. The `httpOnly` `access_token` cookie is accepted when a request carries no `Authorization` header (native media tags).
- URL prefixes: `/api/`, `/media/` (internal only), `/static/covers/` (public).
- Routes: `POST /api/auth/token` (login), `POST /api/auth/logout` (clears the cookie).

## Repository Structure

```
backend/app/
  api/           routers only — HTTP concerns, dependency injection, status mapping
  services/      business rules, orchestration, domain exceptions
  repositories/  persistence — one per aggregate, returns models, no HTTP types
  models/        SQLAlchemy models; every model re-exported from __init__.py
  schemas/       Pydantic; layered Base → Create → Read → Update
  dependencies/  FastAPI DI (get_current_user, RoleChecker)
  config.py      ALL paths and settings, anchored to BASE_DIR
  tests/         subfolders per area (auth/, media/…): test_<module>_<aspect>.py
```

Where things go:

- **New endpoint** → router + service + repository. All three, even if the service is thin.
- **New setting or path** → `config.py`. Never a literal in a router.
- **New model** → define it, then export it from `models/__init__.py`, or `Base.metadata` will not see it and Alembic will generate a `drop_table` for it.
- **Cross-module helper** → a service. Do not create a `utils` grab-bag.

### Naming

Invariant 6 is the enforceable core; this table is the full convention.

| Thing | Rule |
|---|---|
| Classes | `PascalCase`, no underscores (ruff `N801`) |
| Schemas | `<Entity>Base / Create / Read / Update`; request/response pairs `<Verb><Noun>Request / Response`; paged lists `Page[T]` |
| Route prefixes | plural noun: `/books`, `/videos`, `/tags`, `/authors`; exception `/audio` (mass noun) |
| Handlers | `list_<plural>`, `get_<singular>`, `upload_<singular>`, `update_<singular>`, `delete_<singular>`, `stream_<singular>` |
| Domain exceptions | `<Noun><State>` with no `Error` suffix (`BookNotFound`, `InvalidMediaFile`); base classes `<Area>Error` (`BookError`, `MediaError`). ruff `N818` is ignored for this reason. |
| Services / repos | `<Entity>Service`, `<Entity>Repo`; leaf helpers named for what they do (`ContentValidator`, `MediaFileStorage`) |
| Modules | `snake_case`; `<entity>_router.py`, `<entity>_schema.py`, `<entity>_repo.py`, `<entity>_service.py`, `<area>_errors.py` |
| Tests | `tests/<area>/test_<module>_<aspect>.py` (`test_book_stream.py`, `test_video_api.py`) |
| Settings | `UPPER_CASE` fields and properties on `Settings` (`N802` per-file-ignore on `config.py`) |

## Best Practices

Advisory, not binding — apply judgment. Each of these is a lesson already paid for in this codebase.

- **Validate first, mutate second.** All guards before any write, so a rejected request leaves nothing behind.
- **Tests are the contract.** Every behavior change ships with tests (CI enforces the suite). For bugfixes and service-layer logic, write the failing test first; for routers, config, and migrations, order is free.
- **Exceptions are for exceptional cases.** A failed login is a return value, not a raise. A function typed `-> bool` must be able to return `False`.
- **Know where the correctness boundary is.** The DB constraint is the guarantee; the application-level check is UX. Handle both, and do not mistake one for the other.
- **Keyword-only for boolean parameters.** `change_password(user, pw, *, first_login=True)`. A positional flag is unreadable at the call site and easy to misplace.
- **Make side effects explicit at the composition root.** Import model modules deliberately; never rely on a transitive import to register them.
- **Derived files are generated, never hand-edited.** `uv.lock` is generated. A parallel hand-maintained manifest will drift.
- **Prefer the specific operation.** `startswith()` over `like(f"{x}%")` — the general one makes user input load-bearing on wildcard characters.
- **Functions must be correct on their own terms.** Do not depend on a decorator in another file to make a branch unreachable.
- **Deleting dead code is a contribution.** Untested dead code invites future callers to trust it. Git is the archive.
- **Bare `@computed_field`, never stacked with `@property`.** `@computed_field @property` fails `mypy --strict`; the reverse order passes mypy but breaks at runtime (`PydanticDescriptorProxy is not callable`).

## Execution Boundaries

- ✅ **Always:** strict type hints on every new Python function.
- ✅ **Always:** Pydantic schemas at API boundaries — request and response bodies. Internal function arguments can be plain types; do not wrap everything in a model.

## Build & Test Commands (Definition of Done)

This section is the single owner of the backend DoD. `docs/onboarding.md`, `docs/CONTRIBUTING.md`, and `.opencode/agents/review.md` point here; `.github/workflows/ci.yml` (the `quality` job) is the executable mirror. Lint, format, type, and test configuration live in `backend/pyproject.toml` — never as CLI flags.

Nothing is "done" until these have actually run and you have seen the output. All commands run from `backend/`.

**Dev variant** — rewrites files; what you run while working:

```bash
cd backend
uv run ruff format .
uv run ruff check . --fix
uv run mypy <changed_files> --strict
uv run pytest
```

**Check variant** — read-only; what the `review` agent and CI run:

```bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy <changed_files> --strict
uv run pytest
```

Notes that make the difference between these working and not:

- **`uv run` is mandatory.** A bare `pytest` or `ruff` uses whatever is on PATH, not `backend/.venv`.
- **mypy on changed files only.** `mypy . --strict` across the repo surfaces debt unrelated to your change. Test modules run under a relaxed per-module override in `pyproject.toml`; app code is fully strict.
- **Tests need a running Docker daemon** — testcontainers starts its own `postgres:16-alpine`; you do **not** need `docker compose up -d db`. Verbosity is set by `addopts` in `pyproject.toml`; do not add `-v`/`-q` by hand.
- **CI runs the check variant on changed Python files only** (`ci.yml` "Resolve changed Python files"); the `review` agent runs it on `.`. Docs-only PRs additionally skip the test step in CI (`ci.yml` "Detect docs-only change") — the local DoD is unchanged and the `quality` check still reports.

## Dependencies

Missing dependency → check `backend/pyproject.toml`, then `uv add <pkg>` (asks for confirmation; updates `pyproject.toml` and `uv.lock` together). Never hand-edit either file. There is no `requirements.txt`; do not create one.
