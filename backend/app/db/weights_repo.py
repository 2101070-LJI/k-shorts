from datetime import datetime
from typing import Optional

from app.db.connection import get_conn

SIGNALS = ("retention", "laughter", "volume", "emotion", "tempo")


def current_weights() -> dict[str, float]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM weight_history ORDER BY effective_from DESC, id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return {"retention": 0.35, "laughter": 0.25, "volume": 0.15, "emotion": 0.15, "tempo": 0.10}
    return {s: float(row[f"w_{s}"]) for s in SIGNALS}


def insert_update(
    weights: dict[str, float],
    *,
    reason: str,
    trigger_clip_count: Optional[int] = None,
    notes: str = "",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weight_history
              (effective_from, w_retention, w_laughter, w_volume, w_emotion, w_tempo,
               update_reason, trigger_clip_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                weights["retention"], weights["laughter"], weights["volume"],
                weights["emotion"], weights["tempo"],
                reason, trigger_clip_count, notes,
            ),
        )


def history() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM weight_history ORDER BY effective_from ASC, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]
