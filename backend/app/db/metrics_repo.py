from datetime import datetime
from typing import Optional

from app.db.connection import get_conn


def insert(clip_id: int, stats: dict, *, collected_at: Optional[datetime] = None) -> None:
    ts = (collected_at or datetime.utcnow()).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO metrics
              (clip_id, collected_at, views, likes, comments,
               avg_view_duration, avg_view_percentage, impressions, swipe_away_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clip_id, ts,
                stats.get("views"), stats.get("likes"), stats.get("comments"),
                stats.get("avg_view_duration"), stats.get("avg_view_percentage"),
                stats.get("impressions"), stats.get("swipe_away_rate"),
            ),
        )


def latest_per_clip() -> list[dict]:
    """Most-recent metric row per clip, joined with clip+signals.

    Used by the Phase 2 weight updater: each clip contributes exactly one
    (signals, performance) point.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS clip_id, c.created_at AS clip_created_at,
                   c.yt_video_id,
                   s.retention_avg, s.laughter_peak, s.volume_peak,
                   s.emotion_joy_peak, s.emotion_surprise_peak,
                   s.tempo_change, s.clip_duration,
                   m.collected_at, m.views, m.likes, m.comments,
                   m.avg_view_duration, m.avg_view_percentage,
                   m.impressions, m.swipe_away_rate
              FROM clips c
              JOIN clip_signals s ON s.clip_id = c.id
              JOIN metrics m ON m.clip_id = c.id
              JOIN (
                SELECT clip_id, MAX(collected_at) AS max_at
                  FROM metrics
                 GROUP BY clip_id
              ) latest ON latest.clip_id = m.clip_id AND latest.max_at = m.collected_at
             WHERE c.yt_video_id IS NOT NULL
            """
        ).fetchall()
    return [dict(r) for r in rows]


def weekly_performance_rows() -> list[dict]:
    """Per-clip (clip_created_at, performance inputs). Used by evolution UI."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS clip_id, c.created_at,
                   m.views, m.likes, m.comments,
                   m.avg_view_duration, m.avg_view_percentage
              FROM clips c
              JOIN metrics m ON m.clip_id = c.id
              JOIN (
                SELECT clip_id, MAX(collected_at) AS max_at
                  FROM metrics
                 GROUP BY clip_id
              ) latest ON latest.clip_id = m.clip_id AND latest.max_at = m.collected_at
             WHERE c.yt_video_id IS NOT NULL
          ORDER BY c.created_at ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]
