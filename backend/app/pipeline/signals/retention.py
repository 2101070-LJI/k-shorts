from typing import Optional

import numpy as np


def retention_series(
    heatmap: Optional[list[dict]], duration_s: float, sr: int = 1
) -> Optional[np.ndarray]:
    """
    Convert yt-dlp heatmap (list of {start_time, end_time, value}) to a 1Hz
    normalized series over [0, duration_s). Returns None if heatmap missing or empty.

    Values in heatmap are in arbitrary YouTube units; we min-max to [0, 1].
    """
    if not heatmap:
        return None

    n = max(int(round(duration_s * sr)), 1)
    series = np.zeros(n, dtype=np.float64)
    for h in heatmap:
        try:
            s = float(h["start_time"]); e = float(h["end_time"]); v = float(h["value"])
        except (KeyError, TypeError, ValueError):
            continue
        i0 = max(0, int(s * sr))
        i1 = min(n, int(e * sr))
        if i1 > i0:
            series[i0:i1] = v

    lo, hi = float(series.min()), float(series.max())
    if hi - lo < 1e-9:
        return None
    return (series - lo) / (hi - lo)
