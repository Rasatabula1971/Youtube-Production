"""Story Plan Engine.

Creates a story-structure layer between verified research and narration writing.
Slice 23 treats the title carried here as an internal working title only. Final
public title direction is selected after the script is human-approved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from channel_profiles.channel_profile import (
    load_active_profile_binding,
    normalize_binding,
)
from pipeline_integrity import atomic_write_json
from story_script_engine import (
    RESEARCH_VERIFIED_DIR,
    OUTPUT_DIR,
    assert_unique_slug_ids,
    load_json,
    safe_slug,
    sha256_file,
)

STORY_PLAN_REQUESTS_DIR = OUTPUT_DIR / "story_plan_requests"
STORY_PLAN_RESPONSES_DIR = OUTPUT_DIR / "story_plan_responses"
STORY_PLANS_DIR = OUTPUT_DIR / "story_plans"
STORY_PLAN_SUMMARY_FILE = OUTPUT_DIR / "story_plan_summary.json"

ALLOWED_ROLES = {
    "SETUP",
    "ESCALATION",
    "EXPLANATION",
    "REVEAL",
    "PAYOFF",
}

HOOK_MECHANISMS = {
    "CONTRADICTION",
    "SURPRISING_FACT",
    "STAKES",
    "EXPECTATION_VIOLATION",
    "SPECIFIC_CURIOSITY",
    "BOLD_PROMISE",
}

BEAT_PSYCHOLOGY_MECHANISMS = {
    "CURIOSITY",
    "PREDICTION",
    "TENSION",
    "STAKES",
    "NOVELTY",
    "EXPECTATION_VIOLATION",
    "CLARITY",
    "PAYOFF",
}

OPENING_BEAT_MECHANISMS = {
    "CURIOSITY",
    "PREDICTION",
    "TENSION",
    "STAKES",
    "NOVELTY",
    "EXPECTATION_VIOLATION",
}

LOOP_ACTIONS = {"NONE", "OPEN", "ADVANCE", "PAYOFF"}
TENSION_LEVELS = {"LOW", "MEDIUM", "HIGH"}


def validation_contract_sha256() -> str:
    """Fingerprint deterministic Story Plan acceptance rules."""
    digest = hashlib.sha256()
    digest.update(Path(__file__).resolve().read_bytes())
    return digest.hexdigest()


def _base_from_verified_package(
    package: dict[str, Any],
    package_path: Path,
) -> dict[str, Any]:
    if package.get("status") != "READY_FOR_STORY_SCRIPT":
        raise ValueError("Verified research package is not READY_FOR_STORY_SCRIPT")

    concept_id = str(package.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Verified research package requires concept_id")

    concept = package.get("concept", {})
    if not isinstance(concept, dict):
        raise ValueError("concept must be an object")

    legacy_packaging = concept.get("packaging", {})
    if not isinstance(legacy_packaging, dict):
        legacy_packaging = {}

    working_title = str(
        concept.get("working_title")
        or legacy_packaging.get("title")
        or ""
    ).strip()
    if not working_title:
        raise ValueError("Verified concept requires an internal working_title")

    claims = package.get("claims", [])
    if not isinstance(claims, list) or not claims:
        raise ValueError("Story planning requires accepted research claims")

    accepted: list[dict[str, Any]] = []
    claim_ids: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Every accepted claim must be an object")
        claim_id = str(claim.get("claim_id", "")).strip()
        statement = str(claim.get("statement", "")).strip()
        if not claim_id or not statement:
            raise ValueError("Every accepted claim requires claim_id and statement")
        claim_ids.append(claim_id)
        accepted.append(
            {
                "claim_id": claim_id,
                "statement": statement,
                "role": claim.get("role"),
                "question_ids": list(claim.get("question_ids", [])),
                "coverage": claim.get("coverage", {}),
            }
        )

    # Keep the historical key name "package" so older consumers and artifacts
    # remain readable, but its role is now explicitly pre-packaging story
    # context. No public title or thumbnail is locked at this stage.
    story_contract = {
        "title": working_title,
        "title_role": "INTERNAL_WORKING_TITLE",
        "final_public_title_locked": False,
        "selected_titles": {},
        "thumbnail": {},
        "opening_frame": {},
        "one_sentence_promise": (
            legacy_packaging.get("one_sentence_promise")
            or legacy_packaging.get("core_promise")
            or concept.get("audience_promise")
        ),
        "expected_payoff": (
            legacy_packaging.get("expected_payoff")
            or concept.get("desired_outcome")
        ),
        "viewer_problem": (
            concept.get("viewer_problem")
            or legacy_packaging.get("viewer_problem")
        ),
        "viewer_moment": (
            concept.get("viewer_moment")
            or legacy_packaging.get("viewer_moment")
        ),
        "desired_outcome": (
            concept.get("desired_outcome")
            or legacy_packaging.get("desired_outcome")
        ),
        "format_intent": (
            concept.get("format_intent")
            or legacy_packaging.get("format_intent")
        ),
        "legacy_package_id": legacy_packaging.get("package_id"),
    }

    return {
        "concept_id": concept_id,
        "package": story_contract,
        "concept": {
            "working_title": working_title,
            "premise": concept.get("premise"),
            "audience_promise": concept.get("audience_promise"),
            "viewer_problem": concept.get("viewer_problem"),
            "viewer_moment": concept.get("viewer_moment"),
            "desired_outcome": concept.get("desired_outcome"),
            "human_framing": concept.get("human_framing", {}),
            "mechanism_id": concept.get("mechanism_id"),
            "mechanism_label": concept.get("mechanism_label"),
            "format_intent": concept.get("format_intent"),
        },
        "accepted_claim_ids": sorted(claim_ids),
        "accepted_claims": accepted,
        "source_package": str(package_path.resolve()),
        "source_package_sha256": sha256_file(package_path),
    }


def build_story_plan_request(
    package: dict[str, Any],
    package_path: Path,
    channel_voice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _base_from_verified_package(package, package_path)
    channel_voice_binding = (
        normalize_binding(channel_voice)
        if channel_voice is not None
        else load_active_profile_binding()
    )
    voice_is_active = bool(channel_voice_binding["apply_to_generation"])
    voice_instruction = (
        "Apply the approved Channel Voice Profile to framing choices, "
        "technical-language treatment and narrator posture. It may not "
        "override verified research, the accepted viewer/story contract or the "
        "format psychology contract."
        if voice_is_active
        else (
            "No approved Channel Voice Profile exists. Do not infer a "
            "persistent channel personality from the niche, working title, source "
            "videos or generic creator advice. Use only the supplied "
            "research, human framing and psychology constraints."
        )
    )
    return {
        "artifact": "story_plan_request",
        **{key: value for key, value in base.items() if not key.startswith("source_")},
        "channel_voice": channel_voice_binding,
        "psychology_contract": {
            "opening_line": {
                "required": True,
                "allowed_mechanisms": sorted(HOOK_MECHANISMS),
                "rule": (
                    "Plan a high-impact first spoken line that creates immediate "
                    "curiosity, stakes, surprise, contradiction, expectation "
                    "violation, or a specific promise tied to the approved package."
                ),
                "truth_rule": (
                    "Bold framing may not exaggerate beyond accepted research; "
                    "factual hook claims must cite accepted claim_ids."
                ),
                "support_rule": (
                    "The narration immediately following the hook must justify, "
                    "contextualize, or begin proving it."
                ),
            },
            "beat_mechanisms": sorted(BEAT_PSYCHOLOGY_MECHANISMS),
            "loop_actions": sorted(LOOP_ACTIONS),
            "tension_levels": sorted(TENSION_LEVELS),
            "drama_floor": 4,
            "drama_center": 5,
            "human_framing": base["concept"].get("human_framing", {}),
            "principles": [
                "Create curiosity through a real information gap, not fake withholding.",
                "Make viewer expectations explicit so contradiction or surprise has a target.",
                "Introduce one primary new idea at a time when complexity is high.",
                "Drama never deliberately falls below 4/10; 5/10 is the normal center, with higher peaks when the accepted framing truthfully supports them.",
                "Use tension and release instead of flat intensity; a lower beat is breathing room, not permission to become boring.",
                "Tempo is independent of drama and must also change across the story; a slow-motion beat can remain high drama.",
                "Do not manufacture catastrophe or exaggerate beyond accepted research.",
                "Every opened loop must be advanced and ultimately paid off.",
                "The final payoff must satisfy the accepted viewer/story promise. Final title/thumbnail packaging is selected only after script approval.",
                "No fixed hook-second or pattern-interrupt timing rule is assumed.",
            ],
        },
        "instructions": [
            "Plan the story before writing narration.",
            "The supplied title is an INTERNAL WORKING TITLE used only for artifact identity. Return it unchanged here; it is not the final public YouTube title.",
            "Do not write final narration or prose paragraphs.",
            "Design a clear viewer journey: high-impact opening, progressive understanding, reveal/payoff, and close.",
            "Make the viewer state explicit: what they know, expect, and want resolved.",
            "Assign one primary audience-psychology function to every beat.",
            "Assign every beat a drama_level from 4-10 and a separate tempo_level from 1-10.",
            "Use the accepted Human Framing drama and tempo curves as directional shape: create rises and releases, do not flatten them into one constant level.",
            "The story must reach at least the accepted concept drama target while remaining inside the truthful drama constraint.",
            "Track open loops explicitly; every OPEN must later receive a PAYOFF.",
            "Control cognitive load by stating what each beat should make easier to understand.",
            "Every factual beat may use only accepted claim_ids supplied here.",
            "Framing can be original, but it must not introduce unsupported factual assertions.",
            "Do not copy source-video wording, sequence, personality, or exact execution.",
            voice_instruction,
            "Make each beat advance the viewer rather than repeat the previous beat.",
        ],
        "request_provenance": {
            "verified_research_package": base["source_package"],
            "verified_research_sha256": base["source_package_sha256"],
        },
    }


def validate_story_plan_response(
    response: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if str(response.get("concept_id", "")) != str(request.get("concept_id", "")):
        errors.append("concept_id mismatch")

    working_title = str(request.get("package", {}).get("title") or "")
    if str(response.get("title", "")) != working_title:
        errors.append("title must exactly match the internal working title")

    for field in (
        "story_question",
        "opening_hook_intent",
        "payoff_intent",
        "closing_intent",
    ):
        if not str(response.get(field, "")).strip():
            errors.append(f"{field} is required")

    viewer_state = response.get("viewer_state")
    if not isinstance(viewer_state, dict):
        errors.append("viewer_state is required")
        viewer_state = {}
    for field in ("awareness", "expectation", "desired_resolution"):
        if not str(viewer_state.get(field, "")).strip():
            errors.append(f"viewer_state requires {field}")

    opening_psychology = response.get("opening_psychology")
    if not isinstance(opening_psychology, dict):
        errors.append("opening_psychology is required")
        opening_psychology = {}
    hook_mechanism = str(opening_psychology.get("mechanism", "")).strip().upper()
    if hook_mechanism not in HOOK_MECHANISMS:
        errors.append(
            "opening_psychology mechanism must be one of "
            + ", ".join(sorted(HOOK_MECHANISMS))
        )
    for field in ("impact_intent", "justification_intent"):
        if not str(opening_psychology.get(field, "")).strip():
            errors.append(f"opening_psychology requires {field}")
    opening_claim_ids = opening_psychology.get("claim_ids")
    if not isinstance(opening_claim_ids, list):
        errors.append("opening_psychology claim_ids must be a list")
        opening_claim_ids = []

    beats = response.get("beats")
    if not isinstance(beats, list) or len(beats) < 3:
        errors.append("beats must contain at least 3 story beats")
        beats = []

    allowed_claims = set(request.get("accepted_claim_ids", []))
    used_claims: set[str] = set()
    seen_ids: set[str] = set()
    payoff_seen = False
    opened_loops: set[str] = set()
    paid_loops: set[str] = set()
    drama_levels: list[int] = []
    tempo_levels: list[int] = []

    for claim_id in opening_claim_ids:
        normalized = str(claim_id)
        if normalized not in allowed_claims:
            errors.append(
                f"opening_psychology uses unapproved claim_id {normalized}"
            )
        else:
            used_claims.add(normalized)

    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"beat {index} must be an object")
            continue
        beat_id = str(beat.get("beat_id", "")).strip()
        if not beat_id:
            errors.append(f"beat {index} requires beat_id")
        elif beat_id in seen_ids:
            errors.append(f"duplicate beat_id: {beat_id}")
        seen_ids.add(beat_id)

        role = str(beat.get("role", "")).strip().upper()
        if role not in ALLOWED_ROLES:
            errors.append(
                f"{beat_id or index} role must be one of "
                + ", ".join(sorted(ALLOWED_ROLES))
            )
        if role == "PAYOFF":
            payoff_seen = True

        for field in ("purpose", "viewer_progress", "transition_intent"):
            if not str(beat.get(field, "")).strip():
                errors.append(f"{beat_id or index} requires {field}")

        psychology = beat.get("psychology")
        if not isinstance(psychology, dict):
            errors.append(f"{beat_id or index} requires psychology")
            psychology = {}

        primary = str(psychology.get("primary_mechanism", "")).strip().upper()
        if primary not in BEAT_PSYCHOLOGY_MECHANISMS:
            errors.append(
                f"{beat_id or index} psychology primary_mechanism must be one of "
                + ", ".join(sorted(BEAT_PSYCHOLOGY_MECHANISMS))
            )
        if index == 0 and primary not in OPENING_BEAT_MECHANISMS:
            errors.append(
                f"{beat_id or index} opening beat must use a high-impact psychology mechanism"
            )

        for field in ("viewer_expectation", "cognitive_load_instruction"):
            if not str(psychology.get(field, "")).strip():
                errors.append(f"{beat_id or index} psychology requires {field}")

        tension = str(psychology.get("tension_level", "")).strip().upper()
        if tension not in TENSION_LEVELS:
            errors.append(
                f"{beat_id or index} psychology tension_level must be one of "
                + ", ".join(sorted(TENSION_LEVELS))
            )

        drama_level = psychology.get("drama_level")
        if (
            not isinstance(drama_level, int)
            or isinstance(drama_level, bool)
            or not 4 <= drama_level <= 10
        ):
            errors.append(
                f"{beat_id or index} psychology drama_level must be an integer from 4-10"
            )
        else:
            drama_levels.append(drama_level)

        tempo_level = psychology.get("tempo_level")
        if (
            not isinstance(tempo_level, int)
            or isinstance(tempo_level, bool)
            or not 1 <= tempo_level <= 10
        ):
            errors.append(
                f"{beat_id or index} psychology tempo_level must be an integer from 1-10"
            )
        else:
            tempo_levels.append(tempo_level)

        loop_action = str(psychology.get("loop_action", "")).strip().upper()
        loop_id = str(psychology.get("open_loop_id") or "").strip()
        if loop_action not in LOOP_ACTIONS:
            errors.append(
                f"{beat_id or index} psychology loop_action must be one of "
                + ", ".join(sorted(LOOP_ACTIONS))
            )
        elif loop_action == "NONE":
            if loop_id:
                errors.append(
                    f"{beat_id or index} open_loop_id must be empty when loop_action is NONE"
                )
        elif not loop_id:
            errors.append(
                f"{beat_id or index} psychology requires open_loop_id for {loop_action}"
            )
        elif loop_action == "OPEN":
            if loop_id in opened_loops:
                errors.append(f"{beat_id or index} reopens existing loop {loop_id}")
            else:
                opened_loops.add(loop_id)
        elif loop_action in {"ADVANCE", "PAYOFF"}:
            if loop_id not in opened_loops:
                errors.append(
                    f"{beat_id or index} references unopened loop {loop_id}"
                )
            elif loop_id in paid_loops:
                errors.append(
                    f"{beat_id or index} references already paid-off loop {loop_id}"
                )
            elif loop_action == "PAYOFF":
                paid_loops.add(loop_id)

        claim_ids = beat.get("claim_ids")
        if not isinstance(claim_ids, list):
            errors.append(f"{beat_id or index} claim_ids must be a list")
            continue
        for claim_id in claim_ids:
            normalized = str(claim_id)
            if normalized not in allowed_claims:
                errors.append(
                    f"{beat_id or index} uses unapproved claim_id {normalized}"
                )
            else:
                used_claims.add(normalized)

    if beats and len(drama_levels) == len(beats):
        if len(set(drama_levels)) < 2:
            errors.append("story plan drama_level must pulse; a flat drama curve is not allowed")
        framing = request.get("concept", {}).get("human_framing", {})
        drama = framing.get("drama", {}) if isinstance(framing, dict) else {}
        target = drama.get("target") if isinstance(drama, dict) else None
        if isinstance(target, int) and not isinstance(target, bool):
            if max(drama_levels) < target:
                errors.append(
                    "story plan drama curve never reaches the accepted Human Framing target"
                )

    if beats and len(tempo_levels) == len(beats) and len(set(tempo_levels)) < 2:
        errors.append("story plan tempo_level must change; a flat tempo curve is not allowed")

    if beats and not payoff_seen:
        errors.append("story plan requires a PAYOFF beat")
    unresolved_loops = opened_loops - paid_loops
    if unresolved_loops:
        errors.append(
            "story plan leaves open loop(s) unresolved: "
            + ", ".join(sorted(unresolved_loops))
        )
    if beats and not used_claims:
        errors.append("story plan must use at least one accepted claim")

    return {
        "valid": not errors,
        "errors": errors,
        "claim_usage": sorted(used_claims),
        "unused_accepted_claim_ids": sorted(allowed_claims - used_claims),
    }


def run_prepare(
    verified_dir: Path = RESEARCH_VERIFIED_DIR,
) -> dict[str, Any]:
    STORY_PLAN_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(verified_dir.glob("*.verified_research_package.json"))
        if verified_dir.exists()
        else []
    )

    pending: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for path in paths:
        try:
            pending.append(build_story_plan_request(load_json(path), path))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append(
                {
                    "package": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    assert_unique_slug_ids(
        [str(item["concept_id"]) for item in pending],
        label="concept",
    )

    prepared: list[dict[str, Any]] = []
    current: set[Path] = set()
    for request in pending:
        dest = (
            STORY_PLAN_REQUESTS_DIR
            / f"{safe_slug(str(request['concept_id']))}.story_plan_request.json"
        )
        atomic_write_json(dest, request)
        current.add(dest.resolve())
        prepared.append(
            {"concept_id": request["concept_id"], "request": str(dest)}
        )

    for stale in STORY_PLAN_REQUESTS_DIR.glob("*.story_plan_request.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "STORY_PLAN_REQUESTS_READY"
            if prepared
            else "WAITING_FOR_VERIFIED_RESEARCH"
        ),
        "verified_packages_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
    }
    atomic_write_json(STORY_PLAN_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Story Plan Engine")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.add_argument(
        "--verified-dir",
        type=Path,
        default=RESEARCH_VERIFIED_DIR,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_prepare(args.verified_dir.resolve()),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
