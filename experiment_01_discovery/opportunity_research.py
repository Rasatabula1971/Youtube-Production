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

from core.hashing import sha256_file

from experiment_01_discovery import scheduled_refresh

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUTPUT_ROOT = HERE / "output"
EXP13_DIR = OUTPUT_ROOT / "experiment_01_3"
EXP14_DIR = OUTPUT_ROOT / "experiment_01_4"
EXP15_DIR = OUTPUT_ROOT / "experiment_01_5"

STATE_FILE = OUTPUT_ROOT / "opportunity_research_state.json"
EXP13_SCRIPT = HERE / "experiment_01_3.py"
EXP13_MODULE = "experiment_01_discovery.experiment_01_3"  # started with python -m from the project root (D-175)
EXP14_SCRIPT = HERE / "experiment_01_4.py"
EXP14_MODULE = "experiment_01_discovery.experiment_01_4"  # started with python -m from the project root (D-175)
EXP15_SCRIPT = HERE / "experiment_01_5.py"
EXP15_MODULE = "experiment_01_discovery.experiment_01_5"  # started with python -m from the project root (D-175)
VIDIQ_SCRIPT = HERE / "vidiq_opportunity_enrichment.py"
VIDIQ_MODULE = "experiment_01_discovery.vidiq_opportunity_enrichment"  # started with python -m from the project root (D-175)
VIDIQ_DOCTOR_FILE = OUTPUT_ROOT / "vidiq" / "doctor.json"
VIDIQ_ENRICHMENT_FILE = OUTPUT_ROOT / "vidiq" / "opportunity_enrichment.json"
EXP14_CONFIG = HERE / "experiment_01_4_config.json"
INSTALL_SCHEDULER = (
    PROJECT_ROOT / "scripts" / "install_experiment_01_3_auto_refresh.ps1"
)

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
    vidiq_status: str | None = None,
    vidiq_message: str | None = None,
    study_set_sha256: str | None = None,
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
        "vidiq_status": vidiq_status,
        "vidiq_message": vidiq_message,
        "study_set_sha256": study_set_sha256,
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
            read_json(EXP13_DIR / "summary.json"),
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


def current_study_set_sha256() -> str | None:
    path = EXP15_DIR / "study_set.json"
    return sha256_file(path) if path.exists() else None


def exp14_plan_ready() -> bool:
    plan = read_json(EXP14_DIR / "expansion_plan.json")
    return plan.get("status") == "READY"


def exp14_complete() -> bool:
    summary = read_json(EXP14_DIR / "summary.json")
    return summary.get("execution_status") == "COMPLETE"


# YouTube's daily quota resets at midnight Pacific time: 07:00 UTC in summer
# (PDT), 08:00 UTC in winter (PST). Without a time-zone database (Windows has
# none in the standard library) both are allowed for: the spending moment is
# dated as late as it could be (UTC-7), "now" as early as it could be (UTC-8).
# The wait can be up to an hour too long, never too short.
OWNER_STOP_STATES = {"NEEDS_HUMAN_ATTENTION", "FAILED_DISCOVERY"}
DISCOVERY_STALE_AFTER = timedelta(hours=12)
PACIFIC_LATEST = timedelta(hours=7)
PACIFIC_EARLIEST = timedelta(hours=8)
EXP14_PAUSED_STATUSES = {"QUOTA_EXHAUSTED", "SEARCH_BUDGET_REACHED"}


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def next_quota_boundary_after(spent_at: datetime) -> datetime:
    """The first moment that is surely a later quota day than ``spent_at``."""
    day = (spent_at.astimezone(timezone.utc) - PACIFIC_LATEST).date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + PACIFIC_EARLIEST


