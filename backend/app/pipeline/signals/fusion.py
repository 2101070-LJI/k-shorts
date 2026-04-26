from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class SignalBundle:
    retention: Optional[np.ndarray]   # None if heatmap unavailable
    laughter: np.ndarray
    volume: np.ndarray
    emotion_joy: np.ndarray
    emotion_surprise: np.ndarray
    tempo: np.ndarray

    def emotion(self) -> np.ndarray:
        return np.maximum(self.emotion_joy, self.emotion_surprise)


@dataclass
class Peak:
    t: float
    score: float
    retention: Optional[float]
    laughter: float
    volume: float
    emotion_joy: float
    emotion_surprise: float
    tempo: float


def effective_weights(base: dict[str, float], retention_available: bool) -> dict[str, float]:
    """
    Spec 3.4 fallback: if heatmap missing, zero out w_retention and renormalize
    the remaining four so they still sum to 1.
    """
    if retention_available:
        total = sum(base.values())
        return {k: v / total for k, v in base.items()} if abs(total - 1) > 1e-6 else base
    rest = {k: v for k, v in base.items() if k != "retention"}
    total = sum(rest.values()) or 1.0
    out = {k: v / total for k, v in rest.items()}
    out["retention"] = 0.0
    return out


def audio_interest_score(bundle: SignalBundle, weights: dict[str, float]) -> np.ndarray:
    w = effective_weights(weights, bundle.retention is not None)
    ret = bundle.retention if bundle.retention is not None else np.zeros_like(bundle.volume)
    return (
        w["retention"] * ret
        + w["laughter"] * bundle.laughter
        + w["volume"] * bundle.volume
        + w["emotion"] * bundle.emotion()
        + w["tempo"] * bundle.tempo
    )


def extract_peaks(
    score: np.ndarray,
    bundle: SignalBundle,
    *,
    min_distance_s: int = 30,
    top_k: int = 10,
    quantile: float = 0.7,
) -> list[Peak]:
    from scipy.signal import find_peaks

    if score.size == 0:
        return []
    height = float(np.quantile(score, quantile))
    idxs, _ = find_peaks(score, distance=min_distance_s, height=height)
    if len(idxs) == 0:
        return []
    scored = sorted(idxs, key=lambda i: -float(score[i]))[:top_k]

    peaks: list[Peak] = []
    for i in sorted(scored):
        peaks.append(
            Peak(
                t=float(i),
                score=float(score[i]),
                retention=float(bundle.retention[i]) if bundle.retention is not None else None,
                laughter=float(bundle.laughter[i]),
                volume=float(bundle.volume[i]),
                emotion_joy=float(bundle.emotion_joy[i]),
                emotion_surprise=float(bundle.emotion_surprise[i]),
                tempo=float(bundle.tempo[i]),
            )
        )
    return peaks
