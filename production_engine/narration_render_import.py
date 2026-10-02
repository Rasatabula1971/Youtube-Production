"""Register paid narration provider returns after Human Spend approval.

This module does not call a paid provider. It accepts local audio files returned
by an authorized provider job, copies them into managed project storage, binds
them to the exact current narration request and Human Narration Spend approval,
and invalidates stale downstream Audio QC/timing artifacts.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from narration_cost_review import APPROVED_DIR as APPROVED_SPEND_DIR
from narration_render import (
    ESTIMATES_DIR,
    OUTPUT_DIR,
    REQUESTS_DIR,
    artifact_key,
    load_json,
    safe_slug,
    sha256_file,
    snapshot as narration_render_snapshot,
)

RENDER_RESULTS_DIR = OUTPUT_DIR / "narration_render_results"
MANAGED_AUDIO_DIR = OUTPUT_DIR / "narration_audio"
QC_DIR = OUTPUT_DIR / "narration_audio_qc"
TIMING_DIR = OUTPUT_DIR / "narration_timing_maps"
QC_SUMMARY_FILE = OUTPUT_DIR / "narration_audio_qc_summary.json"
SUMMARY_FILE = OUTPUT_DIR / "narration_render_return_summary.json"
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".opus"}


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _money(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be a non-negative finite amount")
    return round(result, 6)


def _current_render_state_item(
    concept_id: str,
    fmt: str,
) -> dict[str, Any] | None:
    state = narration_render_snapshot()
    for item in state.get("items", []):
        if (
            isinstance(item, dict)
            and str(item.get("concept_id") or "") == concept_id
            and str(item.get("format") or "") == fmt
            and item.get("status") == "READY_FOR_SPEND_GATE"
        ):
            return item
    return None


def current_authorization(
    concept_id: str,
    fmt: str,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any], Path, dict[str, Any]] | None:
    key = artifact_key(concept_id, fmt)
    request_path = REQUESTS_DIR / f"{key}.narration_render_request.json"
    estimate_path = ESTIMATES_DIR / f"{key}.narration_cost_estimate.json"
    spend_path = APPROVED_SPEND_DIR / f"{key}.approved_narration_spend.json"
    if not (request_path.is_file() and estimate_path.is_file() and spend_path.is_file()):
        return None

    request = _load_dict(request_path)
    estimate = _load_dict(estimate_path)
    spend = _load_dict(spend_path)
    if not all(isinstance(value, dict) for value in (request, estimate, spend)):
        return None
    assert request is not None and estimate is not None and spend is not None

    request_hash = sha256_file(request_path)
    estimate_hash = sha256_file(estimate_path)
    spend_gate = spend.get("spend_gate", {})
    approved_provenance = spend.get("approved_provenance", {})
    if (
        not isinstance(spend_gate, dict)
        or spend_gate.get("status") != "NARRATION_SPEND_APPROVED"
        or not isinstance(approved_provenance, dict)
        or approved_provenance.get("narration_cost_estimate_sha256")
        != estimate_hash
        or estimate.get("status") != "READY_FOR_SPEND_GATE"
        or estimate.get("render_request_sha256") != request_hash
        or spend.get("render_request_sha256") != request_hash
        or str(request.get("concept_id") or "") != concept_id
        or str(request.get("format") or "") != fmt
        or str(estimate.get("concept_id") or "") != concept_id
        or str(estimate.get("format") or "") != fmt
        or _current_render_state_item(concept_id, fmt) is None
    ):
        return None

    ceiling = _money(
        spend_gate.get("worst_case_estimate_usd"),
        label="worst_case_estimate_usd",
    )
    if ceiling != _money(
        estimate.get("worst_case_estimate_usd"),
        label="estimate.worst_case_estimate_usd",
    ):
        return None

    return (
        request_path,
        request,
        estimate_path,
        estimate,
        spend_path,
        spend,
    )


def _copy_audio(source: Path, destination: Path) -> None:
    source = source.expanduser().resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise ValueError(f"Narration audio file not found: {source}")
    if source == destination:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    if temp.exists():
        temp.unlink()
    shutil.copy2(source, temp)
    os.replace(temp, destination)


def _invalidate_qc(key: str) -> None:
    for path in (
        QC_DIR / f"{key}.narration_audio_qc.json",
        TIMING_DIR / f"{key}.narration_timing_map.json",
        QC_SUMMARY_FILE,
    ):
        if path.exists() and path.is_file():
            path.unlink()


def current_result(
    concept_id: str,
    fmt: str,
) -> tuple[Path, dict[str, Any]] | None:
    authorization = current_authorization(concept_id, fmt)
    if authorization is None:
        return None
    request_path, request, _estimate_path, _estimate, spend_path, spend = authorization
    key = artifact_key(concept_id, fmt)
    result_path = RENDER_RESULTS_DIR / f"{key}.narration_render_result.json"
    result = _load_dict(result_path)
    if not isinstance(result, dict):
        return None

    spend_gate = spend.get("spend_gate", {})
    ceiling = _money(
        spend_gate.get("worst_case_estimate_usd"),
        label="worst_case_estimate_usd",
    )
    if (
        result.get("artifact") != "narration_render_result"
        or str(result.get("concept_id") or "") != concept_id
        or str(result.get("format") or "") != fmt
        or str(result.get("provider") or "") != str(request.get("provider") or "")
        or result.get("render_request_sha256") != sha256_file(request_path)
        or result.get("spend_approval_sha256") != sha256_file(spend_path)
        or _money(result.get("actual_cost_usd"), label="actual_cost_usd") > ceiling
        or not str(result.get("provider_job_id") or "").strip()
    ):
        return None

    expected = request.get("segments", [])
    supplied = result.get("segments", [])
    if not isinstance(expected, list) or not isinstance(supplied, list):
        return None
    expected_ids = [
        str(item.get("segment_id") or "")
        for item in expected
        if isinstance(item, dict)
    ]
    supplied_ids = [
        str(item.get("segment_id") or "")
        for item in supplied
        if isinstance(item, dict)
    ]
    if (
        len(expected_ids) != len(expected)
        or supplied_ids != expected_ids
        or len(set(expected_ids)) != len(expected_ids)
    ):
        return None

    max_attempts = int(request.get("max_attempts_per_segment") or 0)
    managed_root = (MANAGED_AUDIO_DIR / key).resolve()
    for segment in supplied:
        if not isinstance(segment, dict):
            return None
        path = Path(str(segment.get("audio_file") or "")).resolve()
        attempt = int(segment.get("attempt") or 0)
        if (
            not path.is_file()
            or managed_root not in path.parents
            or segment.get("audio_sha256") != sha256_file(path)
            or attempt < 1
            or attempt > max_attempts
        ):
            return None
    return result_path, result


def register(
    *,
    concept_id: str,
    format: str,
    provider_job_id: str,
    actual_cost_usd: Any,
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    concept_id = str(concept_id or "").strip()
    fmt = str(format or "").strip()
    provider_job_id = str(provider_job_id or "").strip()
    if not concept_id or not fmt:
        raise ValueError("concept_id and format are required")
    if not provider_job_id:
        raise ValueError("provider_job_id is required")

    authorization = current_authorization(concept_id, fmt)
    if authorization is None:
        raise ValueError(
            "Current Human Narration Spend approval was not found for this branch"
        )
    request_path, request, estimate_path, estimate, spend_path, spend = authorization
    spend_gate = spend.get("spend_gate", {})
    ceiling = _money(
        spend_gate.get("worst_case_estimate_usd"),
        label="worst_case_estimate_usd",
    )
    actual_cost = _money(actual_cost_usd, label="actual_cost_usd")
    if actual_cost > ceiling:
        raise ValueError(
            f"Actual narration cost {actual_cost:.2f} exceeds the approved "
            f"worst-case ceiling {ceiling:.2f}"
        )

    expected = request.get("segments", [])
    if not isinstance(expected, list) or not expected:
        raise ValueError("Current narration request has no segments")
    if not isinstance(segments, list):
        raise ValueError("segments must be a list")

    expected_ids = [
        str(item.get("segment_id") or "")
        for item in expected
        if isinstance(item, dict)
    ]
    supplied_ids = [
        str(item.get("segment_id") or "")
        for item in segments
        if isinstance(item, dict)
    ]
    if (
        len(expected_ids) != len(expected)
        or len(supplied_ids) != len(segments)
        or supplied_ids != expected_ids
        or len(set(expected_ids)) != len(expected_ids)
    ):
        raise ValueError(
            "Narration return must cover every current segment in exact order"
        )

    key = artifact_key(concept_id, fmt)
    branch_dir = MANAGED_AUDIO_DIR / key
    staging_dir = MANAGED_AUDIO_DIR / f".{key}.staging"
    backup_dir = MANAGED_AUDIO_DIR / f".{key}.backup"
    for transient in (staging_dir, backup_dir):
        if transient.exists():
            shutil.rmtree(transient)
    staging_dir.mkdir(parents=True, exist_ok=True)

    max_attempts = int(request.get("max_attempts_per_segment") or 0)
    registered_segments: list[dict[str, Any]] = []
    try:
        for index, (supplied, planned) in enumerate(
            zip(segments, expected, strict=True)
        ):
            segment_id = str(supplied.get("segment_id") or "")
            attempt = int(supplied.get("attempt") or 0)
            if attempt < 1 or attempt > max_attempts:
                raise ValueError(
                    f"{segment_id} attempt must be between 1 and {max_attempts}"
                )
            source_value = str(supplied.get("audio_file") or "").strip()
            if not source_value:
                raise ValueError(f"{segment_id} audio_file is required")
            source = Path(source_value).expanduser().resolve()
            suffix = source.suffix.lower()
            if suffix not in ALLOWED_AUDIO_SUFFIXES:
                raise ValueError(
                    f"{segment_id} audio type {suffix or '<none>'} is not supported"
                )
            filename = f"{index:03d}_{safe_slug(segment_id)}{suffix}"
            staged = staging_dir / filename
            _copy_audio(source, staged)
            registered_segments.append(
                {
                    "segment_id": segment_id,
                    "attempt": attempt,
                    "audio_file": str((branch_dir / filename).resolve()),
                    "audio_sha256": sha256_file(staged),
                    "expected_duration_seconds": planned.get(
                        "expected_duration_seconds"
                    ),
                }
            )

        result = {
            "artifact": "narration_render_result",
            "concept_id": concept_id,
            "format": fmt,
            "provider": request.get("provider"),
            "provider_job_id": provider_job_id,
            "actual_cost_usd": actual_cost,
            "approved_cost_ceiling_usd": ceiling,
            "currency": estimate.get("currency"),
            "render_request_sha256": sha256_file(request_path),
            "spend_approval_sha256": sha256_file(spend_path),
            "cost_estimate_sha256": sha256_file(estimate_path),
            "segments": registered_segments,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "provider_called_by_this_module": False,
        }
        RENDER_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_path = (
            RENDER_RESULTS_DIR / f"{key}.narration_render_result.json"
        )

        had_previous = branch_dir.exists()
        if had_previous:
            branch_dir.rename(backup_dir)
        try:
            staging_dir.rename(branch_dir)
            atomic_write_json(result_path, result)
        except Exception:
            if branch_dir.exists():
                shutil.rmtree(branch_dir)
            if backup_dir.exists():
                backup_dir.rename(branch_dir)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise

    _invalidate_qc(key)

    current = current_result(concept_id, fmt)
    if current is None:
        raise RuntimeError("Registered narration result failed current-provenance validation")
    summary = snapshot()
    atomic_write_json(SUMMARY_FILE, summary)
    return {
        "registered": str(result_path.resolve()),
        "result": result,
        "snapshot": summary,
    }


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if not APPROVED_SPEND_DIR.exists():
        return {
            "status": "WAITING_FOR_SPEND_APPROVAL",
            "expected": 0,
            "current": 0,
            "items": [],
        }

    expected_count = 0
    current_count = 0
    for spend_path in sorted(APPROVED_SPEND_DIR.glob("*.approved_narration_spend.json")):
        spend = _load_dict(spend_path)
        if not isinstance(spend, dict):
            continue
        concept_id = str(spend.get("concept_id") or "").strip()
        fmt = str(spend.get("format") or "").strip()
        if not concept_id or not fmt:
            continue
        authorization = current_authorization(concept_id, fmt)
        if authorization is None:
            continue
        request_path, request, _estimate_path, _estimate, _spend_path, current_spend = authorization
        expected_count += 1
        result_state = current_result(concept_id, fmt)
        current_flag = result_state is not None
        if current_flag:
            current_count += 1

        gate = current_spend.get("spend_gate", {})
        planned_segments = request.get("segments", [])
        items.append(
            {
                "concept_id": concept_id,
                "format": fmt,
                "provider": request.get("provider"),
                "provider_job_id": (
                    result_state[1].get("provider_job_id")
                    if result_state is not None
                    else None
                ),
                "actual_cost_usd": (
                    result_state[1].get("actual_cost_usd")
                    if result_state is not None
                    else None
                ),
                "worst_case_estimate_usd": gate.get(
                    "worst_case_estimate_usd"
                ),
                "currency": gate.get("currency"),
                "current_result": current_flag,
                "render_request": str(request_path.resolve()),
                "segments": [
                    {
                        "segment_id": str(segment.get("segment_id") or ""),
                        "purpose": segment.get("purpose"),
                        "expected_duration_seconds": segment.get(
                            "expected_duration_seconds"
                        ),
                        "max_attempts": request.get("max_attempts_per_segment"),
                        "audio_file": (
                            next(
                                (
                                    value.get("audio_file")
                                    for value in result_state[1].get("segments", [])
                                    if isinstance(value, dict)
                                    and value.get("segment_id")
                                    == segment.get("segment_id")
                                ),
                                None,
                            )
                            if result_state is not None
                            else None
                        ),
                        "attempt": (
                            next(
                                (
                                    value.get("attempt")
                                    for value in result_state[1].get("segments", [])
                                    if isinstance(value, dict)
                                    and value.get("segment_id")
                                    == segment.get("segment_id")
                                ),
                                None,
                            )
                            if result_state is not None
                            else None
                        ),
                    }
                    for segment in planned_segments
                    if isinstance(segment, dict)
                ],
            }
        )

    status = (
        "READY_FOR_AUDIO_QC"
        if expected_count > 0 and current_count == expected_count
        else "PARTIAL_PROVIDER_AUDIO"
        if current_count > 0
        else "WAITING_FOR_PROVIDER_AUDIO"
        if expected_count > 0
        else "WAITING_FOR_SPEND_APPROVAL"
    )
    return {
        "status": status,
        "expected": expected_count,
        "current": current_count,
        "items": items,
    }
