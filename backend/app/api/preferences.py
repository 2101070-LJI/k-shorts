from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import clips_repo, preferences_repo
from app.pipeline import fewshot

router = APIRouter(prefix="/preferences", tags=["preferences"])


class RecordRequest(BaseModel):
    clip_id: int
    label: int = Field(..., description="-1 (👎) or 1 (👍)")


class RecordResponse(BaseModel):
    id: int
    total: int


@router.post("/record", response_model=RecordResponse)
def record(req: RecordRequest) -> RecordResponse:
    if req.label not in (-1, 1):
        raise HTTPException(400, "label must be -1 or 1")
    if clips_repo.get_clip(req.clip_id) is None:
        raise HTTPException(404, f"clip not found: {req.clip_id}")
    pref_id = preferences_repo.record(req.clip_id, req.label)
    return RecordResponse(id=pref_id, total=preferences_repo.count())


@router.get("/fewshot")
def get_fewshot() -> list[dict]:
    return fewshot.sample()
