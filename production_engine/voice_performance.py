"""Voice Performance planning boundary.

Consumes Human Format Gate approved plans and prepares one immutable-narration
performance request per production branch. This module is zero-spend: it never
calls Higgsfield or any paid provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
CONFIG_FILE = HERE / "voice_performance_config.json"
APPROVED_FORMAT_DIR = (
    PROJECT_ROOT / "format_engine" / "output" / "approved_format_plans"
)
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "voice_performance_requests"
SPECS_DIR = OUTPUT_DIR / "voice_performance_specs"
RESPONSES_DIR = OUTPUT_DIR / "voice_performance_responses"
MODEL_RUNS_DIR = OUTPUT_DIR / "voice_performance_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_voice_performance_outputs"
SUMMARY_FILE = OUTPUT_DIR / "voice_performance_summary.json"

READY_STATUS = "READY_FOR_PRODUCTION_ENGINE"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_" for char in value
    ).strip("._")
    return cleaned or "unknown"


def _number(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict):
        raise ValueError("Voice Performance config must be an object")
    required = {
        "provider",
        "planning_policy",
        "allowed_emotions",
        "surprised_requires_reveal_beat",
        "max_intensity",
        "max_adjacent_intensity_delta",
        "speed_min",
        "speed_max",
        "pause_ms_max",
        "emphasis_terms_max",
        "voice_identity",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Voice Performance config is missing: " + ", ".join(missing))
    emotions = [str(item).strip() for item in config["allowed_emotions"]]
    if not emotions or len(emotions) != len(set(emotions)):
        raise ValueError("allowed_emotions must contain unique values")
    if "surprised" not in emotions:
        raise ValueError("allowed_emotions must include surprised for reveal-only use")
    maximum = _number(config["max_intensity"], label="max_intensity")
    delta = _number(
        config["max_adjacent_intensity_delta"],
        label="max_adjacent_intensity_delta",
    )
    speed_min = _number(config["speed_min"], label="speed_min")
    speed_max = _number(config["speed_max"], label="speed_max")
    if not 0 <= maximum <= 1:
        raise ValueError("max_intensity must be between 0 and 1")
    if not 0 <= delta <= 1:
        raise ValueError("max_adjacent_intensity_delta must be between 0 and 1")
    if speed_min <= 0 or speed_min > speed_max:
        raise ValueError("speed bounds are invalid")
    pause_max = int(config["pause_ms_max"])
    emphasis_max = int(config["emphasis_terms_max"])
    if pause_max < 0 or emphasis_max < 0:
        raise ValueError("pause/emphasis limits must be non-negative")
    identity = config["voice_identity"]
    if not isinstance(identity, dict):
        raise ValueError("voice_identity must be an object")
    config = dict(config)
    config["allowed_emotions"] = emotions
    config["max_intensity"] = maximum
    config["max_adjacent_intensity_delta"] = delta
    config["speed_min"] = speed_min
    config["speed_max"] = speed_max
    config["pause_ms_max"] = pause_max
    config["emphasis_terms_max"] = emphasis_max
    return config


def validation_contract_sha256() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__).resolve(), CONFIG_FILE.resolve()):
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _approved_identity(plan: dict[str, Any]) -> str:
    gate = plan.get("format_gate", {})
    if not isinstance(gate, dict) or gate.get("status") != READY_STATUS:
        raise ValueError("Format plan is not READY_FOR_PRODUCTION_ENGINE")
    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Approved format plan requires concept_id")
    return concept_id


def _script_context(
    plan: dict[str, Any],
    fmt: str,
) -> tuple[dict[str, dict[str, Any]], str, dict[str, Any]]:
    package = plan.get("package", {})
    branch_packages = plan.get("branch_story_packages")
    if (
        not isinstance(package, dict)
        or not isinstance(branch_packages, dict)
        or not branch_packages
    ):
        raise ValueError(
            "Approved format plan is missing immutable branch script context"
        )
    branch_story = branch_packages.get(fmt)
    if not isinstance(branch_story, dict) or not branch_story:
        raise ValueError(f"Approved format plan is missing {fmt} script context")
    title = str(package.get("title") or "").strip()
    if not title or str(branch_story.get("title") or "") != title:
        raise ValueError("Approved format plan violates immutable Packaging title")
    sections = branch_story.get("sections", [])
    if not isinstance(sections, list) or not sections:
        raise ValueError(f"Approved format plan requires {fmt} script sections")
    by_id: dict[str, dict[str, Any]] = {}
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Every script section must be an object")
        section_id = str(section.get("section_id") or "").strip()
        narration = str(section.get("narration") or "").strip()
        if not section_id or not narration:
            raise ValueError("Every script section requires section_id and narration")
        if section_id in by_id:
            raise ValueError(f"Duplicate {fmt} script section_id: {section_id}")
        by_id[section_id] = section
    return by_id, title, branch_story


def _reveal_beat(beat: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(beat.get("purpose") or ""),
            str(beat.get("treatment") or ""),
            str(beat.get("beat_id") or ""),
        ]
    ).lower()
    return "reveal" in text


def build_request(
    plan: dict[str, Any],
    plan_path: Path,
    branch: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = _approved_identity(plan)
    fmt = str(branch.get("format") or "").strip()
    if not fmt:
        raise ValueError("Every format branch requires format")
    sections, title, branch_story = _script_context(plan, fmt)
    beats = branch.get("beats", [])
    if not isinstance(beats, list) or not beats:
        raise ValueError(f"{fmt} requires beats")

    request_beats: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            raise ValueError(f"{fmt} beat {index} must be an object")
        beat_id = str(beat.get("beat_id") or "").strip()
        if not beat_id or beat_id in seen:
            raise ValueError(f"{fmt} requires unique beat_id values")
        seen.add(beat_id)
        source_ids = beat.get("source_section_ids", [])
        if not isinstance(source_ids, list) or not source_ids:
            raise ValueError(f"{fmt}.{beat_id} requires source_section_ids")
        normalized_ids = [str(item) for item in source_ids]
        missing = [item for item in normalized_ids if item not in sections]
        if missing:
            raise ValueError(
                f"{fmt}.{beat_id} references missing script section(s): "
                + ", ".join(missing)
            )
        narration = "\n\n".join(str(sections[item]["narration"]) for item in normalized_ids)
        request_beats.append(
            {
                "beat_id": beat_id,
                "beat_index": index,
                "purpose": str(beat.get("purpose") or ""),
                "treatment": str(beat.get("treatment") or ""),
                "claim_ids": [str(item) for item in beat.get("claim_ids", [])],
                "source_section_ids": normalized_ids,
                "immutable_narration": narration,
                "immutable_narration_sha256": sha256_text(narration),
                "reveal_beat": _reveal_beat(beat),
            }
        )

    identity = dict(config["voice_identity"])
    render_prerequisites = all(
        str(identity.get(key) or "").strip()
        for key in ("voice_id", "license_reference", "calibration_artifact")
    )
    return {
        "artifact": "voice_performance_request",
        "concept_id": concept_id,
        "format": fmt,
        "title": title,
        "duration_intent_seconds": branch.get("duration_intent_seconds"),
        "promise_delivery": branch.get("promise_delivery"),
        "payoff": branch.get("payoff"),
        "opening_hook": branch_story.get("opening_hook"),
        "closing": branch_story.get("closing"),
        "script_psychology_profile": branch_story.get(
            "psychology_profile", {}
        ),
        "beats": request_beats,
        "performance_controls": {
            "allowed_emotions": list(config["allowed_emotions"]),
            "surprised_requires_reveal_beat": bool(
                config["surprised_requires_reveal_beat"]
            ),
            "max_intensity": config["max_intensity"],
            "max_adjacent_intensity_delta": config[
                "max_adjacent_intensity_delta"
            ],
            "speed_min": config["speed_min"],
            "speed_max": config["speed_max"],
            "pause_ms_max": config["pause_ms_max"],
            "emphasis_terms_max": config["emphasis_terms_max"],
        },
        "voice_identity": {
            "provider": str(config["provider"]),
            **identity,
        },
        "render_prerequisites_configured": render_prerequisites,
        "instructions": [
            "Annotate delivery only; do not rewrite, paraphrase, add or remove spoken words.",
            "Return exactly one direction for every beat and preserve beat order.",
            "Keep emotional amplitude restrained; use pace, pause and emphasis deliberately.",
            "Use surprised only for a beat explicitly marked reveal_beat=true.",
            "Every emphasis term must already occur in immutable_narration.",
            "Do not score predicted retention, virality or performance quality.",
            "Do not select a winning take. This stage plans delivery only.",
        ],
        "request_provenance": {
            "approved_format_plan": str(plan_path.resolve()),
            "approved_format_plan_sha256": sha256_file(plan_path),
        },
    }


def validate_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    if str(response.get("concept_id") or "") != str(request.get("concept_id") or ""):
        errors.append("concept_id mismatch")
    if str(response.get("format") or "") != str(request.get("format") or ""):
        errors.append("format mismatch")

    beats = request.get("beats", [])
    expected = [str(item.get("beat_id") or "") for item in beats if isinstance(item, dict)]
    directions = response.get("directions", [])
    if not isinstance(directions, list):
        errors.append("directions must be a list")
        directions = []
    supplied = [
        str(item.get("beat_id") or "")
        for item in directions
        if isinstance(item, dict)
    ]
    if supplied != expected:
        errors.append("directions must match request beat order exactly")

    controls = request.get("performance_controls", {})
    emotions = set(str(item) for item in controls.get("allowed_emotions", []))
    narration_by_beat = {
        str(item.get("beat_id") or ""): str(item.get("immutable_narration") or "")
        for item in beats
        if isinstance(item, dict)
    }
    reveal_by_beat = {
        str(item.get("beat_id") or ""): bool(item.get("reveal_beat"))
        for item in beats
        if isinstance(item, dict)
    }
    previous_intensity: float | None = None
    normalized: list[dict[str, Any]] = []

    for index, direction in enumerate(directions):
        if not isinstance(direction, dict):
            errors.append(f"direction {index} must be an object")
            continue
        beat_id = str(direction.get("beat_id") or "")
        emotion = str(direction.get("emotion") or "")
        if emotion not in emotions:
            errors.append(f"{beat_id or index} uses unsupported emotion {emotion!r}")
        if (
            emotion == "surprised"
            and controls.get("surprised_requires_reveal_beat")
            and not reveal_by_beat.get(beat_id, False)
        ):
            errors.append(f"{beat_id or index} may use surprised only on a reveal beat")

        try:
            intensity = _number(direction.get("intensity"), label="intensity")
            if intensity < 0 or intensity > float(controls.get("max_intensity", 1)):
                errors.append(f"{beat_id or index} intensity exceeds configured bounds")
            if (
                previous_intensity is not None
                and abs(intensity - previous_intensity)
                > float(controls.get("max_adjacent_intensity_delta", 1))
            ):
                errors.append(
                    f"{beat_id or index} intensity changes too sharply from prior beat"
                )
            previous_intensity = intensity
        except ValueError as exc:
            errors.append(f"{beat_id or index} {exc}")
            intensity = 0.0

        try:
            speed = _number(direction.get("speed"), label="speed")
            if not (
                float(controls.get("speed_min", 0)) <= speed
                <= float(controls.get("speed_max", 999))
            ):
                errors.append(f"{beat_id or index} speed exceeds configured bounds")
        except ValueError as exc:
            errors.append(f"{beat_id or index} {exc}")
            speed = 1.0

        pauses: dict[str, int] = {}
        for field in ("pause_before_ms", "pause_after_ms"):
            value = direction.get(field)
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{beat_id or index} {field} must be an integer")
                pauses[field] = 0
            else:
                pauses[field] = value
                if value < 0 or value > int(controls.get("pause_ms_max", 0)):
                    errors.append(f"{beat_id or index} {field} exceeds configured bounds")

        terms = direction.get("emphasis_terms", [])
        if not isinstance(terms, list):
            errors.append(f"{beat_id or index} emphasis_terms must be a list")
            terms = []
        if len(terms) > int(controls.get("emphasis_terms_max", 0)):
            errors.append(f"{beat_id or index} has too many emphasis terms")
        narration = narration_by_beat.get(beat_id, "")
        lowered = narration.casefold()
        normalized_terms: list[str] = []
        for term in terms:
            text = str(term).strip()
            if not text:
                errors.append(f"{beat_id or index} has an empty emphasis term")
                continue
            if text.casefold() not in lowered:
                errors.append(
                    f"{beat_id or index} emphasis term is not in immutable narration: {text}"
                )
            normalized_terms.append(text)

        normalized.append(
            {
                "beat_id": beat_id,
                "emotion": emotion,
                "intensity": intensity,
                "speed": speed,
                **pauses,
                "emphasis_terms": normalized_terms,
            }
        )

    return {
        "valid": not errors,
        "errors": errors,
        "directions": normalized,
        "immutable_narration_sha256": {
            str(item.get("beat_id") or ""): str(
                item.get("immutable_narration_sha256") or ""
            )
            for item in beats
            if isinstance(item, dict)
        },
    }


def run_prepare(
    approved_dir: Path = APPROVED_FORMAT_DIR,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(approved_dir.glob("*.approved_format_plan.json"))
        if approved_dir.exists()
        else []
    )
    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    current: set[Path] = set()

    for path in paths:
        try:
            plan = load_json(path)
            branches = plan.get("branches", [])
            if not isinstance(branches, list) or not branches:
                raise ValueError("Approved format plan requires branches")
            for branch in branches:
                if not isinstance(branch, dict):
                    raise ValueError("Every branch must be an object")
                request = build_request(plan, path, branch, config)
                dest = REQUESTS_DIR / (
                    f"{safe_slug(request['concept_id'])}."
                    f"{safe_slug(request['format'])}.voice_request.json"
                )
                atomic_write_json(dest, request)
                current.add(dest.resolve())
                prepared.append(
                    {
                        "concept_id": request["concept_id"],
                        "format": request["format"],
                        "request": str(dest),
                    }
                )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            failures.append(
                {
                    "approved_format_plan": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale in REQUESTS_DIR.glob("*.voice_request.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "VOICE_PERFORMANCE_REQUESTS_READY"
            if prepared
            else "WAITING_FOR_APPROVED_FORMAT_PLANS"
        ),
        "approved_format_plans_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REQUESTS_DIR),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice Performance request builder")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.add_argument("--approved-dir", type=Path, default=APPROVED_FORMAT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            run_prepare(args.approved_dir.resolve()),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
