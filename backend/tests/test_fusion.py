import numpy as np
import pytest

from app.pipeline.signals.fusion import SignalBundle, audio_interest_score, effective_weights
from app.pipeline.signals.retention import retention_series

BASE_WEIGHTS = {
    "retention": 0.35, "laughter": 0.25, "volume": 0.15, "emotion": 0.15, "tempo": 0.10,
}


def test_effective_weights_heatmap_present_sums_to_one():
    w = effective_weights(BASE_WEIGHTS, retention_available=True)
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_effective_weights_heatmap_missing_zeros_retention_and_renormalizes():
    w = effective_weights(BASE_WEIGHTS, retention_available=False)
    assert w["retention"] == 0.0
    assert abs(sum(w.values()) - 1.0) < 1e-9
    # ratios between remaining signals preserved
    assert w["laughter"] == pytest.approx(0.25 / 0.65)
    assert w["volume"] == pytest.approx(0.15 / 0.65)


def test_retention_series_none_on_empty():
    assert retention_series(None, 10) is None
    assert retention_series([], 10) is None


def test_retention_series_normalizes():
    heat = [
        {"start_time": 0, "end_time": 2, "value": 1.0},
        {"start_time": 2, "end_time": 4, "value": 5.0},
        {"start_time": 4, "end_time": 6, "value": 3.0},
    ]
    s = retention_series(heat, 6)
    assert s is not None
    assert s.min() == 0.0 and s.max() == 1.0
    assert s[2] == 1.0  # the 5.0 region maps to 1
    assert s[0] == 0.0  # the 1.0 region maps to 0


def test_retention_series_flat_returns_none():
    heat = [{"start_time": 0, "end_time": 5, "value": 1.0}]
    assert retention_series(heat, 5) is None  # no variance → not useful


def test_audio_interest_score_shape_and_weighting():
    n = 5
    bundle = SignalBundle(
        retention=None,
        laughter=np.ones(n),
        volume=np.zeros(n),
        emotion_joy=np.zeros(n),
        emotion_surprise=np.zeros(n),
        tempo=np.zeros(n),
    )
    score = audio_interest_score(bundle, BASE_WEIGHTS)
    assert score.shape == (n,)
    # laughter weight after retention dropout = 0.25 / 0.65
    expected = 0.25 / 0.65
    assert np.allclose(score, expected)
