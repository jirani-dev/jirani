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
| F3 | **One HTTP path.** The generated client is the only HTTP path: `src/api/client.ts` builds it from `src/api/generated/` on the transport in `src/services/api/client.ts`, which attaches the Bearer token. One module per entity in `src/services/api/` wraps its endpoints; components and hooks import those wrappers, never the generated client. No `fetch` or other HTTP client anywhere else. `src/api/generated/` is never edited by hand — `npm run generate-api` writes it. |
| F4 | **Frozen contract.** The frontend depends only on the API surface pinned under backend invariant 7 (`backend/AGENTS.md`). To depend on anything else, pin it there in the same PR. |
| F5 | **Client-side gating is UX, never security.** Route and role gating is convenience; the backend `RoleChecker` enforces. Tokens travel only through the generated client's transport; a 401 triggers the re-login flow, not a hidden button. Native media tags authenticate with the `httpOnly` cookie. |
| F6 | **Config centralized, everything TypeScript.** All env and config reads go through `src/config.ts` — typed, validated, and the only reader of `import.meta.env`. No `.js`/`.jsx` app files, the entry point included. No literal API URLs in components. |

## Backend Integration

- **Login:** `POST /api/auth/token` returns `TokenResponse` (`access_token`, `token_type`, `username`, `role`, `first_login`) and sets an `httpOnly`, `samesite=strict` `access_token` cookie. Read `role` from the body; don't decode the JWT. While `first_login` is true the account still has its temporary password: the library asks for a new one (`POST /api/auth/change-password`) before anything else.
- **API calls:** the generated client sends `Authorization: Bearer <token>`. An invalid Bearer is never masked by a valid cookie (locked by `backend/app/tests/auth/test_auth_api.py`).
- **Media:** covers are public (`<img src="/static/covers/...">`). Native `<video>`, `<audio>`, and `<embed>` tags can't send headers, so they rely on the cookie: point them straight at the stream and read endpoints. Cookie-only auth stays limited to streams and reads; every state-changing call goes through the generated client.
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
| HTTP | `src/api/generated/` (`openapi.json` and `schema.d.ts`, generated), `src/api/client.ts` (the typed client), `src/services/api/client.ts` (transport and `ApiError`), plus one wrapper module per entity: `src/services/api/<entity>.ts` (F3) |
| API types | `src/types.ts` — derived from the generated schema, never hand-written; only shapes pinned under backend invariant 7 (F4) |
| Settings | `src/config.ts` — the only env reader (F6) |
| Tests | co-located `*.test.ts(x)`; end-to-end tests in `e2e/` |
| npm scripts | `dev`, `lint`, `build`, `typecheck`, `test`, `generate-api`; new scripts use the name `e2e` |
| Codegen tooling | `tools/api-codegen/` — its own `package.json` and lockfile, because `openapi-typescript` needs TypeScript 5 and the app is on TypeScript 7 |

## Definition of Done

```bash
cd frontend
npm install
npm run lint
npm run typecheck
npm run test
npm run generate-api && git diff --exit-code src/api/generated
npm run build
```

`generate-api` dumps the backend's OpenAPI document (it needs `uv` and the backend environment, not a running server or database) and regenerates the types from it. A diff means a route or schema changed: commit the regenerated files with the change.

`.github/workflows/ci.yml` (the `frontend` job) is the executable mirror. A PR that adds one of the scripts named in Naming & Layout adds its command here and to the CI job in the same PR.
