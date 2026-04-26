"""Spec 7.4 cron body — pull stats + analytics for every uploaded clip."""
import logging

from app.db import clips_repo, metrics_repo
from app.pipeline.evolution.updater import maybe_update_weights
from app.services import youtube_client

log = logging.getLogger(__name__)


def refresh_all_metrics() -> dict:
    """Fetch fresh YouTube stats for every clip with a yt_video_id, then
    attempt a weight update. Returns a small summary for the UI.
    """
    uploaded = [c for c in clips_repo.list_clips(limit=1000) if c.get("yt_video_id")]
    ok, failed = 0, 0
    for clip in uploaded:
        yt_id = clip["yt_video_id"]
        try:
            stats = youtube_client.get_stats(yt_id)
            if not stats:
                failed += 1
                continue
            stats.update(youtube_client.get_analytics(yt_id))
            metrics_repo.insert(clip["id"], stats)
            ok += 1
        except Exception as e:
            log.warning("metric fetch failed for %s: %s", yt_id, e)
            failed += 1

    updated = maybe_update_weights()
    return {
        "clips_refreshed": ok,
        "failed": failed,
        "weights_updated": updated is not None,
        "new_weights": updated,
    }
