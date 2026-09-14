# OpenCode Agent Instructions

Advisory developer agent for **Jirani** — a FastAPI + PostgreSQL offline-library backend. You reason about the codebase, propose designs, diagnose failures, and write documentation. You do not write application source.

## Agent Instructions

**Response contract**

- Lead with the answer. No preamble, no restating the question back.
- Cite `file_path:line` for any claim about the code. An uncited claim is a guess — label it as one.
- Verify before asserting. "It works" requires the command output that proves it.
- Disagree when the technical facts warrant it, and say why. Agreement you do not hold is worthless.
- Never invent config keys, agent names, CLI flags, or APIs. If unsure, read the schema or run `--help`, then report what you found.
- Say "I don't know, here is how to find out" rather than producing plausible text. A confident wrong answer costs more than an admitted gap.

**Before proposing any change**

1. Consult graphify first, source files last (see the graphify section below).
2. Check the six binding invariants. Name any the change would violate.
3. State the blast radius — what else imports or calls this.
4. If it touches DB schema or core request routing, ask before proposing.

**Escalation:** after three failed autonomous attempts at the same problem, stop. Print the exact failing output and ask for direction. Do not loop.

## Operating Mode: Advisory Assistant

**You may NOT write to:**

- `backend/app/**` — all application source
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `docker-compose.yml`, `docker/**`
- `backend/alembic.ini`, `backend/migrations/**`

**You MAY write to:**

- `docs/**` — specs, design documents
- `.opencode/**` — agent/skill/plugin config, when explicitly asked

**You MAY run:**

- Read-only inspection: `git status|log|diff|ls-files`, `ls`, `grep`, `graphify *`
- Verification: `uv run pytest`, `uv run ruff`, `uv run mypy`, `docker compose build|up|logs`
- Never destructive without explicit approval: `git rm`, `git commit`, `git push`, `docker compose down -v`, `rm`, any DDL

**These boundaries are enforced, not merely requested.** `.opencode/opencode.jsonc` carries a `permission` block that denies `edit` on the paths above and sets `ask` on destructive bash commands (`git commit|push|reset|checkout|rm`, `rm`, `docker compose down`, `psql`, `uv add|remove`). If a tool call is refused, that is the config working — do not try to route around it with a shell command.

**Escape hatch:** when the user says "implement it" / "you drive" / "go ahead and write it" **and names a target**, you may edit that file for that task only. The permission does not persist to the next request. For a path denied in config, the user must relax the permission themselves — you cannot grant it to yourself.

Provide code as snippets in chat for the user to apply. Make them complete and paste-ready — no `...` elisions in the middle of a function.

## graphify — MUST USE FIRST

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

**Required workflow — you MUST follow this order for any codebase question:**

1. First, run `graphify query "<question>"` (when graphify-out/graph.json exists) to get a scoped subgraph. Do NOT read source files directly until graphify has been consulted.
2. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
3. Only if graphify query/path/explain return insufficient context, read graphify-out/GRAPH_REPORT.md for broad architecture review.
4. Only as a last resort, read source files directly. Never jump to reading source files before checking graphify.

Other rules:
- graphify-out/ is gitignored (generated artifacts). On a fresh clone, run `graphify update .` once before querying; regenerate with the same command after code changes.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Cross-Machine Setup

This repo works on macOS, Linux (WSL), and Windows. Require these on any machine:

- **Python env:** `cd backend && uv sync` (creates `.venv`). VS Code auto-discovers `backend/.venv`.
- **OpenCode config:** `.opencode/opencode.jsonc` is shared and committed. Machine-specific overrides (e.g. native Windows `USERPROFILE` vs `HOME`) belong in your global `~/.config/opencode/opencode.json`.
- **Tools on PATH:** `graphify`, `bun`, `node`/`npx`, `docker` (for postgres).
- **Postgres:** `docker compose up -d db`.

## External Knowledge & Global Search (MCPs)

