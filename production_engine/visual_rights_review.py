"""Human rights/context gate for selected creator/editorial visual excerpts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, sha256_file
from visual_candidate_review import candidate_selection_status
from visual_search import search_result_is_current

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
CANDIDATE_REVIEW_DIR = OUTPUT / "visual_candidate_reviews"
SEARCH_RESULT_DIR = OUTPUT / "visual_search_results"
RIGHTS_DIR = OUTPUT / "visual_rights_reviews"


def _path(review_path: Path) -> Path:
    RIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    return RIGHTS_DIR / review_path.name.replace(
        ".visual_candidate_review.json",
        ".visual_rights_review.json",
    )


def _current_review_result(
    review_path: Path,
    review: dict[str, Any],
) -> tuple[Path, dict[str, Any]] | None:
    if (
        not isinstance(review, dict)
        or review.get("status") != "READY_FOR_ROUGH_CUT"
    ):
        return None
    result_path = Path(str(review.get("source_result") or ""))
    if (
        not result_path.is_file()
        or result_path.parent.resolve() != SEARCH_RESULT_DIR.resolve()
        or review.get("source_result_sha256") != sha256_file(result_path)
    ):
        return None

    current = search_result_is_current(result_path)
    if current is None:
        return None
    result = current[0]
    if (
        str(result.get("concept_id") or "")
        != str(review.get("concept_id") or "")
        or str(result.get("format") or "")
        != str(review.get("format") or "")
    ):
        return None
    return result_path, result


def _candidate(
    review_path: Path,
    review: dict[str, Any],
    shot_id: str,
) -> dict[str, Any] | None:
    current = _current_review_result(review_path, review)
    if current is None:
        return None
    _, result = current

    decision = review.get("decisions", {}).get(shot_id, {})
    if (
        not isinstance(decision, dict)
        or decision.get("status")
        != "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
    ):
        return None

    candidate_id = str(decision.get("candidate_id") or "")
    shot = next(
        (
            item
            for item in result.get("shots", [])
            if isinstance(item, dict)
            and str(item.get("shot_id") or "") == shot_id
        ),
        None,
    )
    if not isinstance(shot, dict):
        return None

    result_fingerprint = hashlib.sha256(
        json.dumps(
            shot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if decision.get("result_fingerprint") != result_fingerprint:
        return None

    candidate = next(
        (
            item
            for item in shot.get("candidates", [])
            if isinstance(item, dict)
            and str(item.get("candidate_id") or "") == candidate_id
        ),
        None,
    )
    if candidate is None:
        return None

    candidate_fingerprint = hashlib.sha256(
        json.dumps(
            candidate,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if decision.get("candidate_fingerprint") != candidate_fingerprint:
        return None

    try:
        route = candidate_selection_status(candidate)
    except ValueError:
        return None
    if route != "SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
        return None
    return candidate

def _selection_current(
    review_path: Path,
    review: dict[str, Any],
    shot_id: str,
    rights_decision: dict[str, Any],
) -> bool:
    selection = review.get("decisions", {}).get(shot_id)
    if (
        not isinstance(selection, dict)
        or selection.get("status")
        != "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
    ):
        return False
    candidate = _candidate(review_path, review, shot_id)
    return bool(
        candidate is not None
        and rights_decision.get("candidate_id") == candidate.get("candidate_id")
        and rights_decision.get("selection_candidate_fingerprint")
        == selection.get("candidate_fingerprint")
        and rights_decision.get("selection_result_fingerprint")
        == selection.get("result_fingerprint")
    )


def _reconcile(
    review_path: Path,
    review: dict[str, Any],
    rights: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    old_decisions = (
        rights.get("decisions", {})
        if isinstance(rights, dict)
        and isinstance(rights.get("decisions"), dict)
        else {}
    )
    current_decisions: dict[str, Any] = {}
    stale = 0
    for shot_id, rights_decision in old_decisions.items():
        if (
            isinstance(rights_decision, dict)
            and _selection_current(
                review_path,
                review,
                shot_id,
                rights_decision,
            )
        ):
            current_decisions[shot_id] = rights_decision
        else:
            stale += 1

    reconciled = {
        "artifact": "visual_rights_review",
        "concept_id": review.get("concept_id"),
        "format": review.get("format"),
        "source_candidate_review": str(review_path.resolve()),
        "source_candidate_review_sha256": sha256_file(review_path),
        "decisions": current_decisions,
    }
    return reconciled, stale


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    required_total = 0
    decided_total = 0
    approved_total = 0
    stale_total = 0
    paths = (
        sorted(
            CANDIDATE_REVIEW_DIR.glob("*.visual_candidate_review.json")
        )
        if CANDIDATE_REVIEW_DIR.exists()
        else []
    )
    for review_path in paths:
        review = load_json(review_path)
        rights_path = _path(review_path)
        stored = (
            load_json(rights_path)
            if rights_path.exists()
            else {"decisions": {}}
        )
        rights, stale = _reconcile(review_path, review, stored)
        stale_total += stale
        if rights_path.exists() and rights != stored:
            atomic_write_json(rights_path, rights)

        pending: list[dict[str, Any]] = []
        for shot_id, selection in review.get("decisions", {}).items():
            if (
                not isinstance(selection, dict)
                or selection.get("status")
                != "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
            ):
                continue
            required_total += 1
            candidate = _candidate(review, shot_id)
            decision = rights["decisions"].get(shot_id)
            if isinstance(decision, dict):
                decided_total += 1
                approved_total += int(
                    decision.get("approved_for_rough_cut") is True
                )
            pending.append(
                {
                    "shot_id": shot_id,
                    "candidate": candidate,
                    "decision": decision,
                }
            )

        if pending:
            items.append(
                {
                    "concept_id": review.get("concept_id"),
                    "format": review.get("format"),
                    "candidate_review_file": str(review_path),
                    "candidate_review_sha256": sha256_file(review_path),
                    "pending": pending,
                }
            )

    complete = required_total == 0 or required_total == decided_total
    return {
        "status": (
            "NO_RIGHTS_CONTEXT_REVIEW_REQUIRED"
            if required_total == 0
            else "COMPLETE"
            if complete
            else "READY_FOR_RIGHTS_CONTEXT_REVIEW"
        ),
        "complete": complete,
        "required": required_total,
        "decided": decided_total,
        "approved": approved_total,
        "stale_removed": stale_total,
        "items": items,
    }


def apply_action(
    *,
    candidate_review_file: str,
    shot_id: str,
    decision: str,
    transformative_purpose: str = "",
    context_note: str = "",
) -> dict[str, Any]:
    review_path = Path(candidate_review_file)
    if (
        not review_path.exists()
        or review_path.parent.resolve() != CANDIDATE_REVIEW_DIR.resolve()
    ):
        raise ValueError("Invalid candidate review file")

    review = load_json(review_path)
    selected = review.get("decisions", {}).get(shot_id)
    if (
        not selected
        or selected.get("status")
        != "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
    ):
        raise ValueError("Shot is not awaiting rights/context review")

    if decision not in {"APPROVE_CONTEXT_USE", "REJECT_USE"}:
        raise ValueError("Unsupported rights/context decision")
    if (
        decision == "APPROVE_CONTEXT_USE"
        and not transformative_purpose.strip()
    ):
        raise ValueError(
            "Approval requires a documented transformative/editorial purpose"
        )

    candidate = _candidate(review, shot_id)
    if not candidate:
        raise ValueError("Selected candidate is unavailable or stale")

    rights_path = _path(review_path)
    stored = (
        load_json(rights_path)
        if rights_path.exists()
        else {"decisions": {}}
    )
    rights, _ = _reconcile(review_path, review, stored)
    rights["decisions"][shot_id] = {
        "decision": decision,
        "candidate_id": candidate.get("candidate_id"),
        "source_url": candidate.get("source_url"),
        "creator": candidate.get("creator"),
        "license": candidate.get("license"),
        "selection_candidate_fingerprint": selected.get(
            "candidate_fingerprint"
        ),
        "selection_result_fingerprint": selected.get("result_fingerprint"),
        "transformative_purpose": transformative_purpose.strip(),
        "context_note": context_note.strip(),
        "approved_for_rough_cut": decision == "APPROVE_CONTEXT_USE",
        "policy_note": (
            "Human approval records editorial intent; it is not a legal "
            "determination of fair use."
        ),
    }

    expected_ids = {
        sid
        for sid, item in review.get("decisions", {}).items()
        if isinstance(item, dict)
        and item.get("status") == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
    }
    rights["decisions"] = {
        sid: item
        for sid, item in rights["decisions"].items()
        if sid in expected_ids
    }
    rights["source_candidate_review_sha256"] = sha256_file(review_path)
    rights["summary"] = {
        "required": len(expected_ids),
        "decided": len(rights["decisions"]),
        "approved": sum(
            item.get("approved_for_rough_cut") is True
            for item in rights["decisions"].values()
        ),
    }
    rights["status"] = (
        "COMPLETE"
        if len(rights["decisions"]) == len(expected_ids)
        else "REVIEW_IN_PROGRESS"
    )
    atomic_write_json(rights_path, rights)
    return rights


def main() -> None:
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
