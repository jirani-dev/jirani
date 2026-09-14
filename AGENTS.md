# OpenCode Agent Instructions

Developer agent for **Jirani** — a FastAPI + PostgreSQL offline-library backend — with a human in the loop. You reason about the codebase, propose designs, diagnose failures, write documentation, and edit application source with the human confirming each edit.

## Agent Instructions

**Response contract**

- Lead with the answer. No preamble, no restating the question back.
- Cite `file_path:line` for any claim about the code. An uncited claim is a guess — label it as one.
- Verify before asserting. "It works" requires the command output that proves it.
- Disagree when the technical facts warrant it, and say why. Agreement you do not hold is worthless.
- Never invent config keys, agent names, CLI flags, or APIs. If unsure, read the schema or run `--help`, then report what you found.
- Say "I don't know, here is how to find out" rather than producing plausible text. A confident wrong answer costs more than an admitted gap.

**Before making any change**

1. Consult graphify first, source files last (see the graphify section below).
2. Check the six binding invariants. Name any the change would violate.
3. State the blast radius — what else imports or calls this (e.g. "`book_service` is imported by `book_router` and `tests/media/test_book_api.py`").
4. If it touches DB schema or core request routing, ask before making it.

**Escalation:** after three failed autonomous attempts at the same problem, stop. Print the exact failing output and ask for direction. Do not loop.

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

**These boundaries are enforced, not merely requested.** `.opencode/opencode.jsonc` carries the `permission` block that implements the lists above. If a tool call is refused, that is the config working — do not route around it with a shell command. If a denied path must change, the human changes it (or relaxes the permission themselves).

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
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Cross-Machine Setup

`.opencode/opencode.jsonc` is shared and committed. Machine-specific overrides (e.g. native Windows `USERPROFILE` vs `HOME`) belong in your global `~/.config/opencode/opencode.json`, which merges with the project file. First-day setup — `uv sync`, Docker, pre-commit, graphify — is owned by `ONBOARDING.md` §1; do not repeat it here.

## External Knowledge & Global Search (MCPs)

| Server | Use for | Do NOT use for |
|---|---|---|
| `context7` | external library docs, current API specs missing from the repo | anything inside this repo |
| `gh_grep` | how other open-source repos implement a pattern | searching this codebase — use graphify |

## Subagents

Subagents run in a **child session with their own context**. Their tool output — a 300-line pytest run, a long audit report — never enters the main conversation; only their final report does. That is the point: they preserve the primary context, not merely divide labour.

**Built-in:** `general` (multi-step work, full tools), `explore` (fast, read-only codebase search).

**Project subagents** — defined in `.opencode/agent/`:

| Agent | Model | Writes? | Use it when | Returns |
|---|---|---|---|---|
| `review` | `kimi-k3` | no | before claiming anything is done, before committing, when reviewing a diff or a proposed snippet | DoD pass/fail per command + invariant findings with `file:line` + one combined `DONE`/`NOT DONE` verdict |

**Why kimi-k3:** the agent does real reasoning — it must distinguish a *new* invariant violation from the pre-existing debt listed in this file's invariant table, and a weak model there either false-alarms (you learn to ignore it) or misses real ones (worse). The mechanical DoD commands ride along in the same dispatch; at local frequency the model cost is trivial. The CI `ai-review` check runs the same model (repository variable `AI_REVIEW_MODEL` = `opencode/kimi-k3`) against the same invariant table on every PR, but a narrower contract: CI audits invariants only and emits `VERDICT: PASS|VIOLATION`; the local agent audits invariants **and** runs the DoD and emits `VERDICT: DONE|NOT DONE`. Pay for judgment only where judgment lives.

**Invocation:** `@review <what to gate>` to run one directly, or `/done` to dispatch the same gate.

**When the primary agent should dispatch one without being asked:**

