from pathlib import Path

import numpy as np


def volume_series(audio_path: Path, duration_s: float, sr: int = 1) -> np.ndarray:
    """RMS envelope → downsampled to 1Hz, normalized to [0, 1]."""
    import librosa

    y, audio_sr = librosa.load(str(audio_path), sr=16000, mono=True)
    hop_length = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]

    n = max(int(round(duration_s * sr)), 1)
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=audio_sr, hop_length=hop_length)
    target_times = np.arange(n) / sr
    down = np.interp(target_times, rms_times, rms, left=rms[0], right=rms[-1])

    lo, hi = float(down.min()), float(np.percentile(down, 99))
    if hi - lo < 1e-9:
        return np.zeros(n)
    down = np.clip((down - lo) / (hi - lo), 0, 1)
    return down
