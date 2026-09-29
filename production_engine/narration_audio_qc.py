"""Deterministic local QC and timing map for rendered narration.

The module never judges emotion or chooses a preferred take. It verifies current
render/spend provenance, then checks duration, unexpected silence, clipping and
missing segment files with ffprobe/ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from narration_cost_review import APPROVED_DIR as APPROVED_SPEND_DIR
from narration_render import (
    CONFIG_FILE,
    OUTPUT_DIR,
    REQUESTS_DIR,
    artifact_key,
    load_config,
    load_json,
    sha256_file,
)

RENDER_RESULTS_DIR = OUTPUT_DIR / "narration_render_results"
QC_DIR = OUTPUT_DIR / "narration_audio_qc"
TIMING_DIR = OUTPUT_DIR / "narration_timing_maps"
SUMMARY_FILE = OUTPUT_DIR / "narration_audio_qc_summary.json"

_SILENCE_DURATION = re.compile(r"silence_duration:\s*([0-9]+(?:\.[0-9]+)?)")
_MAX_VOLUME = re.compile(r"max_volume:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*dB")


def _finite_positive(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return result


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"Audio QC command failed ({completed.returncode}): {detail}"
        )
    return completed


def probe_duration_seconds(path: Path, config: dict[str, Any]) -> float:
    binary = str(config["audio_qc"]["ffprobe_binary"])
    completed = _run(
        [
            binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        payload = json.loads(completed.stdout)
        value = payload["format"]["duration"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("ffprobe did not return a usable duration") from exc
    return _finite_positive(value, label="audio duration")


def detect_unexpected_silence(
    path: Path,
    config: dict[str, Any],
) -> list[float]:
    qc = config["audio_qc"]
    minimum = float(qc["unexpected_silence_seconds"])
    noise = float(qc["silence_noise_db"])
    completed = _run(
        [
            str(qc["ffmpeg_binary"]),
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise}dB:d={minimum}",
            "-f",
            "null",
            "-",
        ]
    )
    text = (completed.stderr or "") + "\n" + (completed.stdout or "")
    return [float(match) for match in _SILENCE_DURATION.findall(text)]


def max_volume_dbfs(path: Path, config: dict[str, Any]) -> float:
    qc = config["audio_qc"]
    completed = _run(
        [
            str(qc["ffmpeg_binary"]),
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]
    )
    text = (completed.stderr or "") + "\n" + (completed.stdout or "")
    matches = _MAX_VOLUME.findall(text)
    if not matches:
        raise RuntimeError("ffmpeg volumedetect did not report max_volume")
    return float(matches[-1])


def _current_request(
    result: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    concept_id = str(result.get("concept_id") or "").strip()
    fmt = str(result.get("format") or "").strip()
    key = artifact_key(concept_id, fmt)
    request_path = REQUESTS_DIR / f"{key}.narration_render_request.json"
    if not request_path.exists():
        raise ValueError("Current narration render request is missing")
    expected = str(result.get("render_request_sha256") or "")
    if not expected or sha256_file(request_path) != expected:
        raise ValueError("Render result is stale for the current narration request")
    request = load_json(request_path)
    if not isinstance(request, dict):
        raise ValueError("Narration render request must be an object")
    return request_path, request


def _current_spend_approval(
    result: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    concept_id = str(result.get("concept_id") or "").strip()
    fmt = str(result.get("format") or "").strip()
    key = artifact_key(concept_id, fmt)
    path = APPROVED_SPEND_DIR / f"{key}.approved_narration_spend.json"
    if not path.exists():
        raise ValueError("Human Narration Spend approval is missing")
    expected = str(result.get("spend_approval_sha256") or "")
    if not expected or sha256_file(path) != expected:
        raise ValueError("Render result is stale for the current spend approval")
    payload = load_json(path)
    if (
        not isinstance(payload, dict)
        or payload.get("spend_gate", {}).get("status")
        != "NARRATION_SPEND_APPROVED"
    ):
        raise ValueError("Narration spend approval is invalid")
    return path, payload


def validate_render_result(
    result: dict[str, Any],
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    if result.get("artifact") != "narration_render_result":
        raise ValueError("Render result artifact type is invalid")
    request_path, request = _current_request(result)
    spend_path, spend = _current_spend_approval(result)
    segments = result.get("segments", [])
    expected = request.get("segments", [])
    if not isinstance(segments, list) or not isinstance(expected, list):
        raise ValueError("Render result segments must be a list")
    supplied_ids = [
        str(item.get("segment_id") or "")
        for item in segments
        if isinstance(item, dict)
    ]
    expected_ids = [
        str(item.get("segment_id") or "")
        for item in expected
        if isinstance(item, dict)
    ]
    if supplied_ids != expected_ids:
        raise ValueError("Render result must cover every segment in exact order")
    return request_path, request, spend_path, spend


def qc_render_result(
    result: dict[str, Any],
    result_path: Path,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = config or load_config(CONFIG_FILE)
    request_path, request, spend_path, _ = validate_render_result(result)
    request_segments = {
        str(item["segment_id"]): item for item in request["segments"]
    }
    qc_config = config["audio_qc"]
    tolerance = float(qc_config["duration_tolerance_ratio"])
    clipping_threshold = float(qc_config["clipping_peak_dbfs"])

    checks: list[dict[str, Any]] = []
    timing_segments: list[dict[str, Any]] = []
    cursor = 0.0

    for segment in result["segments"]:
        segment_id = str(segment["segment_id"])
        planned = request_segments[segment_id]
        audio_value = str(segment.get("audio_file") or "").strip()
        expected_duration = _finite_positive(
            segment.get("expected_duration_seconds"),
            label=f"{segment_id}.expected_duration_seconds",
        )
        attempt = int(segment.get("attempt") or 0)
        errors: list[str] = []
        actual_duration: float | None = None
        silence_durations: list[float] = []
        peak_dbfs: float | None = None

        if attempt < 1 or attempt > int(request["max_attempts_per_segment"]):
            errors.append("ATTEMPT_OUTSIDE_APPROVED_REGENERATION_POLICY")

        audio_path = Path(audio_value) if audio_value else Path("")
        if not audio_value or not audio_path.exists() or not audio_path.is_file():
            errors.append("AUDIO_FILE_MISSING")
        else:
            try:
                actual_duration = probe_duration_seconds(audio_path, config)
                delta_ratio = abs(actual_duration - expected_duration) / expected_duration
                if delta_ratio > tolerance:
                    errors.append("DURATION_OUTSIDE_TOLERANCE")
                silence_durations = detect_unexpected_silence(audio_path, config)
                if silence_durations:
                    errors.append("UNEXPECTED_SILENCE")
                peak_dbfs = max_volume_dbfs(audio_path, config)
                if peak_dbfs >= clipping_threshold:
                    errors.append("CLIPPING_RISK")
            except (RuntimeError, ValueError) as exc:
                errors.append(f"AUDIO_QC_TOOL_ERROR: {exc}")

        direction = planned.get("delivery", {})
        pause_before = max(0.0, float(direction.get("pause_before_ms") or 0) / 1000.0)
        pause_after = max(0.0, float(direction.get("pause_after_ms") or 0) / 1000.0)
        audio_start = cursor + pause_before
        duration_for_map = actual_duration or 0.0
        audio_end = audio_start + duration_for_map
        cursor = audio_end + pause_after

        checks.append(
            {
                "segment_id": segment_id,
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
                "attempt": attempt,
                "audio_file": audio_value,
                "expected_duration_seconds": expected_duration,
                "actual_duration_seconds": actual_duration,
                "unexpected_silence_durations_seconds": silence_durations,
                "max_volume_dbfs": peak_dbfs,
            }
        )
        timing_segments.append(
            {
                "segment_id": segment_id,
                "pause_before_seconds": pause_before,
                "audio_start_seconds": audio_start,
                "audio_end_seconds": audio_end,
                "pause_after_seconds": pause_after,
                "timeline_end_seconds": cursor,
            }
        )

    passed = all(item["status"] == "PASS" for item in checks)
    qc_payload = {
        "artifact": "narration_audio_qc",
        "concept_id": result["concept_id"],
        "format": result["format"],
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "regeneration_policy": {
            "max_regenerations_per_segment": request["max_regenerations_per_segment"],
            "max_attempts_per_segment": request["max_attempts_per_segment"],
            "third_failure_escalates_to_human": True,
        },
        "qc_policy": {
            "duration_tolerance_ratio": tolerance,
            "unexpected_silence_seconds": qc_config["unexpected_silence_seconds"],
            "clipping_peak_dbfs": clipping_threshold,
            "acoustic_emotion_grading": False,
            "automatic_take_selection": False,
        },
        "provenance": {
            "render_result": str(result_path.resolve()),
            "render_result_sha256": sha256_file(result_path),
            "render_request": str(request_path.resolve()),
            "render_request_sha256": sha256_file(request_path),
            "spend_approval": str(spend_path.resolve()),
            "spend_approval_sha256": sha256_file(spend_path),
        },
    }
    timing_payload = {
        "artifact": "narration_timing_map",
        "concept_id": result["concept_id"],
        "format": result["format"],
        "status": "READY_FOR_ROUGH_CUT" if passed else "BLOCKED_BY_AUDIO_QC",
        "segments": timing_segments,
        "total_duration_seconds": cursor,
        "source_audio_qc_status": qc_payload["status"],
        "source_render_result_sha256": sha256_file(result_path),
    }
    return qc_payload, timing_payload


def batch(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(CONFIG_FILE)
    QC_DIR.mkdir(parents=True, exist_ok=True)
    TIMING_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(RENDER_RESULTS_DIR.glob("*.narration_render_result.json"))
        if RENDER_RESULTS_DIR.exists()
        else []
    )
    items: list[dict[str, Any]] = []
    for result_path in paths:
        result = load_json(result_path)
        if not isinstance(result, dict):
            continue
        qc, timing = qc_render_result(result, result_path, config)
        key = artifact_key(str(result["concept_id"]), str(result["format"]))
        qc_path = QC_DIR / f"{key}.narration_audio_qc.json"
        timing_path = TIMING_DIR / f"{key}.narration_timing_map.json"
        atomic_write_json(qc_path, qc)
        atomic_write_json(timing_path, timing)
        items.append(
            {
                "concept_id": result["concept_id"],
                "format": result["format"],
                "status": qc["status"],
                "qc": str(qc_path),
                "timing_map": str(timing_path),
            }
        )
    summary = {
        "status": (
            "PASS"
            if items and all(item["status"] == "PASS" for item in items)
            else "FAIL"
            if items
            else "WAITING_FOR_NARRATION_RENDER_RESULTS"
        ),
        "processed": len(items),
        "passed": sum(item["status"] == "PASS" for item in items),
        "failed": sum(item["status"] == "FAIL" for item in items),
        "items": items,
    }
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Local narration Audio QC")
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.parse_args()
    print(json.dumps(batch(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
