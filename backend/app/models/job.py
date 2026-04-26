from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CancelledError(Exception):
    pass


class Stage(str, Enum):
    DOWNLOAD = "download"
    ASR = "asr"
    SIGNALS = "signals"
    SCORING = "scoring"
    RENDER = "render"


class ClipCandidate(BaseModel):
    start: float
    end: float
    title: str
    reason: str
    score: float
    template_id: str = "clean"
    output_path: Optional[str] = None
    clip_id: Optional[int] = None


class Job(BaseModel):
    id: str
    source_url: str
    template_id: str = "clean"
    status: JobStatus = JobStatus.QUEUED
    current_stage: Optional[Stage] = None
    progress_pct: float = 0.0
    message: str = ""
    error: Optional[str] = None
    candidates: list[ClipCandidate] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EditRequest(BaseModel):
    url: str
    template_id: str = "clean"
    llm_model: Optional[str] = None
