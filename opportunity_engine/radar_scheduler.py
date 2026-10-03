"""Automatic viral radar (spec v2.1 slice O13).

One tick decides what, if anything, the radar should do now:

* a full discovery pass when the last one is older than
  ``radar_schedule.discovery_every_hours`` (default 8; the spec allows 6-12);
* otherwise a snapshot-only pass when a tracked video is due on its
  age-based cadence (6 h / 12 h / 24 h): one API unit per 50 videos, no search;
* otherwise nothing.

Ticks are driven by the project's existing Windows task (R1: no second
scheduler) through ``scheduled_tick.py``. A lock file stops overlapping ticks,
state lives in the radar's own files so every tick is resumable, and each tick
writes a small status file the UI shows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json  # noqa: E402

from experiment_01_discovery.scheduled_refresh import acquire_lock, release_lock  # noqa: E402
from opportunity_engine import channel_scope, viral_radar  # noqa: E402

STATUS_FILE = viral_radar.RADAR_DIR / "schedule_status.json"
LOCK_FILE = viral_radar.RADAR_DIR / "radar_tick.lock"

ACTION_DISCOVERY = "DISCOVERY"
ACTION_SNAPSHOTS = "SNAPSHOTS"
ACTION_NONE = "NOT_DUE"
ACTION_DISABLED = "DISABLED"
ACTION_LOCKED = "LOCKED"

Runner = Callable[..., "dict[str, Any]"]


def _parse(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def plan(state: dict[str, Any], config: dict[str, Any], now: datetime) -> dict[str, Any]:
    """What a tick at ``now`` would do, and when the next work falls due."""
    schedule = config["radar_schedule"]
    settings = config["viral_radar"]
    last = _parse(state.get("last_discovery_run"))
    every = timedelta(hours=float(schedule["discovery_every_hours"]))
    next_discovery = (last + every) if last else now
    next_snapshot = viral_radar.next_snapshot_due(state, settings, now)
    if not schedule.get("enabled", True):
        action = ACTION_DISABLED
    elif next_discovery <= now:
        action = ACTION_DISCOVERY
    elif next_snapshot is not None and next_snapshot <= now:
        action = ACTION_SNAPSHOTS
    else:
        action = ACTION_NONE
    return {
        "action": action,
        "next_discovery_due": next_discovery.isoformat(),
        "next_snapshot_due": next_snapshot.isoformat() if next_snapshot else None,
        "tracked_count": len(state.get("tracked") or {}),
    }


def tick(
    *,
    now: datetime | None = None,
    runner: Runner | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    config = config or channel_scope.load_config()
    runner = runner or viral_radar.run
    schedule = config["radar_schedule"]
    if not acquire_lock(LOCK_FILE, now=now, stale_minutes=int(schedule["lock_stale_minutes"])):
        locked: dict[str, Any] = {"checked_at": now.isoformat(), "action": ACTION_LOCKED, "result": None}
        _write(locked)
        return locked
    try:
        decided = plan(viral_radar.load_state(), config, now)
        result = None
        if decided["action"] == ACTION_DISCOVERY:
            result = runner(config=config, now=now, mode=viral_radar.MODE_FULL)
        elif decided["action"] == ACTION_SNAPSHOTS:
            result = runner(config=config, now=now, mode=viral_radar.MODE_SNAPSHOTS)
        after = plan(viral_radar.load_state(), config, now) if result else decided
        status: dict[str, Any] = {
            "checked_at": now.isoformat(),
            "action": decided["action"],
            "result": (
                {
                    "status": result.get("status"),
                    "api_calls": result.get("api_calls"),
                    "errors": (result.get("errors") or [])[:3],
                }
                if result
                else None
            ),
            "next_discovery_due": after["next_discovery_due"],
            "next_snapshot_due": after["next_snapshot_due"],
            "tracked_count": after["tracked_count"],
        }
        _write(status)
        return status
    finally:
        release_lock(LOCK_FILE)


def _write(status: dict[str, Any]) -> None:
    atomic_write_json(STATUS_FILE, status)


def load_status() -> dict[str, Any] | None:
    try:
        status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return status if isinstance(status, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show what a tick would do now.")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(plan(viral_radar.load_state(), channel_scope.load_config(), datetime.now(timezone.utc)), indent=2))
        return
    status = tick()
    result = status.get("result") or {}
    print(f"Radar tick: {status['action']} {result.get('status') or ''}".rstrip())
    print(f"  next discovery due {status.get('next_discovery_due')}, next snapshot due {status.get('next_snapshot_due')}")
    if result.get("status") not in (None, viral_radar.STATUS_COMPLETE, viral_radar.STATUS_PARTIAL):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