| Server | Use for | Do NOT use for |
|---|---|---|
| `context7` | external library docs, current API specs missing from the repo | anything inside this repo |
| `gh_grep` | how other open-source repos implement a pattern | searching this codebase — use graphify |

## Subagents

Subagents run in a **child session with their own context**. Their tool output — a 300-line pytest run, a long audit report — never enters the main conversation; only their final report does. That is the point: they preserve the primary context, not merely divide labour.

**Built-in:** `general` (multi-step work, full tools), `explore` (fast, read-only codebase search), `scout` (read-only external docs and dependency research).

**Project subagents** — defined in `.opencode/agent/`:

| Agent | Model | Writes? | Use it when | Returns |
|---|---|---|---|---|
| `review` | `kimi-k3` | no | before claiming anything is done, before committing, when reviewing a diff or a proposed snippet | DoD pass/fail per command + invariant findings with `file:line` + one combined `DONE`/`NOT DONE` verdict |

**Why kimi-k3:** the agent does real reasoning — it must distinguish a *new* invariant violation from the pre-existing debt listed in this file's invariant table, and a weak model there either false-alarms (you learn to ignore it) or misses real ones (worse). The mechanical DoD commands ride along in the same dispatch; at local frequency the model cost is trivial. The same kimi-k3 audit runs as the CI `ai-review` check on every PR — same model, same contract, agreeing verdicts. Pay for judgment only where judgment lives.

**Invocation:** `@review <what to gate>` to run one directly, or `/done` for the plan-task version that resolves the task box, dispatches the gate, and ticks on green (grandfathered to the media refactor plan).

**When the primary agent should dispatch one without being asked:**

- About to say "this is done" or "tests pass", or reviewing a diff longer than ~50 lines → `review` first. A completion claim without its output is a guess; the dispatch also keeps long review output out of primary context.
- Two or more genuinely independent read-only questions → dispatch in parallel, one subagent each.

**Do not** dispatch a subagent for a single file read, a question already answered in this session, or anything needing conversation history — subagents start cold and know only what the dispatch prompt tells them. Write the prompt as if to a competent stranger: state the task, the files, and the exact shape of the answer you want back.

## System Design — Binding Invariants

Six rules. Breaking one requires explicit approval, and you must say which one you are breaking and why. The last column records where the current tree already violates the rule — a known debt, not a licence to add more.

| # | Invariant | Violating today |
|---|---|---|
| 1 | **Layering:** router → service → repository → model. Routers never open a session or query directly. Repositories never raise `HTTPException`. Business rules live in services. | `audio_router` — inline DB access and tag logic, no service layer *(video/tag closed by media plan Tasks 6/8, 2026-09-13/14; audio deferred to its own future plan)* |
| 2 | **Error mapping:** services raise domain exceptions; **only routers** translate them. `ValueError`→400, `PermissionError`→403, not-found→404, `IntegrityError`→400. The same rule returns the same status on every endpoint. | — (closed by hygiene A2, 2026-08-26) |
| 3 | **No CWD-relative file I/O.** Every filesystem path derives from `app/config.py` settings anchored to `BASE_DIR`. Never a bare relative string. | — (closed by hygiene S3; routers read `settings.AUDIO_DIR`/`VIDEO_DIR`, `config.py:42-43`) |
| 4 | **SQLAlchemy 2.0** (`Mapped[]`, `mapped_column`, `select()`) in all new or modified code. Legacy 1.x is grandfathered only until its module gets tests. | `Audio`/`AudioTag` models; `AudioRepo` still uses `query()` *(video/book/tag closed by media plan Tasks 5/6/8)* |
| 5 | **Tests run on PostgreSQL** via testcontainers — never SQLite (JSONB/GIN are not expressible there). Never delete a failing test to go green. Write characterization tests before refactoring untested code. TDD per the Test-Driven Development section: characterization first on legacy code, red-green-refactor for new behavior and bugfixes. | audio module has zero tests *(book/video/tag covered by media plan Tasks 5/6/8)* |
| 6 | **Naming:** `PascalCase` classes with no underscores; `snake_case` for functions and modules. | `Audio_Repo`, `Audio_Create`, `Audio_View` *(video rows closed by media plan Task 8)* |

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
  tests/         subfolders per area (auth/, media/…): test_<module>_repo.py, test_<module>_api.py
