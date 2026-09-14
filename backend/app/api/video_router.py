from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.account import Account
from app.models.role_enum import RoleEnum
from app.schemas.video_schema import VideoView
from app.services.media_errors import InvalidMediaFile, MediaNotFound
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["videos"])

ROLES = [RoleEnum.admin, RoleEnum.teacher, RoleEnum.student]


def get_video_service(db: Session = Depends(get_db)) -> VideoService:
    return VideoService(db)


@router.get("/", response_model=list[VideoView])
def list_videos(
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> list[VideoView]:
    return svc.list_videos()


@router.post("/upload", response_model=VideoView)
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str | None = Form(None),
    tags: str = Form(""),
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> VideoView:
    data = await file.read()
    tag_names = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        return svc.upload(
            data,
            file.filename or "",
            title=title,
            description=description,
            tag_names=tag_names,
        )
    except InvalidMediaFile as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Invalid video data") from exc


@router.post("/upload_multiple", response_model=list[VideoView])
async def upload_multiple_videos(
    files: list[UploadFile] = File(...),
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> list[VideoView]:
    payloads = [(await file.read(), file.filename or "") for file in files]
    try:
        return svc.upload_multiple(payloads)
    except InvalidMediaFile as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Invalid video data") from exc


@router.patch("/{video_id}", response_model=VideoView)
def update_video(
    video_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> VideoView:
    tag_names = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags is not None else None
    )
    try:
        return svc.update(
            video_id, title=title, description=description, tag_names=tag_names
        )
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> None:
    try:
        svc.delete(video_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc


@router.get("/stream/{video_id}")
def stream_video(
    video_id: int,
    svc: VideoService = Depends(get_video_service),
    user: Account = Depends(RoleChecker(ROLES)),
) -> Response:
    try:
        media_path, media_type = svc.resolve_stream(video_id)
    except MediaNotFound as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return Response(
        status_code=204,
        headers={
            "X-Accel-Redirect": f"/media/vids/{quote(media_path.name)}",
            "Content-Type": media_type,
            "Accept-Ranges": "bytes",
        },
    )
