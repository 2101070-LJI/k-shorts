"""Spec 7.4 — Performance score (pure function, scalar in [0, 1]).

Mapping of YouTube Analytics signals to scoring weights:
  - dur_norm       0.50  (avg_view_percentage — retention is king for Shorts)
  - like_rate      0.25  (engagement)
  - comment_rate   0.15  (engagement, rarer than likes → amplified ×100)
  - view_norm      0.10  (reach, log-scaled so 10k views saturates)
"""
import math


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def performance_score(m: dict) -> float:
    views = m.get("views") or 0
    likes = m.get("likes") or 0
    comments = m.get("comments") or 0
    avp = m.get("avg_view_percentage") or 0.0

    dur_norm = _clamp(avp / 100.0, 0.0, 1.0)
    like_rate = min(likes / max(views, 1) * 10, 1.0)
    comment_rate = min(comments / max(views, 1) * 100, 1.0)
    view_norm = min(math.log1p(views) / math.log(10_000), 1.0)

    return (
        0.50 * dur_norm
        + 0.25 * like_rate
        + 0.15 * comment_rate
        + 0.10 * view_norm
    )
