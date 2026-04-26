import pytest

from app.pipeline.evolution.performance import performance_score


def test_performance_score_all_zero_is_zero():
    assert performance_score({}) == 0.0


def test_performance_score_in_unit_interval():
    m = {"views": 50_000, "likes": 5_000, "comments": 500, "avg_view_percentage": 100}
    s = performance_score(m)
    assert 0.0 <= s <= 1.0


def test_performance_score_duration_dominates():
    """dur_norm weight=0.5 → retention should be the largest single driver."""
    high_retention = performance_score({"views": 100, "avg_view_percentage": 100})
    high_reach = performance_score({"views": 10_000, "avg_view_percentage": 10})
    assert high_retention > high_reach


def test_performance_score_monotone_in_views():
    base = {"avg_view_percentage": 50, "likes": 0, "comments": 0}
    s1 = performance_score({**base, "views": 100})
    s2 = performance_score({**base, "views": 10_000})
    assert s2 > s1


def test_performance_score_handles_none_fields():
    m = {"views": None, "likes": None, "comments": None, "avg_view_percentage": None}
    assert performance_score(m) == pytest.approx(0.0)
