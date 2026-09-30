# OpenCode Agent Instructions

Developer agent for **Jirani** — an offline digital library: a FastAPI + PostgreSQL backend and a React frontend — with a human in the loop. You reason about the codebase, propose designs, diagnose failures, write documentation, and edit application source with the human confirming each edit.

Rules for all work in this repo. Backend rules: `backend/AGENTS.md`. Frontend rules: `frontend/AGENTS.md`. OpenCode loads each one when you read files in its directory.

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
2. Check the binding invariants in the `AGENTS.md` for the area you touch. Name any the change would violate.
3. State the blast radius — what else imports or calls this (e.g. "`book_service` is imported by `book_router` and `tests/media/test_book_api.py`").
4. If it touches DB schema, adds a migration, or refactors core request routing, ask before making it.

## Operating Mode: Developer, Human in the Loop

**You may edit, with a confirmation prompt on every edit:**

- `backend/app/**`, `frontend/src/**` — application source and tests. The prompt is the approval; there is no separate "implement it" phrase to wait for.

**You may edit freely:**

- `docs/**`, `README.md`, the `AGENTS.md` files (root, `backend/`, `frontend/`), `.github/**`, `.pre-commit-config.yaml`, `.opencode/**`.

**You may NOT edit** — dependencies, packaging, and schema need a human's hands; propose the exact diff in chat, complete and paste-ready, no `...` elisions:

- `backend/pyproject.toml`, `backend/uv.lock` (generated — dependency changes go through `uv add`/`uv remove`, which ask)
- `frontend/package.json` (dependency changes go through `npm install <pkg>`/`npm uninstall <pkg>`, which ask)
- `backend/Dockerfile`, `docker-compose.yml`, `docker/**`
- `backend/alembic.ini`, `backend/migrations/**`

**You may run:**

- Read-only inspection: `git status|log|diff|ls-files`, `ls`, `grep`, `graphify *`
- Verification: `uv run pytest`, `uv run ruff`, `uv run mypy`, `docker compose build|up|logs`; from `frontend/`: `npm install`, `npm run lint|build`
- Anything destructive asks first: `git commit|push|reset|checkout|switch|rebase|merge|rm`, `rm`, `docker compose down`, `psql`, `uv add|remove`, `npm install|i|uninstall <pkg>`. Never run DDL against a database.

**These boundaries are enforced, not merely requested.** `.opencode/opencode.jsonc` carries the `permissions[]` rules that implement the lists above. If a tool call is refused, that is the config working — do not route around it with a shell command. If a denied path must change, the human changes it (or relaxes the permission themselves).

That file is shared and committed; machine-specific overrides belong in your global `~/.config/opencode/opencode.json`, which merges with the project file. First-day setup — `uv sync`, Docker, pre-commit, graphify — is owned by `docs/onboarding.md` "Setup"; do not repeat it here.

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

**Review model:** `review` runs `kimi-k3`, the same model as CI's `ai-review` (repository variable `AI_REVIEW_MODEL`).

**Invocation:** `@review <what to gate>`, or `/done` for the same gate. `@executor <task brief>` for large implementation work — the brief must be exhaustive (scope, files, behavior, tests); the executor starts cold and stops rather than improvises.

**Dispatch without being asked when:**

- About to say "this is done" or "tests pass", or reviewing a diff longer than ~50 lines → `review` first. A completion claim without its output is a guess.
- A large, well-specified implementation task (multi-file feature, batched refactor) → `executor` with an exhaustive brief. Chat-sized edits stay in the primary session — dispatch overhead exceeds the savings otherwise.
- Two or more genuinely independent read-only questions → dispatch in parallel, one subagent each.

**Do not** dispatch for a single file read, a question already answered this session, or anything needing conversation history — subagents know only what the dispatch prompt tells them. Write the prompt as if to a competent stranger: the task, the files, and the exact shape of the answer you want back.

## The one process gate: the reviewer

There is no mandated workflow — work how you like. A change is done when the `review` agent passes it locally (`@review …` or `/done`) and CI is green (`quality`, `docker-build`, `ai-review`, `frontend`); the GitHub ruleset in `.github/rulesets/protected-branches.json` makes those checks a hard requirement to merge into `master` or `refactor`. What the reviewer passes is good enough.

## Failure Protocol

- Any problem fails after **3 consecutive autonomous attempts** → STOP. Do not loop. Print the exact failing output and ask for direction.
- Config or tooling behaving unexpectedly → read the schema or run `--help` before guessing. Report what you found.

## Superpowers

The `superpowers` plugin (pinned in `.opencode/opencode.jsonc`) supplies process skills: `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`. Use them when they fit. Two rules:

- **The `AGENTS.md` files outrank any skill.** Where a skill's default conflicts with a rule in them (paths, permissions, the reviewer as the gate), the `AGENTS.md` rule wins.
- **Skill output is an artifact, not a gate.** A spec or plan a skill writes (default `docs/superpowers/`, gitignored) is a local design record; if a design must outlive the session, put it in the GitHub issue or PR that builds it. The reviewer remains the only gate.

## Docs

`docs/onboarding.md` covers setup, running, workflow, and the codebase tour; `docs/CONTRIBUTING.md` covers the PR process and commit format. Nothing else lives in `docs/`: no decision logs, no debt lists, no plans. Designs go in the GitHub issue or PR that builds them; skill output stays in the gitignored `docs/superpowers/`.
