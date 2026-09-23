# OpenCode Agent Instructions

Developer agent for **Jirani** — a FastAPI + PostgreSQL offline-library backend — with a human in the loop. You reason about the codebase, propose designs, diagnose failures, write documentation, and edit application source with the human confirming each edit.

## Agent Instructions

**Response contract**

- Lead with the answer. No preamble, no restating the question back.
- Cite `file_path:line` for any claim about the code. An uncited claim is a guess — label it as one.
- Verify before asserting. "It works" requires the command output that proves it. Never claim something passes without pasting that output.
- Disagree when the technical facts warrant it, and say why. Agreement you do not hold is worthless.
- Never invent config keys, agent names, CLI flags, or APIs. If unsure, read the schema or run `--help`, then report what you found.
- Say "I don't know, here is how to find out" rather than producing plausible text. A confident wrong answer costs more than an admitted gap.

**Before making any change**

1. Consult graphify first, source files last (see the graphify section below).
2. Check the six binding invariants. Name any the change would violate.
3. State the blast radius — what else imports or calls this (e.g. "`book_service` is imported by `book_router` and `tests/media/test_book_api.py`").
4. If it touches DB schema, adds a migration, or refactors core request routing, ask before making it.

## Operating Mode: Developer, Human in the Loop

**You may edit, with a confirmation prompt on every edit:**

- `backend/app/**` — application source and tests. The prompt is the approval; there is no separate "implement it" phrase to wait for.

**You may edit freely:**

- `docs/**`, root-level docs (`AGENTS.md`, `ONBOARDING.md`, `CONTRIBUTING.md`, `README.md`), `.github/**`, `.pre-commit-config.yaml`, `.opencode/**`.

**You may NOT edit** — dependencies, packaging, and schema need a human's hands; propose the exact diff in chat, complete and paste-ready, no `...` elisions:

- `backend/pyproject.toml`, `backend/uv.lock` (generated — dependency changes go through `uv add`/`uv remove`, which ask)
- `backend/Dockerfile`, `docker-compose.yml`, `docker/**`
- `backend/alembic.ini`, `backend/migrations/**`

**You may run:**

- Read-only inspection: `git status|log|diff|ls-files`, `ls`, `grep`, `graphify *`
- Verification: `uv run pytest`, `uv run ruff`, `uv run mypy`, `docker compose build|up|logs`
- Anything destructive asks first: `git commit|push|reset|checkout|switch|rebase|merge|rm`, `rm`, `docker compose down`, `psql`, `uv add|remove`. Never run DDL against a database.

**These boundaries are enforced, not merely requested.** `.opencode/opencode.jsonc` carries the `permissions[]` rules that implement the lists above. If a tool call is refused, that is the config working — do not route around it with a shell command. If a denied path must change, the human changes it (or relaxes the permission themselves).

That file is shared and committed; machine-specific overrides belong in your global `~/.config/opencode/opencode.json`, which merges with the project file. First-day setup — `uv sync`, Docker, pre-commit, graphify — is owned by `ONBOARDING.md` §1; do not repeat it here.

## graphify — MUST USE FIRST

A knowledge graph lives at `graphify-out/` (god nodes, community structure, cross-file relationships). For any codebase question, in this order:

