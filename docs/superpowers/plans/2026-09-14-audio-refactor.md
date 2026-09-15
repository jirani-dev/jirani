# Audio Module Refactor Implementation Plan (2026-09-14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the audio module to the same invariant shape the 2026-09-01 media refactor gave books/videos/tags — service layer (Inv 1), SQLAlchemy 2.0 (Inv 4), full test suite (Inv 5), naming (Inv 6) — fixing the delete-missing 500, the partial-commit upload, the uncontained Python stream, and the zero-auth endpoints, under characterization pins.

**Architecture:** Identical to the media plan's Task 8 (video fused rewrite): the shared leaves (`media_errors.py`, `media_validator.py`, `MediaFileStorage`) are reused, not duplicated; audio gets a thin `AudioService` over a 2.0 `select()` `AudioRepo`, with the router reduced to HTTP translation — `RoleChecker` on every endpoint, `X-Accel-Redirect` stream (204 + headers, nginx's `/media/` internal alias serves the bytes with no config change), error mapping in the router only. Tag logic moves to the existing `TagRepo.get_or_create_by_names`; the orphan sweep gains audio awareness (a live cross-media bug — see Task 2).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (testcontainers for tests), Alembic, uv, pytest/httpx, ruff, mypy.

**Governing precedent:** the 2026-09-01 media refactor plan (`2026-09-01-media-refactor-nginx-entities.md` — Task 8 is the direct template) and the recovered audio tasks from the superseded `2026-08-26-audio-video-tag-refactor.md` (in git history at `4baddc7`; its RFC 7233 Range table is **superseded** by the X-Accel decision and its soft-delete interfaces are **superseded** by the hard-delete amendment below).

## Locked decisions (user, 2026-09-14)

