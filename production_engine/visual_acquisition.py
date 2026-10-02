"""Offline Visual Acquisition + Cost Router.

Consumes Human Format Gate approved plans, creates one visual requirement per
format beat, and applies a cheap-first routing policy to candidate assets.

This module never searches, downloads, or calls paid providers. Those adapters
are intentionally separate so cost and rights policy can be tested before any
external side effect occurs.
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
CONFIG_FILE = HERE / "visual_config.json"
APPROVED_FORMAT_DIR = (
    PROJECT_ROOT / "format_engine" / "output" / "approved_format_plans"
)
OUTPUT_DIR = HERE / "output"
TIMING_DIR = OUTPUT_DIR / "narration_timing_maps"
MANIFESTS_DIR = OUTPUT_DIR / "visual_manifests"
SUMMARY_FILE = OUTPUT_DIR / "visual_summary.json"

READY_STATUS = "READY_FOR_PRODUCTION_ENGINE"
KNOWN_SOURCE_TIERS = {
    "OWN_LIBRARY",
    "FREE_COMMERCIAL_LICENSE",
    "PUBLIC_DOMAIN",
    "CREATIVE_COMMONS_ALLOWED",
    "EDITORIAL_EXCERPT",
    "MOTION_GRAPHIC",
    "CHEAP_AI",
    "HIGGSFIELD_PREMIUM",
    "UNKNOWN",
}


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_" for char in value
    ).strip("._")
    return cleaned or "unknown"


def _float_value(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return parsed


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict):
        raise ValueError("Visual config must be an object")

    required = {
        "production_phase",
        "paid_visual_target_usd",
        "paid_visual_hard_cap_usd",
        "preferred_source_order",
        "verified_rights_source_tiers",
        "human_review_required_source_tiers",
        "generated_source_tiers",
        "max_paid_generated_share",
        "never_treat_clip_duration_as_permission",
        "require_source_url_or_local_path",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Visual config is missing: " + ", ".join(missing))

    order = [str(item) for item in config["preferred_source_order"]]
    if not order or len(order) != len(set(order)):
        raise ValueError("preferred_source_order must contain unique source tiers")
    unknown = sorted(set(order) - KNOWN_SOURCE_TIERS)
    if unknown:
        raise ValueError("Unknown source tiers: " + ", ".join(unknown))

    target = _float_value(
        config["paid_visual_target_usd"],
        label="paid_visual_target_usd",
    )
    hard_cap = _float_value(
        config["paid_visual_hard_cap_usd"],
        label="paid_visual_hard_cap_usd",
    )
    if target > hard_cap:
        raise ValueError("paid visual target cannot exceed hard cap")

    share = _float_value(
        config["max_paid_generated_share"],
        label="max_paid_generated_share",
    )
    if share > 1:
        raise ValueError("max_paid_generated_share must be between 0 and 1")

    config["paid_visual_target_usd"] = target
    config["paid_visual_hard_cap_usd"] = hard_cap
    config["max_paid_generated_share"] = share
    return config


def _approved_plan_identity(plan: dict[str, Any]) -> str:
    gate = plan.get("format_gate", {})
    if not isinstance(gate, dict) or gate.get("status") != READY_STATUS:
        raise ValueError("Format plan is not READY_FOR_PRODUCTION_ENGINE")

    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Approved format plan requires concept_id")
    return concept_id


def _build_requirement(
    *,
    concept_id: str,
    branch: dict[str, Any],
    beat: dict[str, Any],
    beat_index: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    fmt = str(branch.get("format", "")).strip()
    beat_id = str(beat.get("beat_id", "")).strip()
    if not fmt:
        raise ValueError("Every approved branch requires format")
    if not beat_id:
        raise ValueError(f"{fmt} beat {beat_index} requires beat_id")

    purpose = str(beat.get("purpose", "")).strip()
    treatment = str(beat.get("treatment", "")).strip()
    if not purpose or not treatment:
        raise ValueError(f"{fmt}.{beat_id} requires purpose and treatment")

    claim_ids = beat.get("claim_ids", [])
    source_section_ids = beat.get("source_section_ids", [])
    if not isinstance(claim_ids, list):
        raise ValueError(f"{fmt}.{beat_id} claim_ids must be a list")
    if not isinstance(source_section_ids, list) or not source_section_ids:
        raise ValueError(f"{fmt}.{beat_id} requires source_section_ids")

    requirement_id = f"{concept_id}:{fmt}:{beat_id}"
    return {
        "requirement_id": requirement_id,
        "beat_id": beat_id,
        "beat_index": beat_index,
        "narrative_purpose": purpose,
        "visual_treatment": treatment,
        "claim_ids": [str(item) for item in claim_ids],
        "source_section_ids": [str(item) for item in source_section_ids],
        "route_policy": list(config["preferred_source_order"]),
        "attempted_source_tiers": [],
        "candidates": [],
        "routing": {
            "status": "ACQUISITION_REQUIRED",
            "next_source_tier": config["preferred_source_order"][0],
            "selected_candidate_id": None,
            "estimated_paid_cost_usd": 0.0,
        },
    }


def build_manifest(
    plan: dict[str, Any],
    plan_path: Path,
    branch: dict[str, Any],
    config: dict[str, Any],
    *,
    timing_path: Path | None = None,
) -> dict[str, Any]:
    concept_id = _approved_plan_identity(plan)
    fmt = str(branch.get("format", "")).strip()
    if not fmt:
        raise ValueError("Every approved branch requires format")

    beats = branch.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError(f"{fmt} requires a non-empty beats list")

    requirements = []
    seen: set[str] = set()
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            raise ValueError(f"{fmt} beat {index} must be an object")
        requirement = _build_requirement(
            concept_id=concept_id,
            branch=branch,
            beat=beat,
            beat_index=index,
            config=config,
        )
        requirement_id = str(requirement["requirement_id"])
        if requirement_id in seen:
            raise ValueError(f"Duplicate visual requirement: {requirement_id}")
        seen.add(requirement_id)
        requirements.append(requirement)

    duration = branch.get("duration_intent_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        raise ValueError(f"{fmt} requires positive integer duration_intent_seconds")

    package = plan.get("package", {})
    if not isinstance(package, dict):
        package = {}

    return {
        "artifact": "visual_acquisition_manifest",
        "concept_id": concept_id,
        "format": fmt,
        "duration_intent_seconds": duration,
        "package": {
            "title": package.get("title"),
            "one_sentence_promise": package.get("one_sentence_promise"),
            "expected_payoff": package.get("expected_payoff"),
        },
        "production_phase": config["production_phase"],
        "cost_policy": {
            "paid_visual_target_usd": config["paid_visual_target_usd"],
            "paid_visual_hard_cap_usd": config["paid_visual_hard_cap_usd"],
            "max_paid_generated_share": config["max_paid_generated_share"],
        },
        "rights_policy": {
            "never_treat_clip_duration_as_permission": bool(
                config["never_treat_clip_duration_as_permission"]
            ),
            "human_review_required_source_tiers": list(
                config["human_review_required_source_tiers"]
            ),
        },
        "preferred_source_order": list(config["preferred_source_order"]),
        "requirements": requirements,
        "routing_summary": {
            "status": "ACQUISITION_REQUIRED",
            "requirements_total": len(requirements),
            "selected": 0,
            "human_review_required": 0,
            "acquisition_required": len(requirements),
            "estimated_paid_cost_usd": 0.0,
            "within_target": True,
            "within_hard_cap": True,
        },
        "manifest_provenance": {
            "approved_format_plan": str(plan_path.resolve()),
            "approved_format_plan_sha256": sha256_file(plan_path),
            "narration_timing_map": (
                str(timing_path.resolve()) if timing_path is not None else None
            ),
            "narration_timing_map_sha256": (
                sha256_file(timing_path)
                if timing_path is not None
                else None
            ),
        },
    }


def _candidate_cost(candidate: dict[str, Any]) -> float:
    return _float_value(
        candidate.get("estimated_cost_usd", 0.0),
        label="estimated_cost_usd",
    )


def _candidate_has_provenance(candidate: dict[str, Any]) -> bool:
    return bool(
        str(candidate.get("source_url") or "").strip()
        or str(candidate.get("local_path") or "").strip()
    )


def candidate_state(
    candidate: dict[str, Any],
    config: dict[str, Any],
    *,
    remaining_budget_usd: float,
) -> tuple[str, str]:
    tier = str(candidate.get("source_tier", "")).strip().upper()
    if tier not in KNOWN_SOURCE_TIERS:
        return "BLOCKED", "UNKNOWN_SOURCE_TIER"

    cost = _candidate_cost(candidate)
    if cost > remaining_budget_usd:
        return "BLOCKED", "PAID_VISUAL_HARD_CAP"

    review_tiers = {
        str(item) for item in config["human_review_required_source_tiers"]
    }
    if tier in review_tiers:
        return "HUMAN_REVIEW_REQUIRED", "RIGHTS_OR_CONTEXT_REVIEW"

    verified_tiers = {str(item) for item in config["verified_rights_source_tiers"]}
    if tier in verified_tiers:
        if str(candidate.get("rights_status", "")).strip().upper() != "VERIFIED":
            return "BLOCKED", "RIGHTS_NOT_VERIFIED"
        if candidate.get("commercial_use_allowed") is not True:
            return "BLOCKED", "COMMERCIAL_USE_NOT_VERIFIED"
        if (
            config.get("require_source_url_or_local_path")
            and not _candidate_has_provenance(candidate)
        ):
            return "BLOCKED", "MISSING_PROVENANCE"
        return "ELIGIBLE", "VERIFIED_RIGHTS"

    generated_tiers = {str(item) for item in config["generated_source_tiers"]}
    if tier in generated_tiers:
        rights_status = str(candidate.get("rights_status", "")).strip().upper()
        if rights_status not in {"PROJECT_CREATED", "PROVIDER_LICENSED"}:
            return "BLOCKED", "GENERATED_RIGHTS_NOT_VERIFIED"
        return "ELIGIBLE", "GENERATED_ASSET"

    return "BLOCKED", "UNSUPPORTED_SOURCE_TIER"


def _source_priority(config: dict[str, Any]) -> dict[str, int]:
    return {
        str(tier): index
        for index, tier in enumerate(config["preferred_source_order"])
    }


def _next_source_tier(
    requirement: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    attempted = {
        str(item).strip().upper()
        for item in requirement.get("attempted_source_tiers", [])
    }
    for candidate in requirement.get("candidates", []):
        if isinstance(candidate, dict):
            tier = str(candidate.get("source_tier", "")).strip().upper()
            if tier:
                attempted.add(tier)
    for tier in config["preferred_source_order"]:
        normalized = str(tier)
        if normalized not in attempted:
            return normalized
    return None


def route_requirement(
    requirement: dict[str, Any],
    config: dict[str, Any],
    *,
    remaining_budget_usd: float,
) -> dict[str, Any]:
    candidates = requirement.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("requirement candidates must be a list")

    priority = _source_priority(config)
    evaluated: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id", "")).strip()
        if not candidate_id:
            candidate_id = f"candidate-{index + 1}"
        tier = str(candidate.get("source_tier", "")).strip().upper()
        state, reason = candidate_state(
            candidate,
            config,
            remaining_budget_usd=remaining_budget_usd,
        )
        evaluated.append(
            {
                "candidate": candidate,
                "candidate_id": candidate_id,
                "source_tier": tier,
                "state": state,
                "reason": reason,
                "cost": _candidate_cost(candidate),
                "priority": priority.get(tier, len(priority) + 1),
            }
        )

    eligible = [item for item in evaluated if item["state"] == "ELIGIBLE"]
    review = [
        item for item in evaluated if item["state"] == "HUMAN_REVIEW_REQUIRED"
    ]

    eligible.sort(
        key=lambda item: (item["priority"], item["cost"], item["candidate_id"])
    )
    review.sort(key=lambda item: (item["priority"], item["candidate_id"]))

    best_eligible = eligible[0] if eligible else None
    best_review = review[0] if review else None

    if best_review is not None and (
        best_eligible is None
        or best_review["priority"] < best_eligible["priority"]
    ):
        return {
            "status": "HUMAN_REVIEW_REQUIRED",
            "next_source_tier": best_review["source_tier"],
            "selected_candidate_id": None,
            "review_candidate_id": best_review["candidate_id"],
            "reason": best_review["reason"],
            "estimated_paid_cost_usd": 0.0,
        }

    if best_eligible is not None:
        return {
            "status": "SELECTED",
            "next_source_tier": None,
            "selected_candidate_id": best_eligible["candidate_id"],
            "review_candidate_id": None,
            "reason": best_eligible["reason"],
            "estimated_paid_cost_usd": best_eligible["cost"],
        }

    next_tier = _next_source_tier(requirement, config)
    return {
        "status": "ACQUISITION_REQUIRED",
        "next_source_tier": next_tier,
        "selected_candidate_id": None,
        "review_candidate_id": None,
        "reason": "NO_ELIGIBLE_CANDIDATE",
        "estimated_paid_cost_usd": 0.0,
    }


def assert_current_manifest(manifest: dict[str, Any]) -> Path:
    provenance = manifest.get("manifest_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Manifest provenance is missing")
    source = Path(str(provenance.get("approved_format_plan", "")))
    expected = str(provenance.get("approved_format_plan_sha256", ""))
    if not source.exists() or not expected:
        raise ValueError("STALE_MANIFEST: approved format plan is unavailable")
    if sha256_file(source) != expected:
        raise ValueError("STALE_MANIFEST: approved format plan changed")
    return source


def route_manifest(
    manifest: dict[str, Any],
    config: dict[str, Any],
    *,
    verify_provenance: bool = True,
) -> dict[str, Any]:
    if verify_provenance:
        assert_current_manifest(manifest)

    requirements = manifest.get("requirements", [])
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Visual manifest requires requirements")

    hard_cap = _float_value(
        manifest.get("cost_policy", {}).get(
            "paid_visual_hard_cap_usd",
            config["paid_visual_hard_cap_usd"],
        ),
        label="paid_visual_hard_cap_usd",
    )
    target = _float_value(
        manifest.get("cost_policy", {}).get(
            "paid_visual_target_usd",
            config["paid_visual_target_usd"],
        ),
        label="paid_visual_target_usd",
    )

    spent = 0.0
    selected = 0
    review_count = 0
    acquisition_count = 0

    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError("Every visual requirement must be an object")
        decision = route_requirement(
            requirement,
            config,
            remaining_budget_usd=max(0.0, hard_cap - spent),
        )
        requirement["routing"] = decision
        if decision["status"] == "SELECTED":
            selected += 1
            spent += float(decision["estimated_paid_cost_usd"])
        elif decision["status"] == "HUMAN_REVIEW_REQUIRED":
            review_count += 1
        else:
            acquisition_count += 1

    if review_count:
        status = "HUMAN_REVIEW_REQUIRED"
    elif acquisition_count:
        status = "ACQUISITION_REQUIRED"
    else:
        status = "ROUTED"

    manifest["routing_summary"] = {
        "status": status,
        "requirements_total": len(requirements),
        "selected": selected,
        "human_review_required": review_count,
        "acquisition_required": acquisition_count,
        "estimated_paid_cost_usd": round(spent, 4),
        "within_target": spent <= target,
        "within_hard_cap": spent <= hard_cap,
    }
    return manifest


def run_prepare(
    approved_dir: Path = APPROVED_FORMAT_DIR,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    paths = (
        sorted(approved_dir.glob("*.approved_format_plan.json"))
        if approved_dir.exists()
        else []
    )
    prepared = []
    failures = []
    current_destinations: set[Path] = set()

    for path in paths:
        try:
            plan = load_json(path)
            if not isinstance(plan, dict):
                raise ValueError("Approved format plan must be an object")
            _approved_plan_identity(plan)
            branches = plan.get("branches", [])
            if not isinstance(branches, list) or not branches:
                raise ValueError("Approved format plan requires branches")

            for branch in branches:
                if not isinstance(branch, dict):
                    raise ValueError("Every approved format branch must be an object")
                concept_id = _approved_plan_identity(plan)
                fmt = str(branch.get("format") or "").strip()
                timing_path = (
                    TIMING_DIR
                    / f"{safe_slug(concept_id)}.{safe_slug(fmt)}.narration_timing_map.json"
                )
                if not timing_path.is_file():
                    raise ValueError(
                        f"{concept_id}.{fmt} requires current narration timing"
                    )
                timing = load_json(timing_path)
                if (
                    not isinstance(timing, dict)
                    or timing.get("status") != "READY_FOR_ROUGH_CUT"
                    or str(timing.get("concept_id") or "") != concept_id
                    or str(timing.get("format") or "") != fmt
                ):
                    raise ValueError(
                        f"{concept_id}.{fmt} narration timing is not ready"
                    )
                manifest = build_manifest(
                    plan,
                    path,
                    branch,
                    config,
                    timing_path=timing_path,
                )
                fmt = str(manifest["format"])
                concept_id = str(manifest["concept_id"])
                dest = (
                    MANIFESTS_DIR
                    / f"{safe_slug(concept_id)}.{safe_slug(fmt)}.visual_manifest.json"
                )
                atomic_write_json(dest, manifest)
                current_destinations.add(dest.resolve())
                prepared.append(
                    {
                        "concept_id": concept_id,
                        "format": fmt,
                        "manifest": str(dest),
                    }
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append(
                {
                    "format_plan": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale in MANIFESTS_DIR.glob("*.visual_manifest.json"):
        if stale.resolve() not in current_destinations:
            stale.unlink()

    status = (
        "VISUAL_MANIFESTS_READY"
        if prepared and not failures
        else "PARTIAL"
        if prepared
        else "WAITING_FOR_APPROVED_FORMAT_PLANS"
    )
    summary = {
        "status": status,
        "approved_format_plans_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "manifests": prepared,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def run_route(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    paths = (
        sorted(MANIFESTS_DIR.glob("*.visual_manifest.json"))
        if MANIFESTS_DIR.exists()
        else []
    )
    routed = []
    failures = []

    for path in paths:
        try:
            manifest = load_json(path)
            if not isinstance(manifest, dict):
                raise ValueError("Visual manifest must be an object")
            route_manifest(manifest, config)
            atomic_write_json(path, manifest)
            routed.append(
                {
                    "concept_id": manifest.get("concept_id"),
                    "format": manifest.get("format"),
                    "status": manifest.get("routing_summary", {}).get("status"),
                    "estimated_paid_cost_usd": manifest.get(
                        "routing_summary", {}
                    ).get("estimated_paid_cost_usd"),
                    "manifest": str(path),
                }
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append(
                {
                    "manifest": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    status = (
        "ROUTING_UPDATED"
        if routed and not failures
        else "PARTIAL"
        if routed
        else "WAITING_FOR_VISUAL_MANIFESTS"
    )
    summary = {
        "status": status,
        "routed": len(routed),
        "failures": failures,
        "manifests": routed,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline visual acquisition and cost router"
    )
    parser.add_argument("--mode", choices=("prepare", "route"), required=True)
    parser.add_argument("--approved-dir", type=Path, default=APPROVED_FORMAT_DIR)
    args = parser.parse_args()

    if args.mode == "prepare":
        result = run_prepare(args.approved_dir.resolve())
    else:
        result = run_route()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
