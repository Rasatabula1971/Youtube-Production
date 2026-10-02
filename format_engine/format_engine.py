"""Format Engine.

Consumes human-approved scripts and prepares bounded format-plan requests.

Long-form and Shorts are separate production branches. They share source
understanding, research, accepted facts and the master story package, but they
are never treated as identical edits of the same timeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_OVERLAP_ROOT = Path(__file__).resolve().parent.parent
if str(_OVERLAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_OVERLAP_ROOT))

from source_overlap import check_texts

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
CONFIG_FILE = HERE / "format_config.json"
APPROVED_SCRIPTS_DIR = (
    PROJECT_ROOT / "story_script_engine" / "output" / "approved_scripts"
)
SCRIPT_SECTION_STATE_DIR = (
    PROJECT_ROOT / "story_script_engine" / "output" / "script_section_states"
)
SCRIPT_DRAFTS_DIR = (
    PROJECT_ROOT / "story_script_engine" / "output" / "script_drafts"
)
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "format_requests"
RESPONSES_DIR = OUTPUT_DIR / "format_responses"
PLANS_DIR = OUTPUT_DIR / "format_plans"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
MODEL_RUNS_DIR = OUTPUT_DIR / "format_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_format_outputs"
MODEL_BATCH_SUMMARY_FILE = OUTPUT_DIR / "format_model_batch_summary.json"
FORMAT_REVIEW_REQUESTS_DIR = OUTPUT_DIR / "format_review_requests"
FORMAT_REVIEW_RESPONSES_DIR = OUTPUT_DIR / "format_review_responses"
APPROVED_FORMAT_PLANS_DIR = OUTPUT_DIR / "approved_format_plans"
FORMAT_GATE_SUMMARY_FILE = OUTPUT_DIR / "format_gate_summary.json"

READY_STATUS = "READY_FOR_PRODUCTION"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def safe_slug(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in value).strip(
        "._"
    )
    return cleaned or "unknown"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_section_state_path(concept_id: str, fmt: str) -> Path:
    return (
        SCRIPT_SECTION_STATE_DIR
        / (
            f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
            "section_state.json"
        )
    ).resolve()


def _expected_script_draft_path(concept_id: str, fmt: str) -> Path:
    return (
        SCRIPT_DRAFTS_DIR
        / (
            f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
            "script_draft.json"
        )
    ).resolve()


def assert_section_review_provenance_current(
    script: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Fail closed if prepared selective review is no longer current."""
    concept_id = str(script.get("concept_id") or "").strip()
    required = script.get("required_branches", [])
    provenance = script.get("approved_provenance", {})
    if not concept_id:
        raise ValueError("Approved script bundle requires concept_id")
    if not isinstance(required, list) or not required:
        raise ValueError("Approved script bundle requires required_branches")
    if not isinstance(provenance, dict):
        raise ValueError("Approved script bundle requires approved_provenance")

    result: dict[str, dict[str, Any]] = {}
    for fmt in required:
        branch = str(fmt or "").strip()
        record = provenance.get(branch, {})
        if not isinstance(record, dict):
            raise ValueError(
                f"Approved {branch} script is missing review provenance"
            )
        prepared = record.get("section_review_prepared") is True
        if not prepared:
            result[branch] = {
                "prepared": False,
                "section_state_sha256": None,
                "state_version": None,
            }
            continue

        expected_state = _expected_section_state_path(concept_id, branch)
        recorded_state = Path(
            str(record.get("section_state") or "")
        ).resolve()
        if recorded_state != expected_state:
            raise ValueError(
                f"Approved {branch} section-state path is not canonical"
            )
        if not expected_state.is_file():
            raise ValueError(
                f"Approved {branch} section-state artifact is unavailable"
            )
        expected_hash = str(
            record.get("section_state_sha256") or ""
        ).strip()
        if not expected_hash or sha256_file(expected_state) != expected_hash:
            raise ValueError(
                f"Approved {branch} section-state provenance is stale"
            )

        state = load_json(expected_state)
        if (
            str(state.get("concept_id") or "") != concept_id
            or str(state.get("format") or "") != branch
        ):
            raise ValueError(
                f"Approved {branch} section-state identity mismatch"
            )

        expected_draft = _expected_script_draft_path(concept_id, branch)
        recorded_draft = Path(
            str(state.get("source_draft") or "")
        ).resolve()
        if recorded_draft != expected_draft:
            raise ValueError(
                f"Approved {branch} section state points to non-canonical draft"
            )
        if not expected_draft.is_file():
            raise ValueError(
                f"Approved {branch} Script Draft is unavailable"
            )
        if (
            str(state.get("source_draft_sha256") or "")
            != sha256_file(expected_draft)
        ):
            raise ValueError(
                f"Approved {branch} section state is stale against Script Draft"
            )

        targets = [
            item
            for item in state.get("targets", [])
            if isinstance(item, dict)
        ]
        unresolved = [
            str(item.get("target_id") or "")
            for item in targets
            if item.get("decision") != "ACCEPTED"
            or item.get("locked") is not True
        ]
        if unresolved:
            raise ValueError(
                f"Approved {branch} section review is incomplete: "
                + ", ".join(unresolved)
            )

        state_version = int(state.get("state_version") or 0)
        if int(record.get("section_state_version") or -1) != state_version:
            raise ValueError(
                f"Approved {branch} section-state version changed"
            )
        if int(record.get("section_target_count") or -1) != len(targets):
            raise ValueError(
                f"Approved {branch} section target count changed"
            )
        lineage = [
            {
                "target_id": str(item.get("target_id") or ""),
                "target_sha256": str(item.get("target_sha256") or ""),
            }
            for item in sorted(
                targets,
                key=lambda item: int(item.get("ordinal") or 0),
            )
        ]
        if record.get("section_targets") != lineage:
            raise ValueError(
                f"Approved {branch} section target lineage changed"
            )

        result[branch] = {
            "prepared": True,
            "section_state_sha256": expected_hash,
            "state_version": state_version,
            "target_count": len(targets),
        }
    return result