1. **Stream = X-Accel-Redirect** (media parity). Redirect URI `/media/audio/{quote(name)}` — resolves through the existing nginx `internal /media/` alias to `uploads/audio/` with zero nginx config. Legacy Python `StreamingResponse` and the old plan's RFC 7233 Range table die. `Accept-Ranges: bytes` still emitted (nginx owns Range).
2. **Hard delete** (video parity, 2026-09-14 amendment): `Audio.deleted_at` column **dropped** (Alembic migration), `AudioRepo.delete` (missing id → `MediaNotFound`), router `DELETE` → `204` empty, `list_all` replaces `list_active`, the stream-soft-deleted quirk pin dies with the column.
3. **Prefix stays `/audio`** (mass noun; old plan lock; not in the React frozen contract). `AudioView.audio_url` content unchanged: `/audio/stream/{id}`.
4. **Roles = video parity:** read (`GET /`, `GET /stream/{id}`) = admin/teacher/student; write (`POST /upload`, `POST /upload_multiple`, `PATCH /{id}`, `DELETE /{id}`) = admin/teacher.
5. **TimestampMixin NOT adopted** (deliberate deviation from video's 2026-09-13 deviation): `created_at` keeps its legacy nullable column with Python default — one schema change per migration, not two.
6. **Upload keeps the legacy contract:** no `title` form field — title is the filename stem; `description` is always `None` on upload; `upload_multiple` has no tags field.

## Global Constraints

- `requires-python = ">=3.13"`; run all commands with `uv run` from `backend/`
- Tests run against the testcontainers Postgres harness — **Docker daemon must be running**; harness (`backend/app/tests/conftest.py`) exposes `db`, `client`, `setup_paths`, and helpers `setup_admin`/`login`/`auth_headers`. Call `db.expire_all()` before reading via `db` after a write through `client`
- Characterization-first: Task 1 pins are **witnessed green on legacy code**; every behavior fix gets a red-first probe that fails on legacy before implementation. Never delete a failing test to make the suite pass
- `ruff check --ignore B008` and `mypy --strict` on **changed files only**; touched files end at **0 ruff + 0 mypy** — pre-existing errors in a touched file are that task's debt to clear (the audio annex rows below)
- Commit after every task, including the plan-file tick in the same commit; message style: `test:`, `fix:`, `refactor:`, `chore:`
- The harness `create_all`s from models, so Task 3's model change keeps tests green before the Task 4 migration exists; dev compose is safe because the compose entrypoint runs `alembic upgrade head` and the migration lands in Task 4
- **Permissions:** `backend/migrations/**` and `backend/pyproject.toml` are outside the agent's edit set — Task 4's migration and the `per-file-ignores` row deletions are **paste-ready diffs for the human**, not agent edits
- After the final task: `graphify update .` (AST-only), then the `review` agent gates the whole diff

## Current State (verified against the tree, 2026-09-14)

| Area | State | Where |
|---|---|---|
| Audio endpoints | 🔴 6 endpoints, **zero auth**, inline DB queries + inline tag logic + inline file I/O | `backend/app/api/audio_router.py` (178 lines) |
| Delete missing id | 🔴 LIVE 500 — `None.deleted_at` deref | `audio_repo.py:20-25` |
| upload_multiple partial commit | 🔴 earlier files saved + committed before a later file's validation fails | `audio_router.py:88-107` |
| Streaming | 🔴 Python byte-chunk generator, no containment on `file_path` (traversal), missing file → 500 | `audio_router.py:153-178` |
| Models | 🔴 legacy 1.x `Column()` ×2 | `models/audio.py`, `models/audio_tag.py` |
| Repo | 🔴 legacy `query()` ×3; `update_audio` is dead code | `audio_repo.py` |
| Naming (Inv 6) | 🔴 `Audio_Repo`, `Audio_Create`, `Audio_View` | audio repo + schema |
| Orphan sweep | 🔴 three divergent predicates, none knows `audio_tracks` — a tag linked to an audio track is deleted by a book or video sweep (cross-media link loss) | `tag_repo.py:14`, `book_repo.py:64`, `video_repo.py:46` |
| Tests (Inv 5) | 🔴 zero for audio | `backend/app/tests/` |
| Whitelist | ✅ `ALLOWED_AUDIO = {"mp3","mp4","wav","ogg","m4a","aac","flac"}` (preserved verbatim in Task 3) | `audio_router.py:17` |
| Anchored dirs | ✅ `AUDIO_DIR` BASE_DIR-anchored, mkdir at import | `config.py:42`, `main.py:48` |
| Debt (fresh-measured 2026-09-14) | ruff 0 everywhere; mypy: `audio_router.py` 20, `audio_repo.py` 5, models + schema 0 | Debt Coverage Annex |

Blast radius: the audio module is imported only by `main.py:58`, `api/__init__.py`, and (directly, not via `repositories/__init__.py`) its own router; `Tag.audio_tracks` (`tag.py:22-24`) is read by nothing until Task 2. No test file imports audio today.

## File Structure Map

| File | Action | Task | Responsibility |
|---|---|---|---|
| `backend/app/tests/media/test_audio_repo.py` | Create | 1 | Audio repo characterization pins (incl. the `AttributeError` bug pin) |
| `backend/app/tests/media/test_audio_api.py` | Create | 1, 3 | Audio API pins; Task 3 flips bug pins + adds auth/X-Accel probes |
| `backend/app/tests/media/test_media_stream.py` | Modify | 3 | Audio X-Accel contract rows |
| `backend/app/tests/media/test_orphan_cleanup.py` | Modify | 2 | Cross-media orphan probes |
| `backend/app/repositories/tag_repo.py` | Modify | 2 | `delete_orphans()` predicate gains `~Tag.audio_tracks.any()` |
| `backend/app/repositories/book_repo.py`, `video_repo.py` | Modify | 2 | Inline sweeps delegate to `TagRepo.delete_orphans()` |
| `backend/app/models/audio.py`, `audio_tag.py` | Rewrite | 3 | 2.0 `mapped_column()`, `deleted_at` dropped |
| `backend/app/schemas/audio_schema.py` | Rewrite | 3 | `AudioCreate`/`AudioView` (renames), `audio_url` as computed field |
| `backend/app/repositories/audio_repo.py` | Rewrite | 3 | `AudioRepo` — 2.0 `select()`; `create`/`get_by_id`/`list_all`/`delete`; dead `update_audio` deleted |
| `backend/app/services/audio_service.py` | Create | 3 | `AudioService(db)` — orchestration, domain exceptions only |
| `backend/app/api/audio_router.py` | Rewrite | 3 | RoleChecker, X-Accel stream, error mapping, DI; no queries/no `open()`/no tag logic |
| `backend/app/repositories/__init__.py` | Modify | 3 | `AudioRepo` joins `__all__` |
| `backend/app/services/media_validator.py` | Modify | 3 | `ALLOWED_AUDIO_EXTENSIONS` constant joins the video one |
| `backend/migrations/versions/<hash>_audio_hard_delete.py` | Create (human) | 4 | Drop `audio.deleted_at` |
| `backend/pyproject.toml` | Modify (human) | 4 | Delete the three audio `per-file-ignores` rows |
| `AGENTS.md`, `README.md` | Modify | 4 | Invariant-table audio rows struck; zero-auth warning removed |

## Debt Coverage Annex (fresh-measured, 2026-09-14)

| File | ruff | mypy | Owning task |
|---|---|---|---|
| `app/api/audio_router.py` | 0 | 20 | 3 (rewrite) |
| `app/repositories/audio_repo.py` | 0 | 5 | 3 (rewrite) |
| `app/models/audio.py`, `audio_tag.py` | 0 | 0 | 3 (2.0 conversion) |
| `app/schemas/audio_schema.py` | 0 | 0 | 3 (renames keep it at 0) |
| `app/repositories/tag_repo.py` | 0 | 0 | 2 (touch — keep at 0) |

The `pyproject.toml` callout rows (`N801` ×2, `E711` ×1) are struck by Task 4's human diff.

---

# PART A — Characterization pins

Part A pins current behavior — including its bugs — witnessed green on legacy. Bugs are pinned as-broken (`pytest.raises(...)`) and flipped red-first in Task 3. Legacy has no auth: Part A requests carry **no headers**. Uploads read `settings.AUDIO_DIR` at request time (`audio_router.py:53`) but the module constant `AUDIO_DIR` at others (`audio_router.py:92`) — pins patch **both** (`monkeypatch.setattr(audio_router_module, "AUDIO_DIR", target, raising=False)` keeps working after the rewrite deletes the constant).

### Task 1: Audio characterization pins

**Files:**
- Create: `backend/app/tests/media/test_audio_repo.py`
- Create: `backend/app/tests/media/test_audio_api.py`

**Interfaces:**
- Consumes: legacy `Audio_Repo` (`create_audio`, `delete_audio`), `Audio` model, `Audio_Create`/`Audio_View` schemas, harness fixtures
- Produces: the pinned statement Task 3 preserves — soft delete excludes from list but keeps the row; DELETE returns 200 with `id`/`title`/`description`/`audio_url`/`tags` (the incidental `file_path`/`created_at` leak is **not** pinned — the rewrite's `AudioView` deliberately drops it); DELETE missing id raises `AttributeError`; `upload_multiple` persists earlier files before a later failure; PATCH replaces the tag set but old `Tag` rows survive (this pin **flips** in Task 3 — orphan sweep, video parity per media plan Task 12)

Seeding idiom (sample — bodies are yours):

```python
def _seed_audio(db, *, title: str = "song", file_path: str = "/tmp/nonexistent.mp3") -> Audio:
    track = Audio(title=title, description=None, file_path=file_path)
    db.add(track)
    db.commit()
    db.refresh(track)
    return track
```

- [x] **Step 1: Write `test_audio_repo.py`** — three cases:
  1. `create_audio` persists: row gets an id; `title`/`description`/`file_path` round-trip; `deleted_at` is `None`
  2. `delete_audio` soft-deletes: `deleted_at` set (compare `datetime.now(UTC)` within a small delta), row still present in DB
  3. `delete_audio` on a missing id **raises** — the bug pin: `with pytest.raises(AttributeError): Audio_Repo(db).delete_audio(999999)`

- [x] **Step 2: Write `test_audio_api.py`** — case list (bodies yours):
  1. `GET /audio/` on an empty table → `200`, `[]`
  2. `GET /audio/` excludes a soft-deleted track (seed two, delete one via repo) — assert the remaining id as a set (no `ORDER BY` exists)
  3. `POST /audio/upload` happy: `files={"file": ("song.mp3", b"\xff\xfbID3 mock audio bytes", "audio/mpeg")}`, `data={"tags": "math, algebra"}` → `200`: `title == "song"` (filename stem), `audio_url == f"/audio/stream/{id}"`, tags in order `math`, `algebra`; file bytes on disk under the patched AUDIO_DIR with `{uuid4}_{filename}` naming; DB row's `file_path` points there
  4. Upload `data={"tags": " math ,, MATH "}` → single tag, stored lowercase `"math"` (strip, drop empties, lowercase create, duplicates collapse)
  5. Pre-create `Tag(name="Math")` via `db`, upload `tags="MATH"` → the existing `"Math"` row is **reused** (case-insensitive match, stored case returned); `db.query(Tag).count() == 1`
  6. Upload `.txt` filename → `400` detail `File type .txt not allowed`, and the patched dir contains **no** file (validates before any byte reaches disk)
  7. Upload extensionless filename → `400` (extension extraction returns the whole name; whitelist rejects)
  8. `POST /audio/upload_multiple` (two files, second `.txt`, no tags param exists) → `400`; then `GET /audio/` returns exactly **one** track — the partial-commit bug pin
  9. `POST /audio/upload_multiple` (two valid) → `200` list of two views, `title` is each filename stem
  10. `PATCH /audio/{id}` with `title`, `description`, `tags="bass"` → `200` updated view, tag set replaced; the old tag row **survives in DB** (`db.query(Tag)`) — flip target in Task 3
  11. `PATCH` with `tags=""` → tag set cleared (`""` is not `None`); with `tags` omitted → tags untouched
  12. `PATCH /audio/999999` → `404` detail `Audio not found`; no DB change
  13. `DELETE /audio/{id}` → `200`; response has `id`/`title`/`description`/`audio_url`/`tags` keys; afterwards excluded from `GET /audio/`; row still present with `deleted_at` set
  14. `DELETE /audio/999999` → the bug pin: `with pytest.raises(AttributeError): client.delete("/audio/999999")` (harness `raise_server_exceptions=True` surfaces the `None.deleted_at` deref) — flip target for Task 3
  15. `GET /audio/stream/{id}` (real `tmp_path` file with mock bytes) → `200`, `Content-Type: audio/mpeg`, body byte-for-byte
  16. `GET /audio/stream/999999` → `404` detail `Audio not found`
  17. Stream of a soft-deleted track → `200` (quirk pin; dies with the column in Task 3)
  18. Stream whose row's file is missing on disk → `with pytest.raises(FileNotFoundError)` (uncaught `open()`) — flip target for Task 3

- [x] **Step 3: Witness green** — `cd backend && uv run pytest app/tests/media/test_audio_repo.py app/tests/media/test_audio_api.py -v`. Expected: all pass (~21 tests). If a pin fails, fix the **pin** to match verified behavior and record the deviation at the bottom of this task; do not fix legacy code here.

- [x] **Step 4: Lint + commit**

```bash
cd backend && uv run ruff format app/tests/media/test_audio_repo.py app/tests/media/test_audio_api.py && uv run ruff check app/tests/media/test_audio_repo.py app/tests/media/test_audio_api.py --ignore B008
git add backend/app/tests/media/test_audio_repo.py backend/app/tests/media/test_audio_api.py
git commit -m "test: pin audio module behavior — list, upload, patch, delete, stream"
```

---

# PART B — Sweep truth + fused rewrite

### Task 2: Tag orphan sweep knows audio — predicate fix + sweep unification

> **Lint/type gate:** touched files end 0/0 (`tag_repo.py` 0/0 today; `book_repo.py`/`video_repo.py` 0/0 — keep them there).

**Files:**
- Modify: `backend/app/repositories/tag_repo.py:11-21`
- Modify: `backend/app/repositories/book_repo.py:63-70`, `video_repo.py:45-48`
- Test: `backend/app/tests/media/test_orphan_cleanup.py` (Modify)

**Interfaces:**
- `TagRepo.delete_orphans() -> int` — predicate becomes `~Tag.books.any(), ~Tag.videos.any(), ~Tag.audio_tracks.any()` (a tag with **any** link in **any** media survives)
- `BookRepo._delete_orphan_tags` / `VideoRepo._delete_orphan_tags` — deleted; their call sites call `TagRepo(self.db_session).delete_orphans()` (one truth — media plan Task 12's shared operation; the per-repo copies drifted the moment audio existed)
- **Never** call cleanup on read paths or search

**Why (learning):** three divergent `~X.any()` predicates were written when each media forgot the others existed. `BookRepo` deletes video-linked tags; `VideoRepo` deletes book-linked tags; `TagRepo` deletes audio-linked tags. The DB is the single truth for "orphaned" — a tag with zero links in all three media, period.

- [x] **Step 1: Red-first probes** — append to `test_orphan_cleanup.py` (idioms: `_count_by_name`, `TagRepo(db).get_or_create_by_names`):
  1. Tag linked to an audio track and a video; `VideoService(db).delete(video.id)` → tag **survives** (red today: `~Tag.videos.any()` sweeps it)
  2. Tag linked to a book and a video; `VideoService(db).delete(video.id)` → tag **survives** with the book link intact (red today: same predicate)
  3. Tag linked only to an audio track; `TagRepo(db).delete_orphans()` → returns 0, tag survives (red today: audio-only tags look orphaned)
  4. Then a true three-way orphan: tag with no links → `delete_orphans()` still deletes it (green guard, not red)

- [x] **Step 2: Witness red** — `cd backend && uv run pytest app/tests/media/test_orphan_cleanup.py -v`. Expected: probes 1–3 fail (`assert 1 == 0` / `0 != 0`), all pre-existing tests + probe 4 green.

- [x] **Step 3: Implement** per Interfaces. Note `Audio.audio_tracks` already exists on `Tag` (`tag.py:22-24`) — the predicate needs no model change.

- [x] **Step 4: Verify green** — same command, all pass, plus `uv run pytest -v` full suite (book/video orphan tests must stay green — the unification preserves their observable behavior).

- [x] **Step 5: Format, lint, type + commit**

```bash
cd backend && uv run ruff format app/repositories/tag_repo.py app/repositories/book_repo.py app/repositories/video_repo.py app/tests/media/test_orphan_cleanup.py && uv run ruff check app/repositories/tag_repo.py app/repositories/book_repo.py app/repositories/video_repo.py app/tests/media/test_orphan_cleanup.py --ignore B008 && uv run mypy app/repositories/tag_repo.py app/repositories/book_repo.py app/repositories/video_repo.py --strict
git add backend/app/repositories/tag_repo.py backend/app/repositories/book_repo.py backend/app/repositories/video_repo.py backend/app/tests/media/test_orphan_cleanup.py
git commit -m "fix: tag orphan sweep accounts for audio tracks; book/video sweeps delegate to TagRepo"
```

---

### Task 3: Audio fused rewrite — 2.0 models, hard delete, service layer, auth, X-Accel

> **Lint/type gate:** `audio_router.py` (0/20), `audio_repo.py` (0/5) end at 0/0; models + schema stay 0/0; `media_validator.py` stays 0/0.

**Files:**
- Rewrite: `backend/app/models/audio.py`, `models/audio_tag.py` (2.0 conversion + `deleted_at` drop)
- Rewrite: `backend/app/schemas/audio_schema.py` (renames + computed `audio_url`)
- Rewrite: `backend/app/repositories/audio_repo.py`
- Create: `backend/app/services/audio_service.py`
- Rewrite: `backend/app/api/audio_router.py`
- Modify: `backend/app/services/media_validator.py` (`ALLOWED_AUDIO_EXTENSIONS`), `backend/app/repositories/__init__.py`
- Test: `test_audio_repo.py`, `test_audio_api.py` (Modify), `test_media_stream.py` (Modify)

**Interfaces:**

*Models* — `models/audio.py` (table name `"audio"` unchanged — do not "fix" the singular):

```python
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tag import Tag


class Audio(Base):
    __tablename__ = "audio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="audio_tags", back_populates="audio_tracks"
    )
```

`datetime`/`UTC` imports ride along. **No `deleted_at`** (Locked decision 2). `AudioTag` converts to `Mapped[]`/`mapped_column()` with identical columns: `id` PK, `audio_id`/`tag_id` FKs `ondelete="CASCADE"`, `UniqueConstraint("audio_id", "tag_id")`. `models/__init__.py` needs **no edit** — both models are already exported.

*Schemas* — rename only + one computed field:

```python
class AudioCreate(BaseModel):
    title: str
    description: str | None = None
    file_path: str


class AudioView(BaseModel):
    id: int
    title: str
    description: str | None = None
    tags: list[TagRead] = []
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def audio_url(self) -> str:
        return f"/audio/stream/{self.id}"
```

`AudioView` response keys stay `id`/`title`/`description`/`audio_url`/`tags` — the Task 1 pins hold unchanged (the legacy `file_path` leak dies: it was never pinned).

*Repo* — `class AudioRepo`, 2.0 `select()`:
- `create(self, audio_create: AudioCreate) -> Audio` — `add`/`commit`/`refresh` (commit-stays-in-repo convention)
- `get_by_id(self, audio_id: int) -> Audio | None` — `selectinload(Audio.tags)`
- `list_all(self) -> list[Audio]` — `selectinload(Audio.tags)`, **no ORDER BY** (pins assert sets)
- `delete(self, audio_id: int) -> None` — `get_by_id` → `None` means `raise MediaNotFound("Audio not found")` (mirrors `VideoRepo.delete`); hard delete the row; then `TagRepo(self.db_session).delete_orphans()` (Task 2's fixed predicate); `flush` + `commit`
- `update_audio` **deleted** (dead — the router's inline update mutates the loaded row itself)

*Service* — `class AudioService`, `__init__(self, db: Session)`, holding `AudioRepo`, `TagRepo`, and `MediaFileStorage(settings.AUDIO_DIR)`:

```python
def list_tracks(self) -> list[AudioView]: ...
def upload(self, file_bytes: bytes, filename: str, tag_names: list[str]) -> AudioView: ...
def upload_multiple(self, files: list[tuple[bytes, str]]) -> list[AudioView]: ...
def update(self, audio_id: int, *, title: str | None, description: str | None,
           tag_names: list[str] | None) -> AudioView: ...
def delete(self, audio_id: int) -> None: ...
def resolve_stream(self, audio_id: int) -> tuple[Path, str]: ...
```

- `upload`: `validate_media(filename, allowed=ALLOWED_AUDIO_EXTENSIONS)` **first** → `storage.save` → `AudioRepo.create(AudioCreate(title=Path(filename).stem, description=None, file_path=saved))` → `tag_repo.get_or_create_by_names(tag_names)` → link → commit → refresh → `AudioView.model_validate`
- `upload_multiple`: validate **every** file before the first byte is written (probe 8's fix), then per-file `self.upload` (video parity — the observable contract "zero rows on any failure" is what the pin asserts)
- `update`: row missing → `MediaNotFound("Audio not found")`; tri-state (`None` = untouched, `[]`/`""` = clear, list = replace) via `get_or_create_by_names`; commit; `tag_repo.delete_orphans()` after a link-set replacement (video Task 12 parity — flips pin case 10)
- `delete`: row missing → `MediaNotFound("Audio not found")`; `storage.delete(file_path)` then `repo.delete(audio_id)`
- `resolve_stream`: row missing → `MediaNotFound("Audio not found")`; `storage.resolve(file_path)` (traversal + missing → `MediaNotFound`); media type from the **legacy map, preserved verbatim** — `{"mp3": "audio/mpeg", "mp4": "audio/mp4", "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4", "aac": "audio/aac", "flac": "audio/flac"}` with `"audio/mpeg"` fallback
- Domain exceptions only — no HTTP types, no `open()`, no tag loops

*Media validator* — join the existing constant:

```python
ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {"mp3", "mp4", "wav", "ogg", "m4a", "aac", "flac"}
)
```

(the legacy `ALLOWED_AUDIO` set verbatim — including the odd `mp4`; Locked decision 6 context)

*Router* — prefix `/audio`, tags `["audio"]`:

```python
router = APIRouter(prefix="/audio", tags=["audio"])

ROLES = [RoleEnum.admin, RoleEnum.teacher, RoleEnum.student]
WRITE_ROLES = [RoleEnum.admin, RoleEnum.teacher]


def get_audio_service(db: Session = Depends(get_db)) -> AudioService:
    return AudioService(db)
```

- `GET /` → `list_tracks` (ROLES); `POST /upload` (multipart `file: UploadFile = File(...)`, `tags: str = Form("")` — **no title field**, WRITE_ROLES): read bytes, split tags `[t.strip() for t in tags.split(",") if t.strip()]`, map `InvalidMediaFile`→400 / `IntegrityError`→400; `POST /upload_multiple` (`files: list[UploadFile] = File(...)`, WRITE_ROLES): read into `list[tuple[bytes, str]]`, same mapping; `PATCH /{audio_id}` (bare params `title`/`description`/`tags: str | None = None`, WRITE_ROLES): parse tags only when not `None`, map `MediaNotFound`→404; `DELETE /{audio_id}` (WRITE_ROLES, `status_code=204`, returns `None`): map `MediaNotFound`→404; `GET /stream/{audio_id}` (ROLES):

```python
@router.get("/stream/{audio_id}")
def stream_audio(
    audio_id: int,
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> Response:
    try:
        media_path, media_type = svc.resolve_stream(audio_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/audio/{quote(media_path.name)}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )
```

The router holds **no queries, no `open()`, no tag logic, no `os`/`shutil` imports** — the module-level `ALLOWED_AUDIO`, `AUDIO_DIR`, `validate_audio`, and `_build_audio_view` all die.

- [x] **Step 1: Update pins + write the red-first probes**

**Modify `test_audio_api.py`:**
1. `auth_headers(token)` on every request (fixture `auth` idiom from `test_video_api.py:37-41`); parametrized 401 guard over all six paths (`/`, `/upload`, `/upload_multiple`, `/{id}`, `/stream/{id}`, DELETE)
2. Flip bug pins (each must be **red on legacy** — run and witness before implementing):
   - case 14: `DELETE /audio/999999` → `404` (legacy: raises `AttributeError`)
   - case 8: after the failing batch, `GET /audio/` → **zero** rows and **zero** files under the patched dir (legacy: one row + bytes on disk)
   - case 18: missing-file stream → `404` (legacy: `FileNotFoundError`)
   - case 17: soft-deleted stream pin **dies with the column** — replaced by: after `DELETE`, the row is gone from the DB entirely (`db.query(Audio).count() == 0`) and its file is gone from disk
   - case 13: DELETE → `204` empty body (legacy: 200 + view)
   - case 10: PATCH with a new tag set → the orphaned old tag row is **swept** (legacy: survives) — rename the pin `test_patch_replaces_tags_and_sweeps_orphans` (media plan Task 12 precedent)
   - stream pins (15): `204`, body empty, `X-Accel-Redirect == f"/media/audio/{quote(name)}"`, `Content-Type: audio/mpeg`, `Accept-Ranges: bytes`
3. Every write-path happy case gains a `403` student-role probe (student token on `/upload` → 403; on `GET /` → 200) — video parity

**Modify `test_audio_repo.py`:** case 2 flips to hard delete (`delete` → row **gone**, count 0); case 3 flips to `AudioRepo(db).delete(999999)` raising `MediaNotFound` (`pytest.raises(MediaError, match="Audio not found")`); class import becomes `AudioRepo`; `create_audio` calls become `create`.

**Modify `test_media_stream.py`** — audio rows mirroring the video parametrize (new import `Audio`, `AudioService`; the missing module makes this file's collection error the Step-2 red for the new service, same as video's Task 8):
- 204 + `X-Accel-Redirect == f"/media/audio/{quote(name)}"` for `("clip.mp3", "audio/mpeg")`, `("clip.wav", "audio/wav")`, `("clip.flac", "audio/flac")`
- 404 missing id; 404 missing disk file; 404 traversal-seeded `file_path`; 401 unauthenticated
- one **spaced filename** (`"my clip.mp3"`) asserting `X-Accel-Redirect == "/media/audio/my%20clip.mp3"`

- [x] **Step 2: Verify red** — `cd backend && uv run pytest app/tests/media/test_audio_repo.py app/tests/media/test_audio_api.py app/tests/media/test_media_stream.py -v`. Expected red, each for the right reason: 401 guards fail on legacy 200; DELETE-missing raises `AttributeError`; partial-commit leaves one row; missing-file stream raises `FileNotFoundError`; stream asserts fail on 200-with-body; `test_media_stream.py` collection ERROR on missing `audio_service` (correct red). Everything else green.

- [x] **Step 3: Implement, in this order, gate after each:**
  1. Models 2.0 (deleted_at dropped) — `uv run pytest app/tests/media/test_audio_repo.py -v` → only the deliberate Step-1 flips red, nothing else
  2. `media_validator.py` constant + schema renames
  3. `AudioRepo` per Interfaces
  4. `AudioService` per Interfaces — gate: `grep -n "HTTPException\|open(\|ilike" app/services/audio_service.py` prints nothing
  5. Router per Interfaces; `AudioRepo` joins `repositories/__init__.py`

- [x] **Step 4: Verify green** — same pytest command as Step 2, all pass.

- [x] **Step 5: Format, lint, type**

```bash
cd backend && uv run ruff format app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/services/media_validator.py app/repositories/__init__.py app/tests/media/test_audio_api.py app/tests/media/test_audio_repo.py app/tests/media/test_media_stream.py && uv run ruff check app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/services/media_validator.py app/repositories/__init__.py app/tests/media/test_audio_api.py app/tests/media/test_audio_repo.py app/tests/media/test_media_stream.py --ignore B008 && uv run mypy app/models/audio.py app/models/audio_tag.py app/repositories/audio_repo.py app/services/audio_service.py app/api/audio_router.py app/schemas/audio_schema.py app/services/media_validator.py app/repositories/__init__.py --strict
```

Expected: 0/0 on all (Annex audio rows struck).

- [x] **Step 6: Full suite + commit** (one commit — the fused rewrite is one unit, models included)

```bash
cd backend && uv run pytest -v
git add backend/app/models/audio.py backend/app/models/audio_tag.py backend/app/schemas/audio_schema.py backend/app/repositories/audio_repo.py backend/app/services/audio_service.py backend/app/api/audio_router.py backend/app/services/media_validator.py backend/app/repositories/__init__.py backend/app/tests/media/test_audio_api.py backend/app/tests/media/test_audio_repo.py backend/app/tests/media/test_media_stream.py
git commit -m "refactor: audio module — 2.0 models, hard delete, service layer, auth, X-Accel stream"
```

---

# PART C — Migration + docs + final gate

### Task 4: Migration, debt-row deletions, docs, final gate

> **Human hands required:** `backend/migrations/**` and `backend/pyproject.toml` are outside the agent's edit set. The agent provides the paste-ready diffs below and verifies the round-trip; the human creates the files and commits.

**Files:**
- Create: `backend/migrations/versions/<hash>_audio_hard_delete.py` (human)
- Modify: `backend/pyproject.toml` (human — delete the three audio rows from `[tool.ruff.lint.per-file-ignores]`)
- Modify: `AGENTS.md` (agent — invariant table + Naming table rows struck)
- Modify: `README.md` (agent — zero-auth `/audio/` warning removed)

- [ ] **Step 1: The migration** — human runs `cd backend && uv run alembic revision --rev-id "$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-12)" -m "audio hard delete"` (strip hyphens — `uuidgen`'s output has one at position 9 and Alembic rejects `-` in revision ids; the media plan's `cut -c1-12` alone was buggy) and pastes this body (`down_revision` **must** be `c5a1e8b4d9f2`, the current head):

```python
"""audio hard delete: drop audio.deleted_at

Revision ID: <your-hash>
Revises: c5a1e8b4d9f2  (video poster)
"""
from alembic import op
import sqlalchemy as sa

revision = "<your-hash>"
down_revision = "c5a1e8b4d9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("audio", "deleted_at")


def downgrade() -> None:
    op.add_column("audio", sa.Column("deleted_at", sa.DateTime(), nullable=True))
```

- [ ] **Step 2: Round-trip on a scratch DB** (no data migration needed — `deleted_at` carries no data worth preserving: hard delete means no row sets it anymore; the downgrade column is always NULL):

```bash
docker compose up -d db
docker compose exec db psql -U postgres -c "CREATE DATABASE jirani_migtest;" 2>/dev/null || true
docker compose exec db psql -U postgres -d jirani_migtest -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic downgrade -1
cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_migtest uv run alembic upgrade head
```

Expected: all three succeed. Then apply to dev: `cd backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jirani_library uv run alembic upgrade head`

- [ ] **Step 3: Debt-row deletions** — human deletes from `backend/pyproject.toml`:

```toml
"app/repositories/audio_repo.py" = ["N801"]  # Audio_Repo (Invariant 6, audio plan)
"app/schemas/audio_schema.py" = ["N801"]     # Audio_Create, Audio_View (Invariant 6, audio plan)
"app/api/audio_router.py" = ["E711"]         # pre-existing, audio plan
```

(leaving only the `app/config.py` row). Agent verifies: `uv run ruff check .` → 0 errors repo-wide.

- [x] **Step 4: Docs** — `AGENTS.md` invariant table: strike the audio rows from invariants 1, 4, 5, 6 (the "Violating today" column becomes empty; update the closure notes to credit this plan); Naming table: strike the audio rows (classes, `/audio` prefix note resolved as "kept deliberately"); Debt Coverage Annex text in this plan is already struck by the tasks. `README.md`: remove any "audio endpoints are zero-auth" warning (the media plan flagged one must be loud "until the audio plan lands" — it has landed). *(Executed: AGENTS.md rows struck 2026-09-14; README audited — no zero-auth audio warning exists there, no edit needed.)*

## Deviation records

- **Task 1 (pins), 2026-09-14:** the brief's case-13 key list was wrong — legacy `DELETE /audio/{id}` has no `response_model` and serializes the raw ORM row, so the witnessed body carries `id`/`title`/`description` but NOT `audio_url`/`tags`. Pins assert the witnessed body (characterization discipline: pin what legacy DOES). The flip in Task 3 (DELETE → 204 empty) supersedes the pin regardless. Case 7's detail pinned as `File type .song not allowed` (legacy `rsplit` returns the whole extensionless name).
- **Task 2 (sweep), 2026-09-14:** the plan's suggested commit subject (88 chars) exceeds the repo's `commit-msg-length` pre-commit hook (≤72); landed as `fix: orphan sweep knows audio; book/video sweeps delegate to TagRepo` (68). `BookRepo.cleanup_orphan_tags` kept as a try/commit wrapper around the `TagRepo` delegation — it is the named public op `update_book` calls; deleting it was never in the brief.
- **Task 3 (rewrite), 2026-09-14:** the plan missed that the shared validator's `Path(filename).suffix` extraction changes the extensionless-detail message from legacy's `File type .song not allowed` to `File type . not allowed` — flipped red-first, witnessed (controller resolution at dispatch). Task 3 also surfaced a pre-existing import cycle (`services/__init__.py` → `auth_service` → `repositories/__init__` → `audio_repo` → `services`), initially silenced with `# isort: skip_file` and then fixed at the source (`auth_service.py:9` module-path import; skip pragma removed) in the follow-up commit `fb0d041`.

- [ ] **Step 5: Final gate** — `cd backend && uv run pytest -v` (full suite green, ~50 new tests included), then dispatch `@review` over the accumulated diff. On PASS:

```bash
graphify update .
git add AGENTS.md README.md docs/superpowers/plans/2026-09-14-audio-refactor.md
git commit -m "chore: audio refactor complete — migration, debt rows struck, docs updated"
```

## Deferred Work

- **Signed-ticket streaming** (React annex follow-up (b)): applies to audio identically once the SPA consumes it — already tracked there, not here
- **`created_at` NOT NULL tighten** (video got it in `e7c4b9f2a831`): audio's nullable column with Python default is preserved verbatim (Locked decision 5); bundle into a future timestamps sweep if one ever runs
