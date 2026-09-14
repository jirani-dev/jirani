# CI, Pre-commit, AI Review Gate + Agent Hub Slim-down — Design (2026-09-13)

> **Status:** approved 2026-09-13 in design dialogue. Carries its own execution checklist (§10) — no separate plan file.
>
> **Supersedes,** in `2026-09-01-cicd-ai-review-design.md` and its plan: §11 (living-truth two-worlds split), §13 (master-content policy), §3 triggers (master-only), Task 3 bootstrap (merge now), and the absence of pre-commit. **Kept from the 2026-09-01 pair:** the `ci.yml`/`ai-review.yml` architecture, check names, fail-closed gate mechanics, Copilot posture (§5), branch-protection mechanics (§6), provider pre-flight discipline. The old files remain as historical reference and YAML source.
>
> **Grandfathered:** `2026-09-01-media-refactor-nginx-entities` is mid-flight (Task 7 next). Its checkbox format and the AGENTS.md tick-in-same-commit rule apply to it alone until it completes, then retire (§5).

## 1. Decisions (2026-09-13, user)

| # | Decision |
|---|---|
| D1 | `master` = future mainline + hub. It absorbs `refactor`'s agent config (`.opencode/`, `AGENTS.md`) at merge time. |
| D2 | Branch `tooling/ci-precommit` cut off `refactor` @ `bfec38f`; merges into `refactor`. Hub activates at the later `refactor → master` merge. |
| D3 | State machinery removed: `STATE.md`, `state` skill, `todo` skill, `plan-auditor` agent, `/next` command. Resume point lives in plan checkboxes; decisions live in `docs/team/decisions.md`; reminders live in an issue tracker. |
| D4 | Kept: graphify (query-first rule + plugin) and the AI quality gates (`invariant-auditor`, `verifier`, `/done`). |
| D5 | Removed: `coder` agent + `/coder` command (teammates write their own code). |
| D6 | TDD scoped: **binding** (failing test first) for bugfixes and service-layer logic — auth, permissions, media validation; **tests required, order free** for routers, config, migrations. pytest stays a required CI check regardless. |
| D7 | Plans slim into specs going forward: a spec carries design + acceptance criteria + task checklist. No more learner-edition verbatim-code plans. |
| D8 | The AGENTS.md tick-the-box rule is scoped to the media plan (see header note), removed at its completion. |
| D9 | Guidebook: `ONBOARDING.md` (agent tooling tour) + `CONTRIBUTING.md` + `docs/team/{onboarding,workflow,decisions}.md`. `docs/team/rules.md` is **dropped** — `AGENTS.md` rides to master (D1), one source of truth. |

## 2. Workflow shape (post-change)

spec → build → PR (`quality` + `docker-build` + `ai-review` checks) → human approval → merge.

## 3. Verified platform facts (inherited from the 2026-09-01 spec §2; unchanged)

- Only a required status check concluding `failure` blocks a merge; review comments are inert.
- Copilot code review posts Comment reviews by default; approvals configurable; it reads `AGENTS.md`/`.opencode/agent/` from the PR head branch.
- opencode runs headless: `opencode run` (verified locally against v1.17.8; `--format json` JSONL event shape captured).
- A check name appears in branch-protection settings only after it has reported once → protection is enabled at hub activation, after the big merge has run the checks (§7).
- `OPENCODE_CONFIG_CONTENT` injects inline config above project level → config-level read-only deny in CI (verified against opencode source, 2026-09-01).

