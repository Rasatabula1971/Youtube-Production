"""Shared integrity helpers for pipeline runners."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

SUCCESS_STATUSES = {
    "APPLIED",
    "VALIDATED",
    "SKIPPED_ALREADY_APPLIED",
    "SKIPPED_ALREADY_VALIDATED",
    "SKIPPED_ALREADY_TRIAGED",
}
WAIT_STATUSES = {
    "WAITING_FOR_ACQUIRED_EVIDENCE",
    "WAITING_FOR_COMPLETE_EVIDENCE",
    "NO_ACQUIRED_PAGES",
    "MODEL_ESCALATION_REQUIRED",
}
FAIL_STATUSES = {
    "COST_POLICY_VIOLATION",
    "RUNNER_ERROR",
    "MODEL_FAILED",
    "MODEL_OUTPUT_PARSE_ERROR",
    "MODEL_OUTPUT_VALIDATION_ERROR",
    "BRIDGE_ERROR",
    "APPLY_ERROR",
    "APPLY_VALIDATION_FAILED",
    "ERROR",
}


# On Windows, os.replace fails with "Access is denied" or a sharing violation
# (both PermissionError) while another process briefly has the target open,
# for example the UI's status refresh reading a summary file the automation
# job is rewriting. Linux and macOS allow the replace. Retrying for about two
# seconds rides out that overlap; a file that stays locked still raises.
_REPLACE_ATTEMPTS = 12


def _replace(source: Path, target: Path) -> None:
    delay = 0.01
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False),
    )


def tolerant_load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def batch_status(
    results: list[dict[str, Any]],
    *,
    expected_count: int,
    processed_count: int | None = None,
) -> str:
    processed = len(results) if processed_count is None else processed_count
    statuses = [str(item.get("status") or "") for item in results]
    if expected_count == 0:
        return "FAILED"
    successes = sum(status in SUCCESS_STATUSES for status in statuses)
    failures = sum(status in FAIL_STATUSES for status in statuses)
    waits = sum(status in WAIT_STATUSES for status in statuses)
    if successes == expected_count and processed >= expected_count:
        return "COMPLETE"
    if successes == 0 and (failures > 0 or waits > 0 or processed > 0):
        return "FAILED"
    return "PARTIAL"


def exit_code_for_status(status: str) -> int:
    return (
        0
        if status
        in {
            "COMPLETE",
            "VALIDATED",
            "APPLIED",
            "TRIAGE_COMPLETE",
            "SKIPPED_ALREADY_TRIAGED",
            "SCRIPT_GATE_READY",
            "CONCEPT_CANDIDATES_READY",
            "DRAFT_RESEARCH_PACKAGES_READY",
        }
        else 2
    )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON record as a line; earlier lines are never rewritten (D-133)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Records of an append-only log; a torn or invalid line is skipped."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


_NAMED_LOCKS: dict[str, Any] = {}


def named_lock(name: str) -> Any:
    """One process-wide re-entrant lock per name, shared however a module is imported."""
    import threading

    lock = _NAMED_LOCKS.get(name)
    if lock is None:
        lock = _NAMED_LOCKS.setdefault(name, threading.RLock())
    return lock
