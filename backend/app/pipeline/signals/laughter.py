"""Laughter detection via panns_inference.

TODO(M3-follow-up):
  1. Download PANNs checkpoint (Cnn14_mAP=0.431.pth) once; cache in /data/models.
  2. Feed 1s audio chunks, take AudioSet label 'Laughter' posterior.
  3. Return 1Hz series.

M3 baseline: returns zeros so the fusion pipeline still runs end-to-end.
When the actual model is plugged in, callers don't change.
"""
from pathlib import Path

import numpy as np


def laughter_series(audio_path: Path, duration_s: float, sr: int = 1) -> np.ndarray:
    n = max(int(round(duration_s * sr)), 1)
    try:
        return _panns_inference(audio_path, n)
    except ImportError:
        return np.zeros(n, dtype=np.float64)
    except Exception:
        # Model file missing or CUDA hiccup → silent fallback, logged upstream.
        return np.zeros(n, dtype=np.float64)


def _panns_inference(audio_path: Path, n: int) -> np.ndarray:
    # Placeholder — swap in real inference when the checkpoint is available.
    raise ImportError("panns_inference wiring not complete yet")
