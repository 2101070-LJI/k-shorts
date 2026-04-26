from datetime import datetime
from statistics import mean

from fastapi import APIRouter

from app.db import clips_repo, metrics_repo, preferences_repo, weights_repo
from app.pipeline.evolution import scheduler
from app.pipeline.evolution.collector import refresh_all_metrics
from app.pipeline.evolution.performance import performance_score
from app.pipeline.evolution.updater import SIGNAL_FIELDS

router = APIRouter(prefix="/evolution", tags=["evolution"])


@router.get("/weights")
def weights_over_time() -> dict:
    return {
        "history": weights_repo.history(),
        "current": weights_repo.current_weights(),
        "next_cron": scheduler.next_run(),
    }


@router.post("/refresh")
def manual_refresh() -> dict:
    """Trigger metrics fetch + possible weight update on demand (spec 8.M5)."""
    return refresh_all_metrics()


@router.get("/performance")
def performance_trend() -> list[dict]:
    rows = metrics_repo.weekly_performance_rows()
    return [
        {
            "clip_id": r["clip_id"],
            "created_at": r["created_at"],
            "score": performance_score(r),
            "views": r.get("views") or 0,
        }
        for r in rows
    ]


@router.get("/signal-comparison")
def signal_comparison() -> list[dict]:
    """Top 25% vs bottom 25% performer mean for each signal. Chart 3."""
    rows = metrics_repo.latest_per_clip()
    if len(rows) < 6:
        return []
    scored = sorted(rows, key=lambda r: performance_score(r), reverse=True)
    k = max(len(scored) // 4, 3)
    top, bot = scored[:k], scored[-k:]

    def _avg(group: list[dict], field: str) -> float:
        vals = [r[field] for r in group if r.get(field) is not None]
        return float(mean(vals)) if vals else 0.0

    return [
        {"signal": sig, "top": _avg(top, field), "bot": _avg(bot, field)}
        for sig, field in SIGNAL_FIELDS.items()
    ]


@router.get("/insights")
def insights() -> dict:
    history = weights_repo.history()
    clips = clips_repo.list_clips(limit=1000)
    metric_rows = metrics_repo.weekly_performance_rows()

    total_views = sum((r.get("views") or 0) for r in metric_rows)

    biggest = None
    if len(history) >= 2:
        first, last = history[0], history[-1]
        deltas = [
            (last[f"w_{s}"] - first[f"w_{s}"], s)
            for s in ("retention", "laughter", "volume", "emotion", "tempo")
        ]
        biggest = max(deltas)

    improvement_pct = 0.0
    if metric_rows:
        sorted_rows = sorted(
            metric_rows,
            key=lambda r: datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.min,
        )
        quarter = max(len(sorted_rows) // 4, 1)
        early = sorted_rows[:quarter]
        recent = sorted_rows[-quarter:]
        early_avg = sum(performance_score(r) for r in early) / len(early)
        recent_avg = sum(performance_score(r) for r in recent) / len(recent)
        if early_avg > 0:
            improvement_pct = (recent_avg / early_avg - 1) * 100

    return {
        "total_clips": len(clips),
        "total_views": total_views,
        "total_feedbacks": preferences_repo.count(),
        "biggest_grower": {"signal": biggest[1], "delta": biggest[0]} if biggest else None,
        "improvement_pct": round(improvement_pct, 1),
        "weight_updates": max(len(history) - 1, 0),
        "learning_status": "자기진화 작동 중 ✓" if improvement_pct > 10 else "데이터 축적 중",
    }
