"""Incremental UI controller for the human Research Gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import append_jsonl, atomic_write_json, read_jsonl

from evidence_policy import (
    AUTO_CLEARED,
    evaluate_claim,
    policy_fingerprint,
    policy_settings,
)
from research_gate import (
    DEFAULT_DRAFTS_DIR,
    HUMAN_REWORK_ORIGIN,
    POLICY_DECIDER,
    REVIEW_REQUESTS_DIR,
    REVIEWED_DIR,
    SUMMARY_FILE,
    VERIFIED_DIR,
    apply_gate,
    build_review_request,
    load_config,
    load_json,
    safe_slug,
)

OUTPUT_DIR = DEFAULT_DRAFTS_DIR.parent
STATE_FILE = OUTPUT_DIR / "research_gate_ui_state.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def history_file() -> Path:
    """Append-only log of every Research Gate decision (D-133)."""
    return STATE_FILE.parent / "research_gate_history.jsonl"


def record_history(event: dict[str, Any]) -> None:
    append_jsonl(
        history_file(),
        {"recorded_at": datetime.now(timezone.utc).isoformat(), "gate": "research", **event},
    )


def history_by_key() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in read_jsonl(history_file()):
        if event.get("concept_id") and event.get("claim_id"):
            grouped.setdefault(key_for(str(event["concept_id"]), str(event["claim_id"])), []).append(event)
    return grouped


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claim_fingerprint(item: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in item.items()
        if key not in {"decision", "criteria_decisions", "note"}
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preserved_decisions(
    requests: list[dict[str, Any]],
    previous: dict[str, Any],
) -> dict[str, Any]:
    prior = previous.get("decisions", {}) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict):
        return {}
    preserved: dict[str, Any] = {}
    for bundle in requests:
        concept_id = bundle["concept_id"]
        for item in bundle["request"].get("items", []):
            claim_id = str(item.get("claim_id") or "")
            key = key_for(concept_id, claim_id)
            saved = prior.get(key)
            if not isinstance(saved, dict):
                carried = item.get("carried_from_review")
                if isinstance(carried, dict):
                    # Unchanged claim a human already accepted before a rework.
                    preserved[key] = {
                        "claim_id": claim_id,
                        "decision": "ACCEPT",
                        "criteria": {
                            criterion: True
                            for criterion in item.get("required_accept_criteria", [])
                        },
                        "note": (
                            "Accepted before rework as "
                            f"{carried.get('original_claim_id')}; carried forward unchanged."
                        ),
                        "claim_fingerprint": claim_fingerprint(item),
                        "carried_forward": True,
                    }
                continue
            if str(saved.get("decision") or "").upper() == "REWORK":
                # The regenerated claim is reviewed afresh by a person: the
                # rework itself is not carried, but neither may the evidence
                # policy clear what a person sent back (audit 2026-10-04).
                continue
            if saved.get("claim_fingerprint") != claim_fingerprint(item):
                continue
            preserved[key] = saved
    return preserved


def _human_holds(requests: list[dict[str, Any]], previous: dict[str, Any]) -> set[str]:
    """Claims a person REWORKed whose regenerated text is unchanged: they stay with a person."""
    prior = previous.get("decisions", {}) if isinstance(previous, dict) else {}
    held: set[str] = set()
    for bundle in requests:
        for item in bundle["request"].get("items", []):
            key = key_for(bundle["concept_id"], str(item.get("claim_id") or ""))
            saved = prior.get(key)
            if (
                isinstance(saved, dict)
                and str(saved.get("decision") or "").upper() == "REWORK"
                and saved.get("decided_by") != POLICY_DECIDER
            ):
                held.add(key)
    return held


def _apply_evidence_policy(
    requests: list[dict[str, Any]],
    decisions: dict[str, Any],
    config: dict[str, Any],
    held: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Accept the claims the evidence policy clears; leave the rest to a human.

    Conditional review (vision §32, D-131). Automatic decisions are recomputed
    on every prepare, so a changed policy or claim never keeps a stale one. A
    human or carried-forward decision is never replaced: the human always has
    the last word, and can override an automatic acceptance at any time.
    Returns the history events for new automatic acceptances (D-133).
    """
    settings = policy_settings(config)
    fingerprint = policy_fingerprint(settings)
    events: list[dict[str, Any]] = []
    for bundle in requests:
        concept_id = bundle["concept_id"]
        for item in bundle["request"].get("items", []):
            key = key_for(concept_id, str(item.get("claim_id") or ""))
            existing = decisions.get(key)
            if isinstance(existing, dict) and existing.get("decided_by") != POLICY_DECIDER:
                continue
            if held and key in held:
                # A person sent this claim back; it is theirs to decide again.
                decisions.pop(key, None)
                continue
            decisions.pop(key, None)
            evaluation = (
                evaluate_claim(item, settings) if settings.get("enabled", True) else None
            )
            if evaluation is None or evaluation["classification"] != AUTO_CLEARED:
                continue
            decisions[key] = {
                "claim_id": str(item.get("claim_id") or ""),
                "decision": "ACCEPT",
                "criteria": {
                    criterion: True for criterion in item.get("required_accept_criteria", [])
                },
                "note": "Cleared automatically: " + " ".join(evaluation["reasons"]),
                "claim_fingerprint": claim_fingerprint(item),
                "decided_by": POLICY_DECIDER,
                "policy": {
                    "classification": evaluation["classification"],
                    "reasons": evaluation["reasons"],
                    "fingerprint": fingerprint,
                },
            }
            unchanged = (
                isinstance(existing, dict)
                and existing.get("claim_fingerprint") == decisions[key]["claim_fingerprint"]
                and (existing.get("policy") or {}).get("fingerprint") == fingerprint
            )
            if not unchanged:
                events.append(
                    {
                        "concept_id": concept_id,
                        "claim_id": decisions[key]["claim_id"],
                        "decision": "ACCEPT",
                        "decided_by": POLICY_DECIDER,
                        "previous_decision": (existing or {}).get("decision"),
                        "note": decisions[key]["note"],
                        "claim_fingerprint": decisions[key]["claim_fingerprint"],
                    }
                )
    return events


