"""Agent Reach source-acquisition adapter.

Agent Reach is used as a capability and health layer. This adapter asks
agent-reach doctor --json which backend is active, then calls the upstream tool
directly, matching Agent Reach's own design philosophy.

No project scoring, experiment calculations, claim validation, or human gates
are implemented here.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from typing import Any

DOCTOR_TIMEOUT_SECONDS = 90
SEARCH_TIMEOUT_SECONDS = 900
MAX_SEARCH_RESULTS = 100


class AcquisitionError(RuntimeError):
    """Raised when a source-acquisition backend cannot safely run."""


def render_console_json(payload: Any) -> str:
    """Render JSON safely for redirected Windows consoles and UI logs.

    ensure_ascii=True keeps stdout ASCII-only while preserving all Unicode
    content as JSON escape sequences. This avoids cp1252 encode failures when
    Agent Reach returns localized channel messages.
    """
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=True,
    )


def agent_reach_path() -> str | None:
    return shutil.which("agent-reach")


def yt_dlp_path() -> str | None:
    return shutil.which("yt-dlp")


def doctor(
    *,
    timeout_seconds: int = DOCTOR_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    executable = agent_reach_path()
    if not executable:
        return {
            "status": "NOT_INSTALLED",
            "installed": False,
            "channels": {},
            "message": (
                "agent-reach is not installed or is not on PATH"
            ),
        }

    try:
        completed = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "installed": True,
            "channels": {},
            "message": (
                f"agent-reach doctor timed out after "
                f"{timeout_seconds}s"
            ),
        }
    except OSError as exc:
        return {
            "status": "ERROR",
            "installed": True,
            "channels": {},
            "message": f"agent-reach doctor failed: {exc}",
        }

    if completed.returncode != 0:
        return {
            "status": "ERROR",
            "installed": True,
            "channels": {},
            "return_code": completed.returncode,
            "message": (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "agent-reach doctor failed"
            )[:1200],
        }

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "INVALID_JSON",
            "installed": True,
            "channels": {},
            "message": (
                "agent-reach doctor did not return valid JSON"
            ),
            "raw_output": completed.stdout[:1200],
        }

    if isinstance(payload, dict) and isinstance(
        payload.get("channels"), dict
    ):
        channels = payload["channels"]
    elif isinstance(payload, dict):
        channels = payload
    else:
        channels = {}

    return {
        "status": "READY",
        "installed": True,
        "channels": channels,
        "raw": payload,
    }


def channel_status(
    doctor_payload: dict[str, Any],
    channel_name: str,
) -> dict[str, Any] | None:
    channels = doctor_payload.get("channels", {})
    if not isinstance(channels, dict):
        return None
    value = channels.get(channel_name)
    return value if isinstance(value, dict) else None


def youtube_health(
    doctor_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = (
        doctor_payload
        if doctor_payload is not None
        else doctor()
    )
    channel = channel_status(payload, "youtube")

    if payload.get("status") != "READY":
        return {
            "ready": False,
            "doctor_status": payload.get("status"),
            "channel_status": None,
            "active_backend": None,
            "message": payload.get("message"),
        }

    if channel is None:
        return {
            "ready": False,
            "doctor_status": "READY",
            "channel_status": None,
            "active_backend": None,
            "message": (
                "Agent Reach doctor did not report a YouTube channel"
            ),
        }

    status = str(channel.get("status", ""))
    backend = channel.get("active_backend")
    ready = (
        status == "ok"
        and str(backend).casefold() == "yt-dlp"
        and yt_dlp_path() is not None
    )

    return {
        "ready": ready,
        "doctor_status": "READY",
        "channel_status": status,
        "active_backend": backend,
        "message": channel.get("message"),
        "backends": channel.get("backends", []),
    }


def _search_prefix(strategy: str) -> str:
    if strategy == "relevance":
        return "ytsearch"
    if strategy == "date":
        return "ytsearchdate"
    raise ValueError(
        "strategy must be relevance or date"
    )


def search_youtube(
    query: str,
    *,
    limit: int = 20,
    strategy: str = "relevance",
    timeout_seconds: int = SEARCH_TIMEOUT_SECONDS,
    require_agent_reach_health: bool = True,
) -> dict[str, Any]:
    query = str(query).strip()
    if not query:
        raise ValueError("query is required")
    if limit < 1 or limit > MAX_SEARCH_RESULTS:
        raise ValueError(
            f"limit must be between 1 and {MAX_SEARCH_RESULTS}"
        )

    if require_agent_reach_health:
        health = youtube_health()
        if not health["ready"]:
            raise AcquisitionError(
                "Agent Reach YouTube channel is not ready: "
                + str(
                    health.get("message")
                    or health.get("channel_status")
                    or health.get("doctor_status")
                )
            )
    else:
        health = {
            "ready": True,
            "active_backend": "yt-dlp",
        }

    executable = yt_dlp_path()
    if not executable:
        raise AcquisitionError(
            "yt-dlp is not available on PATH"
        )

    search_target = (
        f"{_search_prefix(strategy)}{limit}:{query}"
    )
    command = [
        executable,
        "--dump-json",
        "--no-warnings",
        "--ignore-errors",
        "--skip-download",
        "--",
        search_target,
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AcquisitionError(
            f"yt-dlp search timed out after "
            f"{timeout_seconds}s"
        ) from exc
    except OSError as exc:
        raise AcquisitionError(
            f"yt-dlp search failed to start: {exc}"
        ) from exc

    results: list[dict[str, Any]] = []
    parse_errors = 0

    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        video_id = str(item.get("id", "")).strip()
        if not video_id:
            continue

        results.append(
            {
                "video_id": video_id,
                "title": item.get("title"),
                "channel": (
                    item.get("channel")
                    or item.get("uploader")
                ),
                "channel_id": (
                    item.get("channel_id")
                    or item.get("uploader_id")
                ),
                "upload_date": item.get("upload_date"),
                "timestamp": item.get("timestamp"),
                "duration_seconds": item.get("duration"),
                "view_count": item.get("view_count"),
                "webpage_url": (
                    item.get("webpage_url")
                    or f"https://www.youtube.com/watch?v={video_id}"
                ),
            }
        )

    status = "COMPLETE"
    if completed.returncode != 0 and not results:
        raise AcquisitionError(
            (
                completed.stderr.strip()
                or "yt-dlp returned no usable search results"
            )[:1200]
        )
    if completed.returncode != 0:
        status = "PARTIAL"

    return {
        "status": status,
        "query": query,
        "strategy": strategy,
        "requested_limit": limit,
        "result_count": len(results),
        "parse_errors": parse_errors,
        "active_backend": health.get(
            "active_backend"
        ),
        "results": results,
        "stderr": completed.stderr.strip()[:1200],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent Reach source-acquisition adapter"
    )
    parser.add_argument(
        "--mode",
        choices=("doctor", "youtube-search"),
        required=True,
    )
    parser.add_argument("--query", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--strategy",
        choices=("relevance", "date"),
        default="relevance",
    )
    args = parser.parse_args()

    if args.mode == "doctor":
        payload = doctor()
        payload["youtube"] = youtube_health(payload)
        result = payload
    else:
        if not args.query:
            raise SystemExit(
                "--query is required for youtube-search"
            )
        result = search_youtube(
            args.query,
            limit=args.limit,
            strategy=args.strategy,
        )

    print(render_console_json(result))


if __name__ == "__main__":
    main()
