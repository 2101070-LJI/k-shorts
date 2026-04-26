"""Template dispatcher. Produces a final 1080×1920 mp4 with audio and burned-in subs."""
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import imageio_ffmpeg

from app.config import settings
from app.models.job import ClipCandidate
from app.pipeline.render import subtitles as sub
from app.pipeline.render.facetrack import CropProfile, TrackConfig, compute_crop_profile
from app.pipeline.stages.asr import AsrResult
from app.services.template_loader import load_one

OUT_W = 1080
OUT_H = 1920

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Sentinel: if video_filter starts with this prefix, it must be passed via -filter_complex
_COMPLEX = "_COMPLEX_"


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='replace')[-2000:]}")


def _escape_for_ffmpeg(path: Path) -> str:
    """ffmpeg subtitle filter needs ':' and '\\' escaped."""
    p = str(path).replace("\\", "/")
    return p.replace(":", r"\:")


def _ass_filter(sub_path: Path) -> str:
    return f"ass='{_escape_for_ffmpeg(sub_path)}'"


def _trim_cmd(src: Path, start: float, duration: float, out: Path) -> list[str]:
    return [
        _FFMPEG, "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        str(out),
    ]


# ---------------------------------------------------------------------------
# Layout filter builders
# ---------------------------------------------------------------------------

def _black_bars_filter() -> str:
    """Original 16:9 video centered with black bars top/bottom."""
    return f"scale={OUT_W}:-2:flags=lanczos,pad={OUT_W}:{OUT_H}:0:(oh-ih)/2:black"


def _color_bg_filter(color: str) -> str:
    """Solid color background (any CSS hex or named color)."""
    return f"scale={OUT_W}:-2:flags=lanczos,pad={OUT_W}:{OUT_H}:0:(oh-ih)/2:{color}"


