# OpenCode Agent Instructions

Developer agent for **Jirani** — a FastAPI + PostgreSQL offline-library backend with a TypeScript + Vite SPA frontend — with a human in the loop. You reason about both trees, propose designs, diagnose failures, write documentation, and edit application source with the human confirming each edit.

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
2. Check the six backend binding invariants **and** the six frontend binding invariants (below). Name any the change would violate.
3. State the blast radius — what else imports or calls this (e.g. "`book_service` is imported by `book_router` and `tests/media/test_book_api.py`"; for the frontend, "`services/api/books.ts` is imported by `pages/Library.tsx` and `hooks/useBookSearch.ts`").
4. If it touches DB schema, core request routing, or the frozen backend contract (`docs/devs/specs/react-kickoff-annex.md`), ask before making it.

**Escalation:** after three failed autonomous attempts at the same problem, stop. Print the exact failing output and ask for direction. Do not loop.

## Operating Mode: Developer, Human in the Loop

**You may edit, with a confirmation prompt on every edit:**

- `backend/app/**` — backend application source and tests. The prompt is the approval; there is no separate "implement it" phrase to wait for.
- `frontend/src/**` — frontend application source. Same rule.

**You may edit freely:**

- `docs/**`, root-level docs (`AGENTS.md`, `ONBOARDING.md`, `CONTRIBUTING.md`, `README.md`), `.github/**`, `.pre-commit-config.yaml`, `.opencode/**`.
- `frontend/*.config.*` (`eslint.config.js`, `tailwind.config.js`, `vite.config.js`, `tsconfig*.json`, `postcss.config.js`), `frontend/public/**`, `frontend/index.html` — frontend config and static assets.

**You may NOT edit** — dependencies, packaging, and schema need a human's hands; propose the exact diff in chat, complete and paste-ready, no `...` elisions:

- `backend/pyproject.toml`, `backend/uv.lock` (generated — dependency changes go through `uv add`/`uv remove`, which ask)
- `backend/Dockerfile`, `docker-compose.yml`, `docker/**`
- `backend/alembic.ini`, `backend/migrations/**`
- `frontend/package.json`, `frontend/package-lock.json` (generated since 2026-09-15 — dependency changes go through `npm install`; same human-in-the-loop principle as `uv.lock`)

**You may run:**

- Read-only inspection: `git status|log|diff|ls-files`, `ls`, `grep`, `graphify *`
- Verification: `uv run pytest`, `uv run ruff`, `uv run mypy`, `npm run lint`, `npx tsc --noEmit`, `npx eslint . --fix`, `npx vitest run` (when vitest is installed), `docker compose build|up|logs`
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

`.opencode/opencode.jsonc` is shared and committed. Machine-specific overrides (e.g. native Windows `USERPROFILE` vs `HOME`) belong in your global `~/.config/opencode/opencode.json`, which merges with the project file. First-day setup — `uv sync`, Docker, pre-commit, `npm ci` in `frontend/`, graphify — is owned by `ONBOARDING.md` §1; do not repeat it here.

## External Knowledge & Global Search (MCPs)

| Server | Use for | Do NOT use for |
|---|---|---|
| `context7` | external library docs (FastAPI/SQLAlchemy backend; React+Vite+vitest+ts frontend) and current API specs missing from the repo | anything inside this repo |
| `gh_grep` | how other open-source repos implement a pattern | searching this codebase — use graphify |
| `playwright` | driving the browser end-to-end: navigation, clicks, forms, network mocking, accessibility-tree snapshots (no vision model) | debugging a failure; use `chrome-devtools` |
| `chrome-devtools` | debugging the browser: console with source-mapped stacks, network inspection, Lighthouse audits, performance traces, heap snapshots | driving interactive flows; use `playwright` |

**Browser MCP division of labor (per Microsoft's and Google's own docs).** Playwright drives, Chrome DevTools debugs. Both are first-party (`@playwright/mcp` from Microsoft, `chrome-devtools-mcp` from ChromeDevTools org). Cost in context is ~32k tokens combined — affordable, and the agent picks per task. **Playwright Test Agents** (`npx playwright init-agents --loop=opencode`) scaffold a planner/generator/healer triplet for new e2e tests; use those instead of hand-rolling.

## Subagents

Subagents run in a **child session with their own context**. Their tool output — a 300-line pytest run, a long audit report, a clone of `anthropics/skills` — never enters the main conversation; only their final report does. That is the point: they preserve the primary context, not merely divide labour.

