# Tooling tighten — ruleset, agent config, onboarding, conventions

**Date:** 2026-09-14
**Base:** `refactor` (branch `docs/instruction-polish`, rebased onto `21634ce`)
**Status:** design approved in session; implementation plan to follow

## 1. Problem

An audit of every rule-bearing surface in the repo (`AGENTS.md`, `ONBOARDING.md`,
`CONTRIBUTING.md`, `README.md`, `docs/team/*`, `.opencode/**`, `.github/**`,
`.pre-commit-config.yaml`, `backend/pyproject.toml`, git history) found 27
defects. They fall into six kinds:

| Kind | Count | Examples |
|---|---|---|
| Claims that are false | 6 | "checks must be green before merge" — no branch protection exists (`gh api .../branches/refactor/protection` → 404). "repo carries a precomputed knowledge graph" — `graphify-out/` is gitignored. "`master` is the hub" — it is 119 commits behind `refactor`. |
| References to things that do not exist | 4 | `/graphify` skill (`AGENTS.md:65`), `scout` subagent (`:88`), "Test-Driven Development section" (`:117`), "Plans and Specs below" (`:140`). |
| Duplication that has already drifted | 5 | DoD commands in 5 files (`pytest -v` vs `addopts = "-q"`); `--ignore B008` in 5 files; setup in 4 files. |
| Rules with no enforcement | 6 | Commit prefixes (26 of last 300 commits have none; 49 of last 100 subjects exceed 72 chars). Invariant 6 naming. Branch names. |
| Tooling bugs | 3 | `.opencode/plugins/graphify.js:16` executes backticks inside a double-quoted shell string (reproduced). `review.md` is declared read-only but runs `ruff format .` and `--fix`. `.opencode/package.json` is tracked and gitignored at once. |
| Latent landmines | 3 | `mypy --strict` on `tests/media/*` has 101 pre-existing errors; CI runs it on any changed test file. `STATE.md` was resurrected by merge `21634ce` after `7a7441b` deleted it. Superpowers plugin (unpinned) mandates spec files that `AGENTS.md:196` forbids. |

The root cause of the drift is structural: the same fact is written in several
places and no place owns it. Fixing the 27 in place would leave that mechanism
intact.

## 2. Decisions taken in this session

1. **Base branch:** rebase onto `refactor` first (done: `6691eb9`, 1 ahead, 0 behind).
2. **Enforcement philosophy:** mechanize where cheap. Rules that tooling can
   check move into tooling that already runs; prose shrinks to what tooling
   cannot check.
3. **Superpowers vs `AGENTS.md`:** design docs (specs, plans) are permitted as
   artifacts of the brainstorming/writing-plans skills. They are never process
   gates and never required. The reviewer remains the only gate. The plugin is
   pinned.
4. **Approach:** single owner + executable rules (over minimal correction, over
   hard consolidation into one handbook — `CONTRIBUTING.md` is GitHub-linked
   from every PR and must stay a file).
5. **Backend permission:** `backend/app/**` becomes `ask` (each edit confirmed
   in the TUI). `pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic.ini`,
   `migrations/**`, `docker-compose.yml`, `docker/**` stay `deny`.
6. **Exception naming:** keep the repo's existing `<Noun><State>` names
   (`BookNotFound`, `InvalidMediaFile`); ruff `N818` is ignored.
7. **Branch ruleset:** 1 required approval, strict status checks, no bypass actors.

## 3. Ownership map

One owning file per fact. Every other mention is a link.

| Fact | Owner | Everyone else |
|---|---|---|
| DoD commands (dev + check variants) | `AGENTS.md` § Build & Test Commands | `ONBOARDING.md`, `CONTRIBUTING.md` link. `review.md` reads the section at runtime. `ci.yml` is the executable mirror with a comment saying so. |
| First-day setup | `ONBOARDING.md` §1 | `README.md` is run-the-app only. `AGENTS.md` § Cross-Machine Setup keeps only config-precedence. |
| Commit + branch convention | `CONTRIBUTING.md` | `.pre-commit-config.yaml` enforces the same regex. `ONBOARDING.md` links. |
| Code naming conventions | `AGENTS.md` § Repository Structure → Naming | Invariant 6 links to it. |
| Invariants + known debt | `AGENTS.md` invariant table | Debt column mirrored as `[tool.ruff.lint.per-file-ignores]`. |
| Process gate | `AGENTS.md` § The one process gate; `decisions.md` #7 | unchanged |
| Design docs policy | `AGENTS.md` § Docs (+ new § Superpowers) | `decisions.md` #18 |
| Lint / type / test configuration | `backend/pyproject.toml` | no CLI flags anywhere else |
| Merge protection | `.github/rulesets/protected-branches.json` | `CONTRIBUTING.md` cites it |

