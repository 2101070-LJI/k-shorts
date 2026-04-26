import asyncio
from typing import Optional

from app.models.job import Job

_jobs: dict[str, Job] = {}
_lock = asyncio.Lock()


async def put(job: Job) -> None:
    async with _lock:
        _jobs[job.id] = job


async def get(job_id: str) -> Optional[Job]:
    async with _lock:
        return _jobs.get(job_id)


async def update(job_id: str, **fields) -> Optional[Job]:
    async with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        for k, v in fields.items():
            setattr(job, k, v)
        return job


async def all_jobs() -> list[Job]:
    async with _lock:
        return list(_jobs.values())