**Built-in:** `general` (multi-step work, full tools), `explore` (fast, read-only codebase search).

**Project subagents** — defined in `.opencode/agent/`:

| Agent | Model | Writes? | Use it when | Returns |
|---|---|---|---|---|
| `review` | `kimi-k3` | no | before claiming anything is done, before committing, when reviewing a diff or a proposed snippet | DoD pass/fail per command + invariant findings with `file:line` + one combined `DONE`/`NOT DONE` verdict |

**Why kimi-k3:** the agent does real reasoning — it must distinguish a *new* invariant violation from the pre-existing debt listed in this file's invariant tables, and a weak model there either false-alarms (you learn to ignore it) or misses real ones (worse). The mechanical DoD commands ride along in the same dispatch. The CI `ai-review` check runs the same model (repository variable `AI_REVIEW_MODEL` = `opencode/kimi-k3`) against the same invariant tables on every PR, but a narrower contract: CI audits invariants only and emits `VERDICT: PASS|VIOLATION`; the local agent audits invariants **and** runs the DoD and emits `VERDICT: DONE|NOT DONE`. Pay for judgment only where judgment lives.

**The local `review` agent covers both trees.** When the diff touches both `backend/` and `frontend/`, it audits the diff against **both** invariant tables and emits one combined verdict. CI uses two `sed` extractions (one per table) in the same prompt (see `ai-review.yml`).

**Invocation:** `@review <what to gate>` to run one directly, or `/done` to dispatch the same gate.

**When the primary agent should dispatch one without being asked:**

- About to say "this is done" or "tests pass", or reviewing a diff longer than ~50 lines → `review` first. A completion claim without its output is a guess; the dispatch also keeps long review output out of primary context.
- Two or more genuinely independent read-only or write-non-overlapping tasks → dispatch in parallel, one subagent each.

**Do not** dispatch a subagent for a single file read, a question already answered in this session, or anything needing conversation history — subagents start cold and know only what the dispatch prompt tells them. Write the prompt as if to a competent stranger: state the task, the files, and the exact shape of the answer you want back.

<!-- .github/workflows/ai-review.yml extracts the table below by heading text:
     sed -n '/^## System Design/,/^## Repository Structure/p'
     Keep this heading and "## Repository Structure" byte-identical. -->
## System Design — Binding Invariants

Six rules. Breaking one requires explicit approval, and you must say which one you are breaking and why. The last column records where the current tree already violates the rule — a known debt, not a licence to add more. The debt is mirrored (plus recorded lint debt), machine-readably, in `[tool.ruff.lint.per-file-ignores]` in `backend/pyproject.toml`; when a module is fixed, delete its row here and its line there in the same commit.

| # | Invariant | Violating today |
|---|---|---|
| 1 | **Layering:** router → service → repository → model. Routers never open a session or query directly. Repositories never raise `HTTPException`. Business rules live in services. | — (video/tag closed by media plan Tasks 6/8, 2026-09-13/14; audio closed by audio plan Tasks 2–3, 2026-09-14) |
| 2 | **Error mapping:** services raise domain exceptions; **only routers** translate them. `ValueError`→400, `PermissionError`→403, not-found→404, `IntegrityError`→400. The same rule returns the same status on every endpoint. | — (closed by hygiene A2, 2026-08-26) |
| 3 | **No CWD-relative file I/O.** Every filesystem path derives from `app/config.py` settings anchored to `BASE_DIR`. Never a bare relative string. | — (closed by hygiene S3; routers read `settings.AUDIO_DIR`/`VIDEO_DIR`, `config.py:42-43`) |
| 4 | **SQLAlchemy 2.0** (`Mapped[]`, `mapped_column`, `select()`) in all new or modified code. Legacy 1.x is grandfathered only until its module gets tests. | — (video/book/tag closed by media plan Tasks 5/6/8; audio closed by audio plan Task 3, 2026-09-14) |
| 5 | **Tests run on PostgreSQL** via testcontainers — never SQLite (JSONB/GIN are not expressible there). Never delete a failing test to go green. Write characterization tests before refactoring untested code. TDD per the `test-driven-development` skill (superpowers): characterization first on legacy code, red-green-refactor for new behavior and bugfixes. | — (book/video/tag covered by media plan Tasks 5/6/8; audio covered by audio plan Tasks 1/3, 2026-09-14) |
| 6 | **Naming:** `PascalCase` classes with no underscores (ruff `N801`); `snake_case` for functions and modules. The full convention is the Naming table under Repository Structure. | — (video rows closed by media plan Task 8; audio rows closed by audio plan Task 3, 2026-09-14) |

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