### Deletions

- `STATE.md` — resurrected by a modify/delete merge conflict in `21634ce`;
  obsolete since `7a7441b` (reviewer is the gate, no state file).
- `docs/team/workflow.md` — 33 lines of duplicates. Its two unique sentences
  move: "pull, then run the DoD" → `ONBOARDING.md` §5; "deploy is manual:
  `docker compose up -d --build`" → `README.md`. `decisions.md` #7 owner
  pointer updated.

## 4. Tooling

### 4.1 `backend/pyproject.toml` (human-applied — path is `deny`)

```toml
[tool.pytest.ini_options]
testpaths = ["app/tests"]
pythonpath = ["."]
addopts = "--tb=short"

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "N"]
ignore = [
    "B008",  # FastAPI Depends() default-argument idiom
    "N818",  # domain exceptions are <Noun><State>, not <Noun>Error — see AGENTS.md Naming
]

[tool.ruff.lint.per-file-ignores]
# Known debt from the AGENTS.md invariant table, machine-readable.
# Delete a line when its module is fixed; the AGENTS.md row goes with it.
"app/repositories/audio_repo.py" = ["N801"]  # Audio_Repo (Invariant 6, audio plan)
"app/schemas/audio_schema.py" = ["N801"]     # Audio_Create, Audio_View (Invariant 6, audio plan)
"app/api/audio_router.py" = ["E711"]         # pre-existing, audio plan
"app/config.py" = ["N802"]                   # ALLOWED_EXTENSIONS / ALLOWED_IMAGE_EXTENSIONS are @property constants — intentional

[tool.mypy]
python_version = "3.13"
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["jose", "passlib", "passlib.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
# Tests are exercised by running them; strict annotation of every fixture and
# helper adds no safety. App code stays fully --strict.
module = "app.tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_calls = false
warn_return_any = false
disallow_any_generics = false
```

Evidence behind each line:

- `addopts`: today `-q` in config fights `-v` in every DoD copy. The
  documented command becomes `uv run pytest`; this line owns verbosity.
- `N`: `uv run ruff check . --select N` on the current tree → 11 hits:
  3× N801 (audio, Invariant 6 debt), 2× N802 (`config.py` properties),
  6× N818 (exception names). N801 makes Invariant 6 mechanical.
- `per-file-ignores` = the invariant table's debt column. The 4 remaining
  pre-existing ruff errors (`dependencies/auth.py:36 B904`,
  `models/role_enum.py:4 UP042`, `schemas/tag_schema.py:32` and `:35 E501`)
  are not debt; they are fixed in a `chore:` commit.
- mypy override: verified with `--config-file` against the current tree.
  Two test files under `--strict`: 49 errors → 24 with `disallow_untyped_defs`
  + `disallow_untyped_calls` + `warn_return_any` + `disallow_any_generics`;
  the remaining 3 test-file errors are `disallow_incomplete_defs`, the rest
  are audio debt pulled in via imports. Per-module overrides survive a CLI
  `--strict` (mypy applies them on top of the global flags). App code is
  unaffected: `audio_router.py` still reports 20 errors under the override.

### 4.2 `.pre-commit-config.yaml`