def _record_withdrawn(previous: dict[str, Any], decisions: dict[str, Any]) -> None:
    """Log each automatic acceptance that no longer stands after a prepare."""
    prior = previous.get("decisions", {}) if isinstance(previous, dict) else {}
    for key, saved in (prior if isinstance(prior, dict) else {}).items():
        if not isinstance(saved, dict) or saved.get("decided_by") != POLICY_DECIDER:
            continue
        current = decisions.get(key) or {}
        if (
            current.get("decided_by") == POLICY_DECIDER
            and current.get("claim_fingerprint") == saved.get("claim_fingerprint")
        ):
            continue
        concept_id, _, claim_id = key.partition("::")
        record_history(
            {
                "concept_id": concept_id,
                "claim_id": claim_id,
                "decision": "WITHDRAWN",
                "decided_by": POLICY_DECIDER,
                "previous_decision": saved.get("decision"),
                "note": "Automatic acceptance withdrawn: the claim or the policy changed.",
                "claim_fingerprint": saved.get("claim_fingerprint"),
            }
        )


def _original_questions(request: dict[str, Any]) -> dict[str, str]:
    return {
        str(question.get("question_id")): str(question.get("question") or "")
        for question in request.get("research_questions", [])
        if isinstance(question, dict)
        and question.get("question_id")
        and question.get("origin") != HUMAN_REWORK_ORIGIN
    }


def _preserved_waivers(
    requests: list[dict[str, Any]],
    previous: dict[str, Any],
) -> dict[str, Any]:
    """Keep a waiver only while its question still exists with the same wording."""
    prior = previous.get("waived_questions", {}) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict):
        return {}
    preserved: dict[str, Any] = {}
    for bundle in requests:
        concept_id = bundle["concept_id"]
        questions = _original_questions(bundle["request"])
        saved = prior.get(concept_id)
        if not isinstance(saved, dict):
            continue
        kept = {
            question_id: waiver
            for question_id, waiver in saved.items()
            if isinstance(waiver, dict)
            and questions.get(question_id) == waiver.get("question")
        }
        if kept:
            preserved[concept_id] = kept
    return preserved