def _blur_bg_filter(sigma: int = 30, fg_scale: float = 1.0) -> str:
    """
    Blurred version of the video fills 1080x1920, sharp original centered on top.
    fg_scale < 1.0 shrinks the foreground (e.g. 0.85 leaves room for captions).
    Returns a filter_complex string (no subtitles chained yet).
    """
    fg_w = int(OUT_W * fg_scale)
    return (
        f"[0:v]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},gblur=sigma={sigma}[bg];"
        f"[0:v]scale={fg_w}:-2:flags=lanczos[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )


def _blur_top_filter(sigma: int = 30, top_pct: float = 0.62) -> str:
    """
    Video occupies the top `top_pct` of the frame; blurred fill below (caption zone).
    fg_h = OUT_H * top_pct, centered horizontally.
    """
    fg_h = int(OUT_H * top_pct)
    return (
        f"[0:v]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},gblur=sigma={sigma}[bg];"
        f"[0:v]scale={OUT_W}:{fg_h}:force_original_aspect_ratio=decrease,"
        f"pad={OUT_W}:{fg_h}:(ow-iw)/2:0:black[fg];"
        f"[bg][fg]overlay=0:0"
    )


def _mirror_bg_filter(sigma: int = 15) -> str:
    """
    Vertically mirrored (vflip) blurred background + original centered.
    Gives a symmetrical, visually interesting look.
    """
    return (
        f"[0:v]vflip,scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},gblur=sigma={sigma}[bg];"
        f"[0:v]scale={OUT_W}:-2:flags=lanczos[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )


def _facetrack_filter_expr(profile: CropProfile, src_w: int, src_h: int, zoom: float = 1.0) -> str:
    crop_w = min(src_w, int(src_h * 9 / 16 / zoom))
    crop_h = src_h
    idxs = profile.frame_indices
    centers = profile.smoothed_cx

    def _clamp_x(cx_norm: float) -> float:
        cx = cx_norm * src_w
        return max(crop_w / 2, min(src_w - crop_w / 2, cx)) - crop_w / 2

    if len(idxs) == 0:
        return f"crop={crop_w}:{crop_h}:'{(src_w - crop_w) / 2:.1f}':0,scale={OUT_W}:{OUT_H}"

    # Linear interpolation between sample points: lerp(x0,x1,t) = x0+(x1-x0)*t
    pieces = []
    for i in range(len(idxs) - 1):
        f0, f1 = int(idxs[i]), int(idxs[i + 1])
        x0 = _clamp_x(float(centers[i]))
        x1 = _clamp_x(float(centers[i + 1]))
        t = f"(n-{f0})/({f1}-{f0})"
        lerp = f"{x0:.1f}+({x1:.1f}-{x0:.1f})*{t}"
        pieces.append(f"between(n,{f0},{f1-1})*({lerp})")
    # tail: hold last value
    x_tail = _clamp_x(float(centers[-1]))
    pieces.append(f"gte(n,{int(idxs[-1])})*{x_tail:.1f}")

    x_expr = "+".join(pieces)
    return f"crop={crop_w}:{crop_h}:'{x_expr}':0,scale={OUT_W}:{OUT_H}"


def _letterbox_filter(top_pct: float, bot_pct: float, blur: int) -> str:
    top_h = int(OUT_H * top_pct)
    bot_h = int(OUT_H * bot_pct)
    mid_h = OUT_H - top_h - bot_h
    return (
        f"{_COMPLEX}"
        f"[0:v]split=2[base][bg];"
        f"[base]crop=ih*9/16:ih,scale={OUT_W}:{mid_h}[fg];"
        f"[bg]scale={OUT_W}:{OUT_H},boxblur={blur}:1[bgb];"
        f"[bgb][fg]overlay=0:{top_h}"
    )


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

async def render_templated(
    source_video: Path,
    candidate: ClipCandidate,
    clip_id: str,
    asr: Optional[AsrResult] = None,
) -> Path:
    tpl = load_one(candidate.template_id) or load_one("clean") or {}
    layout = tpl.get("layout", {})
    caption = tpl.get("caption", {})
    animation = tpl.get("animation")

    out_dir = settings.data_dir / "clips" / clip_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rendered_{candidate.template_id}.mp4"

    duration = max(candidate.end - candidate.start, 1.0)

    # 1) Trim
    trimmed = out_dir / "_trimmed.mp4"
    await _run(_trim_cmd(source_video, candidate.start, duration, trimmed))

    # 2) Layout → filter string
    layout_type = layout.get("type", "black_bars")
    zoom = float(layout.get("zoom", 1.0))

    if layout_type == "black_bars":
        video_filter = _black_bars_filter()

    elif layout_type == "color_bg":
        color = layout.get("color", "black")
        video_filter = _color_bg_filter(color)

    elif layout_type == "blur_bg":
        sigma = int(layout.get("blur_sigma", 30))
        fg_scale = float(layout.get("fg_scale", 1.0))
        video_filter = _COMPLEX + _blur_bg_filter(sigma, fg_scale)

    elif layout_type == "blur_top":
        sigma = int(layout.get("blur_sigma", 30))
        top_pct = float(layout.get("top_pct", 0.62))
        video_filter = _COMPLEX + _blur_top_filter(sigma, top_pct)

    elif layout_type == "mirror_bg":
        sigma = int(layout.get("blur_sigma", 15))
        video_filter = _COMPLEX + _mirror_bg_filter(sigma)

    elif layout_type in ("face_track", "face_track_letterbox", "split_screen"):
        src_info = _probe(trimmed)
        profile = await asyncio.to_thread(
            compute_crop_profile, trimmed,
            TrackConfig(alpha=layout.get("smoothing", {}).get("alpha", 0.85)),
        )
        if layout_type == "face_track_letterbox":
            video_filter = _letterbox_filter(
                float(layout.get("letterbox_top", 0.1)),
                float(layout.get("letterbox_bottom", 0.1)),
                int(layout.get("letterbox_blur", 30)),
            )
        else:
            video_filter = _facetrack_filter_expr(
                profile, src_info["width"], src_info["height"], zoom=zoom,
            )
    else:
        video_filter = _black_bars_filter()

    # 3) Subtitles
    sub_path = None
    if asr and caption and asr.words:
        sub_path = out_dir / "subtitles.ass"
        sub.write_ass(sub_path, asr.words, candidate.start, candidate.end, caption, animation)

    # 4) Build ffmpeg command
    is_complex = video_filter.startswith(_COMPLEX)
    raw_filter = video_filter[len(_COMPLEX):] if is_complex else video_filter

    if is_complex:
        if sub_path:
            fc = raw_filter + f"[novid];[novid]{_ass_filter(sub_path)}[outv]"
        else:
            fc = raw_filter + "[outv]"
        cmd = [
            _FFMPEG, "-y", "-i", str(trimmed),
            "-filter_complex", fc,
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_path),
        ]
    else:
        vf = raw_filter
        if sub_path:
            vf += f",{_ass_filter(sub_path)}"
        cmd = [
            _FFMPEG, "-y", "-i", str(trimmed),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_path),
        ]
    await _run(cmd)

    trimmed.unlink(missing_ok=True)
    candidate.output_path = str(out_path.relative_to(settings.data_dir / "clips"))
    return out_path


def _probe(path: Path) -> dict:
    import cv2
    cap = cv2.VideoCapture(str(path))
    try:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    finally:
        cap.release()
    return {"width": w, "height": h, "fps": fps}
