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

The upload is resumable end to end (D-167): the session URI is saved to a
pending-upload record before any video bytes are sent. A retry after a
timeout or lost connection first asks YouTube how much of that session it
holds (``Content-Range: bytes */size``): a finished session yields the
video id and is recorded, a partial one is continued from the byte YouTube
reports, and only a dead session starts a new upload. One approved video
therefore never becomes two private videos on the channel.
"""

from __future__ import annotations

import hashlib
import http.client
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


class UploadHttpError(ValueError):
    """An HTTP error answer, with its status and headers (308 carries the resume offset)."""

    def __init__(self, message: str, *, code: int, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.headers = headers or {}


def _http(request: urllib.request.Request, timeout: float) -> tuple[dict[str, str], bytes]:
    # Every URL here is Google's (fixed endpoints, or the session address
    # Google returned); refuse anything that is not https all the same.
    if urllib.parse.urlparse(request.full_url).scheme != "https":
        raise ValueError("YouTube upload URLs must be https://")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https checked above  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            return dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace") if hasattr(exc, "read") else ""
        headers = dict(exc.headers.items()) if getattr(exc, "headers", None) else {}
        raise UploadHttpError(
            f"YouTube refused the request (HTTP {exc.code}): {detail}", code=int(exc.code), headers=headers
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        # Connection-level failures (RemoteDisconnected, IncompleteRead, a reset)
        # are not URLError; they must still reach the caller as ValueError (audit 2).
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


def metadata_sha256(metadata: dict[str, Any]) -> str:
    """Hash of exactly what YouTube is sent for this video's snippet and status."""
    return hashlib.sha256(json.dumps(body_for(metadata), sort_keys=True).encode("utf-8")).hexdigest()


def _upload(concept_id: str, fmt: str, http: Callable[..., tuple[dict[str, str], bytes]]) -> dict[str, Any]:
    state = status()
    if not state["ready"]:
        raise ValueError("YouTube upload is not available: " + " ".join(state["problems"]))
    if publish_review.publish_record(concept_id, fmt):
        raise ValueError("This video is already published; it will not be uploaded twice")
    approval = publish_review.current_approval(concept_id, fmt)
    pending = publish_review.pending_upload(concept_id, fmt)
    known_id = str((pending or {}).get("video_id") or "")
    if approval is None:
        if known_id:
            raise ValueError(
                f"YouTube already has this video as {known_id}, but its publish approval is no longer "
                "current. Approve the publish package again, then choose Upload to YouTube: it records "
                f"{known_id} and uploads nothing."
            )
        if pending:
            raise ValueError(
                "An upload of this video was started under an approval that is no longer current. Check "
                "YouTube Studio for a half-uploaded private video, discard the interrupted upload, then approve again."
            )
        raise ValueError("Approve the publish package before uploading")
    video = Path(str(approval["video_file"]))
    thumbnail = Path(str(approval["thumbnail_file"]))
    if not known_id:
        if video.suffix.lower() not in VIDEO_TYPES or not video.is_file() or _sha256(video) != approval["video_sha256"]:
            raise ValueError("The approved video file is missing or changed since approval")
    if thumbnail.suffix.lower() not in IMAGE_TYPES or not thumbnail.is_file() or _sha256(thumbnail) != approval["thumbnail_sha256"]:
        raise ValueError("The approved thumbnail file is missing or changed since approval")

    config = settings()
    timeout = float(config.get("timeout_seconds") or 600)
    token = access_token(config, http)
    auth = {"Authorization": f"Bearer {token}"}
    meta_hash = metadata_sha256(approval["metadata"])

    video_id = known_id
    resumed = bool(known_id)
    if not video_id:
        size = video.stat().st_size
        content_type = VIDEO_TYPES[video.suffix.lower()]
        session = str((pending or {}).get("session") or "")
        if pending and session:
            current = (
                pending.get("video_sha256") == approval["video_sha256"]
                and int(pending.get("size") or -1) == size
                and pending.get("metadata_sha256") == meta_hash
                and session.startswith("https://www.googleapis.com/")
            )
            if not current:
                # The session was opened for other bytes or other metadata.
                # It may hold a finished private video: never resume it under
                # this approval and never silently start a second one (audit 2).
                raise ValueError(
                    "An earlier upload session of this video was opened for a different file or different "
                    "metadata. Check YouTube Studio for a private video from "
                    f"{pending.get('started_at') or 'that attempt'}, then discard the interrupted upload and upload again."
                )
            found = _resume(session, video, size, content_type, auth, http, timeout)
            if found:
                video_id, resumed = found, True
        if not video_id:
            base = {
                "artifact": "pending_upload",
                "concept_id": concept_id,
                "format": fmt,
                "size": size,
                "content_type": content_type,
                "video_sha256": approval["video_sha256"],
                "metadata_sha256": meta_hash,
                "approval_reviewed_at": approval.get("reviewed_at"),
                "started_at": publish_review.now(),
            }
            # Written before the session exists, so a decision change cannot
            # slip in between opening the session and saving it (audit 2).
            publish_review.save_pending_upload({**base, "session": None})
            start = urllib.request.Request(  # noqa: S310 - fixed https URL
                UPLOAD_URL,
                data=json.dumps(body_for(approval["metadata"])).encode("utf-8"),
                headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                         "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": content_type},
                method="POST",
            )
            try:
                headers, _ = http(start, 60)
            except ValueError:
                publish_review.clear_pending_upload(concept_id, fmt)  # no session, so no video
                raise
            session = headers.get("Location") or headers.get("location") or ""
            if not session or not session.startswith("https://www.googleapis.com/"):
                publish_review.clear_pending_upload(concept_id, fmt)
                raise ValueError("YouTube did not return an upload session")
            # Saved before any byte goes out: a retry resumes this session (D-167).
            publish_review.save_pending_upload({**base, "session": session})
            try:
                video_id = _put_from(session, video, 0, size, content_type, auth, http, timeout)
            except ValueError as exc:
                raise ValueError(
                    f"{exc} The upload session is saved: choose Upload to YouTube again and it resumes "
                    "where it stopped instead of starting a second video."
                ) from exc
        # The id is kept until the publish record holds it: a failure from here
        # on is retried by recording this id, never by uploading again (audit 2).
        publish_review.save_pending_upload(
            {**(publish_review.pending_upload(concept_id, fmt) or {}), "concept_id": concept_id, "format": fmt,
             "video_id": video_id, "metadata_sha256": meta_hash, "uploaded_at": publish_review.now()}
        )

    thumbnail_error = None
    try:
        http(
            urllib.request.Request(  # noqa: S310 - fixed https URL
                THUMBNAIL_URL + urllib.parse.quote(video_id), data=thumbnail.read_bytes(), method="POST",
                headers={**auth, "Content-Type": IMAGE_TYPES[thumbnail.suffix.lower()]},
            ),
            120,
        )
    except (ValueError, OSError) as exc:
        # The video exists on YouTube: record it so a retry never uploads it again.
        thumbnail_error = str(exc)
    uploaded_with = str((publish_review.pending_upload(concept_id, fmt) or {}).get("metadata_sha256") or meta_hash)
    return publish_review.record_upload(
        concept_id=concept_id, format=fmt, youtube_video_id=video_id, method="YOUTUBE_DATA_API",
        details={
            "thumbnail_set": thumbnail_error is None,
            "thumbnail_error": thumbnail_error,
            "resumed": resumed,
            # False when the approval changed after YouTube received the video:
            # YouTube then shows the earlier metadata until you edit it in Studio.
            "metadata_matches_upload": uploaded_with == meta_hash,
        },
    )


