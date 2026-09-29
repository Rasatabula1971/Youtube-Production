"""Story Plan Engine.

Creates a story-structure layer between verified research and narration writing.
The Packaging title is immutable: story planning may organize the narrative but
may not rewrite the approved click promise.
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

    packaging = concept.get("packaging", {})
    if not isinstance(packaging, dict):
        packaging = {}

    title = str(packaging.get("title") or "").strip()
    if not title:
        raise ValueError("Approved package title is required before story planning")

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

    return {
        "concept_id": concept_id,
        "package": {
            "title": title,
            "thumbnail": packaging.get("thumbnail", {}),
            "opening_frame": packaging.get("opening_frame", {}),
            "one_sentence_promise": packaging.get("one_sentence_promise")
            or packaging.get("core_promise")
            or concept.get("audience_promise"),
            "expected_payoff": packaging.get("expected_payoff"),
            "viewer_problem": packaging.get("viewer_problem")
            or concept.get("viewer_problem"),
            "viewer_moment": packaging.get("viewer_moment")
            or concept.get("viewer_moment"),
            "desired_outcome": packaging.get("desired_outcome")
            or concept.get("desired_outcome"),
            "format_intent": packaging.get("format_intent")
            or concept.get("format_intent"),
        },
        "concept": {
            "premise": concept.get("premise"),
            "audience_promise": concept.get("audience_promise"),
            "viewer_problem": concept.get("viewer_problem"),
            "viewer_moment": concept.get("viewer_moment"),
            "desired_outcome": concept.get("desired_outcome"),
            "mechanism_id": concept.get("mechanism_id"),
            "mechanism_label": concept.get("mechanism_label"),
        },
        "accepted_claim_ids": sorted(claim_ids),
        "accepted_claims": accepted,
        "source_package": str(package_path.resolve()),
        "source_package_sha256": sha256_file(package_path),
    }


def build_story_plan_request(
    package: dict[str, Any],
    package_path: Path,
) -> dict[str, Any]:
    base = _base_from_verified_package(package, package_path)
    return {
        "artifact": "story_plan_request",
        **{key: value for key, value in base.items() if not key.startswith("source_")},
        "instructions": [
            "Plan the story before writing narration.",
            "The approved package title is immutable. Return it exactly as supplied.",
            "Do not write final narration or prose paragraphs.",
            "Design a clear viewer journey: opening tension, progressive understanding, reveal/payoff, and close.",
            "Every factual beat may use only accepted claim_ids supplied here.",
            "Framing can be original, but it must not introduce unsupported factual assertions.",
            "Do not copy source-video wording, sequence, personality, or exact execution.",
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

    approved_title = str(request.get("package", {}).get("title") or "")
    if str(response.get("title", "")) != approved_title:
        errors.append("title must exactly match the approved Packaging title")

    for field in (
        "story_question",
        "opening_hook_intent",
        "payoff_intent",
        "closing_intent",
    ):
        if not str(response.get(field, "")).strip():
            errors.append(f"{field} is required")

    beats = response.get("beats")
    if not isinstance(beats, list) or len(beats) < 3:
        errors.append("beats must contain at least 3 story beats")
        beats = []

    allowed_claims = set(request.get("accepted_claim_ids", []))
    used_claims: set[str] = set()
    seen_ids: set[str] = set()
    payoff_seen = False

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

    if beats and not payoff_seen:
        errors.append("story plan requires a PAYOFF beat")
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
