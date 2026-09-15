# Stream Ticket Auth — SPA media access decision (2026-09-15)

Status: **decided** (design record, not a gate). Resolves the follow-up deliberately
deferred in `react-kickoff-annex.md` §Media access, option (b). Supersedes the annex's
interim blob-URL pattern as the recommended mechanism; blob remains functional
(Bearer path on stream routes is unchanged).

## Problem

Native `<video>`/`<audio>`/`<embed>` tags cannot carry an `Authorization` header, so
the auth-gated streams (`/api/books/{uid}/stream`, `/api/videos/stream/{id}`,
`/api/audio/stream/{id}`) are unreachable by plain media elements. The annex's
interim pattern — fetch with the wrapper into `URL.createObjectURL` — buffers the
whole file in browser memory before playback and provides no native Range/seek.

## Decisions

1. **Mechanism: signed query ticket (option b), uniform across all three media
   types.** Chosen over blob-only and over the hybrid (blob for books, ticket for
   A/V). One mechanism, one dependency, three near-identical mint endpoints; books
   additionally gain progressive PDF rendering and avoid 50MB in-memory blobs.
2. **Ticket lifetime: ~10 minutes, no SPA retry logic required.** Chosen over
   60–120s (annex's example; breaks on seeks past expiry without SPA re-mint/resume
   logic) and over 30min (longer leak window than needed). Covers realistic
   classroom pause/seek windows; tickets appear in nginx access logs, and 10 min is
   the accepted leak window on an offline LAN kiosk. SPA re-mint-on-stall logic may
   be added later if field experience demands shorter TTLs.

## Flow

1. **Mint:** SPA calls the resource's ticket route (exact paths in the table
   below; note the book route's shape is `/api/books/{book_uid}/stream/ticket`)
   with the normal Bearer token. The route sits behind the existing
   `RoleChecker(ROLES)` (read roles: admin/teacher/student), verifies existence
   via the service's existing `resolve_stream()` (same 404 mapping as the stream
   route), and returns `200 StreamTicket`.
2. **Play:** SPA sets the media element's `src` to the server-composed
   `stream_url` (`/api/<resource>/stream/{id}?ticket=<jwt>`). No `Authorization`
   header is sent by the browser.
3. **Verify-then-stream:** the stream route's dependency is dual-mode — Bearer if
   present (today's path; blob URLs, curl, and existing characterization tests keep
   working), else verify `?ticket=`. On success the handler proceeds to
   `svc.resolve_stream()` → 204 + `X-Accel-Redirect`, exactly as today. Containment
   (`is_relative_to` in the storage `resolve()`) and role gating (at mint time) are
   preserved structurally — the ticket path funnels through the same service code.
4. nginx serves `/media/...` natively (Range support, progressive playback,
   seeking). No blob buffering.

## Ticket format & security

- **Ticket = JWT**, HS256, signed with the existing `settings.SECRET_KEY` via the
  existing `jose` machinery (`auth_service.py`). Stateless: no DB table, no
  migration. TTL is the revocation story; there is no revocation list — deliberate.
- **Claims:** `{aud: "stream", kind: "book"|"video"|"audio", rid: "<uid-or-id>", iat, exp}`.
  **No `sub` claim, deliberately:** `get_current_user` rejects tokens without `sub`
  (`dependencies/auth.py`), so a leaked ticket cannot be replayed as a Bearer token
  against the rest of the API. Conversely, login access tokens lack
  `aud`/`kind`/`rid`, so they fail ticket verification. Both abuse directions are
  closed by claim shape alone.
- **Verification:** signature, `exp`, `aud == "stream"`, and `kind`/`rid` matching
  the actual path parameters (a video ticket cannot stream audio; a ticket for
  video 3 cannot stream video 4).
- **Multi-use within TTL** — no one-time-use, no `jti`. Browsers issue many Range
  requests per playback; one-time-use would break seeking.
- **The ticket is a capability:** it carries no role; anyone holding it within the
  TTL may stream that one resource. Standard signed-URL model; role enforcement
  happens at mint time.

## API surface (additive only — frozen contract respected)

