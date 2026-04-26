from app.db.connection import get_conn


def record(clip_id: int, label: int) -> int:
    if label not in (-1, 1):
        raise ValueError("label must be -1 or 1")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO preferences (clip_id, label) VALUES (?, ?)", (clip_id, label),
        )
        return cur.lastrowid


def count() -> int:
    with get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0])


def labeled_clips() -> list[dict]:
    """All preferences joined with their clip info, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.id AS pref_id, p.label, p.created_at AS pref_at,
                   c.id AS clip_id, c.title, c.reason, c.source_video_id
              FROM preferences p
              JOIN clips c ON c.id = p.clip_id
             ORDER BY p.created_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]