def question_coverage(
    requests: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Live per-concept answer status of the original research questions."""
    decisions = state.get("decisions", {})
    waivers = state.get("waived_questions", {})
    rows = []
    for bundle in requests:
        concept_id = bundle["concept_id"]
        request = bundle["request"]
        accepted: dict[str, list[str]] = {}
        for item in request.get("items", []):
            decision = decisions.get(key_for(concept_id, str(item["claim_id"])), {})
            if decision.get("decision") == "ACCEPT":
                for question_id in item.get("question_ids", []):
                    accepted.setdefault(str(question_id), []).append(str(item["claim_id"]))
        concept_waivers = waivers.get(concept_id, {}) if isinstance(waivers, dict) else {}
        questions = []
        for question_id, text in _original_questions(request).items():
            waiver = concept_waivers.get(question_id) if isinstance(concept_waivers, dict) else None
            questions.append(
                {
                    "question_id": question_id,
                    "question": text,
                    "accepted_claim_ids": accepted.get(question_id, []),
                    "status": (
                        "ANSWERED"
                        if accepted.get(question_id)
                        else "WAIVED"
                        if isinstance(waiver, dict)
                        else "UNANSWERED"
                    ),
                    "waiver": waiver if isinstance(waiver, dict) else None,
                }
            )
        working_title = (request.get("concept") or {}).get("working_title")
        rows.append(
            {
                "concept_id": concept_id,
                "working_title": working_title,
                "questions": questions,
                "unanswered": sum(q["status"] == "UNANSWERED" for q in questions),
            }
        )
    return rows


def apply_question_waiver(
    *,
    concept_id: str,
    question_id: str,
    waive: bool,
    note: str | None,
) -> dict[str, Any]:
    """Waive (or un-waive) an original research question for one concept."""
    state = current_state()
    if not state:
        raise ValueError("Research Gate is not prepared or is stale")
    requests = build_requests()
    bundle = next((item for item in requests if item["concept_id"] == concept_id), None)
    if bundle is None:
        raise ValueError("Unknown concept_id")
    questions = _original_questions(bundle["request"])
    if question_id not in questions:
        raise ValueError("Only an original research question of this concept can be waived")
    waivers = state.setdefault("waived_questions", {})
    if waive:
        clean_note = str(note or "").strip()
        if not clean_note:
            raise ValueError("Waiving a research question requires a note explaining why")
        waivers.setdefault(concept_id, {})[question_id] = {
            "question": questions[question_id],
            "note": clean_note,
            "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
            "waived_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        concept_waivers = waivers.get(concept_id, {})
        if isinstance(concept_waivers, dict):
            concept_waivers.pop(question_id, None)
            if not concept_waivers:
                waivers.pop(concept_id, None)
    record_history(
        {
            "concept_id": concept_id,
            "question_id": question_id,
            "question": questions[question_id],
            "decision": "WAIVE_QUESTION" if waive else "UNWAIVE_QUESTION",
            "decided_by": "HUMAN",
            "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
            "note": str(note or "").strip(),
        }
    )
    state["status"] = "AWAITING_HUMAN_DECISION"
    finalize_if_complete(state, requests)
    return snapshot()


CARRIED_PREFIX = "kept_"


def accepted_claims_to_carry(
    bundle: dict[str, Any],
    state: dict[str, Any],
    *,
    exclude_claim_id: str,
) -> list[dict[str, Any]]:
    """Accepted claims of a concept, with their sources, to survive a rework."""
    concept_id = bundle["concept_id"]
    decisions = state.get("decisions", {})
    package = load_json(Path(bundle["draft_path"]))
    sources = {
        str(source.get("source_id")): source
        for source in package.get("sources", [])
        if isinstance(source, dict)
    }
    carried = []
    for claim in package.get("claims", []):
        claim_id = str(claim.get("claim_id") or "")
        if claim_id == exclude_claim_id:
            continue
        decision = decisions.get(key_for(concept_id, claim_id), {})
        if decision.get("decision") != "ACCEPT":
            continue
        used = [
            sources[str(link.get("source_id"))]
            for link in claim.get("evidence_links", [])
            if str(link.get("source_id")) in sources
        ]
        carried.append({"claim": claim, "sources": used})
    return carried


def _carried_key(entry: dict[str, Any]) -> str:
    claim = entry.get("claim", {})
    return json.dumps(
        {
            "statement": claim.get("statement"),
            "quotes": [
                link.get("evidence_quote") for link in claim.get("evidence_links", [])
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _apply_rework_feedback(
    *,
    concept_id: str,
    claim_id: str,
    item: dict[str, Any],
    note: str,
    carried: list[dict[str, Any]] | None = None,
) -> None:
    plans_dir = OUTPUT_DIR / "plans"
    plan_path = plans_dir / f"{safe_slug(concept_id)}.research_plan.json"
    if not plan_path.exists():
        raise ValueError("Research rework cannot find the current research plan")

    plan = load_json(plan_path)
    if str(plan.get("concept_id") or "") != concept_id:
        raise ValueError("Research rework plan concept_id mismatch")

    requests = plan.get("human_rework_requests", [])
    if not isinstance(requests, list):
        requests = []
    previous = [
        value
        for value in requests
        if isinstance(value, dict)
        and str(value.get("claim_id") or "") != claim_id
    ]
    iteration = 1 + max(
        (
            int(value.get("iteration") or 0)
            for value in requests
            if isinstance(value, dict)
            and str(value.get("claim_id") or "") == claim_id
        ),
        default=0,
    )
    question_id = f"hrw_{safe_slug(claim_id)}"
    request = {
        "claim_id": claim_id,
        "iteration": iteration,
        "note": note,
        "question_id": question_id,
        "original_claim": {
            key: value
            for key, value in item.items()
            if key not in {
                "required_accept_criteria",
                "criteria_descriptions",
                "criteria_decisions",
                "decision",
                "note",
            }
        },
    }
    previous.append(request)
    plan["human_rework_requests"] = previous
    plan["human_rework_mode"] = "HUMAN_INSTRUCTION_ONLY"

    # Accepted claims of this concept survive the regeneration: they are merged
    # back into the next draft unchanged and stay accepted (see D-104).
    existing = plan.get("carried_claims", [])
    reworked_ids = {claim_id, claim_id.removeprefix(CARRIED_PREFIX)}
    merged = {
        _carried_key(entry): entry
        for entry in (existing if isinstance(existing, list) else [])
        if isinstance(entry, dict)
        and str(entry.get("claim", {}).get("claim_id") or "") not in reworked_ids
    }
    for entry in carried or []:
        merged.setdefault(_carried_key(entry), entry)
    if merged:
        plan["carried_claims"] = list(merged.values())
    else:
        plan.pop("carried_claims", None)

    questions = plan.get("research_questions", [])
    if not isinstance(questions, list):
        questions = []
    questions = [
        question
        for question in questions
        if not (
            isinstance(question, dict)
            and str(question.get("rework_claim_id") or "") == claim_id
        )
    ]
    questions.append(
        {
            "question_id": question_id,
            "question": note,
            "origin": "human_rework",
            "rework_claim_id": claim_id,
        }
    )
    plan["research_questions"] = questions

    instructions = plan.get("instructions", [])
    if not isinstance(instructions, list):
        instructions = []
    directive = (
        "Human Research Gate rework instructions are authoritative: investigate "
        "the requested issue again using acquired evidence. The instruction may "
        "change what must be researched, but it never authorizes invented facts."
    )
    if directive not in instructions:
        instructions.append(directive)
    plan["instructions"] = instructions
    write_json(plan_path, plan)


def current_drafts() -> list[Path]:
    if not DEFAULT_DRAFTS_DIR.exists():
        return []
    return sorted(DEFAULT_DRAFTS_DIR.glob("*.draft_research_package.json"))


def drafts_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in current_drafts():
        package = load_json(path)
        concept_id = str(package.get("concept_id", "")).strip()
        if concept_id:
            hashes[concept_id] = sha256_file(path)
    return hashes


def build_requests() -> list[dict[str, Any]]:
    requests = []
    config = load_config()
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    for draft_path in current_drafts():
        package = load_json(draft_path)
        request = build_review_request(package, config)
        concept_id = str(request["concept_id"])
        request_path = (
            REVIEW_REQUESTS_DIR / f"{safe_slug(concept_id)}.research_gate_request.json"
        )
        write_json(request_path, request)
        requests.append(
            {
                "concept_id": concept_id,
                "draft_path": str(draft_path),
                "request_path": str(request_path),
                "request": request,
            }
        )
    return requests


def prepare_state() -> dict[str, Any]:
    requests = build_requests()
    if not requests:
        return {"status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES", "claims": []}

    previous = load_json(STATE_FILE) if STATE_FILE.exists() else {}
    decisions = _preserved_decisions(requests, previous)
    accepted_now = _apply_evidence_policy(
        requests, decisions, load_config(), held=_human_holds(requests, previous)
    )
    _record_withdrawn(previous, decisions)
    for event in accepted_now:
        record_history(event)
    state = {
        "schema_version": "1.1",
        "status": "AWAITING_HUMAN_DECISION",
        "draft_hashes": drafts_hashes(),
        "reviewer": os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER),
        "decisions": decisions,
        "waived_questions": _preserved_waivers(requests, previous),
    }
    finalize_if_complete(state, requests)
    return snapshot()


def current_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    state = load_json(STATE_FILE)
    if state.get("draft_hashes") != drafts_hashes():
        return {}
    return state


def key_for(concept_id: str, claim_id: str) -> str:
    return f"{concept_id}::{claim_id}"


def snapshot() -> dict[str, Any]:
    requests = build_requests() if current_drafts() else []
    if not requests:
        return {
            "status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES",
            "claims": [],
            "complete": False,
        }

    state = current_state()
    claim_count = sum(int(item["request"].get("claim_count", 0)) for item in requests)
    if not state:
        return {
            "status": "READY_TO_PREPARE",
            "claims": [],
            "complete": False,
            "claim_count": claim_count,
        }

    decisions = state.get("decisions", {})
    settings = policy_settings(load_config())
    history = history_by_key()
    claims = []
    for bundle in requests:
        request = bundle["request"]
        concept_id = bundle["concept_id"]
        for item in request.get("items", []):
            claim_id = str(item["claim_id"])
            decision = decisions.get(key_for(concept_id, claim_id), {})
            claims.append(
                {
                    **item,
                    "concept_id": concept_id,
                    "concept": request.get("concept", {}),
                    "research_questions": request.get("research_questions", []),
                    "criteria_descriptions": request.get("criteria", {}),
                    "decision": decision.get("decision", "PENDING"),
                    "criteria_decisions": decision.get("criteria", {}),
                    "note": decision.get("note", ""),
                    "decided_by": decision.get("decided_by") or (
                        "HUMAN" if decision else None
                    ),
                    "evidence_policy": evaluate_claim(item, settings),
                    "decision_history": history.get(key_for(concept_id, claim_id), []),
                }
            )

    pending = sum(item["decision"] == "PENDING" for item in claims)
    auto_cleared = sum(item["decided_by"] == POLICY_DECIDER for item in claims)
    verified_statuses = []
    current_concept_ids = {bundle["concept_id"] for bundle in requests}
    if VERIFIED_DIR.exists():
        for path in sorted(VERIFIED_DIR.glob("*.verified_research_package.json")):
            payload = load_json(path)
            if str(payload.get("concept_id", "")) not in current_concept_ids:
                continue
            verified_statuses.append(
                {
                    "concept_id": payload.get("concept_id"),
                    "status": payload.get("status"),
                    "unresolved_question_ids": payload.get(
                        "unresolved_question_ids", []
                    ),
                }
            )

    ready_count = sum(
        item.get("status") == "READY_FOR_STORY_SCRIPT" for item in verified_statuses
    )
    return {
        "status": str(state.get("status") or "AWAITING_HUMAN_DECISION"),
        "complete": state.get("status") == "COMPLETE",
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "claim_count": claim_count,
        "pending": pending,
        "auto_cleared": auto_cleared,
        "evidence_policy_enabled": bool(settings.get("enabled", True)),
        "claims": claims,
        "verified_packages": verified_statuses,
        "ready_for_story_script": ready_count,
        "question_coverage": question_coverage(requests, state),
    }


def normalize_criteria(criteria: Any, required: list[str]) -> dict[str, bool]:
    if not isinstance(criteria, dict):
        criteria = {}
    return {criterion: criteria.get(criterion) is True for criterion in required}


def _decision_identity(decision: dict[str, Any]) -> dict[str, Any]:
    identity = {key: decision.get(key) for key in ("claim_id", "decision", "criteria", "note")}
    # Only automatic decisions add a key, so fingerprints of packages decided
    # by a human before D-131 are unchanged and their downstream work stays current.
    if decision.get("decided_by"):
        identity["decided_by"] = decision["decided_by"]
    return identity


def _decision_fingerprint(
    bundle: dict[str, Any],
    decisions: dict[str, Any],
    waivers: dict[str, Any],
) -> str:
    concept_id = bundle["concept_id"]
    payload = {
        "draft_sha256": sha256_file(Path(bundle["draft_path"])),
        "decisions": [
            _decision_identity(decisions[key_for(concept_id, str(item["claim_id"]))])
            for item in bundle["request"].get("items", [])
        ],
        "waivers": waivers,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def finalize_if_complete(
    state: dict[str, Any],
    requests: list[dict[str, Any]],
) -> None:
    """Write verified research for every concept whose claims are all decided.

    Each concept is finalized on its own so a ready concept can go on to
    Story / Script while another is still under review (D-104). A concept's
    files are rewritten only when its decisions change, so downstream work
    built on an unchanged verified package stays current. The gate is COMPLETE
    only when every concept is decided and ready.
    """
    decisions = state.get("decisions", {})
    all_waivers = state.get("waived_questions") or {}
    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)
    current_concept_ids = {bundle["concept_id"] for bundle in requests}
    for directory, pattern in (
        (REVIEWED_DIR, "*.research_gate_reviewed.json"),
        (VERIFIED_DIR, "*.verified_research_package.json"),
    ):
        for stale_path in directory.glob(pattern):
            payload = load_json(stale_path)
            if str(payload.get("concept_id", "")) not in current_concept_ids:
                stale_path.unlink()

    summaries = []
    for bundle in requests:
        concept_id = bundle["concept_id"]
        request = bundle["request"]
        slug = safe_slug(concept_id)
        reviewed_path = REVIEWED_DIR / f"{slug}.research_gate_reviewed.json"
        verified_path = VERIFIED_DIR / f"{slug}.verified_research_package.json"
        keys = [key_for(concept_id, str(item["claim_id"])) for item in request.get("items", [])]
        if not keys or any(key not in decisions for key in keys):
            for path in (reviewed_path, verified_path):
                if path.exists():
                    path.unlink()
            summaries.append({"concept_id": concept_id, "status": "AWAITING_HUMAN_DECISION"})
            continue

        waivers = all_waivers.get(concept_id, {}) if isinstance(all_waivers, dict) else {}
        fingerprint = _decision_fingerprint(bundle, decisions, waivers)
        existing = load_json(verified_path) if verified_path.exists() else None
        if (
            isinstance(existing, dict)
            and reviewed_path.exists()
            and existing.get("research_gate", {}).get("decision_fingerprint") == fingerprint
        ):
            verified = existing
            reviewed_counts = load_json(reviewed_path).get("counts", {})
        else:
            package = load_json(Path(bundle["draft_path"]))
            response = {
                "concept_id": concept_id,
                "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
                "decisions": [decisions[key] for key in keys],
                "waived_questions": waivers,
                "overall_note": "",
            }
            reviewed, verified = apply_gate(package, request, response, load_config())
            verified["research_gate"]["decision_fingerprint"] = fingerprint
            write_json(reviewed_path, reviewed)
            write_json(verified_path, verified)
            reviewed_counts = reviewed["counts"]
        summaries.append(
            {
                "concept_id": concept_id,
                "status": verified["status"],
                "accepted": reviewed_counts.get("accepted", 0),
                "rework": reviewed_counts.get("rework", 0),
                "rejected": reviewed_counts.get("rejected", 0),
                "unresolved_questions": len(verified.get("unresolved_question_ids", [])),
                "verified_package": str(verified_path),
            }
        )

    all_ready = bool(summaries) and all(
        item["status"] == "READY_FOR_STORY_SCRIPT" for item in summaries
    )
    write_json(
        SUMMARY_FILE,
        {
            "status": "READY_FOR_STORY_SCRIPT" if all_ready else "RESEARCH_INCOMPLETE",
            "packages": summaries,
        },
    )
    state["status"] = "COMPLETE" if all_ready else "AWAITING_HUMAN_DECISION"
    write_json(STATE_FILE, state)


def apply_action(
    *,
    concept_id: str,
    claim_id: str,
    decision: str,
    criteria: Any,
    note: str | None,
) -> dict[str, Any]:
    state = current_state()
    if not state:
        raise ValueError("Research Gate is not prepared or is stale")

    requests = build_requests()
    bundle = next(
        (item for item in requests if item["concept_id"] == concept_id),
        None,
    )
    if bundle is None:
        raise ValueError("Unknown concept_id")
    item = next(
        (
            value
            for value in bundle["request"].get("items", [])
            if str(value.get("claim_id")) == claim_id
        ),
        None,
    )
    if item is None:
        raise ValueError("Unknown claim_id")

    value = str(decision or "").strip().upper()
    if value not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("Decision must be ACCEPT, REWORK, or REJECT")

    required = list(item.get("required_accept_criteria", []))
    clean_note = str(note or "").strip()
    # REWORK and REJECT both record every criterion as unconfirmed; the gate's
    # final validation requires every criterion key on every decision.
    normalized = {criterion: value == "ACCEPT" for criterion in required}
    if value == "REWORK" and not clean_note:
        raise ValueError("REWORK requires a note explaining what must change")
    if (
        value == "ACCEPT"
        and item.get("coverage", {}).get("state") == "CONFLICTED"
        and load_config().get("require_conflict_resolution_note")
        and not clean_note
    ):
        raise ValueError("Accepted conflicted claim requires a resolution note")

    previous = state.setdefault("decisions", {}).get(key_for(concept_id, claim_id)) or {}
    state["decisions"][key_for(concept_id, claim_id)] = {
        "claim_id": claim_id,
        "decision": value,
        "criteria": normalized,
        "note": clean_note,
        "claim_fingerprint": claim_fingerprint(item),
    }
    record_history(
        {
            "concept_id": concept_id,
            "claim_id": claim_id,
            "decision": value,
            "decided_by": "HUMAN",
            "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
            "previous_decision": previous.get("decision"),
            "previous_decided_by": previous.get("decided_by") or ("HUMAN" if previous else None),
            "note": clean_note,
            "claim_fingerprint": claim_fingerprint(item),
        }
    )

    if value == "REWORK":
        _apply_rework_feedback(
            concept_id=concept_id,
            claim_id=claim_id,
            item=item,
            note=clean_note,
            carried=accepted_claims_to_carry(bundle, state, exclude_claim_id=claim_id),
        )

    state["status"] = "AWAITING_HUMAN_DECISION"
    finalize_if_complete(state, requests)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental Research Gate controller")
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    result = prepare_state() if args.mode == "prepare" else snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
