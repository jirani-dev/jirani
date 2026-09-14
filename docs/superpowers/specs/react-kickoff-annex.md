# React Kickoff Annex — SPA integration decisions (2026-09-01)

Recorded by the media refactor plan's final task (spec §9). The frontend scaffold
(`frontend/`, TypeScript + Vite) was landed 2026-09-01 and now lives on the
`frontend` branch (moved off this tree in `358bb45`; merged back when the React
track starts). The backend contract below is frozen; React pins to it.

## Topology — same-origin (Option A, locked)

- The single `nginx:80` published port serves both API and SPA. The nginx config
  gains one block — the `frontend/dist` build output mounted into nginx at
  `/srv/frontend`, with `location /` replaced by:

  ```nginx
  location / {
      root /srv/frontend;
      try_files $uri $uri/ /index.html;
  }
  ```

  `/api/`, `/media/`, `/static/covers/` keep precedence (longer-prefix match).
  No CORS surface, no second published port. Backend is *not* restructured for this.

## Token strategy

- Login: `POST /api/auth/token` returns `{access_token, ...}`.
  *(Corrected 2026-09-14 from the plan draft's `/api/auth/login` — the real route
  is `auth_router.py:29`, same correction as Task 9 Step 4's curl.)*
- Token stored in `localStorage`; every API call goes through a fetch wrapper
  adding `Authorization: Bearer <token>`.

## Role gating

- Role decoded from the JWT payload (`RoleChecker` mirrors it on the backend).
  UI routes gate on it client-side as UX — never as security.

## Media access

- `<img src="/static/covers/...">` works natively (covers are public).
- Protected streams (`/api/books/{uid}/stream`, `/api/videos/stream/{id}`):
  native `<video>/<embed>` tags cannot carry the `Authorization` header.
  Interim pattern (a): fetch with the wrapper into a blob URL
  (`URL.createObjectURL`), buffering the whole file client-side.
  Follow-up (b): a short-lived signed query ticket (`?ticket=`) as a later
  backend feature task — decided deliberately when the SPA media work lands,
  not silently.

## Error shape

- UI reads `{detail}` uniformly; the backend error mapping (Invariant 2)
  already guarantees that shape.

## Where things live

- `frontend/` gets its own convention section in `AGENTS.md` (added in the
  same commit as this annex); the backend advisory boundaries stay unchanged.

## Backend contract frozen surface (for the SPA to pin)

- Response schemas: `BookRead` (incl. `cover_url`), `VideoView`, `TagRead`,
  `AuthorRead`/`LevelRead`/`GenreRead`, `Page[T]`.
- Error body shape: `{detail: str}`.
- Auth: Bearer JWT with role claim.
- URL prefixes: `/api/`, `/media/` (internal-only), `/static/covers/` (public).
