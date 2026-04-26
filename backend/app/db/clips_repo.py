import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.db.connection import get_conn


@dataclass
class ClipRow:
    id: int
    source_url: str
    source_video_id: str
    start_time: float
    end_time: float
    title: Optional[str]
    reason: Optional[str]
    template_id: str
    llm_model: str
    llm_score: Optional[float]
    weights_snapshot: dict
    created_at: str
    yt_video_id: Optional[str]
    output_path: Optional[str] = None  # joined from render cache, see list_clips

    @classmethod
    def from_row(cls, row) -> "ClipRow":
        d = dict(row)
        d["weights_snapshot"] = json.loads(d["weights_snapshot"] or "{}")
        return cls(**{k: d.get(k) for k in cls.__annotations__})


def save_clip(
    *,
    source_url: str,
    source_video_id: str,
    start_time: float,
    end_time: float,
    title: str,
    reason: str,
    template_id: str,
    llm_model: str,
    llm_score: float,
    weights_snapshot: dict,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO clips (source_url, source_video_id, start_time, end_time,
                               title, reason, template_id, llm_model, llm_score,
                               weights_snapshot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_url, source_video_id, start_time, end_time,
                title, reason, template_id, llm_model, llm_score,
                json.dumps(weights_snapshot), datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def list_clips(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clips ORDER BY created_at DESC LIMIT ?", (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_clip(clip_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
    return _row_to_dict(row) if row else None


def set_youtube_id(clip_id: int, yt_video_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE clips SET yt_video_id = ? WHERE id = ?", (yt_video_id, clip_id))


def save_signals(clip_id: int, signals: dict) -> None:
    allowed = {
        "retention_avg", "laughter_peak", "volume_peak",
        "emotion_joy_peak", "emotion_surprise_peak",
        "tempo_change", "clip_duration", "whisper_text",
    }
    cols = {k: v for k, v in signals.items() if k in allowed}
    if not cols:
        return
    keys = list(cols.keys())
    placeholders = ", ".join(["?"] * (len(keys) + 1))
    with get_conn() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO clip_signals (clip_id, {', '.join(keys)}) "
            f"VALUES ({placeholders})",
            [clip_id, *cols.values()],
        )


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["weights_snapshot"] = json.loads(d["weights_snapshot"] or "{}")
    except (TypeError, json.JSONDecodeError):
        d["weights_snapshot"] = {}
    return d