```yaml
default_install_hook_types: [pre-commit, commit-msg]

repos:
  - repo: local
    hooks:
      # ruff from backend/uv.lock — one ruff for hooks, DoD, and CI. No rev to drift.
      # --project selects backend/.venv without changing cwd, so the repo-relative
      # paths pre-commit passes still resolve and ruff finds backend/pyproject.toml.
      - id: ruff
        name: ruff check (locked)
        entry: uv run --project backend ruff check --fix --force-exclude
        language: system
        types_or: [python, pyi]
      - id: ruff-format
        name: ruff format (locked)
        entry: uv run --project backend ruff format --force-exclude
        language: system
        types_or: [python, pyi]
      # Commit convention. The regex here is the one CONTRIBUTING.md documents.
      - id: commit-msg-type
        name: commit subject has a type prefix
        entry: '\A(?:(?:feat|fix|test|refactor|chore|ci|docs|build|perf|revert)(?:\([a-z0-9/_.-]+\))?!?: \S|Merge |Revert "|fixup! |squash! )'
        language: pygrep
        args: [--negate, --multiline]
        stages: [commit-msg]
      - id: commit-msg-length
        name: commit subject is at most 72 characters
        entry: '\A[^\n]{73,}'
        language: pygrep
        args: [--multiline]
        stages: [commit-msg]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: no-commit-to-branch
        args: [--branch, master, --branch, refactor]

exclude: '^(graphify-out/|\.venv/|node_modules/|backend/\.venv/)'
```

Mechanics verified against pre-commit docs: `pygrep --negate` = "require all
files to match" (hook fails when the file does not match); `--multiline`
matches across the whole file so `\A` anchors to the first line only;
`commit-msg` hooks receive the message filename; `default_install_hook_types`
makes plain `pre-commit install` install both hook types.

Verified live from the repo root: `uv run --project backend ruff check
backend/app/models/role_enum.py` reports `UP042` — `UP` is not in ruff's
default rule set, so `backend/pyproject.toml` was read. `--directory` would
have changed cwd and broken the paths; it is not used.

Honest cost of the 72-character subject limit: 49 of the last 100 subjects
would fail it. The em-dash style (`feat: X — a, b, c`) survives if the tail
moves to the body.

`pre-commit` itself: `ONBOARDING.md` §1 currently says `uvx pre-commit
install`. The hook shim pre-commit writes records the path of the Python that
installed it; under `uvx` that is an ephemeral cache environment, so a
`uv cache clean` leaves every clone with a dead hook. The setup line becomes
`uv tool install pre-commit && pre-commit install` (persistent shim in
`~/.local/bin`). Confirm on first run that `.git/hooks/pre-commit` points at
the tool environment.

## 5. Conventions

### 5.1 Commit messages (owner: `CONTRIBUTING.md`)

```
<type>(<scope>)?: <subject>

<body>
```

- `type` ∈ `feat fix test refactor chore ci docs build perf revert`.
- `scope` optional: a module or area (`feat(video): …`, `ci(ai-review): …`).
- `subject`: imperative, ≤ 72 characters including the prefix, no trailing period.
- `body`: what and why, wrapped at 72. Optional; expected for anything non-trivial.
- `Merge …`, `Revert "…"`, `fixup! …`, `squash! …` pass automatically.

### 5.2 Branches (owner: `CONTRIBUTING.md`; prose only)

`feature/<thing>`, `fix/<thing>`, `docs/<thing>`, `test/<thing>`,
`tooling/<thing>`, `ci/<thing>`. Base: `refactor` until the media plan's
Part G closes and merges to `master`; `master` after. `master` and `refactor`
never receive direct commits (ruleset + `no-commit-to-branch`). On those two
branches use `git pull --ff-only` — a pull that creates a merge commit is a
direct commit and the hook will refuse it (that is how `STATE.md` came back in
`21634ce`).

### 5.3 Code naming (owner: `AGENTS.md` § Repository Structure → Naming)

| Thing | Rule | Status today |
|---|---|---|
| Classes | `PascalCase`, no underscores (ruff N801) | audio in `per-file-ignores` |
| Schemas | `<Entity>Base / Create / Read / Update`; request/response pairs `<Verb><Noun>Request / Response`; paged lists `Page[T]` | consistent outside audio |
| Route prefixes | plural noun (`/books`, `/videos`, `/tags`, `/authors`) | `/audio` — audio plan |
| Handlers | `list_<plural>`, `get_<singular>`, `upload_<singular>`, `update_<singular>`, `delete_<singular>`, `stream_<singular>` | `get_all_tags`, `get_videos`, `upload_file` — rename when the module is next touched |
| Domain exceptions | `<Noun><State>` without `Error` suffix (`BookNotFound`, `InvalidMediaFile`); base classes `<Area>Error` | consistent; N818 ignored |
| Services / repos | `<Entity>Service`, `<Entity>Repo`; leaf helpers named for what they do (`ContentValidator`, `MediaFileStorage`) | consistent |
| Modules | `snake_case`; `<entity>_router.py`, `<entity>_schema.py`, `<entity>_repo.py`, `<entity>_service.py`, `<area>_errors.py` | consistent |
| Tests | `tests/<area>/test_<module>_<aspect>.py` | consistent; `AGENTS.md` previously documented only `_repo`/`_api` |
| Settings | `UPPER_CASE` fields and properties on `Settings` | consistent; N802 per-file-ignore on `config.py` |