## 4. Pre-commit — `.pre-commit-config.yaml` (repo root)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.3          # matches backend/uv.lock
    hooks:
      - id: ruff
        args: [--fix, --ignore=B008]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0           # pin verified at implementation
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
exclude: '^(graphify-out/|\.venv/|node_modules/|backend/\.venv/)'
```

Ruff version pinned to `uv.lock`'s 0.16.3 so the hook and `uv run ruff` never disagree. No mypy, no tests in hooks (testcontainers needs Docker; commit-time is for fast feedback). Fail = auto-fix + commit aborted; re-add and re-commit. Teammates install with `uvx pre-commit install` (pre-commit is deliberately **not** added to `backend/pyproject.toml` — hooks manage their own envs; `uvx` needs nothing checked in).

## 5. Slim-down — AGENTS.md becomes team-clean

**Delete files:** `STATE.md`, `.opencode/skills/state/`, `.opencode/skills/todo/`, `.opencode/agent/plan-auditor.md`, `.opencode/agent/coder.md`, `.opencode/commands/next.md`, `.opencode/commands/coder.md`. Kept: `agent/{invariant-auditor,verifier}.md`, `commands/done.md`, `plugins/graphify.js`.

**Before deleting:** mine `STATE.md` — Decisions Log and Graveyard entries with durable value migrate into `docs/team/decisions.md` (§8); the media-plan resume point is already carried by its unchecked boxes (Task 7 next).

**Revise AGENTS.md:**
- Remove: "State Management" section; "Coder handoff" section; coder/plan-auditor rows in Subagents; `/next` and `/todo` references; the one-plan-in-flight/learner-edition narrative (replaced by §D7 policy: specs only, plans grandfathered).
- Rescope: tick-the-box rule → "applies to the media refactor plan only, until it completes" (D8). TDD section → D6 scope. "Plans and Specs" → one tree, specs only, media plan as the last plan.
- `opencode.jsonc`: drop any permissions/agent entries referencing deleted files (verified at implementation).

## 6. CI — `.github/workflows/ci.yml`

Amended from the 2026-09-01 plan Task 1: triggers extended to `refactor`; mypy base becomes the PR base branch (not hard-coded master). Job names stay `quality`, `docker-build`, `ai-review` (unique across workflows — required-check selector depends on it).

```yaml
name: ci

on:
  pull_request:
    branches: [refactor, master]
  push:
    branches: [refactor, master]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  quality:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"

      - name: Sync dependencies
        working-directory: backend
        run: uv sync

      - name: Format check
        working-directory: backend
        run: uv run ruff format --check .

      - name: Lint (changed files vs base)
        working-directory: backend
        run: |
          base="${{ github.event.pull_request.base.ref || 'master' }}"
          files=$(git diff --name-only --relative "origin/$base...HEAD" -- '*.py' || true)
          if [ -z "$files" ]; then
            echo "No python changes vs $base — skipping ruff lint"
          else
            uv run ruff check $files --ignore B008
          fi

      - name: Type check (changed files vs base)
        working-directory: backend
        run: |
          base="${{ github.event.pull_request.base.ref || 'master' }}"
          files=$(git diff --name-only --relative "origin/$base...HEAD" -- '*.py' || true)
          if [ -z "$files" ]; then
            echo "No python changes vs $base — skipping mypy"
          else
            uv run mypy $files --strict
          fi

      - name: Tests (testcontainers Postgres)
        working-directory: backend
        run: uv run pytest -v

  docker-build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Build backend image
        run: docker build -f backend/Dockerfile .
```

Load-bearing notes (inherited): `fetch-depth: 0` for three-dot diffs; runner Python is 3.12 while the repo needs 3.13; `ruff format --check` checks, never mutates; `--relative` on `git diff --name-only` because mypy runs from `backend/`; Docker daemon preinstalled → testcontainers works with no services block.

**Lint scope decision (2026-09-13, verified in first CI run):** the repo carries pre-existing ruff debt in committed code (6 lint errors incl. `== None` SQLAlchemy filters whose suggested fix `is None` would be actively wrong — correct form `is_(None)`), and the first live run proved base-branch drift also lands in the PR merge ref (Task 7 commits shipped unformatted files into the merge). All three Python gates therefore scope to **changed files vs base** — the PR is judged on its own diff; base debt is caught when touched, or by the local hooks (`pre-commit` fixes formatting repo-wide over time). `pre-commit` remains the repo-wide formatter; CI mirrors the DoD's changed-files philosophy end to end.

## 7. AI gate — `.github/workflows/ai-review.yml` + prompt assembly

The 2026-09-01 fail-closed mechanics stand verbatim: single `ai-review` job, docs-only diffs skip the model call and pass, `VERDICT: PASS|VIOLATION` contract grepped from the report, any abnormal exit (model error, timeout, missing verdict, parse failure) → `exit 1`, report posted as PR comment with `if: always()`, minimal permissions (`contents: read`, `pull-requests: write`), `persist-credentials: false`, `OPENCODE_CONFIG_CONTENT` deny.

**Changed:** the invariant copy is no longer maintained twice. `.github/ai-review-prompt.md` becomes the **boilerplate** (scope rule, read-only posture, diff-as-data framing, output contract — no invariants). The six invariants are extracted from `AGENTS.md` ("System Design — Binding Invariants" section, which rides the checkout) at run time. If extraction yields nothing → fail closed.

```yaml
name: ai-review