- About to say "this is done" or "tests pass", or reviewing a diff longer than ~50 lines → `review` first. A completion claim without its output is a guess; the dispatch also keeps long review output out of primary context.
- Two or more genuinely independent read-only questions → dispatch in parallel, one subagent each.

**Do not** dispatch a subagent for a single file read, a question already answered in this session, or anything needing conversation history — subagents start cold and know only what the dispatch prompt tells them. Write the prompt as if to a competent stranger: state the task, the files, and the exact shape of the answer you want back.

<!-- .github/workflows/ai-review.yml extracts the table below by heading text:
     sed -n '/^## System Design/,/^## Repository Structure/p'
     Keep this heading and "## Repository Structure" byte-identical. -->
## System Design — Binding Invariants

Six rules. Breaking one requires explicit approval, and you must say which one you are breaking and why. The last column records where the current tree already violates the rule — a known debt, not a licence to add more. The debt is mirrored (plus recorded lint debt), machine-readably, in `[tool.ruff.lint.per-file-ignores]` in `backend/pyproject.toml`; when a module is fixed, delete its row here and its line there in the same commit.

| # | Invariant | Violating today |
|---|---|---|
| 1 | **Layering:** router → service → repository → model. Routers never open a session or query directly. Repositories never raise `HTTPException`. Business rules live in services. | `audio_router` — inline DB access and tag logic, no service layer *(video/tag closed by media plan Tasks 6/8, 2026-09-13/14; audio deferred to its own future plan)* |
| 2 | **Error mapping:** services raise domain exceptions; **only routers** translate them. `ValueError`→400, `PermissionError`→403, not-found→404, `IntegrityError`→400. The same rule returns the same status on every endpoint. | — (closed by hygiene A2, 2026-08-26) |
| 3 | **No CWD-relative file I/O.** Every filesystem path derives from `app/config.py` settings anchored to `BASE_DIR`. Never a bare relative string. | — (closed by hygiene S3; routers read `settings.AUDIO_DIR`/`VIDEO_DIR`, `config.py:42-43`) |
| 4 | **SQLAlchemy 2.0** (`Mapped[]`, `mapped_column`, `select()`) in all new or modified code. Legacy 1.x is grandfathered only until its module gets tests. | `Audio`/`AudioTag` models; `AudioRepo` still uses `query()` *(video/book/tag closed by media plan Tasks 5/6/8)* |
| 5 | **Tests run on PostgreSQL** via testcontainers — never SQLite (JSONB/GIN are not expressible there). Never delete a failing test to go green. Write characterization tests before refactoring untested code. TDD per the `test-driven-development` skill (superpowers): characterization first on legacy code, red-green-refactor for new behavior and bugfixes. | audio module has zero tests *(book/video/tag covered by media plan Tasks 5/6/8)* |
| 6 | **Naming:** `PascalCase` classes with no underscores (ruff `N801`); `snake_case` for functions and modules. The full convention is the Naming table under Repository Structure. | `Audio_Repo`, `Audio_Create`, `Audio_View` *(video rows closed by media plan Task 8)* |

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
- **Design docs** → `docs/superpowers/specs/`, `docs/superpowers/plans/`. See "Docs" below.

### Naming

Invariant 6 is the enforceable core; this table is the full convention. Where the tree is inconsistent, the rule names the target and the rename happens when that module is next touched — not in a drive-by.

