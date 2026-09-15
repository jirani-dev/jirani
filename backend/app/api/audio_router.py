from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.schemas.audio_schema import AudioRead
from app.services.audio_service import AudioService
from app.services.media_errors import InvalidMediaFile, MediaNotFound

router = APIRouter(prefix="/audio", tags=["audio"])

ROLES = [RoleEnum.admin, RoleEnum.teacher, RoleEnum.student]
WRITE_ROLES = [RoleEnum.admin, RoleEnum.teacher]


def get_audio_service(db: Session = Depends(get_db)) -> AudioService:
    return AudioService(db)


@router.get("/", response_model=list[AudioRead])
def list_tracks(
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> list[AudioRead]:
    return svc.list_tracks()


@router.post("/upload", response_model=AudioRead)
async def upload_track(
    file: UploadFile = File(...),
    tags: str = Form(""),
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(WRITE_ROLES)),
) -> AudioRead:
    data = await file.read()
    tag_names = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        return svc.upload(data, file.filename or "", tag_names)
    except InvalidMediaFile as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Invalid audio data") from exc


@router.post("/upload_multiple", response_model=list[AudioRead])
async def upload_multiple_tracks(
    files: list[UploadFile] = File(...),
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(WRITE_ROLES)),
) -> list[AudioRead]:
    payloads = [(await file.read(), file.filename or "") for file in files]
    try:
        return svc.upload_multiple(payloads)
    except InvalidMediaFile as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Invalid audio data") from exc


@router.patch("/{audio_id}", response_model=AudioRead)
def update_track(
    audio_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(WRITE_ROLES)),
) -> AudioRead:
    tag_names = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags is not None else None
    )
    try:
        return svc.update(
            audio_id, title=title, description=description, tag_names=tag_names
        )
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc


@router.delete("/{audio_id}", status_code=204)
def delete_track(
    audio_id: int,
    svc: AudioService = Depends(get_audio_service),
    user: Account = Depends(RoleChecker(WRITE_ROLES)),
) -> None:
    try:
        svc.delete(audio_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc


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
