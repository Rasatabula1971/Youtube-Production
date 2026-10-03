"""Human Video Intake: paste a YouTube URL, get an Opportunity Packet (slice O5).

The pasted video is measured (official API first, yt-dlp metadata as fallback;
never a download), routed against the channel scope, and stored as a
HUMAN_VIDEO packet. "Analyze why it worked" then makes it the active study set
through ``active_source`` so Experiment 02 analyses it like any approved video.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404 - fixed argument list, no shell
import sys
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, models  # noqa: E402
from opportunity_engine.packet_schema import build_packet, validate_packet  # noqa: E402
from opportunity_engine.provenance import opportunity_id  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKETS_DIR = HERE / "output" / "opportunities" / "human_video"
ENV_FILE = _ROOT / ".env"
GENERATOR = "opportunity_engine.human_video_intake"
YT_DLP_TIMEOUT_SECONDS = 60
SHORT_MAX_SECONDS = 180

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
SHORT_LINK_HOSTS = {"youtu.be", "www.youtu.be"}
PATH_ID_PREFIXES = ("shorts", "embed", "live", "v")

STATUS_COMPLETE = "COMPLETE"
STATUS_UNAVAILABLE = "VIDEO_UNAVAILABLE"
STATUS_FAILED = "METADATA_FAILED"
UNAVAILABLE_MARKERS = (
    "private video",
    "video unavailable",
    "has been removed",
    "this video is not available",
    "account associated with this video has been terminated",
)


class IntakeError(ValueError):
    """A human-facing intake failure; the message is safe to show."""


def parse_video_id(raw: str) -> str:
    """Return the 11-character video id from a YouTube URL or bare id."""
    text = str(raw or "").strip()
    if not text:
        raise IntakeError("Paste a YouTube video link.")
    if VIDEO_ID_PATTERN.fullmatch(text):
        return text
    if "://" not in text:
        text = "https://" + text
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in ("http", "https"):
        raise IntakeError("Only http(s) YouTube links are accepted.")
    host = (parsed.hostname or "").lower()
    segments = [part for part in parsed.path.split("/") if part]
    candidate = ""
    if host in SHORT_LINK_HOSTS:
        candidate = segments[0] if segments else ""
    elif host in YOUTUBE_HOSTS:
        if segments[:1] == ["watch"] or not segments:
            candidate = (urllib.parse.parse_qs(parsed.query).get("v") or [""])[0]
        elif len(segments) >= 2 and segments[0] in PATH_ID_PREFIXES:
            candidate = segments[1]
    else:
        raise IntakeError("That is not a YouTube link.")
    if not VIDEO_ID_PATTERN.fullmatch(candidate):
        raise IntakeError(
            "That link does not point to a single YouTube video "
            "(playlists, channels and searches are not accepted)."
        )
    return candidate


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _iso8601_seconds(duration: str) -> int:
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    days, hours, minutes, seconds = (int(v or 0) for v in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def metadata_from_api_item(item: dict[str, Any]) -> dict[str, Any]:
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    details = item.get("contentDetails") or {}
    status = item.get("status") or {}
    return {
        "video_id": item.get("id"),
        "title": snippet.get("title"),
        "description": (snippet.get("description") or "")[:2000],
        "tags": list(snippet.get("tags") or [])[:30],
        "channel_id": snippet.get("channelId"),
        "channel_title": snippet.get("channelTitle"),
        "published_at": snippet.get("publishedAt"),
        "duration_seconds": _iso8601_seconds(str(details.get("duration") or "")),
        "views": _int_or_none(stats.get("viewCount")),
        "likes": _int_or_none(stats.get("likeCount")),
        "comments": _int_or_none(stats.get("commentCount")),
        "made_for_kids": status.get("madeForKids"),
        "live_broadcast": snippet.get("liveBroadcastContent"),
        "measurement_source": "YOUTUBE_DATA_API",
    }


def metadata_from_yt_dlp(info: dict[str, Any]) -> dict[str, Any]:
    published = None
    if info.get("timestamp"):
        published = datetime.fromtimestamp(int(info["timestamp"]), tz=timezone.utc).isoformat()
    elif re.fullmatch(r"\d{8}", str(info.get("upload_date") or "")):
        raw = str(info["upload_date"])
        published = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}T00:00:00+00:00"
    return {
        "video_id": info.get("id"),
        "title": info.get("title"),
        "description": (info.get("description") or "")[:2000],
        "tags": list(info.get("tags") or [])[:30],
        "channel_id": info.get("channel_id"),
        "channel_title": info.get("channel") or info.get("uploader"),
        "published_at": published,
        "duration_seconds": _int_or_none(info.get("duration")) or 0,
        "views": _int_or_none(info.get("view_count")),
        "likes": _int_or_none(info.get("like_count")),
        "comments": _int_or_none(info.get("comment_count")),
        "made_for_kids": None,
        "live_broadcast": info.get("live_status"),
        "measurement_source": "YT_DLP",
    }


def _load_api_key() -> str | None:
    if not os.getenv("YOUTUBE_API_KEY") and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "YOUTUBE_API_KEY" and value.strip():
                os.environ["YOUTUBE_API_KEY"] = value.strip().strip('"').strip("'")
    return os.getenv("YOUTUBE_API_KEY") or None


def fetch_via_api(video_id: str) -> dict[str, Any] | None:
    """Return metadata, None when the video does not exist, or raise IntakeError."""
    api_key = _load_api_key()
    if not api_key:
        raise IntakeError("YOUTUBE_API_KEY is not configured")
    from experiment_01_discovery.youtube_discovery import api_get

    try:
        data = api_get(
            "videos",
            api_key,
            part="snippet,statistics,contentDetails,status",
            id=video_id,
            maxResults=1,
        )
    except (SystemExit, urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
        raise IntakeError(f"YouTube API request failed: {exc}") from exc
    items = data.get("items") or []
    return metadata_from_api_item(items[0]) if items else None


def fetch_via_yt_dlp(video_id: str) -> dict[str, Any] | None:
    """Metadata only (no download). None when YouTube says the video is gone."""
    binary = shutil.which("yt-dlp")
    if not binary:
        raise IntakeError("yt-dlp is not installed")
    command = [
        binary,
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        "--no-warnings",
        "--",
        watch_url(video_id),
    ]
    try:
        completed = subprocess.run(  # nosec B603 - fixed argument list, no shell
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=YT_DLP_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise IntakeError(f"yt-dlp timed out after {YT_DLP_TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise IntakeError(f"yt-dlp failed to start: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or "").strip()
        if any(marker in message.lower() for marker in UNAVAILABLE_MARKERS):
            return None
        raise IntakeError("yt-dlp failed: " + (message.splitlines() or ["no output"])[-1][:300])
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise IntakeError("yt-dlp returned unreadable metadata") from exc
    if not isinstance(info, dict) or info.get("id") != video_id:
        raise IntakeError("yt-dlp returned metadata for a different item")
    return metadata_from_yt_dlp(info)


Fetcher = Callable[[str], "dict[str, Any] | None"]
FETCHERS: dict[str, Fetcher] = {"youtube_api": fetch_via_api, "yt_dlp": fetch_via_yt_dlp}


def fetch_metadata(video_id: str) -> dict[str, Any]:
    """Try the API, then yt-dlp. Never treat a failed fetch as 'not found'."""
    attempts: list[dict[str, str]] = []
    for name, fetcher in FETCHERS.items():
        try:
            metadata = fetcher(video_id)
        except IntakeError as exc:
            attempts.append({"backend": name, "status": "FAILED", "error": str(exc)})
            continue
        if metadata is None:
            attempts.append({"backend": name, "status": STATUS_UNAVAILABLE})
            return {"status": STATUS_UNAVAILABLE, "video_id": video_id, "attempts": attempts}
        attempts.append({"backend": name, "status": STATUS_COMPLETE})
        return {"status": STATUS_COMPLETE, "metadata": metadata, "attempts": attempts}
    return {"status": STATUS_FAILED, "video_id": video_id, "attempts": attempts}


def _age_days(published_at: str | None, now: datetime) -> float | None:
    if not published_at:
        return None
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max((now - published).total_seconds() / 86400, 1 / 24), 2)


def packet_path(video_id: str) -> Path:
    return PACKETS_DIR / f"{video_id}.json"


def build_video_packet(
    metadata: dict[str, Any],
    *,
    note: str = "",
    topic: str = "",
    attempts: list[dict[str, str]] | None = None,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    config = config or channel_scope.load_config()
    now = now or datetime.now(timezone.utc)
    video_id = str(metadata["video_id"])
    duration = int(metadata.get("duration_seconds") or 0)
    fmt = "short" if 0 < duration <= SHORT_MAX_SECONDS else "long_form"
    text = " ".join(
        [str(metadata.get("title") or ""), " ".join(metadata.get("tags") or []), topic]
    )
    # A human submitted it for the active channel, so it defaults there; the
    # exclusion and future-channel rules still apply first.
    channel = channel_scope.route(
        text,
        niche="everyday_science",
        made_for_kids=bool(metadata.get("made_for_kids")),
        config=config,
    )
    video = {
        "video_id": video_id,
        "youtube_url": watch_url(video_id),
        "title": metadata.get("title"),
        "channel_id": metadata.get("channel_id"),
        "channel_title": metadata.get("channel_title"),
        "format": fmt,
        "published_at": metadata.get("published_at"),
        "age_days": _age_days(metadata.get("published_at"), now),
        "duration_seconds": duration,
        "views": metadata.get("views"),
        "likes": metadata.get("likes"),
        "comments": metadata.get("comments"),
        "made_for_kids": metadata.get("made_for_kids"),
        "measurement_source": metadata.get("measurement_source"),
        "measured_at": now.isoformat(),
    }
    packet = build_packet(
        opportunity_id=opportunity_id(models.SOURCE_HUMAN_VIDEO, video_id),
        source_type=models.SOURCE_HUMAN_VIDEO,
        title=str(metadata.get("title") or video_id),
        summary=(
            f"Video you submitted from {metadata.get('channel_title') or 'an unknown channel'}"
            f" ({metadata.get('views') if metadata.get('views') is not None else 'unknown'} views)."
            " Its performance is context only; why it worked is decided in Experiment 02."
        ),
        channel=channel,
        topic=topic.strip(),
        niche="everyday_science",
        formats=[fmt],
        seed={"video_url": watch_url(video_id), "topic": topic.strip() or None},
        candidate_videos=[video],
        generator=GENERATOR,
        created_at=now.isoformat(),
    )
    packet["human_notes"] = [note.strip()] if note.strip() else []
    packet["intake"] = {"attempts": list(attempts or [])}
    return packet


def save_packet(packet: dict[str, Any]) -> Path:
    errors = validate_packet(packet)
    if errors:
        raise ValueError("Invalid HUMAN_VIDEO packet: " + "; ".join(errors))
    video_id = packet["candidate_videos"][0]["video_id"]
    path = packet_path(video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_packet(video_id: str) -> dict[str, Any] | None:
    if not VIDEO_ID_PATTERN.fullmatch(str(video_id or "")):
        return None
    path = packet_path(video_id)
    if not path.is_file():
        return None
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return packet if isinstance(packet, dict) else None


def list_packets() -> list[dict[str, Any]]:
    if not PACKETS_DIR.is_dir():
        return []
    packets = []
    for path in PACKETS_DIR.glob("*.json"):
        packet = load_packet(path.stem)
        if packet:
            packets.append(packet)
    return sorted(packets, key=lambda p: str(p.get("created_at") or ""), reverse=True)


def intake(url: str, *, note: str = "", topic: str = "") -> dict[str, Any]:
    """Validate, measure, route and store one human-submitted video."""
    video_id = parse_video_id(url)
    result = fetch_metadata(video_id)
    if result["status"] == STATUS_UNAVAILABLE:
        raise IntakeError("YouTube reports this video as private, removed or unavailable.")
    if result["status"] != STATUS_COMPLETE:
        details = "; ".join(f"{a['backend']}: {a.get('error', a['status'])}" for a in result["attempts"])
        raise IntakeError(f"Could not read this video's details ({details}). Nothing was saved.")
    packet = build_video_packet(
        result["metadata"], note=note, topic=topic, attempts=result["attempts"]
    )
    save_packet(packet)
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--note", default="")
    parser.add_argument("--topic", default="")
    args = parser.parse_args()
    try:
        packet = intake(args.url, note=args.note, topic=args.topic)
    except IntakeError as exc:
        raise SystemExit(f"Not saved: {exc}") from exc
    video = packet["candidate_videos"][0]
    print(f"Saved {packet['opportunity_id']}")
    print(f"  {video['title']} — {video['channel_title']} ({video['views']} views, {video['format']})")
    print(f"  Route: {packet['channel']['route']} {packet['channel'].get('channel_id') or packet['channel'].get('rule_id') or ''}")


if __name__ == "__main__":
    main()
