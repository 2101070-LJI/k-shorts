"""Spec 7.4 — Weight update algorithm.

Gated by: (a) ≥10 clips with settled metrics, (b) +10 new clips since last
update. When triggered, compares top 25% vs bottom 25% performers on each
signal, nudges weights up if the signal was higher in top performers.
"""
import logging
from datetime import datetime, timedelta
from statistics import mean
from typing import Iterable, Optional

from app.db import metrics_repo, weights_repo
from app.db.connection import get_conn
from app.pipeline.evolution.performance import performance_score

log = logging.getLogger(__name__)

LEARNING_RATE = 0.15
WEIGHT_MIN = 0.05
WEIGHT_MAX = 0.60
MIN_CLIPS = 10
RETRIGGER_DELTA = 10
METRIC_SETTLE_DAYS = 7

SIGNAL_FIELDS = {
    "retention": "retention_avg",
    "laughter": "laughter_peak",
    "volume": "volume_peak",
    "emotion": "emotion_joy_peak",
    "tempo": "tempo_change",
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _last_trigger_count() -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trigger_clip_count FROM weight_history "
            "ORDER BY effective_from DESC, id DESC LIMIT 1"
        ).fetchone()
    return None if row is None else row["trigger_clip_count"]


def _settled(rows: Iterable[dict], now: datetime) -> list[dict]:
    cutoff = now - timedelta(days=METRIC_SETTLE_DAYS)
    out = []
    for r in rows:
        try:
            created = datetime.fromisoformat(r["clip_created_at"])
        except (TypeError, ValueError):
            continue
        if created <= cutoff:
            out.append(r)
    return out


def compute_new_weights(rows: list[dict], old_w: dict[str, float]) -> dict[str, float]:
    """Pure function — given settled rows and old weights, return new weights.

    Exposed for testing. No DB access.
    """
    scored = sorted(rows, key=lambda r: performance_score(r), reverse=True)
    n = len(scored)
    k = max(n // 4, 3)
    top = scored[:k]
    bot = scored[-k:]

    new_w: dict[str, float] = {}
    for sig, field in SIGNAL_FIELDS.items():
        top_vals = [r[field] for r in top if r.get(field) is not None]
        bot_vals = [r[field] for r in bot if r.get(field) is not None]
        if not top_vals or not bot_vals:
            new_w[sig] = old_w[sig]
            continue
        ratio = (mean(top_vals) + 1e-3) / (mean(bot_vals) + 1e-3)
        new_w[sig] = old_w[sig] * (1 + LEARNING_RATE * (ratio - 1))

    new_w = {k: _clamp(v, WEIGHT_MIN, WEIGHT_MAX) for k, v in new_w.items()}
    total = sum(new_w.values())
    return {k: v / total for k, v in new_w.items()}


def maybe_update_weights(*, now: Optional[datetime] = None) -> Optional[dict[str, float]]:
    """Run the Phase 2 update if gates allow. Returns new weights or None."""
    now = now or datetime.utcnow()
    all_rows = metrics_repo.latest_per_clip()
    settled = _settled(all_rows, now)
    if len(settled) < MIN_CLIPS:
        log.info("phase2: %d settled clips (<%d) — skip", len(settled), MIN_CLIPS)
        return None

    last = _last_trigger_count()
    if last is not None and len(settled) < last + RETRIGGER_DELTA:
        log.info("phase2: %d settled vs last=%d (need +%d) — skip",
                 len(settled), last, RETRIGGER_DELTA)
        return None

    old_w = weights_repo.current_weights()
    new_w = compute_new_weights(settled, old_w)
    weights_repo.insert_update(
        new_w,
        reason="auto_phase2",
        trigger_clip_count=len(settled),
        notes=f"top/bot of {len(settled)} settled clips",
    )
    log.info("phase2: weights updated from %s → %s", old_w, new_w)
    return new_w
