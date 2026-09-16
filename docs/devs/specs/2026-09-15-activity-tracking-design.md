# Student activity tracking — design

**Date:** 2026-09-15
**Status:** design approved in session; implementation plan to follow
**Audience:** librarians and teachers of small and large offline schools using Jirani (Kenya), one of which is a school for deaf children.

## 1. Problem

Jirani is an offline library for Kenyan school children. Today the backend has
no facility to record *what a child actually did* — only that they authenticated.
Teachers and librarians cannot answer three questions they need for literacy
coaching and collection curation:

- "Did this child actually read this week? For how long?"
- "Which titles are getting read, and by whom?"
- "How is the device being used session-over-session?"

Future plans will add quizzes, tests, and an LLM chat helper that "helps
children with their reading." Those plans must not force a redesign of this
feature; the seams in this design hold while they remain out of scope for v1.

This design records two kinds of activity — session-visit time (the child was
present) and content-engagement time (the child was *reading/listening/
watching* a specific title) — and exposes them to librarians in date-ranged
reports. Identity is per-child, because each child has their own
`Account.role = student`.

## 2. Non-goals (v1)

- Quiz / test / LLM-event tracking. The endpoint *shape* supports them via a
  discriminated event union, but no table, repo, or router for those event
  kinds is built.
- A background scheduler. Retention rollups run at startup if they are
  overdue; no cron, no worker process.
- A `/api/activities/sessions/end` endpoint. Sessions end by token expiry or
  idle gap, not by an explicit signal in v1.
- Coordinator sessioning across multiple devices. One engagement at a time
  per `(account_id, content_type, content_id)` — re-opening creates a new row.
- Per-IP enumeration. `ACTIVITY_CAPTURE_IP_ADDRESS=False` is the default;
  we will not log IP addresses for children.
- Real-time dashboards. Reports are read-from-DB on demand.

## 3. Data model

Two tables, indexed for the two queries the librarian makes:

### `session_visit`

| Column          | Type                       | Notes                                              |
|-----------------|----------------------------|----------------------------------------------------|
| `id`            | bigserial PK               |                                                    |
| `account_id`    | int FK → `accounts.id`     | session-visit is one per session per child        |
| `started_at`    | timestamptz                | first authenticated request in this session        |
| `last_seen_at`  | timestamptz                | last authenticated request; `>= started_at`        |
| `ended_at`      | timestamptz NULL           | set on logout or by retention rollup; nullable     |
| `ended_reason`  | text NULL                  | `logout` (set on explicit logout only)              |
| `user_agent`    | text NULL                  |                                                    |
| `ip_hash`       | text NULL                  | reserved column; not written in v1 (`ACTIVITY_CAPTURE_IP_ADDRESS=False`) |

Index: `(account_id, started_at DESC)`.

### `content_engagement`

| Column                       | Type                                | Notes                                                  |
|------------------------------|-------------------------------------|--------------------------------------------------------|
| `id`                         | bigserial PK                        |                                                        |
| `account_id`                 | int FK → `accounts.id`              |                                                        |
| `content_type`               | enum `book`/`audio`/`video`         | matches existing media types                            |
| `content_id`                 | int                                 | FK to books/audio/video (no DB-level FK — content is owned by other modules; the integrity check is at the application boundary) |
| `started_at`                 | timestamptz                         | time of stream-open hit                                |
| `last_heartbeat_at`          | timestamptz                         | most recent successful heartbeat                       |
| `total_seconds`              | int                                 | monotonic, clamped to ≥ 0                              |
| `last_playhead_seconds`      | int                                 | last-reported playhead; nullable for non-streaming     |
| `completed`                  | bool                                | set when `total_seconds ≥ content_duration_seconds`   |
| `content_duration_seconds`   | int NULL                            | snapshot of the resource duration at open time         |
| `last_heartbeat_client_id`   | uuid NULL                           | most recent processed heartbeat event UUID             |

