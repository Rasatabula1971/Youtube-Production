"""Scheduled Experiment 01.3 frozen-cohort refresh runner.

This wrapper is deliberately conservative. It never performs discovery. It
refreshes only the currently frozen cohort, and skips work when the cohort is
already ready for Experiment 01.4, was refreshed recently, or another scheduled
refresh is running.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUTPUT_ROOT = HERE / "output"
OUTPUT_DIR = OUTPUT_ROOT / "experiment_01_3"
MANIFEST_FILE = OUTPUT_DIR / "cohort_manifest.json"
TOPIC_VELOCITY_FILE = OUTPUT_DIR / "topic_velocity.json"
PERSISTENT_SNAPSHOT_FILE = OUTPUT_ROOT / "experiment_01_3_snapshot_history.jsonl"
EXP14_CONFIG_FILE = HERE / "experiment_01_4_config.json"
STATUS_FILE = OUTPUT_DIR / "scheduled_refresh_status.json"
LOG_FILE = OUTPUT_DIR / "scheduled_refresh.log"
LOCK_FILE = OUTPUT_ROOT / "experiment_01_3_scheduled_refresh.lock"
REFRESH_SCRIPT = HERE / "experiment_01_3.py"

DEFAULT_MINIMUM_INTERVAL_HOURS = 1.5
DEFAULT_LOCK_STALE_MINUTES = 60
DEFAULT_TIMEOUT_SECONDS = 900


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_status(
    status: str,
    message: str,
    *,
    checked_at: datetime,
    exit_code: int | None = None,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "checked_at": checked_at.isoformat(),
        "status": status,
        "message": message,
        "exit_code": exit_code,
    }
    STATUS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def completed_output_text(value: bytes | str | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def append_log(
    checked_at: datetime,
    status: str,
    message: str,
    *,
    stdout: str = "",
    stderr: str = "",
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{checked_at.isoformat()}] {status}: {message}\n")
        if stdout:
            handle.write(stdout.rstrip() + "\n")
        if stderr:
            handle.write("STDERR:\n" + stderr.rstrip() + "\n")


def current_cohort_ready_for_01_4(
    topic_velocity: dict[str, Any],
    config_01_4: dict[str, Any],
) -> bool:
    minimum_channels = int(config_01_4["minimum_unique_channels"])
    minimum_velocity = int(config_01_4["minimum_velocity_samples"])

    for payload in topic_velocity.get("topics", {}).values():
        for cell in payload.get("by_format", {}).values():
            if (
                int(cell.get("unique_channels") or 0) >= minimum_channels
                and int(cell.get("velocity_sample_count") or 0) >= minimum_velocity
                and cell.get("age_matched_velocity_index") is not None
            ):
                return True
    return False


def latest_snapshot_at(
    path: Path,
    video_ids: set[str],
) -> datetime | None:
    if not path.exists() or not video_ids:
        return None

    latest: datetime | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(item.get("video_id") or "") not in video_ids:
            continue
        observed = str(item.get("observed_at") or "").strip()
        if not observed:
            continue
        try:
            timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc)
        if latest is None or timestamp > latest:
            latest = timestamp

    return latest


def acquire_lock(
    path: Path,
    *,
    now: datetime,
    stale_minutes: int,
) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            )
            age_minutes = (now - modified).total_seconds() / 60
        except OSError:
            age_minutes = 0

        if age_minutes >= stale_minutes:
            try:
                path.unlink()
            except OSError:
                return False
        else:
            return False

    try:
        fd = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError:
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "created_at": now.isoformat(),
                }
            )
        )
    return True


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def run_scheduled_refresh(
    *,
    now: datetime | None = None,
    minimum_interval_hours: float = DEFAULT_MINIMUM_INTERVAL_HOURS,
    lock_stale_minutes: int = DEFAULT_LOCK_STALE_MINUTES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    python_executable: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    checked_at = (now or utc_now()).astimezone(timezone.utc)

    if not MANIFEST_FILE.exists():
        message = "No frozen Experiment 01.3 cohort exists."
        payload = write_status(
            "SKIPPED_NO_COHORT",
            message,
            checked_at=checked_at,
        )
        append_log(checked_at, payload["status"], message)
        return payload

    try:
        manifest = load_json(MANIFEST_FILE)
    except (OSError, json.JSONDecodeError) as exc:
        message = f"Cannot read the 01.3 cohort manifest: {exc}"
        payload = write_status(
            "FAILED_MANIFEST",
            message,
            checked_at=checked_at,
        )
        append_log(checked_at, payload["status"], message)
        return payload

    readiness = manifest.get("cohort_readiness", {})
    if not readiness.get("refresh_worthy"):
        message = (
            "Frozen cohort is not refresh-worthy; discovery must improve it "
            "before scheduled velocity refreshes are useful."
        )
        payload = write_status(
            "SKIPPED_INSUFFICIENT_COHORT",
            message,
            checked_at=checked_at,
        )
        append_log(checked_at, payload["status"], message)
        return payload

    if TOPIC_VELOCITY_FILE.exists() and EXP14_CONFIG_FILE.exists():
        try:
            topic_velocity = load_json(TOPIC_VELOCITY_FILE)
            config_01_4 = load_json(EXP14_CONFIG_FILE)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            topic_velocity = {}
            config_01_4 = {}
        if (
            topic_velocity
            and config_01_4
            and current_cohort_ready_for_01_4(
                topic_velocity,
                config_01_4,
            )
        ):
            message = (
                "Current cohort already has enough velocity evidence for "
                "Experiment 01.4."
            )
            payload = write_status(
                "SKIPPED_EVIDENCE_READY",
                message,
                checked_at=checked_at,
            )
            append_log(checked_at, payload["status"], message)
            return payload

    video_ids = {
        str(video_id) for video_id in manifest.get("video_ids", []) if video_id
    }
    latest = latest_snapshot_at(
        PERSISTENT_SNAPSHOT_FILE,
        video_ids,
    )
    if latest is not None:
        elapsed_hours = (checked_at - latest).total_seconds() / 3600
        if elapsed_hours < minimum_interval_hours:
            message = (
                "Latest frozen-cohort snapshot is only "
                f"{elapsed_hours:.2f} hours old; minimum interval is "
                f"{minimum_interval_hours:.2f} hours."
            )
            payload = write_status(
                "SKIPPED_RECENT_SNAPSHOT",
                message,
                checked_at=checked_at,
            )
            append_log(checked_at, payload["status"], message)
            return payload

    if dry_run:
        message = (
            "Frozen cohort is due for a refresh. Dry-run mode did not call "
            "the YouTube API."
        )
        payload = write_status(
            "DUE",
            message,
            checked_at=checked_at,
        )
        append_log(checked_at, payload["status"], message)
        return payload

    if not acquire_lock(
        LOCK_FILE,
        now=checked_at,
        stale_minutes=lock_stale_minutes,
    ):
        message = "Another scheduled 01.3 refresh appears to be running."
        payload = write_status(
            "SKIPPED_LOCKED",
            message,
            checked_at=checked_at,
        )
        append_log(checked_at, payload["status"], message)
        return payload

    executable = python_executable or sys.executable
    command = [
        executable,
        str(REFRESH_SCRIPT),
        "--mode",
        "refresh",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode == 0:
            status = "REFRESHED"
            message = "Scheduled frozen-cohort refresh completed successfully."
        else:
            status = "FAILED_REFRESH"
            message = (
                "Scheduled frozen-cohort refresh exited with code "
                f"{completed.returncode}."
            )

        payload = write_status(
            status,
            message,
            checked_at=checked_at,
            exit_code=completed.returncode,
        )
        append_log(
            checked_at,
            status,
            message,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return payload

    except subprocess.TimeoutExpired as exc:
        message = (
            "Scheduled frozen-cohort refresh exceeded " f"{timeout_seconds} seconds."
        )
        payload = write_status(
            "FAILED_TIMEOUT",
            message,
            checked_at=checked_at,
        )
        append_log(
            checked_at,
            payload["status"],
            message,
            stdout=completed_output_text(exc.stdout),
            stderr=completed_output_text(exc.stderr),
        )
        return payload
    finally:
        release_lock(LOCK_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the frozen Experiment 01.3 cohort only when another "
            "velocity snapshot is actually needed."
        )
    )
    parser.add_argument(
        "--minimum-interval-hours",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL_HOURS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report whether a refresh is due without calling the API.",
    )
    args = parser.parse_args()

    result = run_scheduled_refresh(
        minimum_interval_hours=args.minimum_interval_hours,
        dry_run=args.dry_run,
    )
    print(f"{result['status']}: {result['message']}")
    if str(result["status"]).startswith("FAILED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
