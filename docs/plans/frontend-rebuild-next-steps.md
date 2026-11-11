# Frontend Rebuild — Next Steps, Team Plan, and Agent Handoff

**Purpose:** the team's committed plan for the frontend rebuild and a cold-start handoff for
any agent picking up after PR #58. Issue #54 is the original design record this plan grew
from; this file is the current source of truth and is updated as scope changes.

**Verified against:** `master` @ `f87578f`, 2026-11-03. Re-verify before acting — the state
below can drift.

Binding rules live in the root `AGENTS.md`, `frontend/AGENTS.md`, and `backend/AGENTS.md`.
This file is the spec + orientation, not a substitute; where it conflicts with those files,
they win.

---

## 1. Verified current state

| Fact | Value |
|---|---|
| Branch | `master`, clean, up to date with `origin/master` |
| HEAD | `f87578f` — merge of PR #58 (rebuild 2/4) |
| Post-merge CI | run `40972561765`: `quality` ✓, `frontend` ✓, `docker-build` ✓ |
| Frontend DoD | `lint` clean, `typecheck` clean, **36 tests / 11 files**, `build` ✓ (3.47 s) |
| TanStack Query | **not installed** |
| Blob media path | **still present** (`useVideoStream`, `useAudioStream`, `streamVideo`, `streamAudio`) |
| Guest button | **still present** (`Home.tsx`) |
| PR 3 plan | **does not exist** — this document is the spec + handoff |

Merged branches still present locally and remotely: `frontend-harness`,
`frontend-auth-hardening`. Safe to delete.

---

## 2. Spec — issue #54, remaining scope

Issue: <https://github.com/jirani-dev/jirani/issues/54>
Title: *Frontend rebuild: harden v1 in place to F1–F6 — design + PR sequence*.

### 2.1 Why in-place hardening, not a rewrite

v1 lives in-tree at `frontend/` — identical to tag `archive/frontend-v1`, updated through
2026-09-21 including the `1e22cee` streaming fix. `frontend/AGENTS.md` F3 mandates the
hand-written `src/services/api/` + `apiFetch` pattern — v1's own architecture. A from-zero
rewrite would re-derive the same design and API layer at 2–3× the cost of hardening what
exists. PR 1 (harness + hygiene) and PR 2 (auth/error hardening) have landed; PR 3 and PR 4
are what remain.

### 2.2 Locked decisions that constrain PR 3/4

- **TanStack Query** for server state — replaces the hand-rolled `refresh()` patterns (PR 3).
- **Tailwind only.** Bootstrap/react-bootstrap were phantom deps (zero imports) — purged.
- **tsconfig:** `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- **zod** validates `src/config.ts` (F6 "typed, validated"). **No Storybook** (YAGNI).
- **Decision A — drop dead dark-theme code:** `pages/Video.tsx` + `/video` route; six
  zero-importer components; `hooks/useBooks.ts`; `utils/formatters.js`; unreferenced assets.
  Landed in PR 1. Blob-stream hooks stayed until PR 3 replaces their consumers.
- **Decision B — drop the "Continue as Student" guest button:** it navigates unauthenticated
  to `/library`, where every fetch 401s (all list endpoints are `RoleChecker`-gated, e.g.
  `backend/app/api/book_router.py:105-107`) → re-login bounce loop under F5. Login is the only
  entry (PR 3).
- **Prettier deferred:** not mandated by `frontend/AGENTS.md`; a whole-tree reformat is diff
  churn with no rule behind it.

### 2.3 PR 3 — media + server state (verbatim scope)

> - Native `<video>/<audio>` tags pointed straight at stream endpoints (cookie channel);
>   delete `useVideoStream`/`useAudioStream` + `streamVideo`/`streamAudio` blob fetchers
> - TanStack Query: queries/mutations/invalidations replace `refresh()`; remove guest button
>   (Decision B)

### 2.4 PR 4 — E2E + deployment (verbatim scope)

> - Playwright `e2e/`: login, library list, protected stream playback, logout; adds `e2e`
>   script → DoD/CI extended in the same PR
> - Hex → Tailwind-token cleanup pass (light "Offlib" palette becomes the token set;
>   `tailwind.config.js` dark tokens replaced)
> - **Human-applied paste-ready diffs** (agent no-edit zone): nginx `location /` → SPA root +
>   `try_files`; proxy blocks for `/openapi.json`, `/docs`, `/redoc` (they ride the catch-all
>   today and would otherwise be shadowed); cache split (hashed `/assets/` immutable,
>   `index.html` no-cache); optional gzip; compose nginx volume
>   `./frontend/dist:/srv/frontend:ro`
> - Decide backend CORS fate (`backend/app/main.py:39-45`): with the dev proxy in place, the
>   `:5173` allow-origin serves only the documented containerless-dev override — keep or remove
>   deliberately

### 2.5 Verification contract (verbatim)

> Every PR: frontend DoD green locally **with pasted output**, `review` agent pass, CI green
> (`quality`, `docker-build`, `ai-review`, `frontend`).

Per-PR implementation plans belong in gitignored `docs/superpowers/plans/` (use
`superpowers:writing-plans`, then `executing-plans` or `subagent-driven-development`). This
document is the committed team plan; the superpowers plans are the disposable working detail.

---

## 3. Next step — PR 3 of 4: media + server state

**Branch:** `frontend-media-server-state`, from `master` @ `f87578f`.

**Dependency (already approved):**

```bash
cd frontend
npm install @tanstack/react-query@^5
```

`package.json` / `package-lock.json` are human-owned; `npm install` is the only allowed way to
change them. Never hand-edit the lockfile. Do not add any other dependency.

### Task 1 — Native media tags on the cookie channel

The backend already accepts the `access_token` cookie when no `Authorization` header is present
(`backend/app/dependencies/auth.py:22-29`). Native media tags cannot set headers, so point
them straight at the stream endpoints.

**Fix the latent URL bug first.** `getAudioStreamUrl` is missing the `/api` prefix:

```ts
// frontend/src/services/api/audio.ts:7-9 — current, wrong
export function getAudioStreamUrl(id: Audio['id']): string {
    return `${BASE}/stream/${id}`;          // → /audio/stream/{id}
}

