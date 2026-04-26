import numpy as np

from app.pipeline.stages.asr import AsrResult


def tempo_series(asr: AsrResult, duration_s: float, window_s: float = 10.0, sr: int = 1) -> np.ndarray:
    """
    Word density change rate. For each second, count words in a symmetric window
    and take the absolute derivative (change per second), normalized to [0, 1].
    """
    n = max(int(round(duration_s * sr)), 1)
    density = np.zeros(n, dtype=np.float64)
    if not asr.words:
        return density

    starts = np.array([w.start for w in asr.words])
    half = window_s / 2.0
    for i in range(n):
        t = i / sr
        count = int(np.sum((starts >= t - half) & (starts < t + half)))
        density[i] = count / window_s  # words/sec

    diff = np.abs(np.diff(density, prepend=density[0]))
    peak = float(np.percentile(diff, 99))
    if peak < 1e-9:
        return np.zeros(n)
    return np.clip(diff / peak, 0, 1)
