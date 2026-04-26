"""Korean speech emotion via Wav2Vec2.

TODO(M3-follow-up):
  1. Choose a Hugging Face model (candidates: 'kresnik/wav2vec2-large-xlsr-korean',
     community-tuned emotion heads). Cache to /data/models on first use.
  2. 1s chunks → joy/surprise probabilities.
  3. Return dict with 'joy' and 'surprise' 1Hz series.

M3 baseline returns zeros; fusion handles missing signals gracefully.
"""
from pathlib import Path

import numpy as np


def emotion_series(audio_path: Path, duration_s: float, sr: int = 1) -> dict[str, np.ndarray]:
    n = max(int(round(duration_s * sr)), 1)
    zeros = np.zeros(n, dtype=np.float64)
    return {"joy": zeros, "surprise": zeros}
