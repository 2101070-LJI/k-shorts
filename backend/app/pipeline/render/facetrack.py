"""Face-track 9:16 reframe with EMA smoothing.

Strategy:
  1. Sample face positions at ~5 Hz using OpenCV Haar cascade (CPU, fast).
  2. EMA-smooth the center-x timeline (alpha=0.85 by default).
  3. For every video frame, interpolate the smoothed x and crop a 9:16 window.

Output target: 1080×1920 @ source fps, audio preserved.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class TrackConfig:
    alpha: float = 0.85
    sample_hz: float = 5.0
    out_w: int = 1080
    out_h: int = 1920


def _pick_primary_face(faces, frame_w: int, frame_h: int) -> Optional[float]:
    """Return normalized cx of the largest face closest to center."""
    if len(faces) == 0:
        return None
    cx_target = frame_w / 2
    best = None
    best_score = -1.0
    for (x, y, w, h) in faces:
        cx = x + w / 2
        area = w * h
        score = area - 0.1 * abs(cx - cx_target)
        if score > best_score:
            best_score = score
            best = cx / frame_w
    return best


def _sample_face_positions(video_path: Path, cfg: TrackConfig) -> tuple[np.ndarray, np.ndarray, int]:
    import cv2

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, int(round(fps / cfg.sample_hz)))

    sample_idxs: list[int] = []
    centers: list[float] = []

    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            cx = _pick_primary_face(faces if len(faces) > 0 else [], frame_w, frame_h)
            if cx is not None:
                sample_idxs.append(i)
                centers.append(cx)
        i += 1
    cap.release()

    if not sample_idxs:
        # No faces detected; return a flat center line.
        return np.array([0, total], dtype=np.int64), np.array([0.5, 0.5]), total

    return np.array(sample_idxs), np.array(centers), total


def _ema(values: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * out[i - 1] + (1 - alpha) * values[i]
    return out


def compute_crop_profile(video_path: Path, cfg: TrackConfig | None = None) -> "CropProfile":
    """Sample + smooth face positions and return an interpolator usable per frame."""
    cfg = cfg or TrackConfig()
    idxs, centers, total = _sample_face_positions(video_path, cfg)
    smoothed = _ema(centers, cfg.alpha)
    return CropProfile(frame_indices=idxs, smoothed_cx=smoothed, total_frames=total)


@dataclass
class CropProfile:
    frame_indices: np.ndarray
    smoothed_cx: np.ndarray  # normalized [0, 1]
    total_frames: int

    def cx_at_frame(self, frame_idx: int) -> float:
        if self.frame_indices.size == 0:
            return 0.5
        return float(np.interp(frame_idx, self.frame_indices, self.smoothed_cx))
