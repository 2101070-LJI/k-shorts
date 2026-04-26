from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.pipeline.stages.asr import AsrResult

MIN_LEN = 15.0
MAX_LEN = 59.0
MIN_SILENCE_S = 0.3


@dataclass
class Interval:
    start: float
    end: float


def detect_silences(audio_path: Path, min_silence_s: float = MIN_SILENCE_S) -> list[Interval]:
    """Simple RMS-threshold silence detection (16kHz mono)."""
    import librosa

    y, sr = librosa.load(str(audio_path), sr=16000, mono=True)
    frame = 1024
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop)[0]
    threshold = float(np.percentile(rms, 20))
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)

    silences: list[Interval] = []
    cur_start: float | None = None
    for t, v in zip(times, rms):
        if v < threshold:
            if cur_start is None:
                cur_start = float(t)
        else:
            if cur_start is not None and t - cur_start >= min_silence_s:
                silences.append(Interval(start=cur_start, end=float(t)))
            cur_start = None
    if cur_start is not None and times[-1] - cur_start >= min_silence_s:
        silences.append(Interval(start=cur_start, end=float(times[-1])))
    return silences


def _nearest_silence_before(silences: list[Interval], t: float, max_offset: float = 2.0) -> float:
    cand = [s.end for s in silences if s.end <= t and t - s.end <= max_offset]
    return max(cand) if cand else t


def _nearest_silence_after(silences: list[Interval], t: float, max_offset: float = 2.5) -> float:
    cand = [s.start for s in silences if s.start >= t and s.start - t <= max_offset]
    return min(cand) if cand else t


def _snap_to_words(t: float, words: list, which: str) -> float:
    if not words:
        return t
    # nearest word start (for 'start') or word end (for 'end')
    if which == "start":
        candidates = [w.start for w in words]
    else:
        candidates = [w.end for w in words]
    i = int(np.argmin(np.abs(np.array(candidates) - t)))
    return float(candidates[i])


def snap_boundaries(
    start: float,
    end: float,
    asr: AsrResult,
    silences: list[Interval],
    tail_reaction_s: float = 1.0,
) -> tuple[float, float]:
    """Spec 3.7:
       1. start → nearest silence-end before
       2. end   → nearest silence-start after, plus reaction tail
       3. snap to word boundaries
       4. enforce length bounds
    """
    start_sil = _nearest_silence_before(silences, start)
    end_sil = _nearest_silence_after(silences, end) + tail_reaction_s

    start_snapped = _snap_to_words(start_sil, asr.words, "start")
    end_snapped = _snap_to_words(end_sil, asr.words, "end")

    length = end_snapped - start_snapped
    if length < MIN_LEN:
        pad = (MIN_LEN - length) / 2
        start_snapped = max(0.0, start_snapped - pad)
        end_snapped = end_snapped + pad
    elif length > MAX_LEN:
        mid = (start_snapped + end_snapped) / 2
        start_snapped = mid - MAX_LEN / 2
        end_snapped = mid + MAX_LEN / 2

    return max(0.0, start_snapped), max(start_snapped + MIN_LEN, end_snapped)
