# Jirani — Onboarding for the AI-Assisted Workflow

This repo is developed with **opencode** as a core team member. This guide
teaches you the setup and the rules of working alongside it. For backend
concepts themselves, read `docs/team/onboarding.md` next. `AGENTS.md` is the
binding ruleset — this file is the guided tour, it never overrides it.

## 1. One-time setup

```bash
# tools needed: python via uv, docker (daemon), node, graphify, opencode
cd backend && uv sync        # creates backend/.venv (VS Code auto-discovers it)
docker compose up -d db      # development Postgres
uvx pre-commit install       # hooks run ruff + hygiene on every commit
```

Install opencode: `npm i -g opencode-ai` (or see opencode.ai). Launch it in
the repo root — it picks up `.opencode/opencode.jsonc` automatically.

Cross-machine notes: works on macOS, Linux (WSL), and Windows. Tests need a
running Docker daemon (testcontainers starts its own Postgres — you never
create a database by hand).

## 2. What's in `.opencode/`

| Path | What it is |
|---|---|
| `opencode.jsonc` | Shared config: plugins, MCP servers, and the **permission block** that enforces what the agent may not touch (app source, DB schema, destructive git ops) |
| `agent/review.md` | The one review gate — runs the DoD commands (ruff, mypy, pytest) AND audits the diff against the six invariants from AGENTS.md, one combined verdict. Used by `/done` and before claiming anything works |
| `commands/done.md` | `/done` — one gate: invariant audit + DoD verification together |
| `plugins/graphify.js` | The knowledge-graph plugin |

## 3. Graphify — query the map before reading code

The repo carries a precomputed knowledge graph in `graphify-out/` (god nodes,
cross-file relationships). The rule is binding in `AGENTS.md`:

```bash
graphify query "how does audio upload validation work"   # scoped subgraph first
graphify path "audio_router" "MediaFileStorage"          # relationships
graphify explain "X-Accel"                               # focused concepts
graphify update .                                        # after code changes (local, no API cost)
```

Read source files last, not first.

## 4. The rules you cannot break

`AGENTS.md` carries the six binding invariants (layering, error mapping,
no CWD-relative paths, SQLAlchemy 2.0 style, tests on PostgreSQL, naming) and
the Definition of Done commands. There is **no mandated workflow** — work how
you like. A change is done when the `review` agent passes it locally
(`@review …` or `/done`) and CI is green: the `ai-review` check audits every
PR diff against the invariants and blocks merge on new violations; `quality`
runs the DoD.

## 5. How work flows

1. **Build** — however you like. New model? Export it from
   `models/__init__.py` or Alembic will generate a `drop_table` for it.
2. **PR** — three checks run: `quality` (ruff + mypy + pytest), `docker-build`,
   `ai-review` (see `CONTRIBUTING.md`). Human approval merges.

Branches: `master` is the mainline and hub (it carries the agent config and
docs). `refactor` is the active development line until the media refactor
completes. Branch names: `feature/*`, `fix/*`, `tooling/*`.

## 6. Definition of Done (run locally before pushing)

From `backend/`, always with `uv run`:

```bash
uv run ruff format .
uv run ruff check . --fix --ignore B008   # B008 is FastAPI's Depends() idiom
uv run mypy <your changed files> --strict
uv run pytest -v
```

`pre-commit` runs the fast subset on every commit; CI runs the full set on
every PR. Something failing that you don't understand? Ask in the PR — a
documented question beats a silent guess.