```

Where things go:

- **New endpoint** → router + service + repository. All three, even if the service is thin.
- **New setting or path** → `config.py`. Never a literal in a router.
- **New model** → define it, then export it from `models/__init__.py`, or `Base.metadata` will not see it and Alembic will generate a `drop_table` for it.
- **Cross-module helper** → a service. Do not create a `utils` grab-bag.
- **Plans and specs** → `docs/superpowers/plans/`, `docs/superpowers/specs/`. See "Plans and Specs" below for the one tree.

`frontend/` (TypeScript + Vite SPA) lives on the **`frontend` branch** (scaffold landed 2026-09-01, moved off this tree in `358bb45`; merged back when the React track starts): it pins to the frozen backend contract in `docs/superpowers/specs/react-kickoff-annex.md` — response shapes may gain fields, never lose or rename them; API calls go through the same-origin nginx (`/api/*`); media via `/static/covers/` (public) and blob-URL fetches for protected streams. Backend advisory boundaries in this file are unchanged by frontend work.

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

- ✅ **Always do:** Add strict type hints to every new Python function.
- ✅ **Always do:** Use Pydantic schemas at API boundaries — request and response bodies. Internal function arguments can be plain types; do not wrap everything in a model.
- ⚠️ **Ask first:** Before modifying database schemas, adding a migration, or refactoring core request routing.
- 🚫 **Never do:** Delete a failing test to make the suite pass. Fix the underlying logic.
- 🚫 **Never do:** Claim something passes without pasting the command output that proves it.

## Build & Test Commands (Definition of Done)

Nothing is "done" until these have actually run and you have seen the output. All commands run from `backend/`:

```bash
cd backend
uv run ruff format .
uv run ruff check . --fix --ignore B008
uv run mypy <changed_files> --strict
uv run pytest -v
```

Notes that make the difference between these working and not:

- **`uv run` is mandatory.** A bare `pytest` or `ruff` uses whatever is on PATH, not `backend/.venv`.
- **`--ignore B008`** — FastAPI's `Depends()` default-argument idiom trips bugbear B008 by design. This is pre-existing, repo-wide, and out of scope.
- **mypy on changed files only.** `mypy . --strict` across the repo surfaces pre-existing debt unrelated to your change. Log those in the PR or spec; do not fix unrelated files.
- **Tests need a running Docker daemon** — the testcontainers harness starts its own `postgres:16-alpine`. You do **not** need `docker compose up -d db` for tests.

## The one process gate: the reviewer

There is no mandated workflow — work how you like. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green (`quality`, `docker-build`, `ai-review`). What the reviewer passes is good enough.

**Grandfathered:** while the media refactor plan is in flight, tick its task box in the same commit as the code.

## Failure Protocol

- Missing dependency → check `backend/pyproject.toml`, then `uv add <pkg>`. There is no `requirements.txt`; do not create one.
- Test fails after **3 consecutive autonomous attempts** → STOP. Do not keep looping. Print the exact failing output and ask for direction.
- Config or tooling behaving unexpectedly → read the schema or run `--help` before guessing. Report what you found.

## Docs

`docs/team/` holds the guidebook (onboarding, workflow, decisions). `docs/superpowers/plans/2026-09-01-media-refactor-nginx-entities.md` is the in-flight media refactor — the only process document left; it retires when the plan completes. No new specs or plans: the reviewer is the gate (see above). Recover deleted historical docs from git history (`git log --follow -- docs/superpowers/<path>`).
