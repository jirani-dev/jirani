# Jirani — an offline digital library for schools

Jirani is a library server for schools in Kenya where the internet cannot
be assumed: books, audio, and video served over the school's local network,
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

Jirani is aimed at a concrete place: schools in Kenya where a library is
rare and an internet connection is never guaranteed. In real terms, the
project succeeds when:

- **A school with no library has one.** A full catalog of books, audio,
  and video on one machine in the school, organized by level and genre.
- **No internet needed, no internet bill.** Everything works over the
  school's local network — no data costs, no cloud subscription, nothing
  that stops when the connection does.
- **Hardware the school can afford.** One modest computer runs the whole
  stack; there is nothing else to buy.
- **Teachers can use it the same day.** Student and teacher accounts mint
  with temporary credentials replaced at first login — a class starts the
  afternoon it is installed.
- **Students can trust it with their work.** Every change is tested on a
  real database and reviewed before it ships; a library that loses
  students' records is worse than none.

## How it works

nginx receives every request and serves media itself; API calls are proxied
to FastAPI at `/api/*`. A request flows router (HTTP concerns) → service
(business rules) → repository (persistence) → model (the saved row).
Database schema changes go through Alembic migrations. The whole stack
ships as Docker containers.

## Where to go

| I want to… | Go to |
|---|---|
| Run it | `docs/devs/operations.md` |
| Join the team and learn the AI-assisted workflow | `ONBOARDING.md` |
| Learn backend concepts as a newcomer | `docs/devs/onboarding.md` |
| Open a pull request | `CONTRIBUTING.md` |
| Know the binding rules | `AGENTS.md` |
| Understand why things are the way they are | `docs/devs/decisions.md` |

**Stack:** Python · FastAPI · PostgreSQL 16 · SQLAlchemy 2.0 · Alembic ·
nginx · Docker. A React SPA is scaffolded on the `frontend` branch.