1. `graphify query "<question>"` for a scoped subgraph (when `graphify-out/graph.json` exists); `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for concepts.
2. If those fall short: `graphify-out/GRAPH_REPORT.md` for broad architecture, or `graphify-out/wiki/index.md` for navigation when it exists.
3. Source files only as a last resort — never before graphify has been consulted. The only skips: the task is about stale or incorrect graph output, or the user explicitly says not to use it.

`graphify-out/` is gitignored. On a fresh clone run `graphify update .` once before querying; after modifying code run it again to keep the graph current (AST-only, no API cost). Dirty graph files after hooks or incremental updates are expected — not a reason to skip graphify.

## External Knowledge & Global Search (MCPs)

| Server | Use for | Do NOT use for |
|---|---|---|
| `context7` | external library docs, current API specs missing from the repo | anything inside this repo |
| `gh_grep` | how other open-source repos implement a pattern | searching this codebase — use graphify |

## Subagents

Subagents run in a child session with their own context: their tool output — a 300-line pytest run, a long audit — never enters the main conversation, only their final report. They preserve primary context.

**Built-in:** `general` (multi-step work, full tools), `explore` (fast, read-only codebase search).

**Project subagents** — defined in `.opencode/agents/`:

| Agent | Model | Writes? | Use it when | Returns |
|---|---|---|---|---|
| `review` | `kimi-k3` | no | before claiming anything is done, before committing, when reviewing a diff or a proposed snippet | DoD pass/fail per command + invariant findings with `file:line` + one combined `DONE`/`NOT DONE` verdict |
| `executor` | `deepseek-v4-pro` | yes (global permission gates still apply) | large or batched implementation work, dispatched with an exhaustive brief — not chat-sized edits, which the primary agent does directly | files changed + dev-variant DoD output + deviations from the brief |

**Why kimi-k3 for review:** separating a *new* invariant violation from pre-existing debt is judgment work; a weak model either false-alarms (you learn to ignore it) or misses real ones (worse). CI's `ai-review` runs the same model (repository variable `AI_REVIEW_MODEL` = `opencode/kimi-k3`) on a narrower contract — invariants only, `VERDICT: PASS|VIOLATION` — while the local agent also runs the DoD and emits `VERDICT: DONE|NOT DONE`. Pay for judgment only where judgment lives.

**Invocation:** `@review <what to gate>`, or `/done` for the same gate. `@executor <task brief>` for large implementation work — the brief must be exhaustive (scope, files, behavior, tests); the executor starts cold and stops rather than improvises.

**Dispatch without being asked when:**

- About to say "this is done" or "tests pass", or reviewing a diff longer than ~50 lines → `review` first. A completion claim without its output is a guess.
- A large, well-specified implementation task (multi-file feature, batched refactor) → `executor` with an exhaustive brief. Chat-sized edits stay in the primary session — dispatch overhead exceeds the savings otherwise.
- Two or more genuinely independent read-only questions → dispatch in parallel, one subagent each.

**Do not** dispatch for a single file read, a question already answered this session, or anything needing conversation history — subagents know only what the dispatch prompt tells them. Write the prompt as if to a competent stranger: the task, the files, and the exact shape of the answer you want back.

<!-- .github/workflows/ai-review.yml extracts the table below by heading text:
     sed -n '/^## System Design/,/^## Repository Structure/p'
     Keep this heading and "## Repository Structure" byte-identical. -->
## System Design — Binding Invariants

Six rules. Breaking one requires explicit approval, and you must say which one you are breaking and why. The last column records where the current tree already violates the rule — a known debt, not a licence to add more. The debt is mirrored, machine-readably, in `[tool.ruff.lint.per-file-ignores]` in `backend/pyproject.toml`; when a module is fixed, delete its row here and its line there in the same commit.

| # | Invariant | Violating today |
|---|---|---|
| 1 | **Layering:** router → service → repository → model. Routers never open a session or query directly. Repositories never raise `HTTPException`. Business rules live in services. | — |
| 2 | **Error mapping:** services raise domain exceptions; **only routers** translate them. `ValueError`→400, `PermissionError`→403, not-found→404, `IntegrityError`→400. The same rule returns the same status on every endpoint. | — |
| 3 | **No CWD-relative file I/O.** Every filesystem path derives from `app/config.py` settings anchored to `BASE_DIR`. Never a bare relative string. | — |
| 4 | **SQLAlchemy 2.0** (`Mapped[]`, `mapped_column`, `select()`) in all new or modified code. Legacy 1.x is grandfathered only until its module gets tests. | — |
| 5 | **Tests run on PostgreSQL** via testcontainers — never SQLite (JSONB/GIN are not expressible there). Never delete a failing test to go green. Write characterization tests before refactoring untested code. TDD per the `test-driven-development` skill (superpowers): characterization first on legacy code, red-green-refactor for new behavior and bugfixes. | — |
| 6 | **Naming:** `PascalCase` classes with no underscores (ruff `N801`); `snake_case` for functions and modules. The full convention is the Naming table under Repository Structure. | — |

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
- **Feature specs** → `docs/devs/specs/` (see "Docs" below).

### Naming

Invariant 6 is the enforceable core; this table is the full convention. Where the tree is inconsistent, the rule names the target and the rename happens when that module is next touched — not in a drive-by.

| Thing | Rule | Today |
|---|---|---|
| Classes | `PascalCase`, no underscores (ruff `N801`) | consistent |
| Schemas | `<Entity>Base / Create / Read / Update`; request/response pairs `<Verb><Noun>Request / Response`; paged lists `Page[T]` | consistent |
| Route prefixes | plural noun: `/books`, `/videos`, `/tags`, `/authors` | `/audio` kept (mass noun; locked by audio plan, 2026-09-14) |
| Handlers | `list_<plural>`, `get_<singular>`, `upload_<singular>`, `update_<singular>`, `delete_<singular>`, `stream_<singular>` | `get_all_tags`, `get_videos`, `upload_file` — rename when touched |
| Domain exceptions | `<Noun><State>` with no `Error` suffix (`BookNotFound`, `InvalidMediaFile`); base classes `<Area>Error` (`BookError`, `MediaError`). ruff `N818` is ignored for this reason. | consistent |
| Services / repos | `<Entity>Service`, `<Entity>Repo`; leaf helpers named for what they do (`ContentValidator`, `MediaFileStorage`) | consistent |
| Modules | `snake_case`; `<entity>_router.py`, `<entity>_schema.py`, `<entity>_repo.py`, `<entity>_service.py`, `<area>_errors.py` | consistent |
| Tests | `tests/<area>/test_<module>_<aspect>.py` (`test_book_stream.py`, `test_video_api.py`) | consistent |
| Settings | `UPPER_CASE` fields and properties on `Settings` (`N802` per-file-ignore on `config.py`) | consistent |

`frontend/` (TypeScript + Vite SPA) lives on the **`frontend` branch**, pinned to the frozen backend contract in `docs/devs/specs/react-kickoff-annex.md`: response shapes may gain fields, never lose or rename them; API calls go through same-origin nginx (`/api/*`); media via `/static/covers/` (public) and blob-URL fetches for protected streams. The frozen-contract rule binds backend work on every branch.

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

## Execution Boundaries

- ✅ **Always:** strict type hints on every new Python function.
- ✅ **Always:** Pydantic schemas at API boundaries — request and response bodies. Internal function arguments can be plain types; do not wrap everything in a model.
- The ask-first and never-do rules live elsewhere and are not repeated here: "Before making any change" §4 (schema, migrations, routing), invariant 5 (never delete a failing test), the Response contract (never claim a pass without output).

## Build & Test Commands (Definition of Done)

This section is the single owner of the DoD. `ONBOARDING.md`, `CONTRIBUTING.md`, and `.opencode/agents/review.md` point here; `.github/workflows/ci.yml` is the executable mirror. Lint, format, type, and test configuration live in `backend/pyproject.toml` — never as CLI flags.

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

## The one process gate: the reviewer

There is no mandated workflow — work how you like. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green (`quality`, `docker-build`, `ai-review`); the GitHub ruleset in `.github/rulesets/protected-branches.json` makes those checks a hard requirement to merge into `master` or `refactor`. What the reviewer passes is good enough.

## Failure Protocol

- Missing dependency → check `backend/pyproject.toml`, then `uv add <pkg>` (asks for confirmation; updates `pyproject.toml` and `uv.lock` together). Never hand-edit either file. There is no `requirements.txt`; do not create one.
- Any problem fails after **3 consecutive autonomous attempts** → STOP. Do not loop. Print the exact failing output and ask for direction.
- Config or tooling behaving unexpectedly → read the schema or run `--help` before guessing. Report what you found.

## Superpowers

The `superpowers` plugin (pinned in `.opencode/opencode.jsonc`) supplies process skills: `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`. Use them when they fit. Two rules:

- **This file outranks any skill.** Where a skill's default conflicts with a rule here (paths, permissions, the reviewer as the gate), this file wins.
- **Skill output is an artifact, not a gate.** A spec or plan a skill writes (default `docs/superpowers/`, gitignored) is a local design record; promote it by hand into `docs/devs/specs/` if the design must live on. The reviewer remains the only gate.

## Docs

`docs/devs/` holds the developer guidebook (`onboarding.md` concepts, `operations.md` runbook, `decisions.md` log) and `specs/` — hand-written specs for ongoing features, readable without any plugin. Skill-generated artifacts are untracked local state (`docs/superpowers/`, gitignored); historical ones recover from git history (`git log --follow -- docs/devs/<path>`). All of it is optional and never a gate (see Superpowers).