```
frontend/
  src/
    components/  React components, grouped by domain area
                  (audio/, books/, video/, auth/, shared/, organisms/)
    pages/       one file per screen; default export is the route component
    hooks/       custom React hooks (`use<Thing>` camelCase filenames)
    services/    api/<resource>.ts leaves the boundary; utils/formatters.js sorts units
    context/     React context providers (one Provider + Context per file)
    utils/       leaf utilities (legacy .js grandfathered)
    assets/      images, svgs imported by components
    config.ts    frontend constants; mirrors backend/app/config.py
    types.ts     shared frontend types (mirror of backend/schemas where useful)
    App.tsx      route shell
    main.jsx     entry; legacy .jsx, convert on touch
  public/        static files served by Vite at root
  eslint.config.js, tailwind.config.js, vite.config.js, postcss.config.js
  tsconfig*.json TS strict (app.json), node refs (node.json)
  package.json   deps; never hand-edit; use `npm install`. Lockfile is committed since 2026-09-15.
```

Where things go:

- **New endpoint** → router + service + repository. All three, even if the service is thin.
- **New setting or path** → `backend/app/config.py` or `frontend/src/config.ts`. Never a literal in a router or service.
- **New model** → define it, then export it from `models/__init__.py`, or `Base.metadata` will not see it and Alembic will generate a `drop_table` for it.
- **New page** → `frontend/src/pages/<PascalCase>.tsx` + the components it composes + the `services/api/*` call it issues.
- **Cross-module helper** → a service. Do not create a `utils` grab-bag.
- **Feature specs** → `docs/devs/specs/`, hand-written and tracked — for ongoing features, readable without any plugin. See "Docs" below.

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
| **Component folder (frontend)** | **Default home**: domain folder first (`components/<domain>/...`). `components/common/` only when 2+ domains use the same component. | consistent |
| **`common/` is promotion-only** | a component enters `components/common/` only after a second feature adopts it | consistent |
| **Pinned-token exemption** | data tables, headers, and other large composites belong in `components/common/` once they earn the bar; do NOT introduce a new upper tier (atoms/molecules/organisms/etc.) without explicit human approval. | consistent |
| **React components** | `PascalCase` filename matching the default export; `.tsx` for new code; React functional components | consistent |
| **Hooks** | `use<Thing>` camelCase filename; `.ts`; default-exports the hook function | consistent |
| **Pages** | `PascalCase`; default-export the route component; `.tsx` | consistent |
| **Frontend services** | `<resource>.ts` under `services/api/`; default-export `api<Resource>` (a thin fetch wrapper) | consistent |
| **Frontend contexts** | `PascalCase`; one Provider + Context per file under `context/`; `.tsx` | consistent |
| **Legacy `.jsx`/`.js`** | grandfathered in `utils/` and `main.jsx`; convert to `.tsx`/`.ts` on next touch | `utils/formatters.js`, `main.jsx` |
| **Frontend tests** *(when vitest lands)* | `*.test.ts(x)` colocated with units; e2e under `e2e/` | not yet installed (decision 2026-09-15) |

The frontend pins to the frozen backend contract in `docs/devs/specs/react-kickoff-annex.md`: response shapes may gain fields, never lose or rename them; API calls go through same-origin nginx (`/api/*`); media via `/static/covers/` (public) and blob-URL fetches for protected streams; error envelope `{detail: str}`; auth is Bearer JWT with role claim. The frontend is NOT a land for backend renaming — the contract freezes on the backend side.

## Frontend System Design — Binding Invariants

Six rules. Breaking one requires explicit approval, and you must say which one you are breaking and why. The last column records where the current tree already violates the rule — a known debt, not a licence to add more. The `ai-review` workflow extracts this section with `sed -n '/^## Frontend System Design/,/^## Best Practices/p'` (see `ai-review.yml`); the `review` agent reads it locally.