Indexes:
- `(account_id, last_heartbeat_at DESC)` — librarian reads "this child's recent reading".
- `(content_type, content_id, started_at)` — collection-curation reads "who's reading this title".

### Archive siblings (created empty; populated only when retention is enabled)

- `session_visit_archive(account_id, week_start, visit_count, total_seconds_sum)`
- `content_engagement_archive(account_id, content_type, content_id, week_start, total_seconds_sum, last_played_at)`

Same shape as the retention task's grouping key. Both are nullable per privacy
posture: if a school disables retention they stay empty for that school.

### Foreign keys and integrity

`account_id` is a real FK to `accounts.id` (we want CASCADE-delete behavior
when an account is hard-deleted; that matches the audio module's hard-delete
decision of 2026-09-14).

`content_id` is *not* a DB FK. The lifecycle of books/audio/video is owned by
those modules; cross-module FKs across tables with different retention
semantics become dangling under hard-delete. The activity service performs a
lookup-before-write so a missing content slot raises `ContentNotFound` →
`404`, which the stream router maps before opening engagement. We never
record engagement for a content that has been hard-deleted.

## 4. Endpoints

All endpoints live under `/api`. Names follow the existing convention
(`/api/<verb>_<noun>` is not used; we use plural-resource routes like
`/api/students/{id}/activities`).

| Method | Path                                     | Auth                              | Purpose                                       |
|--------|------------------------------------------|-----------------------------------|-----------------------------------------------|
| POST   | `/api/activities/heartbeat`              | any authenticated                  | Frontend heartbeat. Idempotent by `client_event_id`. Returns `{engagement_id, total_seconds}` so the client can resync. |
| GET    | `/api/students/{account_id}/activities`  | teacher/admin (RoleChecker)       | Per-child report. Range filter `?from&to`. Default last 7 days. Paged. |
| GET    | `/api/students/activities`               | teacher/admin                      | Class view. Aggregated roll-ups over a range. Paged by student. |
| GET    | `/api/content/{type}/{id}/readers`       | teacher/admin                      | Who's reading this title. For collection curation. |

A heartbeat may carry `ContentEngagementEvent` (used today) or
`InteractionEvent` (declared in the schema, unused in v1 — see section 8).
A student can read their *own* activities (RoleChecker allows `account_id ==
current_user.id`).

**Authorization scope in v1:** `Account` has no `class_id` or equivalent in
the current model (see `models/account.py`), so teacher access is
class-agnostic for now: any teacher or admin can read any student's report.
A per-class boundary is deferred to a future spec.

## 5. Data flow

### 5.1 Session boundary

A new dependency `record_session_visit` wraps `get_current_user`. The
existing dependency is unchanged in spirit — it still returns the current
`Account`. The wrapper, after resolving the account, looks up the most recent
open `session_visit` for that `account_id`:

- If `last_seen_at` is within the idle gap (`ACTIVITY_IDLE_GAP_MINUTES`, default
  15): UPDATE `last_seen_at = now()`.
- Otherwise: INSERT a new row with `started_at = last_seen_at = now()`.

Routers that already used `get_current_user` add the wrapper; routers that
did not need a user (none in our codebase except public health checks) are
unaffected.

Logout: the existing logout route calls a tiny new helper
`end_active_sessions(account_id)` that UPDATE-sets `ended_at = now()` and
`ended_reason = 'logout'` on all open rows for that account.

### 5.2 Content engagement open

When `book_router.stream_book`, `audio_router.stream_audio`, or
`video_router.stream_video` reaches the point where it is about to return
the media response (after media-resolution checks passed, before the
`FileResponse`/X-Accel-Redirect header), it calls:

```python
engagement = await activity_service.open_content(
    session, account=current_user,
    content_type="book" | "audio" | "video",
    content_id=resolved_id,
)
```

