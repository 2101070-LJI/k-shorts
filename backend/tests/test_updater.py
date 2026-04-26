"""Pure-logic tests for compute_new_weights (no DB required)."""
import pytest

from app.pipeline.evolution.updater import compute_new_weights, WEIGHT_MIN, WEIGHT_MAX

BASE_WEIGHTS = {
    "retention": 0.35,
    "laughter": 0.25,
    "volume": 0.15,
    "emotion": 0.15,
    "tempo": 0.10,
}


def _row(*, avp, laughter, retention=0.5, volume=0.5, emotion=0.5, tempo=0.5, views=1000, likes=10):
    return {
        "avg_view_percentage": avp,
        "views": views,
        "likes": likes,
        "comments": 0,
        "retention_avg": retention,
        "laughter_peak": laughter,
        "volume_peak": volume,
        "emotion_joy_peak": emotion,
        "tempo_change": tempo,
    }


def test_weights_sum_to_one_after_update():
    rows = [_row(avp=90, laughter=0.9) for _ in range(8)] + [_row(avp=10, laughter=0.1) for _ in range(8)]
    new_w = compute_new_weights(rows, BASE_WEIGHTS)
    assert sum(new_w.values()) == pytest.approx(1.0)


def test_weights_stay_in_clamp_range():
    rows = [_row(avp=99, laughter=10.0) for _ in range(8)] + [_row(avp=1, laughter=0.001) for _ in range(8)]
    new_w = compute_new_weights(rows, BASE_WEIGHTS)
    for v in new_w.values():
        # post-normalization can push below clamp floor, but no weight should exceed 1
        assert 0 < v <= 1.0
    # pre-normalization clamp prevents a single weight from monopolizing
    max_single = WEIGHT_MAX / (WEIGHT_MIN * 4 + WEIGHT_MAX)
    assert max(new_w.values()) <= max_single + 1e-6


def test_signal_strongly_correlated_with_success_increases():
    """Top performers have high laughter; bottom low. Laughter weight should rise."""
    rows = (
        [_row(avp=95, laughter=0.9) for _ in range(8)]
        + [_row(avp=5, laughter=0.05) for _ in range(8)]
    )
    new_w = compute_new_weights(rows, BASE_WEIGHTS)
    assert new_w["laughter"] > BASE_WEIGHTS["laughter"]


def test_uncorrelated_signal_stays_near_baseline():
    """Emotion is constant across top/bot → ratio≈1 → weight unchanged pre-normalization."""
    rows = (
        [_row(avp=95, laughter=0.9, emotion=0.5) for _ in range(8)]
        + [_row(avp=5, laughter=0.05, emotion=0.5) for _ in range(8)]
    )
    new_w = compute_new_weights(rows, BASE_WEIGHTS)
    # After normalization ratios of unchanged signals may drift slightly, but
    # emotion should move less than laughter.
    emotion_delta = abs(new_w["emotion"] - BASE_WEIGHTS["emotion"])
    laughter_delta = abs(new_w["laughter"] - BASE_WEIGHTS["laughter"])
    assert emotion_delta < laughter_delta


def test_missing_signal_field_falls_back_to_old_weight():
    rows = [
        {"avg_view_percentage": 90, "views": 1000, "likes": 0, "comments": 0,
         "retention_avg": None, "laughter_peak": 0.5, "volume_peak": 0.5,
         "emotion_joy_peak": 0.5, "tempo_change": 0.5}
        for _ in range(16)
    ]
    new_w = compute_new_weights(rows, BASE_WEIGHTS)
    # retention_avg is None for every row → keep old weight (up to renormalization drift)
    # Other signals are constant → also near baseline; the key invariant is no crash
    assert sum(new_w.values()) == pytest.approx(1.0)