def _video_id_from(body: bytes) -> str:
    try:
        video_id = str(json.loads(body.decode("utf-8")).get("id") or "")
    except (ValueError, AttributeError):
        video_id = ""
    if not publish_review.VIDEO_ID.match(video_id):
        raise ValueError("YouTube did not return a video id")
    return video_id


def _put_from(
    session: str, video: Path, offset: int, size: int, content_type: str, auth: dict[str, str],
    http: Callable[..., tuple[dict[str, str], bytes]], timeout: float,
) -> str:
    """Send the video bytes from ``offset`` to the end of the session; returns the video id."""
    headers = {**auth, "Content-Type": content_type, "Content-Length": str(size - offset)}
    if offset:
        headers["Content-Range"] = f"bytes {offset}-{size - 1}/{size}"
    with video.open("rb") as handle:
        handle.seek(offset)
        put = urllib.request.Request(  # noqa: S310 - session checked to be https://www.googleapis.com/
            session, data=handle, method="PUT", headers=headers,
        )
        _headers, body = http(put, timeout)
    return _video_id_from(body)


def _resume(
    session: str, video: Path, size: int, content_type: str, auth: dict[str, str],
    http: Callable[..., tuple[dict[str, str], bytes]], timeout: float,
) -> str | None:
    """Ask YouTube what it holds of a saved session and finish it (D-167).

    Returns the video id when the session is complete or could be continued,
    None when the session is gone and a new upload must start.
    """
    probe = urllib.request.Request(  # noqa: S310 - session checked to be https://www.googleapis.com/
        session, data=b"", method="PUT",
        headers={**auth, "Content-Length": "0", "Content-Range": f"bytes */{size}"},
    )
    try:
        _headers, body = http(probe, 60)
    except UploadHttpError as exc:
        if exc.code == 308:
            received = {k.lower(): v for k, v in exc.headers.items()}.get("range") or ""
            offset = 0
            if received:
                try:
                    offset = int(received.split("-")[-1]) + 1
                except ValueError:
                    offset = 0
            if offset >= size:
                offset = 0
            return _put_from(session, video, offset, size, content_type, auth, http, timeout)
        if exc.code in {400, 404, 410}:
            return None
        raise
    # 200/201: the session already finished; the body carries the video.
    return _video_id_from(body)
