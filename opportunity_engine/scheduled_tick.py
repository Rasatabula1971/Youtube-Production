"""The project's one scheduled task (D-052 extended by D-114).

Windows Task Scheduler runs this every few hours. It does, in order:

1. the existing Opportunity Research continuation (frozen-cohort velocity
   refresh, then 01.4 / 01.5 when evidence is ready), exactly as before;
2. one viral radar tick (discovery when due, otherwise snapshots when due).

Each step is independent: one failing never skips the other. Output is
appended to ``opportunity_engine/output/viral/scheduled_tick.log``.
"""

from __future__ import annotations

import subprocess  # nosec B404 - fixed argument list, no shell
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import radar_scheduler, viral_radar  # noqa: E402

RESEARCH_RUNNER = _ROOT / "experiment_01_discovery" / "opportunity_research.py"
LOG_FILE = viral_radar.RADAR_DIR / "scheduled_tick.log"
RESEARCH_TIMEOUT_SECONDS = 1800


def _log(line: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")


def run_research_continue() -> int:
    try:
        completed = subprocess.run(  # nosec B603 - fixed argument list, no shell
            [sys.executable, str(RESEARCH_RUNNER), "--mode", "continue"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RESEARCH_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log(f"opportunity research: FAILED to run ({exc})")
        return 1
    last = (completed.stdout or completed.stderr or "").strip().splitlines()[-1:] or ["(no output)"]
    _log(f"opportunity research: exit {completed.returncode}: {last[0][:300]}")
    return completed.returncode


def run_radar_tick() -> int:
    try:
        status = radar_scheduler.tick()
    except (OSError, ValueError, RuntimeError) as exc:
        _log(f"viral radar: FAILED ({exc})")
        return 1
    result = status.get("result") or {}
    _log(
        f"viral radar: {status['action']} {result.get('status') or ''} "
        f"(next discovery {status.get('next_discovery_due')}, next snapshot {status.get('next_snapshot_due')})"
    )
    ok = result.get("status") in (None, viral_radar.STATUS_COMPLETE, viral_radar.STATUS_PARTIAL)
    return 0 if ok else 1


def main() -> None:
    research = run_research_continue()
    radar = run_radar_tick()
    raise SystemExit(1 if research != 0 and radar != 0 else 0)


if __name__ == "__main__":
    main()
