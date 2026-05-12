import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import shutil

import imageio_ffmpeg

from app.config import settings


def _resolve_ffmpeg() -> str:
    # Prefer system ffmpeg (named 'ffmpeg') so yt-dlp can locate it by directory.
    # imageio_ffmpeg bundles a non-standard filename that yt-dlp cannot find.
    sys = shutil.which("ffmpeg")
    if sys:
        return sys
    return imageio_ffmpeg.get_ffmpeg_exe()


_FFMPEG = _resolve_ffmpeg()

_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})")


@dataclass
class DownloadResult:
    video_id: str
    video_path: Path
    info_path: Path
    audio_path: Path
    title: str
    duration: float
    heatmap: Optional[list[dict]]  # each {'start_time', 'end_time', 'value'}


def extract_video_id(url: str) -> str:
    m = _VIDEO_ID_RE.search(url)
    if not m:
        raise ValueError(f"cannot extract YouTube video id from url: {url}")
    return m.group(1)


def _download_video(url: str, out_dir: Path, ffmpeg_path: str) -> None:
    import yt_dlp

    ydl_opts = {
        # Prefer 1080p with ffmpeg merge; fall back to pre-merged if merge unavailable.
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "writeinfojson": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "ffmpeg_location": str(Path(ffmpeg_path).parent),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


async def _run_ffmpeg(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='replace')[:800]}")


async def download(url: str) -> DownloadResult:
    video_id = extract_video_id(url)
    out_dir = settings.data_dir / "videos" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    video_path = out_dir / "source.mp4"
    info_path = out_dir / "info.json"
    audio_path = out_dir / "audio.wav"

    if not video_path.exists():
        await asyncio.to_thread(_download_video, url, out_dir, _FFMPEG)

    src_info = out_dir / "source.info.json"
    if src_info.exists() and not info_path.exists():
        src_info.rename(info_path)

    if not audio_path.exists():
        await _run_ffmpeg([
            _FFMPEG, "-y", "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(audio_path),
        ])

    info = json.loads(info_path.read_text(encoding="utf-8"))
    return DownloadResult(
        video_id=video_id,
        video_path=video_path,
        info_path=info_path,
        audio_path=audio_path,
        title=info.get("title", ""),
        duration=float(info.get("duration", 0)),
        heatmap=info.get("heatmap"),
    )
