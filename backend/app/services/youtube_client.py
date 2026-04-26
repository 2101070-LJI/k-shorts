"""YouTube Data API v3 — OAuth + Shorts upload.

First-run requires a local browser to authorize. Subsequent calls reuse token.json.
"""
from pathlib import Path
from typing import Optional

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token = settings.youtube_token_file
    secret = settings.youtube_client_secrets

    creds: Optional[Credentials] = None
    if Path(token).exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not Path(secret).exists():
            raise RuntimeError(
                f"client_secret.json not found at {secret}. "
                "Google Cloud Console에서 OAuth desktop 클라이언트를 다운받아 배치하세요."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")

    Path(token).write_text(creds.to_json(), encoding="utf-8")
    return creds


def _build():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_load_credentials(), cache_discovery=False)


def upload_short(
    video_path: Path,
    title: str,
    description: str = "",
    tags: Optional[list[str]] = None,
    privacy: str = "private",
) -> str:
    from googleapiclient.http import MediaFileUpload

    if not video_path.exists():
        raise FileNotFoundError(str(video_path))

    if len(title) > 95:
        title = title[:92] + "…"

    full_desc = description.rstrip() + "\n\n#Shorts"
    yt = _build()
    body = {
        "snippet": {
            "title": title,
            "description": full_desc,
            "tags": list({*(tags or []), "Shorts", "예능"}),
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = req.next_chunk()
    return response["id"]


def get_stats(yt_video_id: str) -> dict:
    yt = _build()
    r = yt.videos().list(part="statistics,contentDetails", id=yt_video_id).execute()
    items = r.get("items", [])
    if not items:
        return {}
    stats = items[0].get("statistics", {})
    return {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
    }


def _build_analytics():
    from googleapiclient.discovery import build
    return build("youtubeAnalytics", "v2", credentials=_load_credentials(), cache_discovery=False)


def get_analytics(yt_video_id: str) -> dict:
    """YouTube Analytics metrics (channel-owner only).

    Returns {} when the video is too new, has too little data, or the API
    is unavailable — callers must tolerate missing fields.
    """
    try:
        ya = _build_analytics()
        r = ya.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate="2099-12-31",
            metrics="averageViewDuration,averageViewPercentage",
            filters=f"video=={yt_video_id}",
        ).execute()
    except Exception:
        return {}

    headers = [h["name"] for h in r.get("columnHeaders", [])]
    rows = r.get("rows") or []
    if not rows:
        return {}
    row = dict(zip(headers, rows[0]))
    return {
        "avg_view_duration": float(row.get("averageViewDuration", 0) or 0),
        "avg_view_percentage": float(row.get("averageViewPercentage", 0) or 0),
    }
