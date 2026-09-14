# Jirani — Onboarding for the AI-Assisted Workflow

This repo is developed with **opencode** as a core team member. This guide
teaches you the setup and the rules of working alongside it. For backend
concepts themselves, read `docs/team/onboarding.md` next. `AGENTS.md` is the
binding ruleset — this file is the guided tour, it never overrides it.

## 1. One-time setup (this section owns setup — nothing else repeats it)

Tools: Python via `uv`, Docker (daemon), `node`, `graphify`, `opencode`, `gh`.

```bash
cd backend && uv sync                              # creates backend/.venv (VS Code auto-discovers it)
cd ..
docker compose up -d db                            # development Postgres
uv tool install pre-commit && pre-commit install   # installs the pre-commit AND commit-msg hooks
graphify update .                                  # builds graphify-out/ (gitignored — every clone generates its own)
```

Install opencode: `npm i -g opencode-ai` (or see opencode.ai). Launch it in
the repo root — it picks up `.opencode/opencode.jsonc` automatically.

Why `uv tool install` and not `uvx`: the hook script pre-commit writes records
the path of the Python that installed it. Under `uvx` that is an ephemeral
cache environment, and a `uv cache clean` leaves you with a dead hook.

Cross-machine notes: works on macOS, Linux (WSL), and Windows. Tests need a
running Docker daemon (testcontainers starts its own Postgres — you never
create a database by hand). Machine-specific opencode overrides go in
`~/.config/opencode/opencode.json`, never in the shared project file.

## 2. What's in `.opencode/`

| Path | What it is |
|---|---|
| `opencode.jsonc` | Shared config: plugins (graphify, superpowers — pinned), MCP servers, and the **permission block**. The agent edits `backend/app/**` with a confirmation prompt on every edit; dependencies, packaging, schema, and destructive git operations are denied or ask |
| `agent/review.md` | The one review gate — runs the DoD check commands (from `AGENTS.md`) AND audits the diff against the six invariants, one combined verdict. Used by `/done` and before claiming anything works |
| `commands/done.md` | `/done` — dispatches the review gate on demand |
| `plugins/graphify.js` | Prints a one-time reminder to query the knowledge graph before grepping raw files |

## 3. Graphify — query the map before reading code

`graphify-out/` is **generated, not shipped**: it is gitignored, so `graphify
update .` in §1 is what creates it, and you re-run that after code changes
(local AST only, no API cost). The rule is binding in `AGENTS.md`:

```bash
graphify query "how does book upload validation work"    # scoped subgraph first
graphify path "book_router" "BookFileStorage"            # relationships
graphify explain "X-Accel"                               # focused concepts
```

Read source files last, not first.

## 4. The rules you cannot break

`AGENTS.md` carries the six binding invariants (layering, error mapping,
no CWD-relative paths, SQLAlchemy 2.0 style, tests on PostgreSQL, naming) and
the Definition of Done. Some of them are enforced by tooling now, not prose:
ruff's `N801` is Invariant 6; the known debt is listed both in the AGENTS.md
table and in `[tool.ruff.lint.per-file-ignores]`; the commit format is a
commit-msg hook; merging into `master`/`refactor` requires green checks and
one approval (`.github/rulesets/protected-branches.json`).

There is **no mandated workflow** — work how you like. A change is done when
the `review` agent passes it locally (`@review …` or `/done`) and CI is green.

## 5. How work flows

1. **Start** — `git pull --ff-only` on `refactor` (the base until the media
   plan's Part G lands; `master` after), branch off it, run the DoD once
   before changing anything so you know the tree was green when you started.
2. **Build** — however you like, with the agent or without. New model?
   Export it from `models/__init__.py` or Alembic will generate a
   `drop_table` for it. The agent may edit `backend/app/**`; you confirm each
   edit in the TUI.
3. **Gate** — `@review <what you changed>`; fix what it blocks; re-run.
4. **Commit** — the commit-msg hook enforces the format in
   `CONTRIBUTING.md`.
5. **PR** — three checks run (`quality`, `docker-build`, `ai-review`); the
   ruleset makes them required. One human approval merges.

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

# 5. push, open the PR, watch the three checks, request a human review
```

## 6. Definition of Done

Owned by `AGENTS.md` § Build & Test Commands (dev variant while you work,
check variant is what the reviewer and CI run). Run it from `backend/`,
always with `uv run`. Something failing that you don't understand? Ask in
the PR — a documented question beats a silent guess.
