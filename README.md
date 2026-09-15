# Jirani — an offline digital library for schools

Jirani is a library server for schools where the internet cannot be
assumed: books, audio, and video served over the school's local network,
on modest hardware, with no cloud in the path. The backend is FastAPI +
PostgreSQL behind nginx.

*jirani* is Swahili for **neighbor** — the library that lives next door,
not across the ocean.

## Mission

Put a real library in front of students for whom the internet is not a
reliable utility. Jirani runs on one machine in the building: media lives
on local disk, accounts exist from day one, and nothing a student does in
the library depends on a connection to the outside world.

## Goals

- **Offline-first media.** Books, audio, and video stream from local disk
  through nginx's X-Accel mechanism; protected streams are never public
  URLs.
- **Day-one accounts.** Student and teacher accounts mint with temporary
  credentials that must be replaced at first login.
- **Honest engineering.** A layered architecture (router → service →
  repository → model), tests that run on real PostgreSQL, and every change
  gated by automated review and CI before merge.
- **AI-assisted, human-confirmed.** The repo is developed alongside an AI
  agent that edits application source only with a human confirming each
  edit. AI proposes; people decide.

## How it works

nginx receives every request and serves media itself; API calls are proxied
to FastAPI at `/api/*`. A request flows router (HTTP concerns) → service
(business rules) → repository (persistence) → model (the saved row).
Database schema changes go through Alembic migrations. The whole stack
ships as Docker containers.

## Where to go

| I want to… | Go to |
|---|---|
| Run it | `docs/team/operations.md` |
| Join the team and learn the AI-assisted workflow | `ONBOARDING.md` |
| Learn backend concepts as a newcomer | `docs/team/onboarding.md` |
| Open a pull request | `CONTRIBUTING.md` |
| Know the binding rules | `AGENTS.md` |
| Understand why things are the way they are | `docs/team/decisions.md` |

**Stack:** Python · FastAPI · PostgreSQL 16 · SQLAlchemy 2.0 · Alembic ·
nginx · Docker. A React SPA is scaffolded on the `frontend` branch.