def next_quota_day_wait(summary_01_3: dict[str, Any], now: datetime) -> datetime | None:
    """When 01.4 may spend search quota, or None if it may now (D-178).

    Discovery can use up to 6,000 units. 01.4's searches on the same quota
    day, with the radar, could pass the 10,000-unit daily limit, so they wait
    for a later quota day than the one discovery finished in (a discovery
    that resumed the next day counts from when it finished).
    """
    finished = _parse_time(summary_01_3.get("discovery_completed_at")) or _parse_time(
        summary_01_3.get("cohort_created_at")
    )
    if finished is None:
        return None
    boundary = next_quota_boundary_after(finished)
    return boundary if now < boundary else None


def held_until(state: dict[str, Any], now: datetime) -> datetime | None:
    """A quota-day wait already recorded in the research state."""
    if state.get("status") != "WAITING_FOR_NEXT_QUOTA_DAY":
        return None
    due = _parse_time(state.get("next_refresh_due_at"))
    return due if due is not None and now < due else None


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


# The one Windows task (scripts/install_experiment_01_3_auto_refresh.ps1) runs
# opportunity_engine.scheduled_tick: this continuation AND the viral radar
# (O13). The research flow therefore never removes it; before D-178 it did, on
# every finished, failed or started run, which silently stopped the radar.
# Only the owner removes it (Tools -> Remove Opportunity Automation).

def run_vidiq_supplemental(
    *,
    python_executable: str,
) -> tuple[str, str]:
    """Run vidIQ only when the zero-cost doctor confirms the live safety contract.

    vidIQ is supplemental. Any unavailable, partial, or fail-closed state skips
    paid research and still allows the Human Opportunity Gate to open.
    """
    doctor_code = run_command(
        [
            python_executable,
            "-m",
            VIDIQ_MODULE,
            "--mode",
            "doctor",
        ],
        "AUTOMATIC SUPPLEMENT — CHECK vidIQ SAFETY",
    )
    doctor = read_json(VIDIQ_DOCTOR_FILE)
    doctor_status = str(doctor.get("status") or "UNAVAILABLE")
    if doctor_code != 0 or doctor_status != "READY":
        return (
            f"SKIPPED_{doctor_status}",
            "vidIQ supplemental evidence was skipped because its free-credit "
            "safety check was not READY.",
        )

    enrich_code = run_command(
        [
            python_executable,
            "-m",
            VIDIQ_MODULE,
            "--mode",
            "enrich",
        ],
        "AUTOMATIC SUPPLEMENT — vidIQ OPPORTUNITY CHECK",
    )
    enrichment = read_json(VIDIQ_ENRICHMENT_FILE)
    enrich_status = str(enrichment.get("status") or "UNAVAILABLE")
    if enrich_code != 0:
        return (
            f"SKIPPED_{enrich_status}",
            "vidIQ supplemental evidence failed closed; canonical YouTube "
            "evidence remains available for human review.",
        )

    if enrich_status in {"COMPLETE", "PARTIAL", "NO_PAID_RESULTS"}:
        return (
            enrich_status,
            "vidIQ supplemental validation finished under the project credit guards.",
        )

    return (
        f"SKIPPED_{enrich_status}",
        "vidIQ supplemental evidence was unavailable; canonical YouTube "
        "evidence remains available for human review.",
    )


def finalize_opportunity_handoff(
    *,
    python_executable: str,
    refresh_attempts: int,
) -> dict[str, Any]:
    vidiq_status, vidiq_message = run_vidiq_supplemental(
        python_executable=python_executable,
    )
    return write_state(
        "AWAITING_HUMAN_OPPORTUNITY_REVIEW",
        "Opportunity research is complete. Review the selected opportunity and examples.",
        refresh_attempts=refresh_attempts,
        vidiq_status=vidiq_status,
        vidiq_message=vidiq_message,
        # The handoff (and its vidIQ supplement) runs once per study set; the
        # every-2-hours task must not repeat paid calls (D-178 review).
        study_set_sha256=current_study_set_sha256(),
    )