## 6. Agent configuration

### 6.1 `.opencode/opencode.jsonc`

```jsonc
"plugin": [
  ".opencode/plugins/graphify.js",
  // pinned: superpowers 6.0.3 — bump deliberately, not on every restart
  "superpowers@git+https://github.com/obra/superpowers.git#896224c4b1879920ab573417e68fd51d2ccc9072"
],
"permission": {
  "edit": {
    "*": "allow",
    "backend/app/**": "ask",
    "backend/pyproject.toml": "deny",
    "backend/uv.lock": "deny",
    "backend/Dockerfile": "deny",
    "backend/alembic.ini": "deny",
    "backend/migrations/**": "deny",
    "docker-compose.yml": "deny",
    "docker/**": "deny"
  },
  "bash": {
    "*": "allow",
    "git commit*": "ask",
    "git push*": "ask",
    "git reset*": "ask",
    "git checkout*": "ask",
    "git switch*": "ask",
    "git rebase*": "ask",
    "git merge*": "ask",
    "git rm*": "ask",
    "rm *": "ask",
    "docker compose down*": "ask",
    "psql*": "ask",
    "uv add*": "ask",
    "uv remove*": "ask"
  }
}
```

Removed: `backend/app/tests/**: ask` (subsumed). Added: `git switch`,
`git rebase`, `git merge` (a rebase ran today under `*: allow`; it should have
asked). `uv add`/`uv remove` remain the only route to a dependency change —
`uv.lock` is generated, `pyproject.toml` is never hand-edited by the agent.

### 6.2 `.opencode/agent/review.md`

1. Part 1 no longer lists commands. It says: run the **check variant** in
   `AGENTS.md` § Build & Test Commands — the same read-at-runtime pattern Part 2
   already uses for the invariant table. The DoD has one owner.
2. `ruff format .` and `ruff check --fix` are gone; a reviewer that rewrites
   files is not read-only.
3. `task: deny` added to the permission block, matching the CI twin
   (`ai-review.yml:22`).
4. Part 3 gains its retirement trigger: when
   `docs/superpowers/plans/2026-09-01-media-refactor-nginx-entities.md` has no
   `- [ ]` boxes, delete Part 3 and `/done` steps 1 and 5.

### 6.3 `.opencode/commands/done.md`

Reference fixes only. Tick logic stays until Part G closes (27 boxes open on
`refactor`).

### 6.4 `.opencode/plugins/graphify.js`

Line 16 wraps the example command in backticks inside a double-quoted shell
string; the shell executes it on the first bash call of every session
(reproduced: `run No matching nodes found. instead`). Fix: single quotes
around the example, no backticks.

### 6.5 `.opencode/package.json`, `.opencode/package-lock.json`

`git rm --cached` both. They are already listed in `.opencode/.gitignore:2-3`;
opencode rewrites the version on every start; the plugin imports only `fs`
and `path`.

### 6.6 `AGENTS.md`