| Endpoint | Auth | Success | Errors |
|---|---|---|---|
| `POST /api/books/{book_uid}/stream/ticket` | `RoleChecker(ROLES)` | `200 StreamTicket` | 401/403 auth, 404 unknown book |
| `POST /api/videos/stream/{video_id}/ticket` | `RoleChecker(ROLES)` | `200 StreamTicket` | 401/403 auth, 404 unknown video |
| `POST /api/audio/stream/{audio_id}/ticket` | `RoleChecker(ROLES)` | `200 StreamTicket` | 401/403 auth, 404 unknown audio |

- **POST, not GET** — minting a credential must not be cacheable; same convention
  as `POST /api/auth/token`.
- **`StreamTicket { ticket: str, stream_url: str, expires_in: int }`** — new schema
  in a new `app/schemas/stream_schema.py`. `stream_url` is composed server-side:
  the SPA stays dumb and the query-param name remains server-owned.
- **Stream routes change one dependency:** `RoleChecker(ROLES)` →
  `StreamRoleChecker(ROLES, kind=..., id_param=...)`, a new class in
  `dependencies/auth.py` returning `Account | None` (`None` on the ticket path — no
  `sub`, no DB load). None of the three stream handlers use `user` beyond the gate,
  so this is safe.
- **Error mapping (Invariant 2):** no credential (no Bearer, no ticket) → 401;
  presented-but-unacceptable ticket (expired, bad signature, kind/rid mismatch) →
  403; unknown resource → 404. Same rule, same status on all three endpoints.
- **New setting:** `STREAM_TICKET_EXPIRE_MINUTES: int = 10` in `config.py`.
- **Out of scope (YAGNI):** `/api/books/{uid}/read` (derived-PDF) — the SPA reader
  can XHR it with Bearer; it can gain its own ticket later if needed.

## nginx: no change

The ticket rides the query string of the `/api/` request; verification completes in
FastAPI before the 204; the X-Accel target (`/media/...`) is computed server-side
and carries no ticket; `/media/` stays `internal`. Residual: nginx access logs
record `?ticket=...` lines — accepted with the 10-min TTL; optional `log_format`
scrubbing is future human-owned nginx hardening, not part of this design.

## Invariant compliance

1. **Layering** ✓ — sign/verify live in `AuthService` + a dependency; routers only
   map errors.
2. **Error mapping** ✓ — 401/403/404 table above, uniform across endpoints.
3. **No CWD-relative I/O** ✓ — none added.
4. **SQLAlchemy 2.0** ✓ — no models touched.
5. **Tests on testcontainers PostgreSQL, TDD** ✓ — red-first; see test plan.
6. **Naming** ✓ — `StreamTicket`, `StreamRoleChecker` (PascalCase, no underscores);
   `stream_schema.py` module.

## Test plan (TDD, red first)

- Mint: 200 + `StreamTicket` shape; 404 unknown resource; 403 wrong role; 401 no
  auth.
- Dual-auth stream: Bearer still works (characterization); valid ticket works;
  missing credential → 401.
- Abuse: ticket-as-Bearer rejected by `get_current_user`; access-token-as-ticket
  rejected; expired ticket → 403; kind mismatch → 403; rid mismatch → 403.
- `stream_url` composition asserted (path + `?ticket=`).

## Implementation touch-list (blast radius)

- `app/dependencies/auth.py` — add `StreamRoleChecker`; `get_current_user`
  untouched.
- `app/services/auth_service.py` — add ticket sign/verify helpers.
- `app/api/book_router.py`, `video_router.py`, `audio_router.py` — one new route
  each + one `Depends` swap on the stream route.
- `app/schemas/stream_schema.py` — new module, `StreamTicket`.
- `app/config.py` — add `STREAM_TICKET_EXPIRE_MINUTES: int = 10`.
- `app/tests/` — new tests per the plan above (media + auth areas).

No existing caller changes behavior. No migration. No nginx change. No dependency
additions (`jose` already present).

## Next step

Implementation plan (separate session, TDD binding):
`docs/superpowers/plans/2026-09-16-stream-ticket-auth-plan.md` — then PR-only into
`refactor` per branch protection. The SPA media components are a further separate
effort on the `frontend` branch, pinning to this design.