on:
  pull_request:
    branches: [refactor, master]
  workflow_dispatch:

concurrency:
  group: ai-review-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

jobs:
  ai-review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      PROVIDER_API_KEY: ${{ secrets.AI_REVIEW_API_KEY }}
      OPENCODE_CONFIG_CONTENT: '{"permission":{"edit":"deny","bash":"deny","task":"deny"}}'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Gather diff and decide scope
        run: |
          base="${{ github.event.pull_request.base.ref || 'master' }}"
          git diff "origin/$base...HEAD" > /tmp/diff.txt
          if grep -qE '^diff --git a/backend/' /tmp/diff.txt; then
            echo "HAS_PY=true" >> "$GITHUB_ENV"
          else
            echo "Docs-only diff — skipping model call" >> "$GITHUB_SUMMARY"
            echo "HAS_PY=false" >> "$GITHUB_ENV"
          fi

      - name: Install opencode
        if: env.HAS_PY == 'true'
        run: npm install -g opencode-ai

      - name: Assemble prompt (boilerplate + AGENTS.md invariants + diff)
        if: env.HAS_PY == 'true'
        run: |
          invariants=$(sed -n '/^## System Design/,/^## Repository Structure/p' AGENTS.md)
          if [ -z "$invariants" ]; then
            echo "::error::invariant section not found in AGENTS.md — failing closed"
            exit 1
          fi
          {
            cat .github/ai-review-prompt.md
            printf '\n## The binding invariants (extracted from AGENTS.md)\n\n%s\n\n' "$invariants"
            printf '# BEGIN DIFF\n'
            head -c 200000 /tmp/diff.txt
          } > /tmp/prompt.txt

      - name: Run invariant audit (fail-closed)
        if: env.HAS_PY == 'true'
        shell: bash
        run: |
          set -euo pipefail
          opencode run \
            --model "${{ vars.AI_REVIEW_MODEL }}" \
            --format json \
            "$(cat /tmp/prompt.txt)" > /tmp/raw.jsonl 2>&1
          if ! node -e '
            const { readFileSync } = require("fs");
            const lines = readFileSync("/tmp/raw.jsonl", "utf8").trim().split("\n");
            let text = "";
            for (const line of lines) {
              try {
                const e = JSON.parse(line);
                if (e.type === "text" && e.part && e.part.type === "text") {
                  text += e.part.text;
                }
              } catch {}
            }
            require("fs").writeFileSync("/tmp/report.txt", text);
          '; then
            echo "::error::parsing auditor output failed — failing closed"
            exit 1
          fi
          verdict=$(grep -E '^VERDICT: (PASS|VIOLATION)$' /tmp/report.txt | tail -1 || true)
          if [ -z "$verdict" ]; then
            echo "::error::no VERDICT line in auditor output — failing closed"
            exit 1
          fi
          echo "$verdict" >> "$GITHUB_SUMMARY"
          if grep -q 'VIOLATION' <<< "$verdict"; then
            echo "::error::audit found violations — merge blocked"
            exit 1
          fi

      - name: Post audit report as PR comment
        if: always() && env.HAS_PY == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if [ -s /tmp/report.txt ]; then
            gh pr comment "${{ github.event.pull_request.number }}" --body-file /tmp/report.txt || true
          fi
