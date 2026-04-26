import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db import clips_repo
from app.services import youtube_client

router = APIRouter(prefix="/clips", tags=["clips"])


@router.get("")
def list_clips(limit: int = 100) -> list[dict]:
    return clips_repo.list_clips(limit=limit)


@router.get("/{clip_id}")
def get_clip(clip_id: int) -> dict:
    row = clips_repo.get_clip(clip_id)
    if row is None:
        raise HTTPException(404, "clip not found")
    return row


class UploadRequest(BaseModel):
    title: str | None = None
    description: str = ""
    privacy: str = "private"
    rendered_file: str  # relative path under data/clips/


class UploadResponse(BaseModel):
    yt_video_id: str
    yt_url: str


@router.post("/{clip_id}/upload", response_model=UploadResponse)
async def upload_clip(clip_id: int, req: UploadRequest) -> UploadResponse:
    clip = clips_repo.get_clip(clip_id)
    if clip is None:
        raise HTTPException(404, "clip not found")

    rel = Path(req.rendered_file)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(400, "invalid rendered_file path")

    path = settings.data_dir / "clips" / rel
    if not path.exists():
        raise HTTPException(404, f"rendered file not found: {rel}")

    title = (req.title or clip.get("title") or "Korean shorts")[:95]
    reason = clip.get("reason", "")

    yt_id = await asyncio.to_thread(
        youtube_client.upload_short,
        path,
        title,
        reason + "\n\n" + req.description,
        None,
        req.privacy,
    )
    clips_repo.set_youtube_id(clip_id, yt_id)

    return UploadResponse(
        yt_video_id=yt_id,
        yt_url=f"https://www.youtube.com/shorts/{yt_id}",
    )
