# Workflow — daily mechanics

## Environment (first day only)

Tools: uv, Docker (daemon only for tests), git, opencode.
Setup: `cd backend && uv sync` creates `backend/.venv`. Tests need a running
Docker daemon (testcontainers manages its own database — do not create one by
hand). Development database: `docker compose up -d db`. The schema is managed
by Alembic and applied automatically when the container starts. Run
`uvx pre-commit install` once — hooks check formatting on every commit.

## Returning to work

`git pull`, then run the quality commands in `ONBOARDING.md` §6 before
changing anything.

## Branches and PRs

Always work on a branch created from an up-to-date base (`master` after the
media refactor lands; `refactor` until then). Open a PR for anything that is
not a one-character typo fix. Push small.

## Reviews

The AI gate runs first (see `CONTRIBUTING.md`). For human review: pull the
branch and run the failing/affected tests before approving. Point to
files/lines. "AI found X, I disagree because Y" is a normal and expected
comment — do not approve silent-but-suspicious diffs.

## Deploy (manual, after merge)

`docker compose up -d --build` on the machine. The pipeline deliberately does
not deploy for you.