| # | Invariant | "Violating today" / Notes |
|---|---|---|
| F1 | **TypeScript strict, no `any`** in new code. `tsconfig.app.json` is strict; `npx tsc --noEmit` is the gate. Legacy `.jsx`/`.js` files in `utils/` and `main.jsx` are grandfathered — convert on next touch (see Naming table). | — (legacy JSX grandfathered; tracked in Naming table) |
| F2 | **Same-origin API.** UI calls the backend through `import.meta.env.VITE_API_BASE` (`/api/*`) only — `services/api/*` is the only place that knows the base URL. Never embed backend host or port in a page or component. | — |
| F3 | **Frozen backend contract.** Response shapes from `docs/devs/specs/react-kickoff-annex.md` (`BookRead` incl. `cover_url`, `VideoRead`, `TagRead`, `AuthorRead`/`LevelRead`/`GenreRead`, `Page[T]`). Error body shape `{detail: str}`. Auth: Bearer JWT with role claim. URL prefixes: `/api/`, `/media/` (internal-only), `/static/covers/` (public). May gain fields, never lose or rename them. | — |
| F4 | **Media access rule.** `<img src="/static/covers/...">` works natively (public). For protected streams (`/api/books/{uid}/stream`, `/api/videos/stream/{id}`) — fetch with the auth wrapper into a blob URL (`URL.createObjectURL`), buffering the whole file client-side. Native `<video>`/`<embed>` tags cannot carry the `Authorization` header; do not use them for protected streams. A short-lived signed ticket (`?ticket=`) is a deliberate later backend feature, not silently invented. | — (ticket-style shorts deferred; blob-URL fetch is the standing pattern until the backend feature lands) |
| F5 | **Vitest is the test runner for the frontend.** When tests land, `npx vitest run` enters the Frontend DoD; `*.test.ts(x)` colocated with units; e2e under `e2e/`. Until vitest is installed (no `test` script in `package.json`), the DoD is lint + tsc; the `review` agent reports `vitest: NOT RUN` rather than inventing a script. Bugs are fixed, not pinned. | — (vitest not yet installed; install deferred per 2026-09-15 handoff) |
| F6 | **Frontend naming:** see the "Frontend rows" of the Naming table under Repository Structure. Same grandfather-on-touch rule as backend invariant 6. | — |

## Best Practices

Advisory, not binding — apply judgment. Each of these is a lesson already paid for in this codebase.

- **Validate first, mutate second.** All guards before any write, so a rejected request leaves nothing behind.
- **Tests are the contract.** Every behavior change ships with tests (CI enforces the suite). For bugfixes and service-layer logic, write the failing test first; for routers, config, and migrations, order is free. On the frontend side: vitest has not been installed yet; when it lands, the rule applies to changes to `frontend/src/**` minus the legacy `.jsx`/`.js` grandfathered files.
- **Exceptions are for exceptional cases.** A failed login is a return value, not a raise. A function typed `-> bool` must be able to return `False`. (Frontend mirror: a failed fetch is a returned error, not a thrown exception, in `services/api/*` — domain callers decide.)
- **Know where the correctness boundary is.** The DB constraint is the guarantee; the application-level check is UX. Handle both, and do not mistake one for the other. (Frontend mirror: the backend's response schema is the contract; the frontend's type and a runtime `zod`-style check are both UX, never silent.)
- **Keyword-only for boolean parameters.** `change_password(user, pw, *, first_login=True)`. A positional flag is unreadable at the call site and easy to misplace.
- **Make side effects explicit at the composition root.** Import model modules deliberately; never rely on a transitive import to register them. (Frontend mirror: import services at the page or component that uses them; barrel `index.ts` re-exports are an antipattern for this tree.)
- **Derived files are generated, never hand-edited.** `uv.lock` and `frontend/package-lock.json` are generated. A parallel hand-maintained manifest will drift.
- **Prefer the specific operation.** `startswith()` over `like(f"{x}%")` — the general one makes user input load-bearing on wildcard characters.
- **Functions must be correct on their own terms.** Do not depend on a decorator in another file to make a branch unreachable.
- **Deleting dead code is a contribution.** Untested dead code invites future callers to trust it. Git is the archive.

## Execution Boundaries

- ✅ **Always do:** Add strict type hints to every new Python function; add strict TypeScript types (no `any`) to every new TS file.
- ✅ **Always do:** Use Pydantic schemas at API boundaries — request and response bodies. Internal function arguments can be plain types; do not wrap everything in a model. (Frontend mirror: validate at the boundary in `services/api/*`; internal page/component props can be plain types.)
- ⚠️ **Ask first:** Before modifying database schemas, adding a migration, refactoring core request routing, or **changing the frozen backend contract surface** (renaming a response field, changing an error envelope, dropping a URL prefix).
- 🚫 **Never do:** Delete a failing test to make the suite pass. Fix the underlying logic.
- 🚫 **Never do:** Claim something passes without pasting the command output that proves it.

## Build & Test Commands (Definition of Done)

