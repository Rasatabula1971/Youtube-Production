"""Deterministic pre-render engagement validation.

Runs after Human Performance approval and before narration spend preparation.
It does not rewrite narration and makes no model/provider call. The checks are
production heuristics, not claims about dopamine, physiology, or guaranteed
retention.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import sha256_file
from voice_review import APPROVED_DIR

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RESULTS_DIR = OUTPUT_DIR / "pre_render_engagement"
SUMMARY_FILE = OUTPUT_DIR / "pre_render_engagement_summary.json"

SHORT_FORMATS = {"short", "shorts", "youtube_short", "short_form"}


def _words(value: str) -> int:
    return len([part for part in value.split() if part.strip()])


def _purpose_text(beat: dict[str, Any]) -> str:
    return " ".join(
        str(beat.get(key) or "") for key in ("purpose", "treatment", "beat_id")
    ).casefold()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def validate_spec(spec: dict[str, Any], source: Path) -> dict[str, Any]:
    concept_id = str(spec.get("concept_id") or "").strip()
    fmt = str(spec.get("format") or "").strip()
    beats = spec.get("beats", [])
    directions = spec.get("directions", [])
    errors: list[str] = []
    warnings: list[str] = []

    if not concept_id or not fmt:
        errors.append("MISSING_BRANCH_IDENTITY")
    if spec.get("performance_gate", {}).get("status") != "PERFORMANCE_SPEC_APPROVED":
        errors.append("PERFORMANCE_GATE_NOT_APPROVED")
    if not isinstance(beats, list) or len(beats) < 2:
        errors.append("INSUFFICIENT_STORY_BEATS")
        beats = []
    if not isinstance(directions, list) or len(directions) != len(beats):
        errors.append("DELIVERY_DIRECTIONS_DO_NOT_MATCH_BEATS")
        directions = []

    purposes = [_purpose_text(beat) for beat in beats if isinstance(beat, dict)]
    narration = [
        str(beat.get("immutable_narration") or "").strip()
        for beat in beats if isinstance(beat, dict)
    ]
    total_words = sum(_words(text) for text in narration)

    hook_terms = ("hook", "opening", "question", "tension", "problem", "stakes", "contradiction")
    problem_terms = ("problem", "tension", "stakes", "conflict", "question", "obstacle", "risk")
    payoff_terms = ("payoff", "reveal", "solution", "answer", "resolution", "conclusion")

    if purposes and not _has_any(purposes[0], hook_terms):
        errors.append("OPENING_BEAT_LACKS_HOOK_OR_TENSION_INTENT")
    if purposes and not any(_has_any(text, problem_terms) for text in purposes[: max(2, len(purposes) // 2 + 1)]):
        errors.append("PROBLEM_OR_TENSION_NOT_ESTABLISHED_EARLY")
    if purposes and not any(_has_any(text, payoff_terms) for text in purposes):
        errors.append("NO_EXPLICIT_PAYOFF_OR_RESOLUTION_BEAT")
    if purposes and not _has_any(purposes[-1], payoff_terms):
        warnings.append("FINAL_BEAT_DOES_NOT_SIGNAL_PAYOFF_OR_RESOLUTION")

    longest_words = max((_words(text) for text in narration), default=0)
    is_short = fmt.casefold() in SHORT_FORMATS or "short" in fmt.casefold()
    exposition_limit = 55 if is_short else 140
    if longest_words > exposition_limit:
        errors.append("EXPOSITION_BEAT_TOO_LONG_WITHOUT_STRUCTURAL_RESET")

    if directions:
        intensity = [round(float(item.get("intensity") or 0), 3) for item in directions]
        speed = [round(float(item.get("speed") or 1), 3) for item in directions]
        emotions = [str(item.get("emotion") or "") for item in directions]
        pauses = [
            (int(item.get("pause_before_ms") or 0), int(item.get("pause_after_ms") or 0))
            for item in directions
        ]
        if len(set(intensity)) == 1 and len(set(speed)) == 1 and len(set(emotions)) == 1:
            errors.append("DELIVERY_CURVE_IS_FLAT")
        if len(beats) >= 4 and len(set(speed)) == 1 and len(set(pauses)) == 1:
            warnings.append("PACE_AND_PAUSE_PATTERN_HAS_NO_VARIATION")

    if is_short:
        duration = spec.get("duration_intent_seconds")
        if duration is not None:
            try:
                duration_value = float(duration)
                if duration_value > 0 and total_words / duration_value > 3.6:
                    warnings.append("SHORTS_WORD_DENSITY_MAY_OVERLOAD_COMPREHENSION")
            except (TypeError, ValueError):
                warnings.append("SHORTS_DURATION_INTENT_IS_NOT_NUMERIC")
        profile = spec.get("script_psychology_profile", {})
        if isinstance(profile, dict):
            profile_text = json.dumps(profile, ensure_ascii=False).casefold()
            if "3" not in profile_text:
                warnings.append("SHORTS_PROFILE_DOES_NOT_EXPOSE_FIRST_3_SECOND_HOOK_TARGET")
            if not ("4" in profile_text and "6" in profile_text):
                warnings.append("SHORTS_PROFILE_DOES_NOT_EXPOSE_4_TO_6_SECOND_REFRESH_HYPOTHESIS")
    else:
        # Long-form deliberately has no fixed attention-reset interval.
        if len(beats) >= 5 and len(set(purposes)) < 3:
            warnings.append("LONG_FORM_HAS_LOW_STRUCTURAL_VARIETY")

    return {
        "artifact": "pre_render_engagement_validation",
        "concept_id": concept_id,
        "format": fmt,
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "beat_count": len(beats),
            "total_words": total_words,
            "longest_beat_words": longest_words,
            "format_profile": "shorts" if is_short else "long_form",
        },
        "policy": {
            "rewrites_narration": False,
            "uses_model": False,
            "predicts_retention": False,
            "claims_dopamine_measurement": False,
            "shorts_first_hook_target_seconds": 3,
            "shorts_reward_refresh_hypothesis_seconds": "4-6",
            "long_form_fixed_reset_interval": False,
        },
        "provenance": {
            "approved_voice_spec": str(source.resolve()),
            "approved_voice_spec_sha256": sha256_file(source),
        },
    }


def batch() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(APPROVED_DIR.glob("*.approved_voice_spec.json")) if APPROVED_DIR.exists() else []
    items: list[dict[str, Any]] = []
    current: set[Path] = set()
    for source in paths:
        payload = json.loads(source.read_text(encoding="utf-8"))
        result = validate_spec(payload, source)
        dest = RESULTS_DIR / f"{source.stem}.engagement.json"
        atomic_write_json(dest, result)
        current.add(dest.resolve())
        items.append({
            "concept_id": result["concept_id"],
            "format": result["format"],
            "status": result["status"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "result": str(dest),
        })
    for stale in RESULTS_DIR.glob("*.engagement.json"):
        if stale.resolve() not in current:
            stale.unlink()
    summary = {
        "status": (
            "PASS" if items and all(item["status"] == "PASS" for item in items)
            else "BLOCKED" if items
            else "WAITING_FOR_APPROVED_PERFORMANCE"
        ),
        "processed": len(items),
        "passed": sum(item["status"] == "PASS" for item in items),
        "blocked": sum(item["status"] == "BLOCKED" for item in items),
        "items": items,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-render engagement validation")
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.parse_args()
    print(json.dumps(batch(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
