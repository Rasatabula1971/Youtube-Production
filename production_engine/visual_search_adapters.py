"""Zero-cost visual discovery adapters for storyboard shots.

Pexels/Pixabay return stock candidates. YouTube is discovery-only for creator
footage and never grants reuse permission. Wikimedia results remain blocked
until their item-level license metadata is verified.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Callable


def _json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def pexels_videos(query: str, limit: int = 5) -> list[dict[str, Any]]:
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    url = "https://api.pexels.com/v1/videos/search?" + urllib.parse.urlencode({"query": query, "per_page": limit})
    data = _json(url, headers={"Authorization": key})
    out = []
    for item in data.get("videos", [])[:limit]:
        files = item.get("video_files") or []
        file_url = files[0].get("link") if files and isinstance(files[0], dict) else None
        user = item.get("user") or {}
        out.append({
            "candidate_id": f"pexels-{item.get('id')}",
            "title": f"Pexels video {item.get('id')}",
            "media_type": "video",
            "source_tier": "FREE_COMMERCIAL_LICENSE",
            "source_url": item.get("url"),
            "preview_media_url": file_url,
            "thumbnail_url": (item.get("video_pictures") or [{}])[0].get("picture"),
            "creator": user.get("name"),
            "license": "Pexels License",
            "rights_status": "VERIFIED",
            "commercial_use_allowed": True,
            "duration_seconds": item.get("duration"),
            "search_provider": "pexels",
            "estimated_cost_usd": 0.0,
        })
    return out


def pixabay_videos(query: str, limit: int = 5) -> list[dict[str, Any]]:
    key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not key:
        return []
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": query[:100], "per_page": max(3, limit)})
    data = _json(url)
    out = []
    for item in data.get("hits", [])[:limit]:
        videos = item.get("videos") or {}
        media = videos.get("medium") or videos.get("small") or {}
        out.append({
            "candidate_id": f"pixabay-{item.get('id')}",
            "title": f"Pixabay video {item.get('id')}",
            "media_type": "video",
            "source_tier": "FREE_COMMERCIAL_LICENSE",
            "source_url": item.get("pageURL"),
            "preview_media_url": media.get("url"),
            "thumbnail_url": None,
            "creator": item.get("user"),
            "license": "Pixabay Content License",
            "rights_status": "VERIFIED",
            "commercial_use_allowed": True,
            "duration_seconds": item.get("duration"),
            "search_provider": "pixabay",
            "estimated_cost_usd": 0.0,
        })
    return out


def youtube_creator_discovery(query: str, limit: int = 5, *, creative_commons_only: bool = False) -> list[dict[str, Any]]:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    params = {"key": key, "part": "snippet", "type": "video", "q": query, "maxResults": limit}
    if creative_commons_only:
        params["videoLicense"] = "creativeCommon"
    data = _json("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params))
    out = []
    for item in data.get("items", [])[:limit]:
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id:
            continue
        out.append({
            "candidate_id": f"youtube-{video_id}",
            "title": snippet.get("title"),
            "media_type": "video",
            "source_tier": "EDITORIAL_EXCERPT",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": ((snippet.get("thumbnails") or {}).get("high") or {}).get("url"),
            "creator": snippet.get("channelTitle"),
            "license": "YouTube Creative Commons filter" if creative_commons_only else "UNKNOWN",
            "rights_status": "DISCOVERY_ONLY",
            "commercial_use_allowed": None,
            "search_provider": "youtube_data_api",
            "estimated_cost_usd": 0.0,
            "human_review_required": True,
        })
    return out


def _safe_provider_call(
    name: str,
    call: Callable[[], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    try:
        value = call()
    except Exception as exc:  # External provider/network boundary.
        return [], {
            "provider": name,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }
    if not isinstance(value, list):
        return [], {
            "provider": name,
            "error_type": "InvalidProviderResponse",
            "error": "Provider adapter did not return a list.",
        }
    return [item for item in value if isinstance(item, dict)], None


def discover_with_diagnostics(
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    query = str(query or "").strip()
    if not query:
        raise ValueError("Visual discovery query is required")
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("Visual discovery limit must be an integer") from exc
    if limit < 1 or limit > 20:
        raise ValueError("Visual discovery limit must be between 1 and 20")

    providers: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    calls: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
        ("pexels", lambda: pexels_videos(query, limit)),
        ("pixabay", lambda: pixabay_videos(query, limit)),
        (
            "youtube_creator",
            lambda: youtube_creator_discovery(query, limit),
        ),
        (
            "youtube_creative_commons",
            lambda: youtube_creator_discovery(
                query,
                limit,
                creative_commons_only=True,
            ),
        ),
    ]
    for name, call in calls:
        candidates, error = _safe_provider_call(name, call)
        providers[name] = candidates
        if error is not None:
            errors.append(error)

    return {
        "providers": providers,
        "errors": errors,
        "paid_calls_allowed": False,
    }


def discover(query: str, limit: int = 5) -> dict[str, Any]:
    """Backward-compatible candidate-only discovery result."""
    return discover_with_diagnostics(query, limit)["providers"]