| Section | Change |
|---|---|
| Agent Instructions | "Before proposing" → "Before making". Blast-radius step keeps its example. |
| Operating Mode | Retitled *Developer, human in the loop*. Edits under `backend/app/**` are confirmed per edit — that confirmation is the approval. The "implement it" escape-hatch paragraph is deleted. Denied paths listed with the reason (dependencies, packaging, schema need a human). "Provide code as snippets" applies to denied paths only. |
| graphify | `/graphify` skill line deleted — no such skill exists in any skill directory. |
| Cross-Machine Setup | Shrinks to config precedence (project `opencode.jsonc` vs global). Setup → link to `ONBOARDING.md` §1. |
| Subagents | `scout` removed. `review` row: same model (`AI_REVIEW_MODEL` repo variable = `opencode/kimi-k3`, verified via `gh variable list`), same invariant table; CI verdict is `PASS\|VIOLATION` on invariants only, local is `DONE\|NOT DONE` on invariants + DoD. |
| Invariants | Table headings kept verbatim (`ai-review.yml:47` extracts by `## System Design` … `## Repository Structure`); an HTML comment above the heading says so. Inv 5's "Test-Driven Development section" → "the `test-driven-development` skill (superpowers)". Inv 6 links to Naming. Debt column notes it is mirrored in `per-file-ignores`. |
| Repository Structure | + **Naming** subsection (§5.3). "Plans and Specs below" → § Docs. Test layout corrected to `test_<module>_<aspect>.py`. |
| Build & Test | Two variants, one owner. Dev: `uv run ruff format .` · `uv run ruff check . --fix` · `uv run mypy <changed> --strict` · `uv run pytest`. Check (reviewer, CI): `uv run ruff format --check .` · `uv run ruff check .` · same mypy · same pytest. CI applies the check variant to changed files only (`ci.yml` "Resolve changed Python files" step); the reviewer runs it on `.`. No `B008`, no `-v`. |
| Failure Protocol | Dependency changes go through `uv add` (asks), never by editing `pyproject.toml`. |
| Docs | Rewritten: `docs/superpowers/{specs,plans}/` hold design artifacts from brainstorming/writing-plans — optional, never a gate. Media plan tick rule + its retirement trigger. Recovery via `git log --follow`. |
| *new* Superpowers | Pinned plugin; the skills relevant here (brainstorming, writing-plans, test-driven-development, systematic-debugging, verification-before-completion); `AGENTS.md` outranks any skill. |

## 7. CI and GitHub

### 7.1 `.github/rulesets/protected-branches.json`

```json
{
  "name": "protected-branches",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/master", "refs/heads/refactor"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "quality" },
          { "context": "docker-build" },
          { "context": "ai-review" }
        ]
      }
    }
  ]
}
```

Applied once: `gh api -X POST repos/{owner}/{repo}/rulesets --input .github/rulesets/protected-branches.json`
(asks before running — it mutates repository settings). Shape verified against
the GitHub REST reference for "Create a repository ruleset".

Judgment calls: `strict_required_status_checks_policy: true` prevents the
base-drift red seen in `da89575`/`211e078` at the cost of one "Update branch"
click. `required_approving_review_count: 1` means the author cannot merge
alone. `bypass_actors: []` binds admins too; emergencies edit the ruleset.

### 7.2 `.github/workflows/ci.yml`

Drop `--ignore B008` from the lint step. Add a header comment: *mirrors
`AGENTS.md` § Build & Test Commands (check variant)*. Changed-files scoping
unchanged.

### 7.3 `.github/workflows/ai-review.yml`, `.github/ai-review-prompt.md`

Unchanged. The invariant extraction depends on the two `AGENTS.md` headings
staying literal; §6.6 pins them.

## 8. Documentation changes

| File | Change |
|---|---|
| `README.md` | Run-the-app only. Gains the deploy line from `workflow.md`. Tests/deps notes collapse to one link line. |
| `ONBOARDING.md` | §1 owns setup and adds `graphify update .` (graph is generated, not shipped); `uvx pre-commit install` → `uv tool install pre-commit && pre-commit install` (§4.2). §2 table: plugin description corrected. §5: base is `refactor`; "returning to work" folded in from `workflow.md`; commit/branch → link to `CONTRIBUTING.md`. §6 → link to `AGENTS.md`. Notes that the agent edits `backend/app/**` with per-edit confirmation. |
| `CONTRIBUTING.md` | Owns commit + branch convention (§5.1, §5.2; same regex as the hook). "Must be green before merge" is now true — says so and cites the ruleset file. |
| `docs/team/onboarding.md` | §3 stub written for real: six rules × one plain sentence, compliant example from the auth module, live violation (audio only — `audio_router.py:40` `db.query(Audio)` verified). |
| `docs/team/decisions.md` | +16 *Rules live in tooling where tooling can check them* (per-file-ignores = debt table; commit-msg hooks; ruleset). +17 *The agent edits app source with a human confirming each edit; dependencies, schema, packaging stay human-only.* +18 *Design docs are permitted artifacts, never gates.* #7 owner pointer drops `workflow.md`. |
| `docs/team/workflow.md` | deleted (§3) |
| `STATE.md` | deleted (§3) |