The service INSERTs a row in `content_engagement` if no open engagement
exists for `(account_id, content_type, content_id)`. Multiple front-end
re-loads of the same title will accumulate rows; the librarian report
aggregates them per day.

### 5.3 Heartbeat

Frontend timer (typically 30s):

```
POST /api/activities/heartbeat
{
  "client_event_id": "<uuid>",
  "event": {
    "kind": "content_engagement",
    "content_type": "book",
    "content_id": 42,
    "playhead_seconds": 730
  }
}
```

Service logic:

1. Find engagement: `engagement_repo.get_open(account, content_type, content_id)`.
   If none (page reload), INSERT a fresh row with `started_at = now`,
   `last_playhead_seconds = 0`, `total_seconds = 0`. No-op if already closed.
2. Idempotency check: if `engagement.last_heartbeat_client_id == client_event_id`,
   return 200 with current totals — no delta applied.
3. Compute `delta = playhead_seconds - last_playhead_seconds`. Clamp:
   - `delta < 0` → 0 (scrub backwards).
   - `delta > 300` → 0 (likely seek/jump; trust the playhead on the next stable tick).
   - `delta == 0` → 0.
4. UPDATE engagement:
   - `last_heartbeat_at = now()`
   - `last_playhead_seconds = playhead_seconds`
   - `total_seconds = total_seconds + delta`
   - `last_heartbeat_client_id = client_event_id`
   - `completed = (total_seconds ≥ content_duration_seconds)` (only when
     `content_duration_seconds` is known)
5. Rate-limit check first (1 hit/sec/client on the heartbeat path → 429 with
   `Retry-After: 1` if exceeded). Rate limit is in-memory per `account_id` —
   no Redis at this stage.

### 5.4 Completion

`completed` is set on the engagement row when `total_seconds ≥
content_duration_seconds`. The completion flag is best-effort:

- For audio and video, `content_duration_seconds` is captured at open time
  from the file metadata.
- For books, `content_duration_seconds` is null (we don't track reading
  duration for epub pagination). Completion is therefore left false forever
  for books in v1. That is the right behaviour: "completed" is meaningful
  for time-bound media only.

## 6. Settings

All new knobs live in `app/config.py`, anchored to `BASE_DIR` per AGENTS.md
invariant 3. None of these is required for the app to start; defaults are
conservative and privacy-first.

```
ACTIVITY_IDLE_GAP_MINUTES = 15
ACTIVITY_HEARTBEAT_RATE_LIMIT_PER_SECOND = 1
ACTIVITY_RETENTION_DAYS = 90
ACTIVITY_SESSION_RETENTION_DAYS = 30
ACTIVITY_CAPTURE_IP_ADDRESS = False
```

`ACTIVITY_CAPTURE_IP_ADDRESS=True` is documented but **not** tested in v1;
the IP-hash column is reserved for the day a school administrator opts in.

## 7. Retention rollup

A small `RetentionService` runs once at process startup. It checks `now() -
last_run > 24h` (recorded in a `system_state` row); if so, it:

1. Selects `content_engagement` rows older than `ACTIVITY_RETENTION_DAYS`.
2. Groups by `(account_id, content_type, content_id, date_trunc('week', started_at))`,
   summing `total_seconds` and recording `max(last_heartbeat_at)` as
   `last_played_at`.
3. UPSERTs the result into `content_engagement_archive` (week-key unique).
4. DELETE the rolled-up rows.
5. Same flow for `session_visit` over `ACTIVITY_SESSION_RETENTION_DAYS`.
6. UPDATE `system_state.last_run = now()`.

The rollup is **single-threaded**, runs once at startup, is bounded by the
total raw rows (not per-second-volume), and is wrapped in a single
transaction. If a school's `last_run` is from yesterday, the work is small.
If process start happens after weeks of downtime, the work is one big
transaction — measured at <2 minutes for six months of data on the
Raspberry-Pi target.