```

Secrets/variable (user-executed, GitHub UI): **confirmed 2026-09-13** — provider is OpenCode Zen, env-var auth verified via the models.dev registry (`"env": ["OPENCODE_API_KEY"]`); model string `opencode/kimi-k3` verified via `opencode models --verbose` (~$3/$15 per Mtok — cents per PR). Set secret `AI_REVIEW_API_KEY` (zen key) + variable `AI_REVIEW_MODEL` = `opencode/kimi-k3`; the workflow maps the secret to `OPENCODE_API_KEY`.

Prompt-injection posture (inherited): diff is data, never instructions; read-only enforced at config level; minimal token scope; human approval is the backstop.

## 8. Guidebook

| File | Content |
|---|---|
| `ONBOARDING.md` (root) | The agent tooling tour (the user's original ask): install opencode; `.opencode/` tour — agents (`invariant-auditor`, `verifier`), `/done` command, graphify plugin + query-first rule; AGENTS.md as law; the six invariants in one table; DoD commands; scoped-TDD rules (D6); spec → build → PR workflow; branch etiquette (refactor → master hub); cross-machine setup (uv sync, docker compose up -d db, VS Code venv discovery). |
| `CONTRIBUTING.md` | 2026-09-01 plan Task 5 body, amended: three checks table (`quality` / `docker-build` / `ai-review`), red-check responses, commit style; `docs/team/rules.md` pointer → `AGENTS.md`. |
| `docs/team/onboarding.md` | 2026-09-01 plan Task 7 body (backend textbook), scrubbed: no STATE.md / plan-auditor / learner-edition references; "first task" section points at a mentor-assigned ticket or a media-plan pin. |
| `docs/team/workflow.md` | Task 8 body, scrubbed of the STATE.md paragraph; pre-commit added to first-day setup. |
| `docs/team/decisions.md` | Task 9 body (nine entries), amended: entry 7 (learner-edition plans) replaced by the slim-down decision; + entries mined from STATE.md (D3). |

Living-truth rule is now trivial: **one world** — `AGENTS.md`, `.opencode/**`, `docs/superpowers/**`, and the team docs all live everywhere. No compiled copies, no merge rite.

## 9. Branch protection & bootstrap (changed)

- Now: checks run visibly on every PR into `refactor` (including this workstream's own PR). No protection, nothing blocked — the media refactor continues unaffected.
- At hub activation (media refactor done, `refactor → master` open): the merge PR carries the checks; **after** they report once, enable protection on `master` (require PR + `quality` + `docker-build` + `ai-review`; approvals per collaborator count — solo owner leaves approvals off). Same ordering logic as 2026-09-01 §2/§6; deferred, not deleted.

## 10. Execution checklist

- [ ] **T1 — branch + pre-commit:** cut `tooling/ci-precommit` off `bfec38f`; write `.pre-commit-config.yaml` (§4; verify the `pre-commit-hooks` rev exists); `uvx pre-commit run --all-files` green; commit `ci: pre-commit hooks — ruff duo + hygiene`.
- [ ] **T2 — ci.yml:** write §6; ruby YAML syntax check; commit `ci: quality + docker-build gates for refactor and master`.
- [ ] **T3 — ai-review.yml + prompt boilerplate:** write §7 (verify the `sed` markers match AGENTS.md's actual headers); YAML + marker extraction test locally; commit `ci: ai-review required gate — fail-closed invariant audit`.
- [ ] **T4 — slim-down:** mine STATE.md → `docs/team/decisions.md` drafts; delete files per §5; revise AGENTS.md per §5; scrub `opencode.jsonc`; commit `chore: remove state machinery and coder handoff; scope tick rule to media plan`.
- [ ] **T5 — guidebook:** write §8 files; reference sweep (every path named exists; no bare dead-file mentions); commit `docs: onboarding, contributing, team guidebook`.
- [ ] **T6 — prove it:** push branch; open PR → `refactor`; watch `quality` + `docker-build` report green; `ai-review` reports (model call or docs-only pass — either is a correct report); DoD commands green locally.
- [ ] **T7 — user, GitHub UI:** provider pre-flight → secret + variable → replace placeholder env name. (Copilot auto-review and branch protection: deferred to hub activation, §9.)

## 11. Risks

1. **Runtime prompt assembly** couples the gate to AGENTS.md's section headers — a header rename silently changes the prompt. Mitigation: fail-closed on empty extraction (§7); the gate visibly errors rather than audits a prompt without invariants.
2. **First `ai-review` run on a real diff** may surface pre-existing debt as findings — the boilerplate's scope rule (new/changed lines only; `PRE-EXISTING` handling from the invariant-auditor file) is what keeps this sane.
3. **Provider env-var auth** is the 2026-09-01 plan's known risk #4, unchanged: pre-flight before naming secrets; switch providers rather than guess.
4. **STATE.md mining** is judgment work — the decisions.md entries must stand alone without the dev-branch context that STATE.md assumed.