| Thing | Rule | Today |
|---|---|---|
| Classes | `PascalCase`, no underscores (ruff `N801`) | audio classes in `per-file-ignores` |
| Schemas | `<Entity>Base / Create / Read / Update`; request/response pairs `<Verb><Noun>Request / Response`; paged lists `Page[T]` | consistent outside audio |
| Route prefixes | plural noun: `/books`, `/videos`, `/tags`, `/authors` | `/audio` — audio plan |
| Handlers | `list_<plural>`, `get_<singular>`, `upload_<singular>`, `update_<singular>`, `delete_<singular>`, `stream_<singular>` | `get_all_tags`, `get_videos`, `upload_file` — rename when touched |
| Domain exceptions | `<Noun><State>` with no `Error` suffix (`BookNotFound`, `InvalidMediaFile`); base classes `<Area>Error` (`BookError`, `MediaError`). ruff `N818` is ignored for this reason. | consistent |
| Services / repos | `<Entity>Service`, `<Entity>Repo`; leaf helpers named for what they do (`ContentValidator`, `MediaFileStorage`) | consistent |
| Modules | `snake_case`; `<entity>_router.py`, `<entity>_schema.py`, `<entity>_repo.py`, `<entity>_service.py`, `<area>_errors.py` | consistent |
| Tests | `tests/<area>/test_<module>_<aspect>.py` (`test_book_stream.py`, `test_video_api.py`) | consistent |
| Settings | `UPPER_CASE` fields and properties on `Settings` (`N802` per-file-ignore on `config.py`) | consistent |

`frontend/` (TypeScript + Vite SPA) lives on the **`frontend` branch** (scaffold landed 2026-09-01, moved off this tree in `358bb45`; merged back when the React track starts): it pins to the frozen backend contract in `docs/superpowers/specs/react-kickoff-annex.md` — response shapes may gain fields, never lose or rename them; API calls go through the same-origin nginx (`/api/*`); media via `/static/covers/` (public) and blob-URL fetches for protected streams. Backend boundaries in this file are unchanged by frontend work.

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

This section is the single owner of the DoD. `ONBOARDING.md`, `CONTRIBUTING.md`, and `.opencode/agent/review.md` point here; `.github/workflows/ci.yml` is the executable mirror. Lint, format, type, and test configuration live in `backend/pyproject.toml` — never as CLI flags.

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
- **mypy on changed files only.** `mypy . --strict` across the repo surfaces pre-existing debt unrelated to your change (audio module). Test modules run under a relaxed per-module override in `pyproject.toml`; app code is fully strict.
- **Tests need a running Docker daemon** — the testcontainers harness starts its own `postgres:16-alpine`. You do **not** need `docker compose up -d db` for tests. Verbosity is set by `addopts` in `pyproject.toml`; do not add `-v`/`-q` by hand.
- **CI runs the check variant on changed Python files only** (`ci.yml` "Resolve changed Python files"); the `review` agent runs it on `.`.

## The one process gate: the reviewer

There is no mandated workflow — work how you like. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green (`quality`, `docker-build`, `ai-review`), and the GitHub ruleset in `.github/rulesets/protected-branches.json` makes those checks a hard requirement to merge into `master` or `refactor`. What the reviewer passes is good enough.

## Failure Protocol

- Missing dependency → check `backend/pyproject.toml`, then `uv add <pkg>` (asks for confirmation; it updates `pyproject.toml` and `uv.lock` together). Never hand-edit either file. There is no `requirements.txt`; do not create one.
- Test fails after **3 consecutive autonomous attempts** → STOP. Do not keep looping. Print the exact failing output and ask for direction.
- Config or tooling behaving unexpectedly → read the schema or run `--help` before guessing. Report what you found.

## Superpowers

The `superpowers` plugin is pinned in `.opencode/opencode.jsonc` and supplies process skills: `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`. Use them when they fit. Two rules:

- **This file outranks any skill.** Where a skill's default conflicts with a rule here (paths, permissions, the reviewer as the gate), this file wins.
- **Skill output is an artifact, not a gate.** A skill may write a spec or plan under `docs/superpowers/`; that document is a design record. It does not become a required step for anyone, and the reviewer remains the only gate.

## Docs

`docs/team/` holds the guidebook (onboarding concepts, decisions log). `docs/superpowers/specs/` and `docs/superpowers/plans/` hold design artifacts — optional, never gates (see Superpowers). Recover deleted historical docs from git history (`git log --follow -- docs/superpowers/<path>`).