This section is the single owner of the DoD. `ONBOARDING.md`, `CONTRIBUTING.md`, and `.opencode/agent/review.md` point here; `.github/workflows/ci.yml` is the executable mirror. Backend lint/format/type/test lives in `backend/pyproject.toml`; frontend lint lives in `frontend/eslint.config.js`, type in `frontend/tsconfig.app.json` — never as CLI flags.

Nothing is "done" until these have actually run and you have seen the output. All commands run from the relevant directory.

**Dev variant** — rewrites files; what you run while working:

```bash
# Backend
cd backend
uv run ruff format .
uv run ruff check . --fix
uv run mypy <changed_files> --strict
uv run pytest

# Frontend
cd frontend
npx eslint . --fix
npx tsc --noEmit
# vitest run lands here when vitest is installed; nothing to run yet
```

**Check variant** — read-only; what the `review` agent and CI run:

```bash
# Backend
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy <changed_files> --strict
uv run pytest

# Frontend
cd frontend
npm run lint   # wraps eslint .
npx tsc --noEmit
# vitest run lands here when vitest is installed
```

Notes that make the difference between these working and not:

- **`uv run` is mandatory.** A bare `pytest` or `ruff` uses whatever is on PATH, not `backend/.venv`.
- **`npm ci` in CI.** The frontend lockfile (`frontend/package-lock.json`) is committed since 2026-09-15; CI uses `npm ci` for reproducibility. Local dev may use `npm install` to refresh after editing `package.json`.
- **mypy on changed files only.** `mypy . --strict` across the repo can surface debt in files unrelated to your change. Test modules run under a relaxed per-module override in `pyproject.toml`; app code is fully strict.
- **tsc on the changed TS files when practical.** The local gate scopes `tsc --noEmit` where feasible; the `review` agent reports whole-tree results.
- **Tests need a running Docker daemon** — the backend testcontainers harness starts its own `postgres:16-alpine`. You do **not** need `docker compose up -d db` for backend tests.
- **CI runs the check variant on changed files** — backend ruff/mypy on changed Python files (`ci.yml` "Resolve changed Python files"); frontend lint and tsc on changed files under `frontend/`. Docs-only PRs (markdown and `docs/**` only) additionally skip the test step in CI (`ci.yml` "Detect docs-only change") — the local DoD is unchanged and the `quality` check still reports.
- **Frontend vitest deferral.** Until vitest is installed (decision 2026-09-15), the `quality` job's frontend step is lint + tsc; the `review` agent's Frontend DoD reports `vitest: NOT RUN` and the whole check is green if lint + tsc are green. Re-eval when the first test lands.

## The one process gate: the reviewer

There is no mandated workflow — work how you like. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green (`quality`, `docker-build`, `ai-review`). The GitHub rulesets in `.github/rulesets/` (one for `master`/`refactor`, one for `frontend`) make those checks a hard requirement to merge. What the reviewer passes is good enough.

## Failure Protocol

- Missing backend dependency → check `backend/pyproject.toml`, then `uv add <pkg>` (asks for confirmation; it updates `pyproject.toml` and `uv.lock` together). Never hand-edit either file. There is no `requirements.txt`; do not create one.
- Missing frontend dependency → ask for `npm install <pkg>` (the human runs it; it updates `package.json` and `package-lock.json` together). Never hand-edit either file.
- Test fails after **3 consecutive autonomous attempts** → STOP. Do not keep looping. Print the exact failing output and ask for direction.
- Config or tooling behaving unexpectedly → read the schema or run `--help` before guessing. Report what you found.

## Superpowers

The `superpowers` plugin is pinned in `.opencode/opencode.jsonc` and supplies process skills: `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`. Use them when they fit. Two rules:

- **This file outranks any skill.** Where a skill's default conflicts with a rule here (paths, permissions, the reviewer as the gate), this file wins.
- **Skill output is an artifact, not a gate.** A skill may write a spec or plan (its default is `docs/superpowers/`, gitignored — this file's paths win where they differ); that document is a local design record, untracked by git. If a design must live on, promote it by hand into `docs/devs/specs/`. It does not become a required step for anyone, and the reviewer remains the only gate.

## Docs

`docs/devs/` holds the developer guidebook (`onboarding.md` concepts, `operations.md` runbook, `decisions.md` log) and `specs/` — hand-written specs for ongoing features, readable without the superpowers plugin. Skill-generated artifacts are untracked local state (`docs/superpowers/`, gitignored); historical ones recover from git history (`git log --follow -- docs/devs/<path>`). All of it is optional and never a gate (see Superpowers).
