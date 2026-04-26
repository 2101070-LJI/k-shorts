import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect

from app.models.job import EditRequest, Job, JobStatus
from app.pipeline import orchestrator, registry
from app.pipeline.progress import bus

router = APIRouter(tags=["edit"])


@router.post("/edit", response_model=Job)
async def start_edit(req: EditRequest, tasks: BackgroundTasks) -> Job:
    job = await orchestrator.create_job(req)
    tasks.add_task(orchestrator.run_job, job.id, req.llm_model)
    return job


@router.delete("/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str) -> None:
    job = await registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise HTTPException(409, f"job is already {job.status.value}")
    await registry.update(job_id, status=JobStatus.CANCELLED, message="사용자가 취소함")
    await bus.publish(job_id, {"stage": "error", "pct": 0, "message": "취소됨"})


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = await registry.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    job = await registry.get(job_id)
    if job is None:
        await ws.send_json({"stage": "error", "pct": 0, "message": "unknown job"})
        await ws.close()
        return

    await ws.send_json({"stage": "connected", "pct": job.progress_pct, "message": job.message})

    q = await bus.subscribe(job_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_json({"stage": "heartbeat", "pct": 0, "message": ""})
                continue
            await ws.send_json(event)
            if event.get("stage") in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await bus.unsubscribe(job_id, q)
        try:
            await ws.close()
        except RuntimeError:
            pass
