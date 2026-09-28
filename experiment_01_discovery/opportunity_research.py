"""Guided Opportunity Research orchestrator.

Automates the mechanical Opportunity Engine sequence:

01.3 discovery -> timed frozen-cohort refresh -> 01.4 plan/execute -> 01.5 handoff

The orchestrator deliberately stops before the human opportunity gate. Existing
experiment scripts remain the source of truth; this file only sequences them
and records orchestration state.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import scheduled_refresh

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUTPUT_ROOT = HERE / "output"
EXP13_DIR = OUTPUT_ROOT / "experiment_01_3"
EXP14_DIR = OUTPUT_ROOT / "experiment_01_4"
EXP15_DIR = OUTPUT_ROOT / "experiment_01_5"

STATE_FILE = OUTPUT_ROOT / "opportunity_research_state.json"
EXP13_SCRIPT = HERE / "experiment_01_3.py"
EXP14_SCRIPT = HERE / "experiment_01_4.py"
EXP15_SCRIPT = HERE / "experiment_01_5.py"
EXP14_CONFIG = HERE / "experiment_01_4_config.json"
INSTALL_SCHEDULER = (
    PROJECT_ROOT / "scripts" / "install_experiment_01_3_auto_refresh.ps1"
)
REMOVE_SCHEDULER = PROJECT_ROOT / "scripts" / "remove_experiment_01_3_auto_refresh.ps1"

DEFAULT_REFRESH_INTERVAL_HOURS = 2
DEFAULT_MAX_REFRESH_ATTEMPTS = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_state(
    status: str,
    message: str,
    *,
    refresh_attempts: int,
    next_refresh_due_at: str | None = None,
    scheduler_armed: bool = False,
) -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "message": message,
        "updated_at": utc_now().isoformat(),
        "refresh_attempts": refresh_attempts,
        "max_refresh_attempts": DEFAULT_MAX_REFRESH_ATTEMPTS,
        "refresh_interval_hours": DEFAULT_REFRESH_INTERVAL_HOURS,
        "next_refresh_due_at": next_refresh_due_at,
        "scheduler_armed": scheduler_armed,
    }
    STATE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def run_command(command: list[str], label: str) -> int:
    print()
    print("=" * 60)
    print(label)
    print("=" * 60)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )
    return int(completed.returncode)


def velocity_ready() -> bool:
    topic_velocity_file = EXP13_DIR / "topic_velocity.json"
    if not topic_velocity_file.exists() or not EXP14_CONFIG.exists():
        return False
    topic_velocity = read_json(topic_velocity_file)
    config_01_4 = read_json(EXP14_CONFIG)
    if not topic_velocity or not config_01_4:
        return False
    try:
        return scheduled_refresh.current_cohort_ready_for_01_4(
            topic_velocity,
            config_01_4,
        )
    except (KeyError, TypeError, ValueError):
        return False


def study_set_ready() -> bool:
    path = EXP15_DIR / "study_set.json"
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, list) and bool(payload)


def exp14_plan_ready() -> bool:
    plan = read_json(EXP14_DIR / "expansion_plan.json")
    return plan.get("status") == "READY"


def exp14_complete() -> bool:
    summary = read_json(EXP14_DIR / "summary.json")
    return summary.get("execution_status") == "COMPLETE"


def schedule_continuation(
    *,
    python_executable: str,
    every_hours: int,
) -> bool:
    if os.name != "nt":
        return False
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(INSTALL_SCHEDULER),
        "-EveryHours",
        str(every_hours),
        "-PythonPath",
        python_executable,
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )
    return completed.returncode == 0


def remove_continuation_task() -> None:
    if os.name != "nt":
        return
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REMOVE_SCHEDULER),
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )


def advance_downstream(
    *,
    python_executable: str,
    refresh_attempts: int,
) -> dict[str, Any]:
    if not velocity_ready():
        raise RuntimeError("advance_downstream called before velocity was ready")

    remove_continuation_task()

    if not exp14_complete() and not exp14_plan_ready():
        plan_code = run_command(
            [
                python_executable,
                str(EXP14_SCRIPT),
                "--mode",
                "plan",
            ],
            "AUTOMATIC STEP — BUILD 01.4 EXPANSION PLAN",
        )
        if plan_code != 0:
            return write_state(
                "FAILED_01_4_PLAN",
                "Experiment 01.4 planning failed.",
                refresh_attempts=refresh_attempts,
            )

    if not exp14_complete() and not exp14_plan_ready():
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            "01.4 plan did not become READY despite velocity evidence.",
            refresh_attempts=refresh_attempts,
        )

    if not exp14_complete():
        execute_code = run_command(
            [
                python_executable,
                str(EXP14_SCRIPT),
                "--mode",
                "execute",
            ],
            "AUTOMATIC STEP — EXECUTE 01.4 EXPANSION",
        )
        if execute_code != 0 or not exp14_complete():
            return write_state(
                "FAILED_01_4_EXECUTION",
                "Experiment 01.4 did not complete successfully.",
                refresh_attempts=refresh_attempts,
            )

    handoff_code = run_command(
        [
            python_executable,
            str(EXP15_SCRIPT),
            "--mode",
            "build",
        ],
        "AUTOMATIC STEP — BUILD 01.5 OPPORTUNITY HANDOFF",
    )
    if handoff_code != 0:
        return write_state(
            "FAILED_01_5",
            "Experiment 01.5 handoff failed.",
            refresh_attempts=refresh_attempts,
        )

    if not study_set_ready():
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            "01.5 completed but produced no passing study set.",
            refresh_attempts=refresh_attempts,
        )

    return write_state(
        "AWAITING_HUMAN_OPPORTUNITY_REVIEW",
        "Opportunity research is complete. Review the selected opportunity and examples.",
        refresh_attempts=refresh_attempts,
    )


def continue_research(
    *,
    python_executable: str,
    minimum_interval_hours: float,
    max_refresh_attempts: int,
    schedule_if_waiting: bool,
) -> dict[str, Any]:
    state = read_json(STATE_FILE)
    refresh_attempts = int(state.get("refresh_attempts") or 0)

    if study_set_ready():
        remove_continuation_task()
        return write_state(
            "AWAITING_HUMAN_OPPORTUNITY_REVIEW",
            "Opportunity handoff already exists. Human review is required.",
            refresh_attempts=refresh_attempts,
        )

    if velocity_ready():
        return advance_downstream(
            python_executable=python_executable,
            refresh_attempts=refresh_attempts,
        )

    refresh_result = scheduled_refresh.run_scheduled_refresh(
        minimum_interval_hours=minimum_interval_hours,
        python_executable=python_executable,
    )
    refresh_status = str(refresh_result.get("status") or "")

    if refresh_status == "REFRESHED":
        refresh_attempts += 1
    elif refresh_status.startswith("FAILED"):
        remove_continuation_task()
        return write_state(
            "FAILED_VELOCITY_REFRESH",
            str(refresh_result.get("message") or "Velocity refresh failed."),
            refresh_attempts=refresh_attempts,
        )
    elif refresh_status == "SKIPPED_INSUFFICIENT_COHORT":
        remove_continuation_task()
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            "The frozen cohort is insufficient; discovery must be rerun.",
            refresh_attempts=refresh_attempts,
        )

    if velocity_ready():
        return advance_downstream(
            python_executable=python_executable,
            refresh_attempts=refresh_attempts,
        )

    if refresh_attempts >= max_refresh_attempts:
        remove_continuation_task()
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            (
                "Velocity evidence is still insufficient after "
                f"{refresh_attempts} refresh attempts."
            ),
            refresh_attempts=refresh_attempts,
        )

    due_at = (utc_now() + timedelta(hours=DEFAULT_REFRESH_INTERVAL_HOURS)).isoformat()
    scheduler_armed = False
    if schedule_if_waiting:
        scheduler_armed = schedule_continuation(
            python_executable=python_executable,
            every_hours=DEFAULT_REFRESH_INTERVAL_HOURS,
        )

    status = (
        "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH"
        if scheduler_armed
        else "WAITING_FOR_MANUAL_VELOCITY_REFRESH"
    )
    message = (
        f"Waiting for the next velocity measurement in about "
        f"{DEFAULT_REFRESH_INTERVAL_HOURS} hours."
        if scheduler_armed
        else (
            "Velocity needs another measurement. Automatic scheduling is "
            "available on Windows; rerun Continue Opportunity Research manually otherwise."
        )
    )
    return write_state(
        status,
        message,
        refresh_attempts=refresh_attempts,
        next_refresh_due_at=due_at,
        scheduler_armed=scheduler_armed,
    )


def start_research(
    *,
    python_executable: str,
    minimum_interval_hours: float,
    max_refresh_attempts: int,
) -> dict[str, Any]:
    remove_continuation_task()
    write_state(
        "DISCOVERY_RUNNING",
        "Experiment 01.3 discovery is running.",
        refresh_attempts=0,
    )

    code = run_command(
        [
            python_executable,
            str(EXP13_SCRIPT),
            "--mode",
            "discover",
            "--replace-cohort",
            "--discovery-backend",
            "auto",
        ],
        "AUTOMATIC OPPORTUNITY RESEARCH — 01.3 DISCOVERY",
    )
    if code != 0:
        return write_state(
            "FAILED_DISCOVERY",
            "Experiment 01.3 discovery failed.",
            refresh_attempts=0,
        )

    if not (EXP13_DIR / "cohort_manifest.json").exists():
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            "Discovery finished without a frozen cohort.",
            refresh_attempts=0,
        )

    return continue_research(
        python_executable=python_executable,
        minimum_interval_hours=minimum_interval_hours,
        max_refresh_attempts=max_refresh_attempts,
        schedule_if_waiting=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Guided automatic Opportunity Research workflow"
    )
    parser.add_argument(
        "--mode",
        choices=("start", "continue"),
        required=True,
    )
    parser.add_argument(
        "--minimum-interval-hours",
        type=float,
        default=scheduled_refresh.DEFAULT_MINIMUM_INTERVAL_HOURS,
    )
    parser.add_argument(
        "--max-refresh-attempts",
        type=int,
        default=DEFAULT_MAX_REFRESH_ATTEMPTS,
    )
    args = parser.parse_args()

    if args.max_refresh_attempts < 1:
        raise SystemExit("--max-refresh-attempts must be at least 1")

    if args.mode == "start":
        result = start_research(
            python_executable=sys.executable,
            minimum_interval_hours=args.minimum_interval_hours,
            max_refresh_attempts=args.max_refresh_attempts,
        )
    else:
        result = continue_research(
            python_executable=sys.executable,
            minimum_interval_hours=args.minimum_interval_hours,
            max_refresh_attempts=args.max_refresh_attempts,
            schedule_if_waiting=True,
        )

    print()
    print("OPPORTUNITY RESEARCH")
    print("=" * 60)
    print(f"Status:  {result['status']}")
    print(f"Message: {result['message']}")
    if result.get("next_refresh_due_at"):
        print(f"Next measurement due: {result['next_refresh_due_at']}")

    if str(result["status"]).startswith("FAILED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
