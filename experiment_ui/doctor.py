"""One-click doctor for Tools (D-169): every key and binary, tested for real.

System Health (UI-15) is cheap and local: it says whether a key is set.
The doctor says whether it works: the YouTube key makes one real API call,
the OAuth upload settings are checked, each binary reports its version,
the paid and free providers report their own readiness, and the disk is
measured. Each check has a time limit and reports its own failure, so one
broken dependency never hides the others. Results are saved to
``.experiment_ui/doctor.json`` and shown on the Tools page.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
RESULT_FILE = PROJECT_ROOT / ".experiment_ui" / "doctor.json"
CHECK_TIMEOUT_SECONDS = 20
LOW_DISK_GB = 2.0
# One public video, one quota unit: proves the key, the project and the quota.
YOUTUBE_PROBE_VIDEO = "jNQXAC9IVRw"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"

READY, WARN, MISSING = "READY", "WARN", "MISSING"


def env_value(name: str) -> str:
    """An environment variable, else its line in the project .env (never echoed)."""
    value = os.getenv(name, "")
    if value or not ENV_FILE.exists():
        return value.strip()
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, sep, raw = line.strip().partition("=")
            if sep and key.strip() == name:
                return raw.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def _version(binary: str, flag: str = "-version") -> str:
    path = shutil.which(binary)
    if not path:
        raise FileNotFoundError(f"{binary} is not on PATH")
    completed = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        [path, flag], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=CHECK_TIMEOUT_SECONDS, check=False,
    )
    first = (completed.stdout or completed.stderr or "").strip().splitlines()
    return (first[0] if first else "installed")[:120]


# ----------------------------------------------------------------- checks

def check_youtube_key() -> tuple[str, str]:
    key = env_value("YOUTUBE_API_KEY")
    if not key:
        return MISSING, "YOUTUBE_API_KEY is not set (environment or .env)."
    if len(key) != 39 or not key.startswith("AIza"):
        return WARN, f"The key is {len(key)} characters; a Google API key is 39 and starts with AIza."
    # Its own single request with a time limit: the discovery helper retries
    # and exits the process on a refused key, which would take the whole
    # doctor down exactly when the key is the problem (audit 2).
    query = urllib.parse.urlencode({"part": "id", "id": YOUTUBE_PROBE_VIDEO, "fields": "items/id", "key": key})
    request = urllib.request.Request(f"{YOUTUBE_API}/videos?{query}")  # noqa: S310 - fixed https URL
    try:
        with urllib.request.urlopen(request, timeout=CHECK_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URL  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read()[:2000].decode("utf-8", "replace") if hasattr(exc, "read") else ""
        reason = (
            "quota exceeded for today" if "quotaExceeded" in body
            else "the key is not valid" if "keyInvalid" in body or "API key not valid" in body
            else "the YouTube Data API is not enabled for this key's project" if "accessNotConfigured" in body
            else "the key is restricted from this API or address" if exc.code == 403
            else f"HTTP {exc.code}"
        )
        return MISSING, f"YouTube refused the key: {reason} (HTTP {exc.code})."
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # The URL holds the key: report only the error type, never its text.
        return WARN, f"YouTube could not be reached ({type(exc).__name__}); check the network or proxy."
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        return WARN, "The key works but the probe video was not returned; check the Data API is enabled."
    return READY, "Key accepted; the Data API answered (1 quota unit)."


def check_gemini() -> tuple[str, str]:
    from experiment_02_analysis.analysis_model_runner import DIRECT_GEMINI_KEY_ENV, direct_gemini_billing_status

    key = env_value(DIRECT_GEMINI_KEY_ENV)
    billing = direct_gemini_billing_status()
    if not key:
        return WARN, f"{DIRECT_GEMINI_KEY_ENV} is not set: the direct Gemini route is off (free models still run)."
    if not billing.get("confirmed"):
        return WARN, "Key set, but billing_disabled_confirmed is false in direct_gemini_billing.json: no direct Gemini call is made."
    return READY, f"Key set and billing attested as disabled on {billing.get('confirmed_on') or 'an unknown date'}."


def check_binary(binary: str, flag: str = "-version") -> Callable[[], tuple[str, str]]:
    def run() -> tuple[str, str]:
        try:
            return READY, _version(binary, flag)
        except FileNotFoundError as exc:
            return MISSING, str(exc)
    return run


def check_search_backends() -> tuple[str, str]:
    from source_acquisition import agent_reach_adapter as reach

    mcporter = reach.mcporter_path()
    curl = shutil.which("curl")
    parts = []
    parts.append("mcporter (Exa) on PATH" if mcporter else "mcporter (Exa) missing: Exa search is off")
    parts.append("curl on PATH" if curl else "curl missing")
    if reach.agent_reach_path():
        report = reach.doctor(timeout_seconds=CHECK_TIMEOUT_SECONDS)
        parts.append(f"agent-reach doctor: {str(report.get('status') or 'unknown').lower()}")
    else:
        parts.append("agent-reach not installed (optional)")
    status = READY if mcporter else WARN if curl else MISSING
    return status, "; ".join(parts) + ". DuckDuckGo and Wikipedia need only curl."


def check_kokoro() -> tuple[str, str]:
    missing = [name for name in ("kokoro", "soundfile", "numpy") if importlib.util.find_spec(name) is None]
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if missing:
        return MISSING, "Python packages missing: " + ", ".join(missing) + ". Free previews and the local narration voice need them."
    if not espeak:
        return WARN, "kokoro is installed but espeak-ng is not on PATH; Kokoro needs it for phonemes."
    return READY, "kokoro, soundfile, numpy and espeak-ng are installed: the free local voice can render."


def check_upload_oauth() -> tuple[str, str]:
    from production_engine import youtube_upload

    state = youtube_upload.status()
    if state["ready"]:
        return READY, "YouTube upload is on and the three OAuth values are set (never shown)."
    problems = " ".join(state["problems"])
    return (WARN if "off" in problems else MISSING), problems


def check_narration_provider() -> tuple[str, str]:
    from production_engine import narration_dispatch

    state = narration_dispatch.provider_status()
    label = f"{state.get('provider')} ({'local, $0' if state.get('local') else 'paid'})"
    if state["ready"]:
        return READY, f"{label}: ready."
    return MISSING, f"{label}: " + " ".join(state["problems"])


def check_image_providers() -> tuple[str, str]:
    from production_engine import thumbnail_image_provider, visual_dispatch

    thumbs = thumbnail_image_provider.provider_status()
    visuals = visual_dispatch.provider_status()
    parts = [
        "thumbnails: " + ("ready" if thumbs.get("ready") else "off (" + " ".join(thumbs.get("problems") or []) + ")"),
        "visuals: " + ("ready" if visuals.get("ready") else "off (" + " ".join(visuals.get("problems") or []) + ")"),
    ]
    status = READY if thumbs.get("ready") and visuals.get("ready") else WARN
    return status, "; ".join(parts) + ". Off is fine until you authorize paid images."


def check_disk() -> tuple[str, str]:
    usage = shutil.disk_usage(PROJECT_ROOT)
    free_gb = usage.free / 1e9
    detail = f"{free_gb:.1f} GB free of {usage.total / 1e9:.0f} GB on the project drive."
    return (WARN if free_gb < LOW_DISK_GB else READY), detail + (" Renders need a few GB." if free_gb < LOW_DISK_GB else "")


def check_python() -> tuple[str, str]:
    return READY, f"Python {sys.version.split()[0]} at {sys.executable}"


CHECKS: list[tuple[str, str, Callable[[], tuple[str, str]]]] = [
    ("python", "Python", check_python),
    ("youtube_key", "YouTube Data API key (live call)", check_youtube_key),
    ("gemini", "Direct Gemini key and billing flag", check_gemini),
    ("ffmpeg", "FFmpeg", check_binary("ffmpeg")),
    ("ffprobe", "FFprobe", check_binary("ffprobe")),
    ("yt_dlp", "yt-dlp", check_binary("yt-dlp", "--version")),
    ("search", "Web search backends (Exa / DuckDuckGo / Wikipedia)", check_search_backends),
    ("kokoro", "Kokoro local voice", check_kokoro),
    ("narration", "Narration provider", check_narration_provider),
    ("images", "Image providers (thumbnails, visuals)", check_image_providers),
    ("upload", "YouTube upload OAuth", check_upload_oauth),
    ("disk", "Disk space", check_disk),
]


def run(checks: list[tuple[str, str, Callable[[], tuple[str, str]]]] | None = None) -> dict[str, Any]:
    """Run every check, each on its own; a crash in one is that one's result."""
    rows = []
    for check_id, label, func in checks or CHECKS:
        started = time.monotonic()
        try:
            status, detail = func()
        except subprocess.TimeoutExpired:
            status, detail = MISSING, f"Timed out after {CHECK_TIMEOUT_SECONDS}s."
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - SystemExit too: every check must report (audit 2)
            status, detail = MISSING, f"{type(exc).__name__}: {str(exc)[:300]}"
        rows.append(
            {
                "id": check_id,
                "label": label,
                "status": status,
                "detail": detail,
                "ms": int((time.monotonic() - started) * 1000),
            }
        )
    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "checks": rows,
        "ready": sum(row["status"] == READY for row in rows),
        "warn": sum(row["status"] == WARN for row in rows),
        "missing": sum(row["status"] == MISSING for row in rows),
    }
    try:
        RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        pass
    return report


def last_report() -> dict[str, Any] | None:
    try:
        payload = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
