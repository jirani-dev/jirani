# Frontend Guide — rules and integration

The React SPA lives in `frontend/` (TypeScript + Vite). All frontend work is
bound by the "Frontend — Binding Invariants & DoD" section of `AGENTS.md` and
the frozen backend contract in §2.1 below. This guide is the long form of the
integration; `AGENTS.md` owns the binding table and the DoD.

## 1. Where the rules live

`AGENTS.md` is the single ruleset for both sides of the stack: backend
invariants 1–6, frontend invariants F1–F6, both Definitions of Done, and both
naming tables. This guide is the long form of the frontend side — integration
patterns, testing policy, tooling — and owns one binding thing of its own: the
frozen backend contract in §2.1. Rules are referenced here by ID (F1–F6);
never forked or restated as a second source.

## 2. Pinned stack & topology

| Concern | Pinned | Notes |
|---|---|---|
| Framework | React 19 | |
| Language | TypeScript, `strict: true` | No `.js`/`.jsx` app files (F6) |
| Build | Vite | |
| Package manager | npm | `package-lock.json` committed, always |
| Unit/component tests | Vitest + Testing Library | HTTP mocked with MSW (§4) |
| E2E | Playwright | |
| Lint/format | ESLint flat config + typescript-eslint (**covers `.tsx`**) + Prettier | no file-type exclusions |
| API client | `openapi-typescript` + `openapi-fetch`, generated | F3 |

Topology is **same-origin, locked**: the single nginx `:80` published port
serves both API and SPA. The nginx config gains one block — the
`frontend/dist` build output mounted into nginx at `/srv/frontend`, with
`location /` replaced by:

```nginx
location / {
    root /srv/frontend;
    try_files $uri $uri/ /index.html;
}
```

`/api/`, `/media/`, `/static/covers/` keep precedence (longer-prefix match).
No CORS surface, no second published port; the backend is *not* restructured
for this. In development, `npm run dev` uses the Vite dev-server proxy for
`/api/` and `/static/` to the backend — same-origin semantics preserved.

### 2.1 Frozen backend contract

This surface binds **backend work on every branch**: response shapes may gain
fields, never lose or rename them. A change that removes or renames anything
below requires explicit approval and a same-PR frontend impact note.

- Response schemas: `BookRead` (incl. `cover_url`), `VideoRead`, `TagRead`,
  `AuthorRead`/`LevelRead`/`GenreRead`, `Page[T]`.
