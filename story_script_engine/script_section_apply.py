"""Human selection and safe application of script rework alternatives.

Slice 3 is the first destructive selective-rework step. It changes only one
chosen target after explicit human selection and protects the operation with
backups plus a recoverable transaction journal.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from story_script_engine import OUTPUT_DIR, load_json, safe_slug, sha256_file, validate_script_response
from script_section_state import build_targets, validate_state
from script_section_rework_runner import assert_request_current

from script_review import (
    APPROVED_DIR,
    RESPONSES_DIR as SCRIPT_REVIEW_RESPONSES_DIR,
    REVIEW_REQUESTS_DIR as SCRIPT_REVIEW_REQUESTS_DIR,
    build_review_request,
)

SCRIPT_VERSIONS_DIR = OUTPUT_DIR / "script_versions"
SELECTION_TRANSACTIONS_DIR = OUTPUT_DIR / "script_section_selection_transactions"

ALLOWED_SELECTIONS = {"ORIGINAL", "A", "B", "C"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _branch_key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _selection_transaction_paths(
    *,
    concept_id: str,
    fmt: str,
    state_version: int,
    target_id: str,
    transactions_dir: Path,
) -> tuple[Path, Path]:
    stem = (
        f"{_branch_key(concept_id, fmt)}."
        f"v{state_version}.{safe_slug(target_id)}"
    )
    transaction = transactions_dir / f"{stem}.selection_transaction.json"
    backups = transactions_dir / "backups" / stem
    return transaction, backups


def _restore_backup_file(backup_path: Path, destination: Path) -> None:
    payload = load_json(backup_path)
    atomic_write_json(destination, payload)


def recover_prepared_transaction(transaction_path: Path) -> dict[str, Any]:
    """Roll back a PREPARED/IN_PROGRESS selection transaction from backups."""
    transaction_path = transaction_path.resolve()
    transaction = load_json(transaction_path)
    status = str(transaction.get("status") or "")
    if status not in {"PREPARED", "IN_PROGRESS"}:
        return transaction

    backups = transaction.get("backups")
    destinations = transaction.get("destinations")
    if not isinstance(backups, dict) or not isinstance(destinations, dict):
        raise ValueError("Selection transaction is missing backup metadata")

    for key in ("draft", "state", "alternatives"):
        backup = Path(str(backups.get(key) or "")).resolve()
        destination = Path(str(destinations.get(key) or "")).resolve()
        if not backup.is_file():
            raise ValueError(
                f"Cannot recover selection transaction: missing {key} backup"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        _restore_backup_file(backup, destination)

    transaction["status"] = "ROLLED_BACK"
    transaction["rolled_back_at"] = _utc_now()
    atomic_write_json(transaction_path, transaction)
    return transaction


def recover_incomplete_transactions(
    concept_id: str,
    fmt: str,
    *,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
) -> list[dict[str, Any]]:
    branch = _branch_key(concept_id, fmt)
    if not transactions_dir.exists():
        return []
    recovered: list[dict[str, Any]] = []
    for path in sorted(
        transactions_dir.glob(f"{branch}.*.selection_transaction.json")
    ):
        value = load_json(path)
        if str(value.get("status") or "") in {"PREPARED", "IN_PROGRESS"}:
            recovered.append(recover_prepared_transaction(path))
    return recovered


def _alternative_by_id(
    artifact: dict[str, Any],
    selection_id: str,
) -> dict[str, Any] | None:
    if selection_id == "ORIGINAL":
        return None
    for item in artifact.get("alternatives", []):
        if (
            isinstance(item, dict)
            and str(item.get("alternative_id") or "") == selection_id
        ):
            return item
    raise ValueError(f"Alternative {selection_id} is not present")


def _replace_target_text(
    draft: dict[str, Any],
    *,
    target_id: str,
    replacement_text: str,
) -> None:
    if target_id == "hook:opening":
        draft["opening_hook"] = replacement_text
        return
    if target_id == "closing:closing":
        draft["closing"] = replacement_text
        return
    if target_id.startswith("section:"):
        section_id = target_id.split(":", 1)[1]
        for section in draft.get("sections", []):
            if (
                isinstance(section, dict)
                and str(section.get("section_id") or "") == section_id
            ):
                section["narration"] = replacement_text
                return
        raise ValueError(f"Script section not found: {section_id}")
    raise ValueError(f"Unsupported script target: {target_id}")


def _target_map(targets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("target_id") or ""): item
        for item in targets
        if isinstance(item, dict) and str(item.get("target_id") or "")
    }


def _assert_only_selected_target_changed(
    old_draft: dict[str, Any],
    new_draft: dict[str, Any],
    *,
    target_id: str,
    old_state: dict[str, Any],
) -> None:
    old_targets = _target_map(build_targets(old_draft))
    new_targets = _target_map(build_targets(new_draft))
    if set(old_targets) != set(new_targets):
        raise ValueError("Selective replacement changed the script target set")

    locked_ids = {
        str(item.get("target_id") or "")
        for item in old_state.get("targets", [])
        if isinstance(item, dict) and item.get("locked") is True
    }
    if target_id in locked_ids:
        raise ValueError("Selected target is unexpectedly locked")

    for current_id in sorted(old_targets):
        old_hash = str(old_targets[current_id].get("target_sha256") or "")
        new_hash = str(new_targets[current_id].get("target_sha256") or "")
        if current_id == target_id:
            if old_hash == new_hash:
                raise ValueError("Selected replacement did not change target text")
            continue
        if old_hash != new_hash:
            raise ValueError(
                f"Selective replacement modified non-target {current_id}"
            )


def _validate_revised_script(
    revised_draft: dict[str, Any],
    original_script_request: dict[str, Any],
) -> dict[str, Any]:
    response = {
        "concept_id": revised_draft.get("concept_id"),
        "format": revised_draft.get("format"),
        "title": revised_draft.get("title"),
        "opening_hook": revised_draft.get("opening_hook"),
        "opening_hook_mechanism": revised_draft.get("opening_hook_mechanism"),
        "opening_hook_claim_ids": revised_draft.get(
            "opening_hook_claim_ids", []
        ),
        "sections": revised_draft.get("sections", []),
        "closing": revised_draft.get("closing"),
    }
    validation = validate_script_response(response, original_script_request)
    if not validation["valid"]:
        raise ValueError(
            "Selected alternative fails full script validation: "
            + "; ".join(validation["errors"])
        )
    return validation


def _rebase_state(
    old_state: dict[str, Any],
    revised_draft: dict[str, Any],
    revised_draft_path: Path,
    *,
    selected_target_id: str,
    reviewer: str,
    selection_id: str,
) -> dict[str, Any]:
    validation = validate_state(old_state)
    if not validation["valid"]:
        raise ValueError("Invalid section state: " + "; ".join(validation["errors"]))

    old_by_id = _target_map(old_state.get("targets", []))
    fresh_targets = build_targets(revised_draft)
    for target in fresh_targets:
        target_id = str(target["target_id"])
        previous = old_by_id.get(target_id)
        if not previous:
            raise ValueError(f"Missing prior target state: {target_id}")
        if target_id == selected_target_id:
            target["decision"] = "ACCEPTED"
            target["locked"] = True
            target["rework_reason"] = None
            target["custom_instruction"] = None
        else:
            target["decision"] = previous.get("decision")
            target["locked"] = previous.get("locked")
            target["rework_reason"] = previous.get("rework_reason")
            target["custom_instruction"] = previous.get("custom_instruction")
            if str(target.get("target_sha256") or "") != str(
                previous.get("target_sha256") or ""
            ):
                raise ValueError(
                    f"Rebase detected unexpected change to {target_id}"
                )

    new_state = copy.deepcopy(old_state)
    new_state["source_draft"] = str(revised_draft_path.resolve())
    new_state["source_draft_sha256"] = sha256_file(revised_draft_path)
    new_state["state_version"] = int(old_state.get("state_version") or 0) + 1
    new_state["updated_at"] = _utc_now()
    new_state["targets"] = fresh_targets
    history = list(old_state.get("history", []))
    history.append(
        {
            "state_version": new_state["state_version"],
            "reviewed_at": new_state["updated_at"],
            "reviewer": reviewer,
            "target_id": selected_target_id,
            "action": "SELECT_ALTERNATIVE",
            "selection_id": selection_id,
        }
    )
    new_state["history"] = history
    return new_state


def _invalidate_and_refresh_script_gate(
    revised_draft: dict[str, Any],
    draft_path: Path,
    *,
    review_requests_dir: Path,
    review_responses_dir: Path,
    approved_dir: Path,
) -> None:
    concept_id = str(revised_draft.get("concept_id") or "")
    fmt = str(revised_draft.get("format") or "")
    branch = _branch_key(concept_id, fmt)

    review_requests_dir.mkdir(parents=True, exist_ok=True)
    request_path = (
        review_requests_dir / f"{branch}.script_review_request.json"
    )
    atomic_write_json(
        request_path,
        build_review_request(revised_draft, draft_path),
    )

    response_path = (
        review_responses_dir / f"{branch}.script_review_response.json"
    )
    if response_path.exists():
        response_path.unlink()

    approved_path = approved_dir / f"{safe_slug(concept_id)}.approved_script.json"
    if approved_path.exists():
        approved_path.unlink()


def apply_selection(
    alternatives_path: Path,
    *,
    selection_id: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Apply ORIGINAL/A/B/C only after verifying all bound artifacts are current."""
    alternatives_path = alternatives_path.resolve()
    if not alternatives_path.is_file():
        raise FileNotFoundError(alternatives_path)

    artifact = load_json(alternatives_path)
    if artifact.get("artifact") != "script_section_alternatives":
        raise ValueError("Not a script_section_alternatives artifact")
    if artifact.get("selection") is not None:
        raise ValueError("An alternative has already been selected")

    selection = str(selection_id or "").strip().upper()
    if selection not in ALLOWED_SELECTIONS:
        raise ValueError("selection_id must be ORIGINAL, A, B or C")
    reviewer_value = str(reviewer or "").strip()
    if not reviewer_value:
        raise ValueError("reviewer is required")

    concept_id = str(artifact.get("concept_id") or "").strip()
    fmt = str(artifact.get("format") or "").strip()
    target_id = str(artifact.get("target_id") or "").strip()
    if not concept_id or not fmt or not target_id:
        raise ValueError("Alternatives artifact identity is incomplete")

    recover_incomplete_transactions(
        concept_id,
        fmt,
        transactions_dir=transactions_dir,
    )
    artifact = load_json(alternatives_path)
    if artifact.get("selection") is not None:
        raise ValueError("An alternative has already been selected")

    provenance = artifact.get("artifact_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Alternatives artifact is missing provenance")

    request_path = Path(str(provenance.get("rework_request") or "")).resolve()
    expected_request_hash = str(
        provenance.get("rework_request_sha256") or ""
    )
    if not request_path.is_file() or not expected_request_hash:
        raise ValueError("Alternatives artifact is missing rework request provenance")
    if sha256_file(request_path) != expected_request_hash:
        raise ValueError("STALE_ALTERNATIVES: rework request changed")

    rework_request = load_json(request_path)
    assert_request_current(rework_request)

    request_provenance = rework_request.get("request_provenance", {})
    draft_path = Path(
        str(request_provenance.get("script_draft") or "")
    ).resolve()
    state_path = Path(
        str(request_provenance.get("section_state") or "")
    ).resolve()
    script_request_path = Path(
        str(request_provenance.get("script_request") or "")
    ).resolve()

    old_draft = load_json(draft_path)
    old_state = load_json(state_path)
    old_artifact = load_json(alternatives_path)

    selected = _alternative_by_id(artifact, selection)
    replacement_text = (
        str(artifact.get("original", {}).get("text") or "")
        if selection == "ORIGINAL"
        else str(selected.get("replacement_text") or "")
    )
    if not replacement_text.strip():
        raise ValueError("Selected replacement text is empty")

    state_target = next(
        (
            item
            for item in old_state.get("targets", [])
            if isinstance(item, dict)
            and item.get("target_id") == target_id
        ),
        None,
    )
    if not isinstance(state_target, dict):
        raise ValueError("Selected target is missing from section state")
    if state_target.get("decision") != "REWORK_REQUESTED":
        raise ValueError("Selected target no longer requests rework")
    if state_target.get("locked") is True:
        raise ValueError("Selected target is locked")

    revision = int(
        old_draft.get("human_revision", {}).get("revision", 0)
        if isinstance(old_draft.get("human_revision"), dict)
        else 0
    ) + (0 if selection == "ORIGINAL" else 1)

    transaction_path, backup_dir = _selection_transaction_paths(
        concept_id=concept_id,
        fmt=fmt,
        state_version=int(old_state.get("state_version") or 0),
        target_id=target_id,
        transactions_dir=transactions_dir,
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_draft = backup_dir / "draft.json"
    backup_state = backup_dir / "state.json"
    backup_alternatives = backup_dir / "alternatives.json"
    atomic_write_json(backup_draft, old_draft)
    atomic_write_json(backup_state, old_state)
    atomic_write_json(backup_alternatives, old_artifact)

    transaction = {
        "artifact": "script_section_selection_transaction",
        "status": "PREPARED",
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_id,
        "selection_id": selection,
        "reviewer": reviewer_value,
        "prepared_at": _utc_now(),
        "backups": {
            "draft": str(backup_draft.resolve()),
            "state": str(backup_state.resolve()),
            "alternatives": str(backup_alternatives.resolve()),
        },
        "destinations": {
            "draft": str(draft_path),
            "state": str(state_path),
            "alternatives": str(alternatives_path),
        },
    }
    transaction_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(transaction_path, transaction)

    try:
        transaction["status"] = "IN_PROGRESS"
        transaction["started_at"] = _utc_now()
        atomic_write_json(transaction_path, transaction)

        if selection == "ORIGINAL":
            revised_draft = copy.deepcopy(old_draft)
            validation = old_draft.get("validation", {})
            new_state = _rebase_state(
                old_state,
                revised_draft,
                draft_path,
                selected_target_id=target_id,
                reviewer=reviewer_value,
                selection_id=selection,
            )
        else:
            revised_draft = copy.deepcopy(old_draft)
            _replace_target_text(
                revised_draft,
                target_id=target_id,
                replacement_text=replacement_text,
            )
            _assert_only_selected_target_changed(
                old_draft,
                revised_draft,
                target_id=target_id,
                old_state=old_state,
            )
            original_script_request = load_json(script_request_path)
            validation = _validate_revised_script(
                revised_draft,
                original_script_request,
            )

            branch_versions_dir = versions_dir / _branch_key(concept_id, fmt)
            branch_versions_dir.mkdir(parents=True, exist_ok=True)
            previous_revision = revision - 1
            version_path = (
                branch_versions_dir
                / f"revision_{previous_revision:04d}.script_draft.json"
            )
            if version_path.exists():
                if load_json(version_path) != old_draft:
                    raise ValueError(
                        "Script version collision with different content"
                    )
            else:
                atomic_write_json(version_path, old_draft)

            revised_draft["validation"] = validation
            revised_draft["human_revision"] = {
                "revision": revision,
                "parent_draft_sha256": sha256_file(draft_path),
                "selected_target_id": target_id,
                "selection_id": selection,
                "selected_by": reviewer_value,
                "selected_at": _utc_now(),
                "alternatives_artifact": str(alternatives_path),
                "alternatives_artifact_sha256_before_selection": sha256_file(
                    alternatives_path
                ),
                "previous_version": str(version_path.resolve()),
            }
            atomic_write_json(draft_path, revised_draft)

            new_state = _rebase_state(
                old_state,
                revised_draft,
                draft_path,
                selected_target_id=target_id,
                reviewer=reviewer_value,
                selection_id=selection,
            )

        atomic_write_json(state_path, new_state)

        artifact["status"] = (
            "ORIGINAL_SELECTED"
            if selection == "ORIGINAL"
            else "ALTERNATIVE_SELECTED"
        )
        artifact["selection"] = {
            "selection_id": selection,
            "replacement_text": replacement_text,
            "reviewer": reviewer_value,
            "selected_at": _utc_now(),
            "resulting_draft_sha256": sha256_file(draft_path),
            "resulting_state_version": new_state.get("state_version"),
            "revision": revision,
        }
        atomic_write_json(alternatives_path, artifact)

        _invalidate_and_refresh_script_gate(
            revised_draft,
            draft_path,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )

        transaction["status"] = "COMMITTED"
        transaction["committed_at"] = _utc_now()
        transaction["resulting_draft_sha256"] = sha256_file(draft_path)
        transaction["resulting_state_sha256"] = sha256_file(state_path)
        transaction["resulting_alternatives_sha256"] = sha256_file(
            alternatives_path
        )
        atomic_write_json(transaction_path, transaction)

    except Exception:
        recover_prepared_transaction(transaction_path)
        raise

    return {
        "status": artifact["status"],
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_id,
        "selection_id": selection,
        "revision": revision,
        "script_draft": str(draft_path),
        "section_state": str(state_path),
        "alternatives": str(alternatives_path),
        "transaction": str(transaction_path),
    }
