# Frontend rules — React + TypeScript + Vite

Applies to everything under `frontend/`. Cross-cutting rules: the root `AGENTS.md`. Stack: React 19, TypeScript (`strict`), Vite, Tailwind, npm.

<!-- .github/workflows/ai-review.yml extracts the section below by heading text:
     sed -n '/^## Frontend Invariants/,/^## Backend Integration/p' frontend/AGENTS.md
     Keep this heading and "## Backend Integration" byte-identical. -->
## Frontend Invariants

Breaking one requires explicit approval, same as the backend invariants.

| # | Invariant |
|---|---|
| F1 | **Verify everything.** Nothing is done until the frontend Definition of Done below has run and passed — locally and in CI (the `frontend` check). |
| F2 | **Tests are the contract.** Every behavior change ships with tests; a bugfix starts with a failing test that reproduces the bug. Never delete or skip a failing test to go green. |
| F3 | **One HTTP path.** All HTTP goes through `src/services/api/`: `apiFetch` in `client.ts` attaches the Bearer token, and one module per entity wraps its endpoints. No `fetch` or other HTTP client anywhere else. |
| F4 | **Frozen contract.** The frontend depends only on the API surface pinned under backend invariant 7 (`backend/AGENTS.md`). To depend on anything else, pin it there in the same PR. |
| F5 | **Client-side gating is UX, never security.** Route and role gating is convenience; the backend `RoleChecker` enforces. Tokens travel only through `apiFetch`; a 401 triggers the re-login flow, not a hidden button. Native media tags authenticate with the `httpOnly` cookie. |
| F6 | **Config centralized, everything TypeScript.** All env and config reads go through `src/config.ts` — typed, validated, and the only reader of `import.meta.env`. No `.js`/`.jsx` app files, the entry point included. No literal API URLs in components. |

## Backend Integration

- **Login:** `POST /api/auth/token` returns `TokenResponse` (`access_token`, `token_type`, `username`, `role`, `first_login`) and sets an `httpOnly`, `samesite=strict` `access_token` cookie. Read `role` from the body; don't decode the JWT.
- **API calls:** `apiFetch` sends `Authorization: Bearer <token>`. An invalid Bearer is never masked by a valid cookie (locked by `backend/app/tests/auth/test_auth_api.py`).
- **Media:** covers are public (`<img src="/static/covers/...">`). Native `<video>`, `<audio>`, and `<embed>` tags can't send headers, so they rely on the cookie: point them straight at the stream and read endpoints. Cookie-only auth stays limited to streams and reads; every state-changing call goes through `apiFetch`.
- **Logout does two things:** call `POST /api/auth/logout` (clears the cookie) and drop the stored token. Skipping either leaves streams authenticated.
- **Errors:** every error body is `{detail}`. Form-field errors show inline, everything else as a toast; 401 → re-login flow; 403 → a visible "insufficient permissions" message, never a silent failure.
- **Lists:** paged endpoints return `Page[T]`; wrappers take page parameters and return `Page<T>`; components never re-implement paging math.

## Naming & Layout

| Thing | Rule |
|---|---|
| Components | `PascalCase`, one per file: `src/components/<area>/<Name>.tsx` (`components/books/BookCard.tsx`) |
| Pages | `src/pages/<Name>.tsx`, routed in `src/App.tsx` |
| Hooks | `src/hooks/use<Name>.ts` |
| Context | `src/context/<Name>Context.tsx` |
| HTTP | `src/services/api/client.ts` (`apiFetch`) plus one module per entity: `src/services/api/<entity>.ts` (F3) |
| API types | `src/types.ts` — shapes of the schemas pinned under backend invariant 7 (F4) |
| Settings | `src/config.ts` — the only env reader (F6) |
| Tests | co-located `*.test.ts(x)`; end-to-end tests in `e2e/` |
| npm scripts | `dev`, `lint`, `build`; new scripts use the names `typecheck`, `test`, `e2e`, `generate-api` |

## Definition of Done

```bash
cd frontend
npm install
npm run lint
npm run build
```

`.github/workflows/ci.yml` (the `frontend` job) is the executable mirror. A PR that adds one of the scripts named in Naming & Layout adds its command here and to the CI job in the same PR.