def advance_downstream(
    *,
    python_executable: str,
    refresh_attempts: int,
) -> dict[str, Any]:
    if not velocity_ready():
        raise RuntimeError("advance_downstream called before velocity was ready")


    if not exp14_complete() and not exp14_plan_ready():
        plan_code = run_command(
            [
                python_executable,
                "-m",
                EXP14_MODULE,
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
        now = utc_now()
        waits = [
            wait
            for wait in (
                next_quota_day_wait(read_json(EXP13_DIR / "summary.json"), now),
                held_until(read_json(STATE_FILE), now),
            )
            if wait is not None
        ]
        resume_at = max(waits) if waits else None
        if resume_at is not None:
            return write_state(
                "WAITING_FOR_NEXT_QUOTA_DAY",
                (
                    "The 01.4 plan is ready. Its searches wait for the next YouTube "
                    "quota day after discovery, so one day never spends both."
                ),
                refresh_attempts=refresh_attempts,
                next_refresh_due_at=resume_at.isoformat(),
            )
        execute_code = run_command(
            [
                python_executable,
                "-m",
                EXP14_MODULE,
                "--mode",
                "execute",
            ],
            "AUTOMATIC STEP — EXECUTE 01.4 EXPANSION",
        )
        paused = str(read_json(EXP14_DIR / "search_checkpoint.json").get("status") or "")
        if execute_code == 0 and not exp14_complete() and paused in EXP14_PAUSED_STATUSES:
            # Out of quota (or budget) part-way: the checkpoint resumes on the
            # next quota day; this is a pause, not a failure (D-178 review).
            return write_state(
                "WAITING_FOR_NEXT_QUOTA_DAY",
                f"01.4 paused part-way ({paused}); it resumes from its checkpoint on the next quota day.",
                refresh_attempts=refresh_attempts,
                next_refresh_due_at=next_quota_boundary_after(utc_now()).isoformat(),
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
            "-m",
            EXP15_MODULE,
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

    return finalize_opportunity_handoff(
        python_executable=python_executable,
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
    status = str(state.get("status") or "")

    # The shared task runs this every 2 hours for good (D-178), so states
    # that wait for the owner stay as they are; they used to end the task.
    if status in OWNER_STOP_STATES:
        return state

    if not (EXP13_DIR / "cohort_manifest.json").exists():
        started = _parse_time(state.get("updated_at"))
        if status == "DISCOVERY_RUNNING" and started and utc_now() - started < DISCOVERY_STALE_AFTER:
            return state  # a discovery is still running; leave its state alone
        return write_state(
            "NEEDS_HUMAN_ATTENTION",
            (
                "No frozen 01.3 cohort exists (discovery paused, failed or never ran). "
                "Run Opportunity Research to resume or restart it."
            ),
            refresh_attempts=refresh_attempts,
        )

    if study_set_ready():
        if status == "AWAITING_HUMAN_OPPORTUNITY_REVIEW":
            recorded = state.get("study_set_sha256")
            current = current_study_set_sha256()
            if recorded == current:
                return state  # already handed off; nothing to repeat
            if recorded is None:
                # Handed off before D-178: adopt it rather than re-run vidIQ.
                return write_state(
                    status,
                    str(state.get("message") or ""),
                    refresh_attempts=refresh_attempts,
                    vidiq_status=state.get("vidiq_status"),
                    vidiq_message=state.get("vidiq_message"),
                    study_set_sha256=current,
                )
        return finalize_opportunity_handoff(
            python_executable=python_executable,
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
        return write_state(
            "FAILED_VELOCITY_REFRESH",
            str(refresh_result.get("message") or "Velocity refresh failed."),
            refresh_attempts=refresh_attempts,
        )
    elif refresh_status == "SKIPPED_INSUFFICIENT_COHORT":
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
    write_state(
        "DISCOVERY_RUNNING",
        "Experiment 01.3 discovery is running.",
        refresh_attempts=0,
    )

    code = run_command(
        [
            python_executable,
            "-m",
            EXP13_MODULE,
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
