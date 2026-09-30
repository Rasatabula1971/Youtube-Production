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
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "format_requests"
RESPONSES_DIR = OUTPUT_DIR / "format_responses"
PLANS_DIR = OUTPUT_DIR / "format_plans"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"

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
        if str(branch_script.get("title") or "") != approved_title:
            raise ValueError(f"Approved {fmt} script violates Packaging title")
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
        if len(drama_levels) == len(beats):
        if len(set(drama_levels)) < 2:
            errors.append(f"{label} drama_level must pulse; a flat drama curve is not allowed")
        contract = request.get("psychology_contract", {})
        framing = contract.get("human_framing", {}) if isinstance(contract, dict) else {}
        drama = framing.get("drama", {}) if isinstance(framing, dict) else {}
        target = drama.get("target") if isinstance(drama, dict) else None
        if isinstance(target, int) and not isinstance(target, bool):
            if max(drama_levels) < target:
                errors.append(f"{label} never reaches the accepted drama target")

    if len(tempo_levels) == len(beats) and len(set(tempo_levels)) < 2:
        errors.append(f"{label} tempo_level must change; a flat tempo curve is not allowed")

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
    summary = {
        "status": (
            "FORMAT_REQUESTS_READY" if prepared else "WAITING_FOR_APPROVED_SCRIPTS"
        ),
        "approved_scripts_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REQUESTS_DIR),
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
