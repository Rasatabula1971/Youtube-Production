"""Upload an approved publish package to YouTube (D-143).

Uses the YouTube Data API v3 with the channel owner's OAuth credentials:
a refresh token (obtained once, with the youtube.upload scope) is exchanged
for an access token, the video is sent with a resumable upload
(videos.insert, part=snippet,status) and the approved thumbnail is set
(thumbnails.set). The metadata is exactly the approved publish package:
title, description, tags, category, language, made-for-kids, privacy,
schedule (publishAt) and the altered/synthetic content flag
(status.containsSyntheticMedia).

It is off until ``youtube_upload.enabled`` is true in publish_config.json and
the client id, client secret and refresh token are set in .env. Each upload
re-checks the approval and the exact video and thumbnail bytes, runs once per
video (a published video cannot be uploaded again) and is recorded through
``publish_review.record_upload``. A failure after YouTube accepted the video
records the video id with the error, so a retry never creates a duplicate.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from pipeline_integrity import named_lock
import publish_review

PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - an endpoint, not a secret
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId="
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska"}
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _env_value(name: str) -> str:
    value = os.getenv(name, "")
    if value or not PROJECT_ENV_FILE.exists():
        return value.strip()
    for line in PROJECT_ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, raw = line.partition("=")
        if key.strip() == name:
            return raw.strip().strip('"').strip("'")
    return ""


def settings() -> dict[str, Any]:
    raw = publish_review.load_config().get("youtube_upload")
    return raw if isinstance(raw, dict) else {}


def status() -> dict[str, Any]:
    config = settings()
    problems = []
    if config.get("enabled") is not True:
        problems.append("YouTube upload is off (youtube_upload.enabled in publish_config.json).")
    for key, label in (
        ("client_id_env", "OAuth client id"),
        ("client_secret_env", "OAuth client secret"),
        ("refresh_token_env", "OAuth refresh token"),
    ):
        if not _env_value(str(config.get(key) or "")):
            problems.append(f"The {label} ({config.get(key) or 'unset'}) is empty.")
    return {"ready": not problems, "problems": problems}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def body_for(metadata: dict[str, Any]) -> dict[str, Any]:
    status_part: dict[str, Any] = {
        "privacyStatus": metadata["privacy_status"],
        "selfDeclaredMadeForKids": bool(metadata["made_for_kids"]),
        "containsSyntheticMedia": bool(metadata["contains_synthetic_media"]),
    }
    if metadata.get("publish_at"):
        status_part["publishAt"] = metadata["publish_at"]
    return {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata.get("tags") or [],
            "categoryId": metadata["category_id"],
            "defaultLanguage": metadata["default_language"],
            "defaultAudioLanguage": metadata["default_language"],
        },
        "status": status_part,
    }


def _http(request: urllib.request.Request, timeout: float) -> tuple[dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed Google https URLs
            return dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace") if hasattr(exc, "read") else ""
        raise ValueError(f"YouTube refused the request (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"YouTube request failed: {type(exc).__name__}") from exc


def access_token(config: dict[str, Any], http: Callable[..., tuple[dict[str, str], bytes]] = _http) -> str:
    data = urllib.parse.urlencode(
        {
            "client_id": _env_value(str(config["client_id_env"])),
            "client_secret": _env_value(str(config["client_secret_env"])),
            "refresh_token": _env_value(str(config["refresh_token_env"])),
            "grant_type": "refresh_token",
        }
    ).encode()
    _headers, body = http(urllib.request.Request(TOKEN_URL, data=data, method="POST"), 60)  # noqa: S310 - fixed https URL
    token = json.loads(body.decode("utf-8")).get("access_token")
    if not token:
        raise ValueError("Google did not return an access token")
    return str(token)


def upload(
    *, concept_id: str, format: str, http: Callable[..., tuple[dict[str, str], bytes]] = _http
) -> dict[str, Any]:
    key = f"{concept_id}:{format}"
    with named_lock(f"youtube_upload:{key}"):
        return _upload(str(concept_id), str(format), http)


def _upload(concept_id: str, fmt: str, http: Callable[..., tuple[dict[str, str], bytes]]) -> dict[str, Any]:
    state = status()
    if not state["ready"]:
        raise ValueError("YouTube upload is not available: " + " ".join(state["problems"]))
    if publish_review.publish_record(concept_id, fmt):
        raise ValueError("This video is already published; it will not be uploaded twice")
    approval = publish_review.current_approval(concept_id, fmt)
    if approval is None:
        raise ValueError("Approve the publish package before uploading")
    video = Path(str(approval["video_file"]))
    thumbnail = Path(str(approval["thumbnail_file"]))
    if video.suffix.lower() not in VIDEO_TYPES or not video.is_file() or _sha256(video) != approval["video_sha256"]:
        raise ValueError("The approved video file is missing or changed since approval")
    if thumbnail.suffix.lower() not in IMAGE_TYPES or not thumbnail.is_file() or _sha256(thumbnail) != approval["thumbnail_sha256"]:
        raise ValueError("The approved thumbnail file is missing or changed since approval")

    config = settings()
    timeout = float(config.get("timeout_seconds") or 600)
    token = access_token(config, http)
    auth = {"Authorization": f"Bearer {token}"}
    size = video.stat().st_size
    start = urllib.request.Request(  # noqa: S310 - fixed https URL
        UPLOAD_URL,
        data=json.dumps(body_for(approval["metadata"])).encode("utf-8"),
        headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": VIDEO_TYPES[video.suffix.lower()]},
        method="POST",
    )
    headers, _ = http(start, 60)
    session = headers.get("Location") or headers.get("location")
    if not session or not session.startswith("https://www.googleapis.com/"):
        raise ValueError("YouTube did not return an upload session")
    with video.open("rb") as handle:
        put = urllib.request.Request(  # noqa: S310 - session checked to be https://www.googleapis.com/
            session, data=handle, method="PUT",
            headers={**auth, "Content-Type": VIDEO_TYPES[video.suffix.lower()], "Content-Length": str(size)},
        )
        _headers, body = http(put, timeout)
    video_id = str(json.loads(body.decode("utf-8")).get("id") or "")
    if not publish_review.VIDEO_ID.match(video_id):
        raise ValueError("YouTube did not return a video id")

    thumbnail_error = None
    try:
        http(
            urllib.request.Request(  # noqa: S310 - fixed https URL
                THUMBNAIL_URL + urllib.parse.quote(video_id), data=thumbnail.read_bytes(), method="POST",
                headers={**auth, "Content-Type": IMAGE_TYPES[thumbnail.suffix.lower()]},
            ),
            120,
        )
    except ValueError as exc:
        # The video exists on YouTube: record it so a retry never uploads it again.
        thumbnail_error = str(exc)
    return publish_review.record_upload(
        concept_id=concept_id, format=fmt, youtube_video_id=video_id, method="YOUTUBE_DATA_API",
        details={"thumbnail_set": thumbnail_error is None, "thumbnail_error": thumbnail_error},
    )
