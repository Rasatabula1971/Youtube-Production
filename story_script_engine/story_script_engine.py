"""Story / Script Engine.

Consumes human-verified research packages and prepares bounded script requests.
Only accepted research claims may be referenced as factual support.
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
RESEARCH_VERIFIED_DIR = (
    PROJECT_ROOT / "research_engine" / "output" / "verified_packages"
)
OUTPUT_DIR = HERE / "output"
STORY_PLANS_DIR = OUTPUT_DIR / "story_plans"
REQUESTS_DIR = OUTPUT_DIR / "script_requests"
RESPONSES_DIR = OUTPUT_DIR / "script_responses"
DRAFTS_DIR = OUTPUT_DIR / "script_drafts"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


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


def validation_contract_sha256() -> str:
    """Fingerprint deterministic Script acceptance and overlap rules."""
    digest = hashlib.sha256()
    for path in (
        Path(__file__).resolve(),
        (PROJECT_ROOT / "source_overlap.py").resolve(),
    ):
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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


def build_script_request(plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    if plan.get("status") != "STORY_PLAN_READY":
        raise ValueError("Story Plan is not STORY_PLAN_READY")

    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Story Plan requires concept_id")

    package = plan.get("package", {})
    if not isinstance(package, dict):
        raise ValueError("Story Plan package must be an object")
    title = str(package.get("title") or "").strip()
    if not title:
        raise ValueError("Story Plan requires the approved Packaging title")
    if str(plan.get("title", "")) != title:
        raise ValueError("Story Plan title must match the approved Packaging title")

    concept = plan.get("concept", {})
    if not isinstance(concept, dict):
        concept = {}

    psychology_contract = plan.get("psychology_contract")
    if not isinstance(psychology_contract, dict) or not psychology_contract:
        raise ValueError("Story Plan requires the audience psychology contract")

    viewer_state = plan.get("viewer_state")
    if not isinstance(viewer_state, dict):
        raise ValueError("Story Plan requires viewer_state")

    opening_psychology = plan.get("opening_psychology")
    if not isinstance(opening_psychology, dict):
        raise ValueError("Story Plan requires opening_psychology")

    claims = plan.get("accepted_claims", [])
    if not isinstance(claims, list) or not claims:
        raise ValueError("Script requires accepted research claims")

    claim_ids: list[str] = []
    accepted: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Every accepted claim must be an object")
        claim_id = str(claim.get("claim_id", "")).strip()
        statement = str(claim.get("statement", "")).strip()
        if not claim_id or not statement:
            raise ValueError("Every accepted claim requires claim_id and statement")
        claim_ids.append(claim_id)
        accepted.append(dict(claim))

    beats = plan.get("beats", [])
    if not isinstance(beats, list) or not beats:
        raise ValueError("Story Plan requires story beats before script drafting")
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict) or not isinstance(beat.get("psychology"), dict):
            raise ValueError(f"Story Plan beat {index} requires psychology metadata")

    return {
        "artifact": "script_request",
        "concept_id": concept_id,
        "package": package,
        "concept": concept,
        "psychology_contract": psychology_contract,
        "story_plan": {
            "title": plan.get("title"),
            "story_question": plan.get("story_question"),
            "opening_hook_intent": plan.get("opening_hook_intent"),
            "viewer_state": viewer_state,
            "opening_psychology": opening_psychology,
            "beats": beats,
            "payoff_intent": plan.get("payoff_intent"),
            "closing_intent": plan.get("closing_intent"),
        },
        "accepted_claim_ids": sorted(set(claim_ids)),
        "accepted_claims": accepted,
        "instructions": [
            "Write the narration from the approved Story Plan rather than inventing a new structure.",
            "Return the approved Packaging title exactly; do not rewrite or optimize it.",
            "The opening_hook is the first spoken line. Make it high-impact using the planned opening psychology mechanism.",
            "A high-impact hook may create contradiction, surprise, stakes, expectation violation, specific curiosity, or a bold promise; it may not exaggerate beyond verified research.",
            "Immediately justify, contextualize, or begin proving the opening hook rather than leaving unsupported drama hanging.",
            "Do not copy or closely paraphrase source-video wording.",
            "Do not introduce factual claims beyond the accepted research claims supplied here.",
            "Every scripted section must map to exactly one story beat using story_beat_id.",
            "Each section must use the same factual claim_ids assigned to that story beat.",
            "Each section must preserve the Story Plan beat's primary psychology mechanism.",
            "Use the beat cognitive-load instruction to keep the explanation easy to follow; avoid stacking unrelated new ideas into one beat.",
            "Preserve planned open-loop OPEN, ADVANCE and PAYOFF behavior. Do not create fake unresolved loops.",
            "Connective narration, transitions, questions and framing may be original but must not add unsupported facts.",
            "Preserve the planned viewer journey, reveal/payoff and closing intent.",
            "Do not use arbitrary fixed hook-second or pattern-interrupt timing rules.",
            "Do not claim virality, guaranteed performance or facts not present in accepted_claims.",
        ],
        "request_provenance": {
            "story_plan": str(plan_path.resolve()),
            "story_plan_sha256": sha256_file(plan_path),
        },
    }


def validate_script_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    if str(response.get("concept_id", "")) != str(request.get("concept_id", "")):
        errors.append("concept_id mismatch")

    approved_title = str(request.get("package", {}).get("title") or "")
    if str(response.get("title", "")) != approved_title:
        errors.append("title must exactly match the approved Packaging title")

    if not str(response.get("opening_hook", "")).strip():
        errors.append("opening_hook is required")
    if not str(response.get("closing", "")).strip():
        errors.append("closing is required")

    story_plan = request.get("story_plan", {})
    if not isinstance(story_plan, dict):
        errors.append("request Story Plan is missing")
        story_plan = {}

    opening_psychology = story_plan.get("opening_psychology", {})
    if not isinstance(opening_psychology, dict):
        opening_psychology = {}
    planned_hook_mechanism = str(
        opening_psychology.get("mechanism", "")
    ).strip().upper()
    actual_hook_mechanism = str(
        response.get("opening_hook_mechanism", "")
    ).strip().upper()
    if not actual_hook_mechanism:
        errors.append("opening_hook_mechanism is required")
    elif actual_hook_mechanism != planned_hook_mechanism:
        errors.append(
            "opening_hook_mechanism must match Story Plan opening psychology"
        )

    sections = response.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        sections = []

    story_beats = story_plan.get("beats", [])
    if not isinstance(story_beats, list) or not story_beats:
        errors.append("request Story Plan beats are missing")
        story_beats = []

    beat_claims: dict[str, set[str]] = {}
    beat_psychology: dict[str, str] = {}
    for beat in story_beats:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id", "")).strip()
        if not beat_id:
            continue
        ids = beat.get("claim_ids", [])
        beat_claims[beat_id] = (
            {str(item) for item in ids}
            if isinstance(ids, list)
            else set()
        )
        psychology = beat.get("psychology", {})
        if isinstance(psychology, dict):
            beat_psychology[beat_id] = str(
                psychology.get("primary_mechanism", "")
            ).strip().upper()

    if story_beats and len(sections) != len(story_beats):
        errors.append("script must contain exactly one section per Story Plan beat")

    allowed = set(request.get("accepted_claim_ids", []))
    used: set[str] = set()
    seen_sections: set[str] = set()
    seen_beats: set[str] = set()

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"section {index} must be an object")
            continue

        sid = str(section.get("section_id", "")).strip()
        if not sid:
            errors.append(f"section {index} requires section_id")
        elif sid in seen_sections:
            errors.append(f"duplicate section_id: {sid}")
        seen_sections.add(sid)

        beat_id = str(section.get("story_beat_id", "")).strip()
        if not beat_id:
            errors.append(f"{sid or index} requires story_beat_id")
        elif beat_id not in beat_claims:
            errors.append(f"{sid or index} references unknown story_beat_id {beat_id}")
        elif beat_id in seen_beats:
            errors.append(f"duplicate story_beat_id mapping: {beat_id}")
        seen_beats.add(beat_id)

        if not str(section.get("purpose", "")).strip():
            errors.append(f"{sid or index} requires purpose")
        if not str(section.get("narration", "")).strip():
            errors.append(f"{sid or index} requires narration")

        actual_psychology = str(
            section.get("psychology_mechanism", "")
        ).strip().upper()
        planned_psychology = beat_psychology.get(beat_id, "")
        if not actual_psychology:
            errors.append(f"{sid or index} requires psychology_mechanism")
        elif actual_psychology != planned_psychology:
            errors.append(
                f"{sid or index} psychology_mechanism must match Story Plan beat {beat_id}"
            )

        ids = section.get("claim_ids")
        if not isinstance(ids, list):
            errors.append(f"{sid or index} claim_ids must be a list")
            continue

        normalized_ids = {str(cid) for cid in ids}
        for cid in normalized_ids:
            if cid not in allowed:
                errors.append(f"{sid or index} uses unapproved claim_id {cid}")
            else:
                used.add(cid)

        if beat_id in beat_claims and normalized_ids != beat_claims[beat_id]:
            errors.append(
                f"{sid or index} claim_ids must match Story Plan beat {beat_id}"
            )

    missing_beats = set(beat_claims) - seen_beats
    if missing_beats:
        errors.append(
            "script is missing Story Plan beat(s): "
            + ", ".join(sorted(missing_beats))
        )

    overlap = check_texts(
        [
            {"field": "title", "text": response.get("title", "")},
            {"field": "opening_hook", "text": response.get("opening_hook", "")},
            *[
                {"field": f"section.{index}", "text": section.get("narration", "")}
                for index, section in enumerate(sections)
                if isinstance(section, dict)
            ],
            {"field": "closing", "text": response.get("closing", "")},
        ]
    )
    if overlap.get("blocking"):
        match = overlap.get("matches", [{}])[0]
        errors.append("source overlap block: " + str(match.get("overlap_text") or ""))

    return {
        "valid": not errors,
        "errors": errors,
        "claim_usage": sorted(used),
        "unused_accepted_claim_ids": sorted(allowed - used),
        "source_overlap": overlap,
        "story_plan_beat_ids": sorted(beat_claims),
        "opening_hook_mechanism": actual_hook_mechanism,
        "psychology_mechanisms": sorted(set(beat_psychology.values())),
    }


def run_prepare(story_plans_dir: Path = STORY_PLANS_DIR) -> dict[str, Any]:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(story_plans_dir.glob("*.story_plan.json"))
        if story_plans_dir.exists()
        else []
    )

    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    pending: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            request = build_script_request(load_json(path), path)
            pending.append((path, request))
        except Exception as exc:
            failures.append(
                {
                    "story_plan": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    assert_unique_slug_ids(
        [str(request["concept_id"]) for _, request in pending],
        label="concept",
    )

    current_destinations: set[Path] = set()
    for _, request in pending:
        dest = (
            REQUESTS_DIR / f"{safe_slug(str(request['concept_id']))}.script_request.json"
        )
        dest.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        current_destinations.add(dest.resolve())
        prepared.append(
            {"concept_id": request["concept_id"], "request": str(dest)}
        )

    for stale_path in REQUESTS_DIR.glob("*.script_request.json"):
        if stale_path.resolve() not in current_destinations:
            stale_path.unlink()

    summary = {
        "status": (
            "SCRIPT_REQUESTS_READY" if prepared else "WAITING_FOR_STORY_PLANS"
        ),
        "story_plans_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REQUESTS_DIR),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Story / Script Engine")
    p.add_argument("--mode", choices=("prepare",), required=True)
    p.add_argument("--story-plans-dir", type=Path, default=STORY_PLANS_DIR)
    a = p.parse_args()
    print(
        json.dumps(
            run_prepare(a.story_plans_dir.resolve()),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
