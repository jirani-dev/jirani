# Contributing to Jirani

All merges into `master` and `refactor` go through pull requests. The GitHub
ruleset in `.github/rulesets/protected-branches.json` makes this a hard
requirement: no direct pushes, no force pushes, three green checks, one
approval, branch up to date with its base.

| Check | What it runs | What it means |
|---|---|---|
| `quality` | the check variant of the Definition of Done (`AGENTS.md` § Build & Test Commands) on changed Python files, full pytest on testcontainers Postgres | The repo's DoD |
| `docker-build` | Docker image build sanity | The backend still packages |
| `ai-review` | Headless invariant audit of your diff against the six binding invariants (`AGENTS.md`) | New invariant violations block the merge |

Expected responses:

- Red `quality`: read the failure log, fix, push.
- Red `ai-review`: read the auditor's PR comment. Fix genuine violations. If you believe the finding is wrong, say so in a PR comment ("I disagree because …") — the auditor reports, humans judge. Example of a good pushback: *"`ai-review` flagged Invariant 2 at `auth_service.py:88`, but that line is untouched by this diff — pre-existing per the debt table."*
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

Base branch: `refactor` until the media plan's Part G lands and merges to `master`; `master` after. Branch from an up-to-date base and push small. On `master`/`refactor` themselves use `git pull --ff-only` — a pull that creates a merge commit is a direct commit, and the `no-commit-to-branch` hook refuses it.

## Reviews

The AI gate runs first. For human review: pull the branch and run the failing or affected tests before approving. Point to files and lines. "AI found X, I disagree because Y" is a normal and expected comment — do not approve silent-but-suspicious diffs.

New to this codebase? Start with `ONBOARDING.md` (the AI-assisted workflow), then `docs/team/onboarding.md` (the backend itself). First task? Ask a mentor — writing one characterization pin is the standard beginner task.