// target
import API_BASE from '../../config';
export function getAudioStreamUrl(id: Audio['id']): string {
    return `${API_BASE}${BASE}/stream/${id}`; // → /api/audio/stream/{id}
}
```

`getVideoStreamUrl` is already correct (`frontend/src/services/api/videos.ts:8-10`).

**Replace the blob hooks:**

| File | Change |
|---|---|
| `frontend/src/components/video/VideoPlayerModal.tsx` | drop `useVideoStream`; `<source src={getVideoStreamUrl(video.id)} />` |
| `frontend/src/components/video/VideoGridCard.tsx` | drop `useVideoStream`; `<source src={`${getVideoStreamUrl(video.id)}#t=1`} />` |
| `frontend/src/components/audio/AudioGridCard.tsx` | drop `useAudioStream`; `<source src={getAudioStreamUrl(audio.id)} />` |

**Delete dead code:**

- `frontend/src/hooks/useVideoStream.ts`
- `frontend/src/hooks/useAudioStream.ts`
- `streamVideo` in `frontend/src/services/api/videos.ts:12-16`
- `streamAudio` in `frontend/src/services/api/audio.ts:11-15`

**Tests (write first, expect red):**

- `frontend/src/components/video/VideoPlayerModal.test.tsx` — `<source>` `src` is
  `/api/videos/stream/{id}` (not a `blob:` URL).
- `frontend/src/components/video/VideoGridCard.test.tsx` — `src` is
  `/api/videos/stream/{id}#t=1`.
- `frontend/src/components/audio/AudioGridCard.test.tsx` — `src` is
  `/api/audio/stream/{id}`. This test is what pins the `/api` fix.

**Verify:** `rg "useVideoStream|useAudioStream|streamVideo|streamAudio|createObjectURL" frontend/src`
returns nothing outside tests.

### Task 2 — Remove the guest button (Decision B)

`frontend/src/pages/Home.tsx:61-72` renders an `or` divider and a **Continue as Student**
button that calls `navigate("/library")` unauthenticated. Every list endpoint is role-gated, so
the page 401s and PR 2's re-login flow bounces the user back to `/` — a loop.

- Remove the divider and the button block entirely.
- Keep `useNavigate` — `handleLogin` still uses it (`Home.tsx:26`).
- Adjust the card's bottom padding (`pb-5` → `pb-7` on the login section) so the card does not
  look truncated.
- Test: `frontend/src/pages/Home.test.tsx` renders `Home` inside `MemoryRouter` +
  `AuthProvider` and asserts `queryByRole('button', { name: /continue as student/i })` is null.

### Task 3 — TanStack Query replaces `refresh()`

