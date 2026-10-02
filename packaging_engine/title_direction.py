"""Post-script title-direction preparation for Packaging Architecture Slice 23.

This stage preserves the existing 5 Short + 5 Long-form title behavior, but
moves it after the Human Script Gate. A selected title is a preferred
psychological direction, not a permanently locked public title.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_STORY = _ROOT / "story_script_engine"
if str(_STORY) not in sys.path:
    sys.path.insert(0, str(_STORY))

from pipeline_integrity import atomic_write_json
from story_script_engine.script_review import (
    APPROVED_DIR as APPROVED_SCRIPTS_DIR,
    _approved_bundle_is_current,
)
from story_script_engine.story_script_engine import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_config.json"
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "title_direction_requests"
RESPONSES_DIR = OUTPUT_DIR / "title_direction_responses"
CANDIDATES_FILE = OUTPUT_DIR / "title_direction_candidates.json"
SUMMARY_FILE = OUTPUT_DIR / "title_direction_summary.json"

PROMPT_VERSION = "title-direction-v1.0"
SCHEMA_VERSION = "1.0"

DEFAULT_ANGLES = ["curiosity", "stakes", "unexpected", "mystery", "payoff"]
SEARCH_INTENTS = {"SEARCH", "BROWSE", "HYBRID"}


def load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if int(payload.get("title_variations_per_format") or 0) != 5:
        raise ValueError("Slice 23 requires exactly five title directions per format")
    angles = [str(x) for x in payload.get("title_angles", [])]
    if len(angles) != 5 or len(set(angles)) != 5:
        raise ValueError("Slice 23 requires five unique title angles")
    return payload


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _branch_context(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    branches = bundle.get("branch_scripts", {})
    if not isinstance(branches, dict) or not branches:
        raise ValueError("Approved script bundle has no branch scripts")
    out: list[dict[str, Any]] = []
    for fmt in sorted(branches):
        branch = branches.get(fmt)
        if not isinstance(branch, dict):
            raise ValueError(f"Approved {fmt} script is invalid")
        sections = branch.get("sections", [])
        if not isinstance(sections, list) or not sections:
            raise ValueError(f"Approved {fmt} script has no sections")
        out.append(
            {
                "format": fmt,
                "opening_hook": branch.get("opening_hook"),
                "opening_hook_mechanism": branch.get("opening_hook_mechanism"),
                "opening_hook_claim_ids": branch.get("opening_hook_claim_ids", []),
                "section_outline": [
                    {
                        "section_id": item.get("section_id"),
                        "purpose": item.get("purpose"),
                        "narration": item.get("narration"),
                        "claim_ids": item.get("claim_ids", []),
                    }
                    for item in sections
                    if isinstance(item, dict)
                ],
                "closing": branch.get("closing"),
            }
        )
    return out


def build_request(script_path: Path, bundle: dict[str, Any]) -> dict[str, Any]:
    concept_id = str(bundle.get("concept_id") or "").strip()
    if not concept_id:
        raise ValueError("Approved script bundle requires concept_id")
    if not _approved_bundle_is_current(concept_id):
        raise ValueError("STALE_APPROVED_SCRIPT_BUNDLE")
    canonical = APPROVED_SCRIPTS_DIR / f"{safe_slug(concept_id)}.approved_script.json"
    if script_path.resolve() != canonical.resolve():
        raise ValueError("Approved script bundle path is not canonical")
    if bundle.get("artifact") != "approved_script_bundle":
        raise ValueError("Invalid approved script bundle artifact")

    claims = bundle.get("accepted_claims", [])
    if not isinstance(claims, list) or not claims:
        raise ValueError("Title direction generation requires approved evidence claims")
    approved_claims = []
    claim_ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Approved claim must be an object")
        claim_id = str(claim.get("claim_id") or "").strip()
        statement = str(claim.get("statement") or "").strip()
        if not claim_id or not statement:
            raise ValueError("Approved claims require claim_id and statement")
        if claim_id in claim_ids:
            raise ValueError(f"Duplicate approved claim_id: {claim_id}")
        claim_ids.add(claim_id)
        approved_claims.append(
            {"claim_id": claim_id, "statement": statement, "role": claim.get("role")}
        )

    package = bundle.get("package", {})
    if not isinstance(package, dict):
        package = {}
    story_plan = bundle.get("story_plan", {})
    if not isinstance(story_plan, dict):
        story_plan = {}

    config = load_config()
    return {
        "artifact": "title_direction_request",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "concept_id": concept_id,
        "working_title": bundle.get("title"),
        "title_role": "PREFERRED_DIRECTION_NOT_FINAL_WORDING",
        "title_count_per_format": 5,
        "formats": ["short", "long_form"],
        "psychological_angles": list(config.get("title_angles", DEFAULT_ANGLES)),
        "title_guidance": {
            "preferred_character_range": [45, 60],
            "critical_information_target_characters": 40,
            "main_ideas": 1,
            "specificity_preferred": True,
            "claim_verification_required": True,
            "final_wording_editable_later": True,
            "length_is_guideline_not_hard_rejection": True,
        },
        "viewer_context": {
            "viewer_problem": package.get("viewer_problem"),
            "viewer_moment": package.get("viewer_moment"),
            "desired_outcome": package.get("desired_outcome"),
            "audience_promise": package.get("one_sentence_promise"),
            "format_intent": package.get("format_intent"),
        },
        "story_context": {
            "story_question": story_plan.get("story_question"),
            "payoff_intent": story_plan.get("payoff_intent"),
            "opening_hook_intent": story_plan.get("opening_hook_intent"),
            "branches": _branch_context(bundle),
        },
        "approved_claims": approved_claims,
        "allowed_evidence_refs": sorted(claim_ids),
        "instructions": [
            "Generate exactly five Short and five Long-form public-title directions.",
            "Use each configured psychological angle exactly once per format.",
            "Treat the approved script, hook and payoff as truth constraints.",
            "The title may be different from the internal working title.",
            "Do not invent evidence, numbers, danger, records, superlatives or certainty.",
            "Every material factual claim must cite approved evidence_refs.",
            "A title is a direction hypothesis; later Packaging may edit exact wording.",
            "Generate Short and Long-form titles independently rather than mechanically resizing wording.",
            "Front-load compelling information where practical and keep one central proposition.",
            "Use specificity when it improves clarity or tension.",
            "Do not predict virality, CTR or recommendation performance.",
        ],
        "request_provenance": {
            "approved_script": str(script_path.resolve()),
            "approved_script_sha256": sha256_file(script_path),
        },
    }


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    if str(response.get("concept_id") or "") != str(request.get("concept_id") or ""):
        raise ValueError("Title response concept_id mismatch")
    titles = response.get("titles")
    if not isinstance(titles, dict):
        raise ValueError("Title response requires titles object")

    configured_angles = [str(x) for x in request.get("psychological_angles", [])]
    allowed_refs = {str(x) for x in request.get("allowed_evidence_refs", [])}
    normalized: dict[str, list[dict[str, Any]]] = {}

    for fmt in ("short", "long_form"):
        items = titles.get(fmt)
        if not isinstance(items, list) or len(items) != 5:
            raise ValueError(f"titles.{fmt} must contain exactly five candidates")
        seen_ids: set[str] = set()
        seen_angles: list[str] = []
        out: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"titles.{fmt}[{index}] must be an object")
            title_id = str(item.get("title_id") or "").strip()
            angle = str(item.get("psychological_angle") or "").strip()
            title_text = str(item.get("title_text") or "").strip()
            expected_id = f"{fmt}-{angle}"
            if not title_id or title_id != expected_id:
                raise ValueError(
                    f"titles.{fmt}[{index}].title_id must be stable ID {expected_id!r}"
                )
            if title_id in seen_ids:
                raise ValueError(f"Duplicate title_id: {title_id}")
            if angle not in configured_angles:
                raise ValueError(f"Unsupported psychological angle: {angle}")
            if not title_text:
                raise ValueError(f"titles.{fmt}[{index}].title_text is required")
            if not str(item.get("primary_driver") or "").strip():
                raise ValueError(f"{title_id} requires primary_driver")
            if not str(item.get("core_claim") or "").strip():
                raise ValueError(f"{title_id} requires core_claim")
            search_intent = str(item.get("search_intent") or "").strip().upper()
            if search_intent not in SEARCH_INTENTS:
                raise ValueError(f"{title_id} has invalid search_intent")
            refs = item.get("evidence_refs", [])
            if not isinstance(refs, list):
                raise ValueError(f"{title_id} evidence_refs must be a list")
            unknown = sorted({str(x) for x in refs} - allowed_refs)
            if unknown:
                raise ValueError(
                    f"{title_id} invents evidence_refs: " + ", ".join(unknown)
                )
            seen_ids.add(title_id)
            seen_angles.append(angle)
            out.append(
                {
                    "title_id": title_id,
                    "candidate_id": title_id,
                    "format": fmt,
                    "title_text": title_text,
                    "title": title_text,
                    "psychological_angle": angle,
                    "angle": angle,
                    "primary_driver": str(item.get("primary_driver") or "").strip(),
                    "secondary_driver": str(item.get("secondary_driver") or "").strip() or None,
                    "core_claim": str(item.get("core_claim") or "").strip(),
                    "evidence_refs": [str(x) for x in refs],
                    "character_count": len(title_text),
                    "search_intent": search_intent,
                }
            )
        if sorted(seen_angles) != sorted(configured_angles):
            raise ValueError(f"titles.{fmt} must use each configured angle exactly once")
        normalized[fmt] = out

    return {
        "artifact": "title_direction_candidate_set",
        "schema_version": SCHEMA_VERSION,
        "concept_id": request["concept_id"],
        "titles": normalized,
        "source_request_fingerprint": _fingerprint(request),
    }


def run_prepare() -> dict[str, Any]:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    current: set[Path] = set()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    paths = (
        sorted(APPROVED_SCRIPTS_DIR.glob("*.approved_script.json"))
        if APPROVED_SCRIPTS_DIR.exists()
        else []
    )
    for path in paths:
        try:
            bundle = load_json(path)
            request = build_request(path, bundle)
            destination = REQUESTS_DIR / (
                f"{safe_slug(str(request['concept_id']))}.title_direction_request.json"
            )
            atomic_write_json(destination, request)
            current.add(destination.resolve())
            items.append(
                {
                    "concept_id": request["concept_id"],
                    "request": str(destination.resolve()),
                    "request_sha256": sha256_file(destination),
                }
            )
        except Exception as exc:
            failures.append(
                {"script": str(path), "error_type": type(exc).__name__, "error": str(exc)}
            )

    for stale in REQUESTS_DIR.glob("*.title_direction_request.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "TITLE_DIRECTION_REQUESTS_READY"
            if items and not failures
            else "PARTIAL"
            if items
            else "WAITING_FOR_APPROVED_SCRIPTS"
        ),
        "prepared": len(items),
        "failed": len(failures),
        "items": items,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def run_apply() -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for request_path in sorted(REQUESTS_DIR.glob("*.title_direction_request.json")):
        request = load_json(request_path)
        response_path = RESPONSES_DIR / (
            f"{safe_slug(str(request.get('concept_id') or ''))}.title_direction_response.json"
        )
        if not response_path.is_file():
            continue
        response = load_json(response_path)
        provenance = response.get("response_provenance", {})
        if (
            not isinstance(provenance, dict)
            or provenance.get("request_sha256") != sha256_file(request_path)
        ):
            rejected.append(
                {
                    "concept_id": request.get("concept_id"),
                    "error": "STALE_TITLE_DIRECTION_RESPONSE",
                }
            )
            continue
        try:
            item = validate_response(response, request)
            item["response_provenance"] = provenance
            item["request_file"] = str(request_path.resolve())
            item["request_sha256"] = sha256_file(request_path)
            candidates.append(item)
        except Exception as exc:
            rejected.append(
                {
                    "concept_id": request.get("concept_id"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    artifact = {
        "artifact": "title_direction_candidates",
        "schema_version": SCHEMA_VERSION,
        "count": len(candidates),
        "concepts": candidates,
        "rejected": rejected,
    }
    atomic_write_json(CANDIDATES_FILE, artifact)
    result = {
        "status": (
            "TITLE_DIRECTION_CANDIDATES_READY"
            if candidates and not rejected
            else "PARTIAL"
            if candidates
            else "WAITING_FOR_TITLE_DIRECTION_RESPONSES"
        ),
        "candidates": len(candidates),
        "rejected": len(rejected),
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-script title direction stage")
    parser.add_argument("--mode", choices=("prepare", "apply"), required=True)
    args = parser.parse_args()
    payload = run_prepare() if args.mode == "prepare" else run_apply()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