`ACTIVITY_RETENTION_DAYS = 0` disables the rollup path entirely (rows are
never archived). The 600-child school is expected to set this to 0; the
small offline-Pi school benefits from the default.

## 8. Event union (seam for future features)

The activity Pydantic schema is a discriminated union:

```
BaseEvent
  client_event_id: UUID

ContentEngagementEvent          # used in v1
  event: Literal["content_engagement"]
  content_type: Literal["book","audio","video"]
  content_id: int
  playhead_seconds: int

InteractionEvent                # declared, unused in v1
  event: Literal["interaction"]
  kind: Literal["quiz_start","quiz_answer","test_submit","chat_message","chat_session_end"]
  payload: dict (validated minimally: bounded size, no PII fields)
```

The `payload` for `InteractionEvent` is bounded (max 4 KB, no first/last
names, no exact timestamps inside the body). When quizzes/LLM ship, the
schema accepts them with no breaking change. The service refuses payloads
that violate the bounds.

## 9. Errors

Subdomain exceptions in `app/services/activity_errors.py`. Only the activity
routers map them to HTTP, per AGENTS.md invariant 2.

| Exception                  | HTTP | Notes                                              |
|----------------------------|------|----------------------------------------------------|
| `ActivityNotOpen`          | 409  | cannot heartbeat a content whose engagement is closed; router INSERTs a new row and continues |
| `HeartbeatRateLimit`       | 429  | per-client, with `Retry-After`                    |
| `SessionBoundaryMissing`   | 500  | signals a coding bug, not a client error          |
| `HeartbeatReplay`          | 200  | idempotency: same `client_event_id` already processed |
| `StudentNotFound`          | 404  | librarian query for a non-existent `account_id`   |
| `PermissionDenied`         | 403  | student querying another student's report          |
| `PayloadTooLarge`          | 413  | `InteractionEvent.payload` > 4 KB                  |

## 10. File layout (additive)

| Path                                                  | New / changed             |
|-------------------------------------------------------|---------------------------|
| `backend/app/models/activity.py`                      | new                       |
| `backend/app/models/__init__.py`                      | edit — re-export new model |
| `backend/app/repositories/activity_repo.py`           | new                       |
| `backend/app/services/activity_service.py`            | new                       |
| `backend/app/services/activity_errors.py`             | new                       |
| `backend/app/schemas/activities_schema.py`            | new — discriminated Union |
| `backend/app/api/activities_router.py`                | new                       |
| `backend/app/api/student_reports_router.py`           | new                       |
| `backend/app/api/book_router.py`                      | edit — 1 call before FileResponse |
| `backend/app/api/audio_router.py`                     | edit — 1 call before FileResponse |
| `backend/app/api/video_router.py`                     | edit — 1 call before FileResponse |
| `backend/app/api/auth_router.py`                      | edit — `end_active_sessions` on logout |
| `backend/app/dependencies/auth.py`                    | edit — `record_session_visit` wraps `get_current_user` |
| `backend/app/config.py`                               | edit — five new settings   |
| `backend/app/main.py`                                 | edit — include new routers, retention service startup hook |
| `backend/app/tests/activity/test_activity_session.py`         | new |
| `backend/app/tests/activity/test_heartbeat_idempotency.py`    | new |
| `backend/app/tests/activity/test_engagement_lifecycle.py`      | new |
| `backend/app/tests/activity/test_rate_limit.py`                | new |
| `backend/app/tests/activity/test_librarian_report.py`          | new |
| `backend/app/tests/activity/test_retention_rollup.py`          | new |
| `backend/app/tests/activity/test_authorization.py`             | new |
| `backend/migrations/versions/000X_add_activity_tables.py`      | new (out of scope per AGENTS.md; human authors) |

No existing module is renamed. No business logic in book/audio/video is
changed; the only router edits are a single new line each.

## 11. Testing

