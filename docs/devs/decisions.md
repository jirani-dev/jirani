# Decisions — what the codebase chose, and why (plain language)

Read this when something looks arbitrary; it rarely is. Each entry is
problem → choice → consequence, ending with the artifact that owns it.

## The architecture and process decisions

1. **Alembic, not `create_all`** — `create_all` can only create missing
   tables, never change them; the first schema change silently breaks every
   existing database. Migrations make schema change reviewable, ordered, and
   repeatable. Owner: `backend/migrations/`.
2. **PostgreSQL in tests, never SQLite** — book searches use JSONB/GIN that
   SQLite cannot express; testing on one database and shipping on another
   produces 500s you cannot see locally. Owner: `AGENTS.md` (invariant 5),
   the testcontainers harness.
3. **nginx X-Accel, not Python byte streaming** — kernel-level file serving
   with native Range support versus a Python generator loop; streaming went
   from ~100 lines of subtle, security-adjacent parsing to a header.
   Owner: `nginx/nginx.conf`, the media refactor spec (dev branches).
4. **author/level/genre are tables; language is a column** — dedup +
   case-insensitivity + a listable vocabulary justify a table; `language`
   needs none of that today. Owner: the media refactor spec (dev branches).
5. **`book_type` renamed to `genre`** — the column once held MIME junk
   ("application/pdf") from a file-format conflation; the real format lives
   in `extension`, and the genre is user-facing. Owner: same as #4.
6. **One dependency manifest (`uv.lock`), no `requirements.txt`** —
   hand-maintained manifests drift in different directions; a generated
   lockfile cannot. Never hand-edit the lock; add deps with `uv add`.
   Owner: `backend/pyproject.toml` + `backend/uv.lock`.
7. **The reviewer is the only process gate** — no mandated workflow, no process
   documents; work how you like, and what passes the `review` agent locally
   plus CI is good enough. Owner: `.opencode/agent/review.md` +
   `.github/workflows/`.
8. **Checks gate every merge** — CI runs the repo's Definition of Done
   (ruff format/lint, changed-files mypy, full pytest on testcontainers
   Postgres) plus a Docker build sanity check; a claimed-complete change with
   no passing evidence is not complete. Owner: `.github/workflows/ci.yml`.
9. **AI reviews before humans finish** — the `ai-review` check runs a
   headless invariant audit (kimi-k3 via opencode zen) on every PR diff,
   fails closed on any abnormal outcome, and posts its report as a PR
   comment. Its findings block merge when new; humans judge afterwards and
   have the final say. Owner: `.github/workflows/ai-review.yml` +
   `.github/ai-review-prompt.md`.
10. **Fixed default temp credentials** — student/teacher accounts mint with
    `student123`/`teacher123` (readable offline-school context); acceptable
    because first login forces replacement on every minting path. The values
    live as `Settings` fields, never literals in services.
    Owner: `backend/app/config.py`, `backend/app/services/auth_service.py`.

## Migrated from the maintainer's log (lessons already paid for)

11. **Bare `@computed_field`, no `@property`** — with mypy 2.3.0 + pydantic
    2.13.4, `@computed_field @property` fails `mypy --strict`, and the
    reversed order passes mypy but breaks at runtime
    (`PydanticDescriptorProxy is not callable`). Bare `@computed_field` is
    clean on both axes. Lesson: mypy-clean ≠ working — test the runtime side
    too.
12. **Submodule imports, not package-attribute imports** — `from
    app.models import X` dies under circular imports (the attribute isn't
    bound yet during partial package init); `from app.models.base import X`
    survives. Same rule for repositories↔services cycles. Never eager-export
    a service from a package `__init__.py`.
13. **LF line endings, enforced** — Windows CRLF once broke the container:
    the shell shebang became `sh\r` and the entrypoint died before it did
    anything. `.gitattributes` (`* text=auto eol=lf`) + `git add
    --renormalize .` fixed it permanently; `git ls-files --eol | grep i/crlf`
    detects relapses.
14. **One toolchain per checkout** — mixing Windows-native Python tooling
    with a Linux-layout venv corrupts the venv silently (VS Code + Windows
    uv deleted `bin/` every few minutes). Point `.vscode/settings.json` at
    the interpreter layout you actually run.
15. **The backend image is baked; nginx binds hold inodes** — after code
    lands, `docker compose build backend && docker compose up -d backend`
    (only `./uploads` is bind-mounted; a running container keeps the old
    image). If nginx serves 404s while the backend serves the file fine,
    `docker compose up -d --force-recreate nginx` — a `restart` does not
    re-resolve a bind-mounted directory whose inode changed on disk.
16. **Rules live in tooling where tooling can check them** — prose rules
    drift (the DoD was copied into five files and two copies disagreed;
    26 of 300 commits had no type prefix). Now: ruff `N801` is Invariant 6;
    the invariant table's debt column is mirrored as
    `[tool.ruff.lint.per-file-ignores]`; the commit format is a commit-msg
    hook; merge protection is a GitHub ruleset. Prose keeps only what
    tooling cannot check. Owner: `backend/pyproject.toml`,
    `.pre-commit-config.yaml`, `.github/rulesets/protected-branches.json`.
17. **The agent edits application source with a human confirming each
    edit; dependencies, schema, and packaging stay human-only** — a pure
    advisory mode made the agent paste snippets for the human to apply,
    which is the same review with more friction; a fully open mode removes
    the human from the one place a wrong edit is expensive to undo
    (migrations, the lock file, the image). `backend/app/**` is `ask`;
    `pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic.ini`,
    `migrations/**`, compose are `deny`. Owner: `.opencode/opencode.jsonc`
    `permission` block; `AGENTS.md` "Operating Mode".
18. **Design docs are artifacts, never gates** — the superpowers skills
    (brainstorming, writing-plans) produce specs and plans locally;
    decision 7 says the reviewer is the only gate.
    Both are true: a spec records a design, it never becomes a required
    step for anyone. The plugin is pinned so a skill update cannot change
    process by surprise. Owner: `AGENTS.md` "Superpowers" and "Docs".
20. **Skill output is untracked; `docs/devs/specs/` is curated** — the
    repo will be open source: contributors should not need the
    superpowers plugin to read a spec, and process artifacts (executed
    plans, per-task checklists) are noise for them. So plugin output
    stays local (`docs/superpowers/`, gitignored), and what is tracked
    under `docs/devs/specs/` is hand-written specs for ongoing features
    only. Executed plans remain recoverable from git history. Owner:
    `.gitignore`, `AGENTS.md` "Docs" and "Superpowers".