**Provider.** In `frontend/src/main.tsx`, wrap the tree:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
```

**Hooks.** Replace the `useState` + `useEffect` + `refresh()` bodies; export stable keys for
invalidation:

```ts
// frontend/src/hooks/useVideos.ts
import { useQuery } from '@tanstack/react-query';
import * as videosApi from '../services/api/videos';

export const videoKeys = { all: ['videos'] as const };

export function useVideos() {
    return useQuery({ queryKey: videoKeys.all, queryFn: videosApi.fetchVideos });
}
```

```ts
// frontend/src/hooks/useAudio.ts
export const audioKeys = { all: ['audio'] as const };
export function useAudio() {
    return useQuery({ queryKey: audioKeys.all, queryFn: audioApi.fetchAudioTracks });
}
```

```ts
// frontend/src/hooks/useBookSearch.ts
export const bookKeys = {
    all: ['books'] as const,
    tags: ['books', 'tags'] as const,
    search: (tags: string[], title: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
        ['books', 'search', tags, title, page, size] as const,
};

export function useBookSearch(tags: string[], title: string, page = 1, size = DEFAULT_PAGE_SIZE) {
    return useQuery({
        queryKey: bookKeys.search(tags, title, page, size),
        queryFn: () => booksApi.searchBooks({ tags, title, page, size }),
    });
}

// New: the unfiltered tag source. `bookKeys.all` invalidation covers this key too.
export function useBookTags() {
    return useQuery({
        queryKey: bookKeys.tags,
        queryFn: () => booksApi.searchBooks(),
    });
}
```

**Library.** `frontend/src/pages/Library.tsx` currently destructures
`{ books, refresh, setBooks }` etc. (`:49-52`), fetches everything in a `useEffect` (`:61-68`),
and calls `refreshBooks/refreshVideos/refreshAudio/refreshBookTags` plus `setBooks/setVideos/`
`setAudioTracks` after uploads, edits, and deletes (`:220-267`).

- Read query results: `const { data: booksPage, isLoading: booksLoading } = useBookSearch(...)`,
  `const books = booksPage?.items ?? []`; same pattern for videos/audio.
- `loading` becomes `booksLoading || videosLoading || audioLoading` (no `useEffect` needed).
- `bookTagsList` becomes `useMemo(() => uniqueTags(bookTagsPage?.items ?? []), [bookTagsPage])`
  fed by `useBookTags()`.
- Replace every `refresh*` / `set*` call with
  `queryClient.invalidateQueries({ queryKey: <entityKeys>.all })`.
  `bookKeys.all` (`['books']`) is prefix-matched, so it also invalidates `bookKeys.tags`.
- Keep the card callback signatures (`onDelete`, `onUpdate`, `onEdit`) unchanged; only the
  parent's implementation changes. Do not move mutations into the cards in this PR.
- Remove the now-unused `booksApi` import from `Library.tsx`.

**Tests (F2).**

- New hook tests with `renderHook` + a `QueryClientProvider` wrapper (retry disabled) + MSW:
  - `frontend/src/hooks/useVideos.test.ts` — fetches `GET /videos/`; data reaches `result.current.data`.
  - `frontend/src/hooks/useAudio.test.ts` — fetches `GET /audio/`.
  - `frontend/src/hooks/useBookSearch.test.ts` — fetches `GET /books/?limit=100&offset=0` and
    `useBookTags` uses the unfiltered query.
- Update `frontend/src/pages/Library.test.tsx`:
  - mocks must return the query shape (`{ data, isLoading: false }`) and export the keys the
    component imports (`bookKeys`, `videoKeys`, `audioKeys`);
  - wrap the render in `QueryClientProvider` (with `retry: false`), because `Library` calls
    `useQueryClient`;
  - keep both role-gating assertions unchanged.

### PR 3 gate

```bash
cd frontend
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

Then dispatch the local reviewer on the branch vs `master` **with `model: opencode-go/kimi-k3`**
(the default `opencode/kimi-k3` can fail with "Insufficient account funds"). Expected:
`VERDICT: DONE`. If `NOT DONE`, fix and re-run; do not push on a `NOT DONE`.

PR body must contain: `Design: #54 (PR 3 of 4)`, the five-command DoD output, a note that the
audio stream URL now carries `/api`, and that the guest button was removed per Decision B.

CI must be green on all four: `quality`, `docker-build`, `ai-review`, `frontend`. Merge requires
a PR and one approving review (author is `tuanlearntodev`; ruleset allows OrganizationAdmin
bypass, used for #57/#58).

---

## 4. After PR 3 — PR 4 of 4: E2E + deployment

Do **not** start PR 4 before PR 3 merges. Scope is §2.4 above; translation to tasks:

**Playwright E2E** (`frontend/e2e/`): login, library list, protected stream playback, logout.
Adding the `e2e` script means extending both `frontend/AGENTS.md` DoD and the `frontend` job in
`.github/workflows/ci.yml` **in the same PR** (repo rule).

**Tailwind-token cleanup:** replace the ad-hoc hex palette with the light "Offlib" tokens in
`frontend/tailwind.config.js` and sweep the `[#...]` arbitrary values out of components.

**Human-applied diffs (agent no-edit zone — propose complete, paste-ready diffs in chat):**

- nginx `location /` → SPA root + `try_files`;
- proxy blocks for `/openapi.json`, `/docs`, `/redoc` (today they ride the catch-all and would
  be shadowed);
- cache split: hashed `/assets/` immutable, `index.html` no-cache; optional gzip;
- `docker-compose.yml` nginx volume `./frontend/dist:/srv/frontend:ro`.

**Decide deliberately:** backend CORS (`backend/app/main.py:39-45`) — with the Vite dev proxy,
`http://localhost:5173` serves only the documented container-less override; keep or remove and
record why.

---

## 5. Housekeeping / open items

- Delete merged branches `frontend-harness` and `frontend-auth-hardening` (local + remote) once
  convenient.
- Issue **#56** (F1/F2/F4) is probably closable now — verify against landed PRs before closing.
  Issues **#46/#49** are likely superseded by #54.
- Ruleset drift: live ruleset has an OrganizationAdmin bypass while
  `.github/rulesets/protected-branches.json` says `bypass_actors: []`. Reconcile deliberately —
  either update the file or remove the bypass.
- `docs/superpowers/plans/` stays gitignored by design; `docs/plans/frontend-rebuild-next-steps.md` is the
  committed team plan. Issue #54 remains the original design context.

---

## 6. Known pitfalls

| Pitfall | Detail |
|---|---|
| Audio stream URL | `getAudioStreamUrl` omits `/api` (`audio.ts:7-9`); native tags would bypass the proxy. Fixed + pinned in PR 3. |
| Dead code | `getBookStreamUrl` (`books.ts:10-12`) has no importers and the same missing-prefix shape. Delete it in PR 3 or PR 4; do not wire it up blindly. |
| `isGuest` | Exposed by `AuthContext` (`AuthContext.tsx:70,73`) but only referenced by `AuthContext.test.tsx`. Removing the guest button does not make it dead in the type contract — leave it. |
| Forgot password | `Home.tsx:57` is an intentional no-op ("no backend route yet"). Out of scope. |
| Bundle size | `vite build` warns the main chunk is 746 kB (gzip 217 kB). Pre-existing; PR 4 may code-split, but it is not a PR 3 gate. |
| Test count | Starts at 36/11. Update this number in the PR body rather than asserting an outdated total. |
| `npm install` output | `npm notice` lines are noise; filter them when pasting DoD output. |
| Local reviewer model | Dispatch `review` with `model: opencode-go/kimi-k3` (same model CI uses). |
| ai-review flake | If `ai-review` dies inside `opencode run` with no audit output, re-run the failed job: `gh run rerun <id> --failed`. |

---

## 7. Cold-start checklist

- [ ] `git fetch --prune && git switch master && git pull --ff-only`
- [ ] Confirm `git log -1` is the expected merge commit
- [ ] `graphify update .` (or `graphify query ...`) before code reading
- [ ] Read root `AGENTS.md`, `frontend/AGENTS.md`, and §2 of this file
- [ ] `npm install @tanstack/react-query@^5` (approved; asks for confirmation)
- [ ] Create branch `frontend-media-server-state`
- [ ] Write PR 3 plan in `docs/superpowers/plans/` with `superpowers:writing-plans`
- [ ] Execute tasks 1–3 test-first, one commit per task
- [ ] Run the five-command DoD; paste the output
- [ ] `@review` (model `opencode-go/kimi-k3`) → `VERDICT: DONE`
- [ ] Push, open PR 3/4, watch `quality`, `docker-build`, `ai-review`, `frontend`
- [ ] After merge: write the PR 4 plan; do not start it early
