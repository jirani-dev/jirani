# Contributing to Jirani

All merges go through pull requests. Three automated checks run on every PR
and **must be green** before merge:

| Check | What it runs | What it means |
|---|---|---|
| `quality` | ruff format/lint (changed files), mypy `--strict` (changed files), full pytest on testcontainers Postgres | The repo's Definition of Done |
| `docker-build` | Docker image build sanity | The backend still packages |
| `ai-review` | Headless invariant audit of your diff against the six binding invariants (`AGENTS.md`) | New invariant violations block the merge |

Expected responses:

- Red `quality`: read the failure log, fix, push. The commands runnable locally are in `ONBOARDING.md` §6.
- Red `ai-review`: read the auditor's PR comment. Fix genuine violations. If you believe the finding is wrong, say so in a PR comment ("I disagree because …") — the auditor reports, humans judge. Example of a good pushback: *"`ai-review` flagged Invariant 2 at `auth_service.py:88`, but that line is untouched by this diff — pre-existing per the debt table."*
- Never push generated media, secrets, or `.venv`. Never force-push to the mainline.

Commit messages follow the repo style: `feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `ci:`, `docs:`.

New to this codebase? Start with `ONBOARDING.md` (the AI-assisted workflow),
then `docs/team/onboarding.md` (the backend itself).

First task? Ask a mentor — writing one characterization pin is the standard
beginner task.