def assert_unique_slug_ids(values: list[str], *, label: str) -> None:
    owners: dict[str, str] = {}
    for raw in values:
        slug = safe_slug(raw)
        previous = owners.get(slug)
        if previous is not None:
            if previous == raw:
                raise ValueError(f"Duplicate {label} ID: {raw!r}")
            raise ValueError(
                f"{label} IDs collide after filesystem normalization: "
                f"{previous!r} and {raw!r} -> {slug!r}"
            )
        owners[slug] = raw


def _request_slug_from_path(path: Path) -> str | None:
    suffix = ".format_request.json"
    name = path.name
    if not name.endswith(suffix):
        return None
    return name[: -len(suffix)]


def _existing_request_hashes(requests_dir: Path) -> dict[str, str]:
    if not requests_dir.exists():
        return {}
    result: dict[str, str] = {}
    for path in requests_dir.glob("*.format_request.json"):
        slug = _request_slug_from_path(path)
        if slug:
            result[slug] = sha256_file(path)
    return result


def _remove_file(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_file():
        raise ValueError(f"Expected file during Format cleanup: {path}")
    path.unlink()
    return True


def _invalidate_format_slug(slug: str) -> list[str]:
    """Remove downstream artifacts derived from an invalidated Format request."""
    removed: list[str] = []
    paths = [
        RESPONSES_DIR / f"{slug}.json",
        PLANS_DIR / f"{slug}.format_plan.json",
        MODEL_RUNS_DIR / f"{slug}.model_run.json",
        RAW_OUTPUTS_DIR / f"{slug}.txt",
        FORMAT_REVIEW_REQUESTS_DIR / f"{slug}.format_review_request.json",
        FORMAT_REVIEW_RESPONSES_DIR / f"{slug}.format_review_response.json",
        APPROVED_FORMAT_PLANS_DIR / f"{slug}.approved_format_plan.json",
    ]
    for path in paths:
        if _remove_file(path):
            removed.append(str(path.resolve()))
    return removed


def _prune_invalidated_format_outputs(
    previous_hashes: dict[str, str],
    current_hashes: dict[str, str],
) -> dict[str, Any]:
    invalidated = sorted(
        slug
        for slug in set(previous_hashes) | set(current_hashes)
        if previous_hashes.get(slug) != current_hashes.get(slug)
    )
    removed: list[str] = []
    for slug in invalidated:
        removed.extend(_invalidate_format_slug(slug))

    summaries_removed: list[str] = []
    if invalidated:
        for path in (MODEL_BATCH_SUMMARY_FILE, FORMAT_GATE_SUMMARY_FILE):
            if _remove_file(path):
                summaries_removed.append(str(path.resolve()))

    return {
        "invalidated_concept_slugs": invalidated,
        "removed_artifacts": removed,
        "removed_summaries": summaries_removed,
    }


def _load_dict_or_none(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _prune_mismatched_active_format_outputs(
    current_hashes: dict[str, str],
) -> dict[str, Any]:
    removed: list[str] = []
    invalidated_review_slugs: set[str] = set()

    for slug, request_hash in sorted(current_hashes.items()):
        response_path = RESPONSES_DIR / f"{slug}.json"
        plan_path = PLANS_DIR / f"{slug}.format_plan.json"
        run_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
        raw_path = RAW_OUTPUTS_DIR / f"{slug}.txt"
        review_request_path = (
            FORMAT_REVIEW_REQUESTS_DIR
            / f"{slug}.format_review_request.json"
        )
        review_response_path = (
            FORMAT_REVIEW_RESPONSES_DIR
            / f"{slug}.format_review_response.json"
        )
        approved_plan_path = (
            APPROVED_FORMAT_PLANS_DIR
            / f"{slug}.approved_format_plan.json"
        )

        response = _load_dict_or_none(response_path)
        response_provenance = (
            response.get("response_provenance", {})
            if isinstance(response, dict)
            else {}
        )
        response_current = bool(
            response
            and isinstance(response_provenance, dict)
            and response_provenance.get("request_sha256") == request_hash
        )
        if response_path.exists() and not response_current:
            if _remove_file(response_path):
                removed.append(str(response_path.resolve()))

        plan = _load_dict_or_none(plan_path)
        plan_provenance = (
            plan.get("plan_provenance", {})
            if isinstance(plan, dict)
            else {}
        )
        plan_current = bool(
            plan
            and isinstance(plan_provenance, dict)
            and plan_provenance.get("request_sha256") == request_hash
        )
        if plan_path.exists() and not plan_current:
            if _remove_file(plan_path):
                removed.append(str(plan_path.resolve()))
            invalidated_review_slugs.add(slug)

        run = _load_dict_or_none(run_path)
        run_current = bool(
            run
            and run.get("status") == "VALIDATED"
            and run.get("request_sha256") == request_hash
        )
        if run_path.exists() and not run_current:
            if _remove_file(run_path):
                removed.append(str(run_path.resolve()))
            if _remove_file(raw_path):
                removed.append(str(raw_path.resolve()))

        if not plan_current:
            invalidated_review_slugs.add(slug)
            continue

        plan_hash = sha256_file(plan_path)
        review_request = _load_dict_or_none(review_request_path)
        review_provenance = (
            review_request.get("request_provenance", {})
            if isinstance(review_request, dict)
            else {}
        )
        review_request_current = bool(
            review_request
            and isinstance(review_provenance, dict)
            and review_provenance.get("format_plan")
            == str(plan_path.resolve())
            and review_provenance.get("format_plan_sha256") == plan_hash
        )
        if review_request_path.exists() and not review_request_current:
            if _remove_file(review_request_path):
                removed.append(str(review_request_path.resolve()))
            invalidated_review_slugs.add(slug)

        review_response = _load_dict_or_none(review_response_path)
        review_response_current = bool(
            review_request_current
            and review_response
            and review_response.get("format_plan_sha256") == plan_hash
        )
        if review_response_path.exists() and not review_response_current:
            if _remove_file(review_response_path):
                removed.append(str(review_response_path.resolve()))

        approved = _load_dict_or_none(approved_plan_path)
        approved_provenance = (
            approved.get("approved_provenance", {})
            if isinstance(approved, dict)
            else {}
        )
        approved_current = bool(
            review_request_current
            and approved
            and isinstance(approved_provenance, dict)
            and approved_provenance.get("format_plan_sha256") == plan_hash
        )
        if approved_plan_path.exists() and not approved_current:
            if _remove_file(approved_plan_path):
                removed.append(str(approved_plan_path.resolve()))

    if invalidated_review_slugs and _remove_file(FORMAT_GATE_SUMMARY_FILE):
        removed.append(str(FORMAT_GATE_SUMMARY_FILE.resolve()))

    return {
        "checked_concept_slugs": sorted(current_hashes),
        "review_invalidated_concept_slugs": sorted(
            invalidated_review_slugs
        ),
        "removed_artifacts": removed,
    }


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    required = {"allowed_formats", "format_intent_branches", "branch_constraints"}
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Format Engine config is missing: " + ", ".join(missing))
    return config


def resolve_branches(format_intent: str, config: dict[str, Any]) -> list[str]:
    """Map an approved concept format intent onto required production branches."""
    intent = str(format_intent or "").strip()
    mapping = config["format_intent_branches"]
    if intent not in mapping:
        raise ValueError(
            "format_intent must be one of "
            + ", ".join(sorted(mapping))
            + f"; got {intent!r}"
        )
    branches = [str(branch) for branch in mapping[intent]]
    if not branches:
        raise ValueError(f"format_intent {intent} resolves to no production branch")
    unknown = sorted(set(branches) - set(config["allowed_formats"]))
    if unknown:
        raise ValueError("Unknown production branch: " + ", ".join(unknown))
    return branches


def normalize_beat(beat: dict[str, Any]) -> str:
    purpose = " ".join(str(beat.get("purpose", "")).lower().split())
    treatment = " ".join(str(beat.get("treatment", "")).lower().split())
    return f"{purpose}|{treatment}"


def branch_shape(branch: dict[str, Any]) -> list[str]:
    beats = branch.get("beats")
    if not isinstance(beats, list):
        return []
    return [normalize_beat(beat) for beat in beats if isinstance(beat, dict)]


def build_format_request(
    script: dict[str, Any],
    script_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    gate = script.get("script_gate", {})
    if not isinstance(gate, dict) or gate.get("status") != READY_STATUS:
        raise ValueError("Approved script bundle is not READY_FOR_PRODUCTION")

    concept_id = str(script.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Approved script bundle requires concept_id")

    section_review_provenance = assert_section_review_provenance_current(
        script
    )

    package = script.get("package", {})
    if not isinstance(package, dict):
        package = {}
    approved_title = str(package.get("title") or "").strip()
    if not approved_title:
        raise ValueError("Approved script bundle requires Packaging title")
    if str(script.get("title") or "") != approved_title:
        raise ValueError(
            "Approved script bundle title does not match the Packaging title contract"
        )

    required_branches = resolve_branches(
        str(package.get("format_intent") or ""),
        config,
    )
    bundle_required = script.get("required_branches", [])
    if not isinstance(bundle_required, list) or set(bundle_required) != set(required_branches):
        raise ValueError(
            "Approved script bundle branches do not match format_intent"
        )

    branch_scripts = script.get("branch_scripts")
    if not isinstance(branch_scripts, dict) or not branch_scripts:
        raise ValueError("Approved script bundle requires branch_scripts")
    if set(branch_scripts) != set(required_branches):
        raise ValueError("Approved script bundle is missing a required branch script")

    claims = script.get("accepted_claims", [])
    if not isinstance(claims, list) or not claims:
        raise ValueError("Format planning requires at least one accepted claim")
    claim_ids: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Every accepted claim must be an object")
        claim_id = str(claim.get("claim_id", "")).strip()
        if not claim_id:
            raise ValueError("Every accepted claim requires claim_id")
        claim_ids.append(claim_id)

    branch_story_packages: dict[str, dict[str, Any]] = {}
    section_ids_by_branch: dict[str, list[str]] = {}
    for fmt in required_branches:
        branch_script = branch_scripts.get(fmt)
        if not isinstance(branch_script, dict):
            raise ValueError(f"Approved script bundle is missing {fmt} script")
        if str(branch_script.get("format") or "") != fmt:
            raise ValueError(f"Approved {fmt} script has wrong format identity")
        expected_title = approved_title
        selected_titles = package.get("selected_titles", {})
        if isinstance(selected_titles, dict):
            selection = selected_titles.get(fmt, {})
            if isinstance(selection, dict):
                expected_title = str(selection.get("title") or "").strip() or approved_title
        if str(branch_script.get("title") or "") != expected_title:
            raise ValueError(
                f"Approved {fmt} script violates format-specific Packaging title"
            )
        sections = branch_script.get("sections", [])
        if not isinstance(sections, list) or not sections:
            raise ValueError(f"Approved {fmt} script requires sections")
        section_ids: list[str] = []
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError(f"Every {fmt} script section must be an object")
            section_id = str(section.get("section_id", "")).strip()
            if not section_id:
                raise ValueError(f"Every {fmt} script section requires section_id")
            if section_id in section_ids:
                raise ValueError(f"Duplicate {fmt} script section_id: {section_id}")
            section_ids.append(section_id)
        section_ids_by_branch[fmt] = sorted(section_ids)
        branch_story_packages[fmt] = {
            "format": fmt,
            "title": branch_script.get("title"),
            "opening_hook": branch_script.get("opening_hook"),
            "opening_hook_mechanism": branch_script.get(
                "opening_hook_mechanism"
            ),
            "sections": sections,
            "closing": branch_script.get("closing"),
            "psychology_profile": branch_script.get("psychology_profile", {}),
        }

    constraints = {
        branch: dict(config["branch_constraints"][branch])
        for branch in required_branches
        if branch in config["branch_constraints"]
    }
    missing_constraints = sorted(set(required_branches) - set(constraints))
    if missing_constraints:
        raise ValueError(
            "Missing branch constraints for: " + ", ".join(missing_constraints)
        )

    return {
        "artifact": "format_request",
        "concept_id": concept_id,
        "format_intent": str(package.get("format_intent", "")).strip(),
        "required_branches": required_branches,
        "branch_constraints": constraints,
        "package": {
            "title": package.get("title"),
            "selected_titles": package.get("selected_titles", {}),
            "one_sentence_promise": package.get("one_sentence_promise"),
            "expected_payoff": package.get("expected_payoff"),
            "viewer_problem": package.get("viewer_problem"),
            "viewer_moment": package.get("viewer_moment"),
            "desired_outcome": package.get("desired_outcome"),
            "thumbnail": package.get("thumbnail", {}),
            "opening_frame": package.get("opening_frame", {}),
        },
        "branch_story_packages": branch_story_packages,
        "story_plan": script.get("story_plan", {}),
        "psychology_contract": script.get("psychology_contract", {}),
        "script_section_ids_by_branch": section_ids_by_branch,
        "accepted_claim_ids": sorted(set(claim_ids)),
        "accepted_claims": claims,
        "instructions": [
            "Plan production treatment for each already-approved script branch.",
            "Do not rewrite, shorten, combine or substitute the approved branch narration.",
            "Every production branch must use only section IDs from its matching approved script branch.",
            "Branches must not collapse into identical edits or a simple truncation of one production timeline.",
            "Every branch must deliver the approved package promise in its own shape.",
            "Attach accepted claim_ids to every beat carrying factual material.",
            "Do not introduce factual claims beyond the accepted claims supplied here.",
            "Respect duration and beat-count constraints for each branch.",
            "Preserve the accepted drama/tempo pulse in production treatment: every format beat must carry drama_level 4-10 and tempo_level 1-10.",
            "Drama and tempo are separate controls. Use rises and releases rather than a flat production rhythm, and reach the accepted concept drama target without inventing unsupported spectacle.",
            "Do not copy source-video wording, footage, story beats or execution.",
            "Do not claim virality or guaranteed performance.",
        ],
        "request_provenance": {
            "approved_script": str(script_path.resolve()),
            "approved_script_sha256": sha256_file(script_path),
            "section_review": section_review_provenance,
        },
    }


def _validate_branch(
    branch: dict[str, Any],
    index: int,
    request: dict[str, Any],
    errors: list[str],
) -> tuple[str, set[str]]:
    constraints_by_branch = request.get("branch_constraints", {})
    allowed_claims = set(request.get("accepted_claim_ids", []))

    fmt = str(branch.get("format", "")).strip()
    label = fmt or f"branch {index}"
    used: set[str] = set()

    if not fmt:
        errors.append(f"branch {index} requires format")
        return label, used

    section_ids_by_branch = request.get("script_section_ids_by_branch", {})
    allowed_sections = set(
        section_ids_by_branch.get(fmt, [])
        if isinstance(section_ids_by_branch, dict)
        else []
    )
    constraints = constraints_by_branch.get(fmt, {})

    duration = branch.get("duration_intent_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool):
        errors.append(f"{label} requires integer duration_intent_seconds")
    else:
        minimum = constraints.get("min_duration_seconds")
        maximum = constraints.get("max_duration_seconds")
        if isinstance(minimum, int) and duration < minimum:
            errors.append(f"{label} duration_intent_seconds below minimum {minimum}")
        if isinstance(maximum, int) and duration > maximum:
            errors.append(f"{label} duration_intent_seconds above maximum {maximum}")

    for field in ("promise_delivery", "payoff"):
        if not str(branch.get(field, "")).strip():
            errors.append(f"{label} requires {field}")

    beats = branch.get("beats")
    if not isinstance(beats, list) or not beats:
        errors.append(f"{label} requires a non-empty beats list")
        return label, used

    minimum_beats = constraints.get("min_beats")
    if isinstance(minimum_beats, int) and len(beats) < minimum_beats:
        errors.append(f"{label} requires at least {minimum_beats} beats")

    seen: set[str] = set()
    drama_levels: list[int] = []
    tempo_levels: list[int] = []
    for beat_index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"{label} beat {beat_index} must be an object")
            continue
        beat_id = str(beat.get("beat_id", "")).strip()
        beat_label = f"{label}.{beat_id or beat_index}"
        if not beat_id:
            errors.append(f"{label} beat {beat_index} requires beat_id")
        elif beat_id in seen:
            errors.append(f"{label} duplicate beat_id: {beat_id}")
        seen.add(beat_id)

        for field in ("purpose", "treatment"):
            if not str(beat.get(field, "")).strip():
                errors.append(f"{beat_label} requires {field}")

        drama_level = beat.get("drama_level")
        if (
            not isinstance(drama_level, int)
            or isinstance(drama_level, bool)
            or not 4 <= drama_level <= 10
        ):
            errors.append(f"{beat_label} drama_level must be an integer from 4-10")
        else:
            drama_levels.append(drama_level)

        tempo_level = beat.get("tempo_level")
        if (
            not isinstance(tempo_level, int)
            or isinstance(tempo_level, bool)
            or not 1 <= tempo_level <= 10
        ):
            errors.append(f"{beat_label} tempo_level must be an integer from 1-10")
        else:
            tempo_levels.append(tempo_level)

        claim_ids = beat.get("claim_ids")
        if not isinstance(claim_ids, list):
            errors.append(f"{beat_label} claim_ids must be a list")
        else:
            for claim_id in claim_ids:
                normalized_claim_id = str(claim_id)
                if normalized_claim_id not in allowed_claims:
                    errors.append(
                        f"{beat_label} uses unapproved claim_id {normalized_claim_id}"
                    )
                else:
                    used.add(normalized_claim_id)

        source_ids = beat.get("source_section_ids")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"{beat_label} requires source_section_ids")
        else:
            for source_id in source_ids:
                normalized_source_id = str(source_id)
                if normalized_source_id not in allowed_sections:
                    errors.append(
                        f"{beat_label} references unknown script section "
                        f"{normalized_source_id}"
                    )

    if not used:
        errors.append(f"{label} requires at least one beat carrying an accepted claim")

    if len(drama_levels) == len(beats):
        if len(set(drama_levels)) < 2:
            errors.append(
                f"{label} drama_level must pulse; a flat drama curve is not allowed"
            )
        contract = request.get("psychology_contract", {})
        framing = (
            contract.get("human_framing", {})
            if isinstance(contract, dict)
            else {}
        )
        drama = framing.get("drama", {}) if isinstance(framing, dict) else {}
        target = drama.get("target") if isinstance(drama, dict) else None
        if isinstance(target, int) and not isinstance(target, bool):
            if max(drama_levels) < target:
                errors.append(f"{label} never reaches the accepted drama target")

    if len(tempo_levels) == len(beats) and len(set(tempo_levels)) < 2:
        errors.append(
            f"{label} tempo_level must change; a flat tempo curve is not allowed"
        )

    return label, used

def _check_branch_separation(
    branches: list[dict[str, Any]], errors: list[str]
) -> dict[str, Any]:
    """Long-form and Shorts must be separate productions, not one timeline."""
    shapes = {
        str(branch.get("format", "")).strip(): branch_shape(branch)
        for branch in branches
        if isinstance(branch, dict) and str(branch.get("format", "")).strip()
    }
    names = sorted(shapes)
    separation = {"compared": names, "identical": False, "truncation": False}
    for position, first in enumerate(names):
        for second in names[position + 1 :]:
            left = shapes[first]
            right = shapes[second]
            if not left or not right:
                continue
            if left == right:
                separation["identical"] = True
                errors.append(
                    f"{first} and {second} are identical edits of the same timeline"
                )
                continue
            shorter, longer = (left, right) if len(left) < len(right) else (right, left)
            if shorter and longer[: len(shorter)] == shorter:
                separation["truncation"] = True
                errors.append(
                    f"{first} and {second} differ only by truncation of one timeline"
                )
    return separation


def validate_format_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []

    if str(response.get("concept_id", "")) != str(request.get("concept_id", "")):
        errors.append("concept_id mismatch")

    branches = response.get("branches")
    if not isinstance(branches, list) or not branches:
        errors.append("branches must be a non-empty list")
        branches = []

    required = list(request.get("required_branches", []))
    supplied = [
        str(branch.get("format", "")).strip()
        for branch in branches
        if isinstance(branch, dict)
    ]
    duplicates = sorted({fmt for fmt in supplied if supplied.count(fmt) > 1 and fmt})
    for fmt in duplicates:
        errors.append(f"duplicate branch: {fmt}")
    for fmt in sorted(set(required) - set(supplied)):
        errors.append(f"missing required branch: {fmt}")
    for fmt in sorted(set(supplied) - set(required)):
        if fmt:
            errors.append(f"unrequested branch: {fmt}")

    usage: dict[str, list[str]] = {}
    for index, branch in enumerate(branches):
        if not isinstance(branch, dict):
            errors.append(f"branch {index} must be an object")
            continue
        label, used = _validate_branch(branch, index, request, errors)
        usage[label] = sorted(used)

    separation = _check_branch_separation(
        [branch for branch in branches if isinstance(branch, dict)], errors
    )

    texts: list[dict[str, Any]] = []
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        fmt = str(branch.get("format", "")).strip() or "branch"
        texts.append(
            {"field": f"{fmt}.promise_delivery", "text": branch.get("promise_delivery")}
        )
        texts.append({"field": f"{fmt}.payoff", "text": branch.get("payoff")})
        beats = branch.get("beats")
        if isinstance(beats, list):
            for beat_index, beat in enumerate(beats):
                if isinstance(beat, dict):
                    texts.append(
                        {
                            "field": f"{fmt}.beat.{beat_index}",
                            "text": beat.get("treatment"),
                        }
                    )
    normalized_texts: list[dict[str, str]] = [
        {
            "field": str(item.get("field") or ""),
            "text": str(item.get("text") or ""),
        }
        for item in texts
    ]
    overlap = check_texts(normalized_texts)
    if overlap.get("blocking"):
        match = overlap.get("matches", [{}])[0]
        errors.append("source overlap block: " + str(match.get("overlap_text") or ""))

    all_used = {claim for claims in usage.values() for claim in claims}
    allowed = set(request.get("accepted_claim_ids", []))
    return {
        "valid": not errors,
        "errors": errors,
        "claim_usage_by_branch": usage,
        "claim_usage": sorted(all_used),
        "unused_accepted_claim_ids": sorted(allowed - all_used),
        "branch_separation": separation,
        "source_overlap": overlap,
    }


def run_prepare(
    approved_dir: Path = APPROVED_SCRIPTS_DIR,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    previous_request_hashes = _existing_request_hashes(REQUESTS_DIR)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(approved_dir.glob("*.approved_script.json"))
        if approved_dir.exists()
        else []
    )
    prepared = []
    failures = []
    pending: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            request = build_format_request(load_json(path), path, config)
            pending.append((path, request))
        except Exception as exc:
            failures.append({"script": str(path), "error_type": type(exc).__name__})

    assert_unique_slug_ids(
        [str(request["concept_id"]) for _, request in pending],
        label="concept",
    )

    current_destinations: set[Path] = set()
    for _, request in pending:
        dest = (
            REQUESTS_DIR / f"{safe_slug(request['concept_id'])}.format_request.json"
        )
        dest.write_text(
            json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        current_destinations.add(dest.resolve())
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "required_branches": request["required_branches"],
                "request": str(dest),
            }
        )

    for stale_path in REQUESTS_DIR.glob("*.format_request.json"):
        if stale_path.resolve() not in current_destinations:
            stale_path.unlink()

    current_request_hashes = _existing_request_hashes(REQUESTS_DIR)
    cleanup = _prune_invalidated_format_outputs(
        previous_request_hashes,
        current_request_hashes,
    )
    cleanup["active_provenance_cleanup"] = (
        _prune_mismatched_active_format_outputs(
            current_request_hashes,
        )
    )
    summary = {
        "status": (
            "FORMAT_REQUESTS_READY" if prepared else "WAITING_FOR_APPROVED_SCRIPTS"
        ),
        "approved_scripts_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REQUESTS_DIR),
        "stale_cleanup": cleanup,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Engine")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.add_argument("--approved-dir", type=Path, default=APPROVED_SCRIPTS_DIR)
    args = parser.parse_args()
    result = run_prepare(args.approved_dir.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