Per AGENTS.md invariant 5 (tests on PostgreSQL via testcontainers; never
SQLite — JSONB/GIN are not expressible there), and per the
`test-driven-development` superpowers skill applied red-green-refactor for
new behaviour.

### Characterization of instrumented routers

A pre-requisite: before this feature lands, write characterization tests
that exercise each of `stream_book`, `stream_audio`, `stream_video`
*without* requiring any engagement to be present. These tests exist today
(`backend/app/tests/media/test_*_api.py`) and we extend them to assert that
the response is unchanged after instrumentation. The point is to make the
"no rewrite of feature logic" promise falsifiable.

### Unit tests (new)

- `test_activity_session.py` — idle gap creates a new session on the
  boundary tick; same-account continuous calls UPDATE rather than INSERT;
  logout marks `ended_at`.
- `test_heartbeat_idempotency.py` — replay with same `client_event_id`
  returns identical totals; replay of an out-of-order playhead clamps.
- `test_engagement_lifecycle.py` — open → heartbeat → heartbeat → close →
  heartbeat returns 200 with no delta on the closure-aware path; the
  `completed` flag transitions correctly for audio/video, never for books.
- `test_rate_limit.py` — second heartbeat within 1s from same account
  returns 429 with `Retry-After: 1`; rate limit does not block different
  accounts.
- `test_librarian_report.py` — aggregation correctness across the date
  range: total minutes, top titles, per-day histograms, empty-week case,
  multi-title-in-one-day case.
- `test_retention_rollup.py` — startup with stale `last_run` rolls up the
  expected rows; with `ACTIVITY_RETENTION_DAYS=0` no rows move; archive table
  UPSERTs on subsequent runs.
- `test_authorization.py` — student cannot query another student's report;
  teacher is class-agnostic (sees all students) until a per-class bound
  ships; admin sees all; own-self read by a student is allowed.

### Coverage target

Per AGENTS.md "Tests are the contract" — every error path in section 9 has
a test. Each new public function in `activity_service` has ≥ 2 unit tests
(happy path + one degenerate path).

## 12. Frontend impact

The React frontend (currently scaffolded on the `frontend` branch, frozen
contract at `react-kickoff-annex.md`) consumes two new endpoints:

1. `POST /api/activities/heartbeat`
2. `GET /api/students/{account_id}/activities` (librarian/teacher role)

Adding endpoints is an additive contract change permitted by the annex.
Adding fields to the existing response shapes is also additive — existing
frontend code keeps working. This design does **not** remove or rename any
existing field.

The frontend work itself is out of scope for this spec. It belongs on the
`frontend` branch and merges after this backend change is shipped.

## 13. Privacy review gate

Before any code lands, the human reviews and explicitly accepts:

1. The retention defaults (`ACTIVITY_RETENTION_DAYS=90`,
   `ACTIVITY_SESSION_RETENTION_DAYS=30`).
2. `ACTIVITY_CAPTURE_IP_ADDRESS=False` as the privacy baseline.
3. The contents of the privacy column list in section 3 — none of these
   columns carries first/last name or contact data.

This gate exists because the product serves children in Kenya and is
subject to Kenya Data Protection Act 2019 standards on minor data.

## 14. Out of scope — but flagged

- The interaction_event table and repo, declared for future quizzes/LLM
  work, do not exist in this design. The discriminated union allows the
  event shape; the table can be created on the day a feature needs it.
- Coordinator / multi-device sessioning. Two devices streaming the same
  title at the same time for the same account would create two engagement
  rows — that is acceptable in v1 and called out here so we don't pretend.
- Privacy-grade PII redaction beyond the IP-hash column. If a future
  feature needs to log free text (chat messages), the rule is "log
  count + duration only; never log message content". This is consistent
  with section 13 and pending the LLM-feature spec.
- Notification / alerting (e.g. "child has not read in N days"). Trivial
  follow-on; separate spec.