## 9. Verification (Definition of Done for this change)

Every step's output is pasted, not summarised.

1. `uv tool install pre-commit && pre-commit install` → both hook types installed. `pre-commit run --all-files` → green.
   Commit-msg hooks: `pre-commit run commit-msg-type --hook-stage commit-msg --commit-msg-filename <good.txt>` passes; with a bad subject it fails; same for `commit-msg-length`.
2. From `backend/`: `uv run ruff format --check .` (93 files already formatted) · `uv run ruff check .` → 0 after the `chore:` commit that clears B904, UP042, and the two E501s · `uv run mypy app/tests --strict` → 0 · `uv run mypy . --strict` → errors only in `audio_router.py` and `audio_repo.py` · `uv run pytest` → all passed (180 expected per `11addc3`; actual count pasted; Docker required).
3. Dead-reference grep across tracked files for `workflow.md`, `STATE.md`, `scout`, `/graphify`, `B008`, `pytest -v`, `Test-Driven Development section`, `Plans and Specs` → zero hits (git history excluded).
4. `gh api repos/{owner}/{repo}/rules/branches/refactor` lists `deletion`, `non_fast_forward`, `pull_request`, `required_status_checks`.
5. `graphify update .`, then `@review` on the full diff → `VERDICT: DONE`.
6. Restart opencode (config loads once). An edit under `backend/app/` prompts instead of refusing; the first bash call no longer prints `No matching nodes found`.

## 10. Commit plan

Each commit passes the new hooks. Owner in parentheses. Order matters: the
permission change goes first so the agent can do commit 3; the reviewer's
pointer to the new `AGENTS.md` section lands in the same commit as the section.

1. `chore(opencode): app edits ask, pin superpowers, fix plugin quoting` (agent) — includes untracking `package.json` and `package-lock.json`. **Restart opencode after this commit**; config loads once.
2. `chore(tooling): pyproject owns lint, type, and test config` (human — path is `deny`)
3. `chore: clear pre-existing ruff errors (B904, UP042, E501)` (agent, per-edit confirmation)
4. `ci: locked-ruff pre-commit, commit-msg hooks, drop B008 flags` (agent) — `pre-commit install` right after, so commits 5–7 are checked by the hooks they document
5. `docs: AGENTS.md developer mode, naming, single-owner DoD` (agent) — includes the `review.md` read-only fix and `task: deny`, since `review.md` now points at the section this commit creates
6. `docs: onboarding and contributing rewrite, delete STATE.md and workflow.md` (agent) — includes decisions 16–18
7. `ci: branch ruleset for master and refactor` (agent writes the file; applying it via `gh api` asks first)

## 11. Out of scope

- The audio module refactor (its own future plan; debt rows stay in the table and in `per-file-ignores`).
- Renaming the drifted handlers (`get_all_tags`, `get_videos`, `upload_file`) — done when each module is next touched.
- A CI commit-lint job or branch-name check — the local hooks plus the ruleset are enough at this team size.
- Media plan Part G (Tasks 11–16).

## 12. Deviations during implementation

Recorded 2026-09-14, after the final whole-branch review (12 commits, base `21634ce`, head of the fix wave):

- **Task 3 (ruff-error cleanup) deferred by the user** — the four pre-existing errors (B904 `dependencies/auth.py:36`, E501 `tag_schema.py:32,35`, UP042 `role_enum.py:4`) plus one new unused `type: ignore` the mypy override created (`tests/media/test_book_cover.py:12`) stay visible until `backend/app/**` becomes `ask` after an opencode restart. §9.2's "→ 0" and §10 item 3 describe work that has not happened yet.
- **`.github/ai-review-prompt.md` was not left untouched** — §7.3 said unchanged; the branch adds three lines (a worked example finding line) that landed with the rebased polish commit.
- **§3/§8's "decisions.md #7 owner pointer drops `workflow.md`" was a no-op** — #7 never referenced `workflow.md`; nothing to change.
- **§9.3's dead-reference grep must target flag forms** — the literal `B008` appears legitimately in `backend/pyproject.toml` (the sanctioned ignore) and in `.superpowers/` scratch; the check is for `--ignore B008` / `--ignore=B008`.
- **`ci.yml` pytest `-v` removal** happened in the fix wave, not Task 4 (brief miss; found by final review).
