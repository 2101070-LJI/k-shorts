"""Sample past preferences as few-shot examples for the LLM prompt.

Spec 7.3: 2×👍 + 1×👎, diversified across source videos so the model
doesn't overfit to one program's pattern. Cold start when fewer than 5
preferences are on record.
"""
import random

from app.db import preferences_repo

COLD_START_MIN = 5


def sample(k_pos: int = 2, k_neg: int = 1) -> list[dict]:
    if preferences_repo.count() < COLD_START_MIN:
        return []

    rows = preferences_repo.labeled_clips()
    pos = [r for r in rows if r["label"] == 1]
    neg = [r for r in rows if r["label"] == -1]

    chosen_pos = _diverse_pick(pos, k_pos)
    chosen_neg = _diverse_pick(neg, k_neg)

    random.shuffle(chosen_pos)
    out = chosen_pos + chosen_neg
    return [
        {"label": r["label"], "title": r.get("title") or "", "reason": r.get("reason") or ""}
        for r in out
    ]


def _diverse_pick(rows: list[dict], k: int) -> list[dict]:
    if k <= 0 or not rows:
        return []
    seen_sources: set[str] = set()
    unique: list[dict] = []
    for r in rows:  # rows are newest-first
        src = r.get("source_video_id") or ""
        if src in seen_sources:
            continue
        seen_sources.add(src)
        unique.append(r)
        if len(unique) >= k:
            return unique
    # Not enough unique sources → pad with any remaining newest items
    if len(unique) < k:
        leftovers = [r for r in rows if r not in unique]
        unique.extend(leftovers[: k - len(unique)])
    return unique[:k]
