"""Render stage — now delegates to the template engine.

`render_simple` kept as the no-subtitle, no-facetrack fallback used when an ASR
result isn't available (edge case) or when a bug in the template engine forces a
safe path during development.
"""
import asyncio
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.job import ClipCandidate
from app.pipeline.render.engine import render_templated
from app.pipeline.stages.asr import AsrResult


async def render(
    source_video: Path,
    candidate: ClipCandidate,
    clip_id: str,
    asr: Optional[AsrResult] = None,
) -> Path:
    return await render_templated(source_video, candidate, clip_id, asr=asr)


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='replace')[:800]}")


async def render_simple(source_video: Path, candidate: ClipCandidate, clip_id: str) -> Path:
    out_dir = settings.data_dir / "clips" / clip_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rendered_{candidate.template_id}.mp4"
    duration = max(candidate.end - candidate.start, 1.0)
    await _run([
        "ffmpeg", "-y",
        "-ss", f"{candidate.start:.3f}",
        "-i", str(source_video),
        "-t", f"{duration:.3f}",
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ])
    candidate.output_path = str(out_path.relative_to(settings.data_dir / "clips"))
    return out_path
