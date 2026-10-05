# Contributing to Jirani

All merges into `master` and `refactor` go through pull requests. The GitHub ruleset in `.github/rulesets/protected-branches.json` makes this a hard requirement: no direct pushes, no force pushes, green required checks, one approval, branch up to date with its base.

| Check | What it runs | What it means |
|---|---|---|
| `quality` | the check variant of the backend Definition of Done (`backend/AGENTS.md` § Build & Test Commands) on changed Python files, full pytest on testcontainers Postgres | The backend DoD |
| `docker-build` | Docker image build sanity | The backend still packages |
| `ai-review` | Headless audit of your diff against the backend invariants (`backend/AGENTS.md`) and the frontend invariants (`frontend/AGENTS.md`) | New invariant violations block the merge |
| `frontend` | the frontend Definition of Done (`frontend/AGENTS.md`) when `frontend/` changed | The SPA still installs, lints, and builds |

Expected responses:

- Red `quality` or `frontend`: read the failure log, fix, push.
- Red `ai-review`: read the auditor's PR comment. Fix genuine violations. If you believe the finding is wrong, say so in a PR comment ("I disagree because …") — the auditor reports, humans judge. Example of a good pushback: *"`ai-review` flagged invariant 2 at `auth_service.py:88`, but this diff doesn't touch that line — it's pre-existing."*
- Never push generated media, secrets, or `.venv`.

## Commit messages (this file owns the convention; the commit-msg hook enforces it)

```
<type>(<scope>)?: <subject>

<body>
```

- `type` is one of `feat fix test refactor chore ci docs build perf revert`.
- `scope` is optional: a lowercase module or area — `feat(video): …`, `ci(ai-review): …`.
- `subject`: imperative, **at most 72 characters including the prefix**, no trailing period. A future teammate should guess the diff from it alone.
- `body`: what and why, wrapped at 72. Optional; expected for anything non-trivial. If you were about to write `feat: X — a, b, c`, put `a, b, c` here.
- `Merge …`, `Revert "…"`, `fixup! …`, `squash! …` pass automatically.

The exact regex lives in `.pre-commit-config.yaml` (`commit-msg-type`, `commit-msg-length`). If the hook rejects a message, fix the message — never `--no-verify`.

## Branches

`feature/<thing>`, `fix/<thing>`, `docs/<thing>`, `test/<thing>`, `tooling/<thing>`, `ci/<thing>`.

Base branch: `master`. Branch from an up-to-date `master` and push small. On `master` itself use `git pull --ff-only` — a pull that creates a merge commit is a direct commit, and the `no-commit-to-branch` hook refuses it.

## Reviews

The AI gate runs first. For human review: pull the branch and run the failing or affected tests before approving. Point to files and lines. "AI found X, I disagree because Y" is a normal and expected comment — do not approve silent-but-suspicious diffs.

New here? Start with `docs/onboarding.md`. First task? Ask a mentor — writing one characterization pin is the standard beginner task.