- Error body shape: `{detail: str}`.
- Auth: Bearer JWT with role claim; `httpOnly` `access_token` cookie fallback
  for header-less requests (native media tags — PR #42, `1e22cee`).
- URL prefixes: `/api/`, `/media/` (internal-only), `/static/covers/`
  (public).
- Login route: `POST /api/auth/token` (not `/api/auth/login`).
- Logout: `POST /api/auth/logout` — unauthenticated; its only job is clearing
  the cookie (`backend/app/api/auth_router.py:64-77`).

## 3. Backend integration

### 3.1 Codegen workflow

The backend serves its OpenAPI schema at `/openapi.json`. The client is
generated, never hand-written (F3):

```bash
npm run generate-api   # openapi-typescript → src/api/generated/
```

- `src/api/generated/**` is machine output: never hand-edited, always
  committed, regenerated in the same PR that changes the backend surface.
- A regeneration diff **is** the contract review: fields may be added; a diff
  that removes or renames a field requires explicit approval in that PR (F4,
  §2.1).
- CI drift gate: `npm run generate-api && git diff --exit-code src/api/generated`.

Domain code never calls `openapi-fetch` directly — thin wrappers in
`src/api/<entity>.ts` (e.g. `books.ts`) expose typed functions over the
generated client; components and hooks import the wrappers.

### 3.2 Auth — dual channel

Login `POST /api/auth/token` does two things at once
(`backend/app/api/auth_router.py:30-61`):

1. Returns `TokenResponse{access_token, token_type, username, role,
   first_login}` in the body.
2. Sets an `httpOnly`, `samesite=strict` `access_token` cookie
   (`auth_router.py:44-53`).

**Channel 1 — Bearer (all API calls).** The SPA stores `access_token` from the
response body; the generated client's fetch wrapper attaches
`Authorization: Bearer <token>` to every request. Header precedence is
test-locked on the backend: an invalid Bearer is never masked by a valid
cookie (`backend/app/tests/auth/test_auth_api.py:271`).

**Channel 2 — cookie (native media tags only).** `<video>/<audio>/<embed>` src
requests cannot carry custom headers; the browser attaches the `httpOnly`
cookie automatically on same-origin requests, and `get_current_user` falls
back to it when no header is present
(`backend/app/dependencies/auth.py:27-29`; rationale comment `auth.py:13-18`).
Cookie-only auth stays confined to what native tags need — streams and reads.
All state-changing calls go through the wrapper with Bearer. The cookie is
`samesite=strict`; Bearer-first keeps CSRF off the table entirely.

**Role.** Read `role` from the login response body — no JWT decoding needed.
Client-side route/role gating is UX, never security (F5): the backend
`RoleChecker` enforces; the SPA reacts to 401/403 with the re-login flow.

**Logout is dual — gotcha.** `POST /api/auth/logout` clears the cookie
(`auth_router.py:64-77`) but knows nothing about localStorage. SPA logout must
do **both**: call the endpoint *and* drop the stored token — otherwise
native-tag streams stay authenticated after "logout". On the must-test list
(§4).

### 3.3 Media

- Covers are public: `<img src="/static/covers/...">`, no auth.
- Protected streams and reads authenticate via the cookie channel (§3.2):
  point native tags straight at `/api/books/{uid}/stream`,
  `/api/videos/stream/{id}`, the audio stream endpoints, and book reads.
  Cookie-only auth on these routes is test-locked
  (`backend/app/tests/media/test_media_stream.py:92` video, `:196` audio;
  `backend/app/tests/media/test_book_api.py:473` stream, `:708` read).

### 3.4 Errors & pagination

- Every error body is `{detail: str}` (§2.1; backend invariant 2 guarantees
  it). One mapping rule set: form-field errors inline, everything else toast;
  401 anywhere → re-login flow; 403 → a visible "insufficient permissions"
  surface, never a silent swallow.
- Paged lists are `Page[T]` (§2.1). Wrapper functions accept page parameters
  and return `Page<T>`; components never re-implement paging math.

## 4. Testing policy

Tests are the contract (F2), mirroring backend invariant 5:

- **Vitest + Testing Library** for components and hooks. HTTP is mocked at
  the routes the generated client calls (MSW) — unit/component tests never
  need a live backend.
- **Playwright** for E2E critical flows: login, library list, protected
  stream playback, logout.
- A bugfix starts with a failing test reproducing the bug (F2). Never delete
  or skip a failing test to go green.
- **Must-test list** (non-negotiable for the first frontend PRs):
  - the auth wrapper attaches Bearer on every API call;
  - 401 handling triggers the re-login flow — no silent cookie fallback;
  - dual logout: endpoint called **and** stored token dropped;
  - native-tag stream playback against a protected endpoint (cookie channel);
  - role gating: UI hides, backend still enforces (a gated route fetched
    directly must 403);
  - `{detail}` error mapping and `Page[T]` pagination rendering.

## 5. Tooling policy

- ESLint flat config with `typescript-eslint`; `.tsx` **included** — no
  file-type exclusions. No per-file disables without a linked reason.
- Prettier for formatting; no formatting debates in review.
- `tsconfig.json` with `strict: true` (pinned). `noUncheckedIndexedAccess`
  and `exactOptionalPropertyTypes` are proposed defaults for the first
  frontend spec to confirm or relax.
- Canonical npm script names — the DoD depends on them: `dev`, `lint`,
  `typecheck`, `test`, `build`, `generate-api`, `e2e`.
- CI runs the frontend DoD on any PR touching `frontend/` — wired when the
  scripts exist to run.

## 6. Definition of Done

`AGENTS.md` is the single owner — see "Frontend — Binding Invariants & DoD"
there. Do not fork the command list into this file.

## 7. Deferred to the first frontend spec

Explicitly **not** decided here (YAGNI):

- Server-state library (e.g., TanStack Query vs context + hooks).
- UI kit — pick exactly **one**.
- Component architecture beyond the pinned naming table (e.g.,
  storybook-or-not).
- Config-validation mechanism for `src/config.ts` (F6 requires *validated*,
  not a specific library).
