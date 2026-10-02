"""Slice 24 Packaging Brief + Viewer Promise Contract.

Builds one rebuild-current brief per approved concept/format after the Human
Title Direction Gate. The brief is deterministic: it projects only human-
approved concept, research, script and title-direction data. It never calls a
model and never invents facts.

The successful Slice 24 boundary is PACKAGING_BRIEF_READY. Thumbnail concepts,
pairing, package scoring and final packaging approval remain later slices.
"""

from __future__ import annotations

import argparse
import json
import re
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
from title_direction_review import (
    APPROVED_FILE as TITLE_SELECTION_FILE,
    snapshot as title_direction_snapshot,
)
from story_script_engine import safe_slug, sha256_file
from script_review import (
    APPROVED_DIR as APPROVED_SCRIPTS_DIR,
    _approved_bundle_is_current,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
BRIEF_DIR = OUTPUT_DIR / "packaging_briefs"
SUMMARY_FILE = OUTPUT_DIR / "packaging_brief_summary.json"

RESEARCH_OUTPUT = _ROOT / "research_engine" / "output"
VERIFIED_RESEARCH_DIR = RESEARCH_OUTPUT / "verified_packages"
REVIEWED_RESEARCH_DIR = RESEARCH_OUTPUT / "reviewed_packages"

SCHEMA_VERSION = "1.0"
PROMISE_VERSION = "viewer-promise-v1.0"
SEARCH_INTENTS = {"SEARCH", "BROWSE", "HYBRID"}
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[$£€]?\d+(?:[.,]\d+)*(?:\s?%|\s?[xX])?)(?![A-Za-z0-9])"
)


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _require_text(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _selection_by_concept() -> dict[str, dict[str, Any]]:
    gate = title_direction_snapshot()
    if (
        gate.get("status") != "TITLE_DIRECTION_SELECTED"
        or not gate.get("ready")
        or not TITLE_SELECTION_FILE.is_file()
    ):
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    payload = load_json(TITLE_SELECTION_FILE)
    if (
        not isinstance(payload, dict)
        or payload.get("artifact") != "selected_title_directions"
        or payload.get("status") != "TITLE_DIRECTION_SELECTED"
    ):
        raise ValueError("INVALID_SELECTED_TITLE_DIRECTION")
    values = payload.get("selected", [])
    if not isinstance(values, list) or not values:
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    out: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("INVALID_SELECTED_TITLE_DIRECTION")
        cid = _require_text(item.get("concept_id"), "INVALID_SELECTED_TITLE_DIRECTION")
        if cid in out:
            raise ValueError("DUPLICATE_SELECTED_TITLE_DIRECTION")
        if item.get("decision") != "ACCEPT":
            raise ValueError("INVALID_SELECTED_TITLE_DIRECTION")
        out[cid] = item
    return out


def _claim_map(claims: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(claims, list) or not claims:
        raise ValueError("MISSING_EVIDENCE")
    out: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("MISSING_EVIDENCE")
        cid = _require_text(claim.get("claim_id"), "MISSING_EVIDENCE")
        statement = _require_text(claim.get("statement"), "MISSING_EVIDENCE")
        if cid in out:
            raise ValueError("DUPLICATE_EVIDENCE_ID")
        out[cid] = {**claim, "claim_id": cid, "statement": statement}
    return out


def _verified_research(concept_id: str, script_claims: Any) -> tuple[Path, dict[str, Any]]:
    path = VERIFIED_RESEARCH_DIR / f"{safe_slug(concept_id)}.verified_research_package.json"
    payload = load_json(path)
    if (
        payload.get("artifact") != "verified_research_package"
        or payload.get("status") != "READY_FOR_STORY_SCRIPT"
        or str(payload.get("concept_id") or "") != concept_id
    ):
        raise ValueError("MISSING_EVIDENCE")
    research_claims = _claim_map(payload.get("claims"))
    approved = _claim_map(script_claims)
    if set(research_claims) != set(approved):
        raise ValueError("EVIDENCE_CONFLICT")
    for cid in sorted(approved):
        if research_claims[cid]["statement"] != approved[cid]["statement"]:
            raise ValueError("EVIDENCE_CONFLICT")
    sources = payload.get("sources", [])
    if not isinstance(sources, list) or not sources:
        raise ValueError("MISSING_EVIDENCE")
    return path, payload


def _unsupported_claims(concept_id: str) -> tuple[Path | None, list[dict[str, Any]]]:
    path = REVIEWED_RESEARCH_DIR / f"{safe_slug(concept_id)}.research_gate_reviewed.json"
    if not path.is_file():
        return None, []
    payload = load_json(path)
    if (
        payload.get("artifact") != "research_gate_reviewed"
        or str(payload.get("concept_id") or "") != concept_id
    ):
        raise ValueError("EVIDENCE_CONFLICT")
    values: list[dict[str, Any]] = []
    for bucket, status in (("rework", "REWORK"), ("rejected", "REJECTED")):
        claims = payload.get(bucket, [])
        if not isinstance(claims, list):
            raise ValueError("EVIDENCE_CONFLICT")
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            statement = str(claim.get("statement") or "").strip()
            if statement:
                values.append(
                    {
                        "claim_id": claim.get("claim_id"),
                        "claim": statement,
                        "status": status,
                        "reason": (
                            claim.get("research_gate", {}).get("note", "")
                            if isinstance(claim.get("research_gate"), dict)
                            else ""
                        ),
                    }
                )
    return path, values


def _approved_numbers(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for claim in claims:
        statement = str(claim.get("statement") or "")
        for match in NUMBER_RE.findall(statement):
            key = (str(claim.get("claim_id") or ""), match)
            if key in seen:
                continue
            seen.add(key)
            values.append(
                {
                    "value": match,
                    "claim_id": claim.get("claim_id"),
                    "statement": statement,
                }
            )
    return values


def _strongest_fact(claims: list[dict[str, Any]]) -> dict[str, Any]:
    claim = next(
        (
            item
            for item in claims
            if str(item.get("role") or "").strip().lower() == "core"
        ),
        claims[0] if claims else None,
    )
    if not isinstance(claim, dict):
        raise ValueError("MISSING_EVIDENCE")
    return {
        "claim_id": claim.get("claim_id"),
        "statement": claim.get("statement"),
        "role": claim.get("role"),
    }


def _target_audience(bundle: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    channel_voice = bundle.get("channel_voice", {})
    profile = (
        channel_voice.get("profile", {})
        if isinstance(channel_voice, dict)
        else {}
    )
    audience = profile.get("audience", {}) if isinstance(profile, dict) else {}
    if not isinstance(audience, dict):
        audience = {}
    return {
        "channel_audience": audience,
        "viewer_problem": concept.get("viewer_problem"),
        "viewer_moment": concept.get("viewer_moment"),
        "desired_outcome": concept.get("desired_outcome"),
    }


def _selected_for_format(selection: dict[str, Any], fmt: str) -> dict[str, Any]:
    selected = selection.get("selected_titles", {})
    if not isinstance(selected, dict):
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    item = selected.get(fmt)
    if not isinstance(item, dict):
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    intent = str(item.get("search_intent") or "").strip().upper()
    if intent not in SEARCH_INTENTS:
        raise ValueError("INVALID_SEARCH_BROWSE_INTENT")
    evidence_refs = item.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        raise ValueError("INVALID_SELECTED_TITLE_DIRECTION")
    return {
        **item,
        "search_intent": intent,
        "evidence_refs": [str(x) for x in evidence_refs],
    }


def build_brief(
    *,
    script_path: Path,
    bundle: dict[str, Any],
    selection: dict[str, Any],
    fmt: str,
) -> dict[str, Any]:
    concept_id = _require_text(bundle.get("concept_id"), "MISSING_APPROVED_SCRIPT")
    if not _approved_bundle_is_current(concept_id):
        raise ValueError("MISSING_APPROVED_SCRIPT")
    canonical = APPROVED_SCRIPTS_DIR / f"{safe_slug(concept_id)}.approved_script.json"
    if script_path.resolve() != canonical.resolve():
        raise ValueError("MISSING_APPROVED_SCRIPT")

    branches = bundle.get("branch_scripts", {})
    if not isinstance(branches, dict):
        raise ValueError("MISSING_APPROVED_SCRIPT")
    branch = branches.get(fmt)
    if not isinstance(branch, dict):
        raise ValueError("MISSING_APPROVED_SCRIPT")
    opening_hook = _require_text(branch.get("opening_hook"), "MISSING_OPENING_HOOK")
    sections = branch.get("sections", [])
    if not isinstance(sections, list) or not sections:
        raise ValueError("MISSING_APPROVED_SCRIPT_SECTIONS")

    research_path, research = _verified_research(
        concept_id, bundle.get("accepted_claims")
    )
    concept = research.get("concept", {})
    if not isinstance(concept, dict):
        raise ValueError("INVALID_PACKAGING_BRIEF")
    human_framing = concept.get("human_framing", {})
    if not isinstance(human_framing, dict):
        raise ValueError("INVALID_PACKAGING_BRIEF")
    psychological_pull = human_framing.get("psychological_pull", {})
    visual_plan = human_framing.get("visual_opening_plan", {})
    if not isinstance(psychological_pull, dict) or not isinstance(visual_plan, dict):
        raise ValueError("INVALID_PACKAGING_BRIEF")
    moments = visual_plan.get("moments", [])
    if not isinstance(moments, list) or not moments or not isinstance(moments[0], dict):
        raise ValueError("INVALID_PACKAGING_BRIEF")

    story_plan = bundle.get("story_plan", {})
    if not isinstance(story_plan, dict):
        raise ValueError("MISSING_APPROVED_SCRIPT")
    central_question = _require_text(
        story_plan.get("story_question")
        or human_framing.get("viewer_question"),
        "INVALID_PACKAGING_BRIEF",
    )
    video_payoff = _require_text(
        story_plan.get("payoff_intent")
        or human_framing.get("explanation_payoff")
        or concept.get("desired_outcome"),
        "INVALID_PACKAGING_BRIEF",
    )

    selected = _selected_for_format(selection, fmt)
    title_text = _require_text(
        selected.get("selected_title_text"),
        "MISSING_SELECTED_TITLE_DIRECTION",
    )

    claims = list(_claim_map(bundle.get("accepted_claims")).values())
    allowed_refs = {str(item.get("claim_id")) for item in claims}
    unknown_refs = sorted(set(selected["evidence_refs"]) - allowed_refs)
    if unknown_refs:
        raise ValueError("UNSUPPORTED_CLAIM")

    reviewed_path, prohibited = _unsupported_claims(concept_id)
    source_evidence = []
    for source in research.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "").strip()
        if source_id:
            source_evidence.append(
                {
                    "source_id": source_id,
                    "title": source.get("title"),
                    "publisher": source.get("publisher"),
                    "source_type": source.get("source_type"),
                    "url": source.get("url"),
                }
            )
    if not source_evidence:
        raise ValueError("MISSING_EVIDENCE")

    strongest_visual = _require_text(
        moments[0].get("visual"), "INVALID_PACKAGING_BRIEF"
    )
    stakes = _require_text(
        psychological_pull.get("stakes"), "INVALID_PACKAGING_BRIEF"
    )
    transformation = _require_text(
        psychological_pull.get("desired_resolution")
        or concept.get("desired_outcome"),
        "INVALID_PACKAGING_BRIEF",
    )
    promise_subject = _require_text(
        concept.get("viewer_problem") or concept.get("premise"),
        "INVALID_PACKAGING_BRIEF",
    )

    viewer_expectation = (
        "A viewer clicking this package expects to discover "
        + central_question.rstrip("?.")
        + " and reach this payoff: "
        + video_payoff.rstrip(".")
        + "."
    )
    promise = {
        "viewer_expectation": viewer_expectation,
        "promise_subject": promise_subject,
        "promise_question": central_question,
        "promise_stakes": stakes,
        "promise_payoff": video_payoff,
    }

    return {
        "artifact": "packaging_brief",
        "schema_version": SCHEMA_VERSION,
        "status": "PACKAGING_BRIEF_READY",
        "video_id": f"{concept_id}:{fmt}",
        "video_id_namespace": "PIPELINE_INTERNAL_PRE_PUBLISH",
        "concept_id": concept_id,
        "format": fmt,
        "source_evidence": source_evidence,
        "approved_concept": concept,
        "approved_script": {
            "working_title": branch.get("title"),
            "opening_hook": opening_hook,
            "opening_hook_mechanism": branch.get("opening_hook_mechanism"),
            "closing": branch.get("closing"),
        },
        "approved_script_sections": sections,
        "opening_hook": opening_hook,
        "central_question": central_question,
        "video_payoff": video_payoff,
        "selected_title": {
            "title_id": selected.get("selected_title_id"),
            "title_text": title_text,
            "psychological_angle": selected.get("selected_psychological_angle"),
            "primary_driver": selected.get("selected_primary_driver"),
            "secondary_driver": selected.get("selected_secondary_driver"),
            "core_claim": selected.get("core_claim"),
            "evidence_refs": selected.get("evidence_refs", []),
            "wording_edited": bool(selected.get("wording_edited")),
        },
        "selected_title_angle": selected.get("selected_psychological_angle"),
        "target_audience": _target_audience(bundle, concept),
        "search_vs_browse_intent": selected["search_intent"],
        "approved_claims": claims,
        "approved_numbers": _approved_numbers(claims),
        "strongest_visual_event": strongest_visual,
        "strongest_fact": _strongest_fact(claims),
        "strongest_consequence": stakes,
        "strongest_transformation": transformation,
        "prohibited_or_unsupported_claims": prohibited,
        "viewer_promise_contract": promise,
        "generation_policy": {
            "deterministic_projection_only": True,
            "model_calls": 0,
            "facts_may_be_invented": False,
            "thumbnail_generation_allowed": False,
            "package_scoring_allowed": False,
            "final_packaging_approval_allowed": False,
        },
        "provenance": {
            "approved_script": str(script_path.resolve()),
            "approved_script_sha256": sha256_file(script_path),
            "selected_title_directions": str(TITLE_SELECTION_FILE.resolve()),
            "selected_title_directions_sha256": sha256_file(TITLE_SELECTION_FILE),
            "verified_research": str(research_path.resolve()),
            "verified_research_sha256": sha256_file(research_path),
            "reviewed_research": (
                str(reviewed_path.resolve()) if reviewed_path is not None else None
            ),
            "reviewed_research_sha256": (
                sha256_file(reviewed_path) if reviewed_path is not None else None
            ),
            "promise_version": PROMISE_VERSION,
        },
    }


def brief_is_current(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.parent.resolve() != BRIEF_DIR.resolve():
        return None
    try:
        brief = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(brief, dict)
        or brief.get("artifact") != "packaging_brief"
        or brief.get("status") != "PACKAGING_BRIEF_READY"
    ):
        return None
    concept_id = str(brief.get("concept_id") or "")
    fmt = str(brief.get("format") or "")
    prov = brief.get("provenance", {})
    if not concept_id or fmt not in {"short", "long_form"} or not isinstance(prov, dict):
        return None
    script_path = Path(str(prov.get("approved_script") or ""))
    if (
        not script_path.is_file()
        or prov.get("approved_script_sha256") != sha256_file(script_path)
    ):
        return None
    try:
        bundle = load_json(script_path)
        selections = _selection_by_concept()
        selection = selections.get(concept_id)
        if not isinstance(selection, dict):
            return None
        rebuilt = build_brief(
            script_path=script_path,
            bundle=bundle,
            selection=selection,
            fmt=fmt,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return brief if rebuilt == brief else None


def snapshot() -> dict[str, Any]:
    current: list[dict[str, Any]] = []
    stale = 0
    if BRIEF_DIR.exists():
        for path in sorted(BRIEF_DIR.glob("*.packaging_brief.json")):
            brief = brief_is_current(path)
            if brief is None:
                stale += 1
                continue
            current.append(
                {
                    "concept_id": brief.get("concept_id"),
                    "format": brief.get("format"),
                    "video_id": brief.get("video_id"),
                    "search_vs_browse_intent": brief.get("search_vs_browse_intent"),
                    "viewer_expectation": (
                        brief.get("viewer_promise_contract", {}).get(
                            "viewer_expectation"
                        )
                        if isinstance(brief.get("viewer_promise_contract"), dict)
                        else None
                    ),
                    "brief_file": str(path.resolve()),
                    "brief_sha256": sha256_file(path),
                }
            )
    gate = title_direction_snapshot()
    expected = 0
    if gate.get("status") == "TITLE_DIRECTION_SELECTED":
        for item in gate.get("concepts", []):
            if isinstance(item, dict) and item.get("decision") == "ACCEPT":
                expected += 2
    ready = expected > 0 and len(current) == expected and stale == 0
    return {
        "status": (
            "PACKAGING_BRIEF_READY"
            if ready
            else "PACKAGING_BRIEF_STALE"
            if stale
            else "WAITING_FOR_PACKAGING_BRIEF"
        ),
        "ready": ready,
        "expected": expected,
        "current": len(current),
        "stale": stale,
        "briefs": current,
    }


def prepare() -> dict[str, Any]:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    selections = _selection_by_concept()
    current_paths: set[Path] = set()
    built: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for concept_id, selection in sorted(selections.items()):
        script_path = APPROVED_SCRIPTS_DIR / (
            f"{safe_slug(concept_id)}.approved_script.json"
        )
        try:
            bundle = load_json(script_path)
            required = bundle.get("required_branches", [])
            if not isinstance(required, list) or not required:
                raise ValueError("MISSING_APPROVED_SCRIPT")
            for fmt in sorted(str(x) for x in required):
                if fmt not in {"short", "long_form"}:
                    raise ValueError("INVALID_PACKAGING_BRIEF")
                brief = build_brief(
                    script_path=script_path,
                    bundle=bundle,
                    selection=selection,
                    fmt=fmt,
                )
                destination = BRIEF_DIR / (
                    f"{safe_slug(concept_id)}.{safe_slug(fmt)}.packaging_brief.json"
                )
                atomic_write_json(destination, brief)
                current_paths.add(destination.resolve())
                built.append(
                    {
                        "concept_id": concept_id,
                        "format": fmt,
                        "brief_file": str(destination.resolve()),
                        "brief_sha256": sha256_file(destination),
                    }
                )
        except Exception as exc:
            failures.append(
                {
                    "concept_id": concept_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale_path in BRIEF_DIR.glob("*.packaging_brief.json"):
        if stale_path.resolve() not in current_paths:
            stale_path.unlink()

    result = {
        "status": (
            "PACKAGING_BRIEF_READY"
            if built and not failures
            else "PARTIAL"
            if built
            else "FAILED"
            if failures
            else "WAITING_FOR_SELECTED_TITLE_DIRECTION"
        ),
        "built": len(built),
        "failed": len(failures),
        "items": built,
        "failures": failures,
        "model_calls": 0,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build deterministic post-script Packaging Briefs"
    )
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    payload = prepare() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("status") in {"FAILED", "PARTIAL"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
