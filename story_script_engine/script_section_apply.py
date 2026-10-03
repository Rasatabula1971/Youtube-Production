"""Human selection and safe application of script rework alternatives.

Slice 5 is destructive only after explicit human selection. It changes one
chosen target, verifies the exact Slice 4 alternatives artifact/model response,
serializes the mutation with canonical section state, preserves exact parent
versions, and protects every touched file with recoverable transaction
snapshots.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from story_script_engine import OUTPUT_DIR, load_json, safe_slug, sha256_file, validate_script_response
from script_section_state import (
    SECTION_STATE_ACTION_LOCK,
    assert_state_matches_draft,
    build_targets,
    validate_state,
)
from script_section_rework_runner import (
    REWORK_RESPONSES_DIR,
    alternatives_artifact_integrity_errors,
    assert_request_current,
    validate_response as validate_rework_response,
    validation_contract_sha256 as rework_validation_contract_sha256,
)

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


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(str(value).encode("utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    path = path.resolve()
    root = root.resolve()
    return path == root or root in path.parents


def _snapshot_file(
    destination: Path,
    *,
    backup_dir: Path,
    key: str,
) -> dict[str, Any]:
    destination = destination.resolve()
    backup_dir = backup_dir.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Transaction destination is not a file: {destination}")

    existed = destination.is_file()
    snapshot: dict[str, Any] = {
        "destination": str(destination),
        "existed": existed,
        "backup": None,
        "sha256_before": None,
        "backup_sha256": None,
    }
    if existed:
        payload = destination.read_bytes()
        backup = backup_dir / f"{safe_slug(key)}.bin"
        _atomic_write_bytes(backup, payload)
        digest = _sha256_bytes(payload)
        snapshot["backup"] = str(backup.resolve())
        snapshot["sha256_before"] = digest
        snapshot["backup_sha256"] = digest
    return snapshot


def _validated_snapshot_paths(
    snapshot: dict[str, Any],
    *,
    allowed_backup_root: Path,
) -> tuple[Path, Path | None]:
    if not isinstance(snapshot, dict):
        raise ValueError("Transaction file snapshot must be an object")
    destination_text = str(snapshot.get("destination") or "").strip()
    if not destination_text:
        raise ValueError("Transaction file snapshot is missing destination")
    destination = Path(destination_text).resolve()
    existed = snapshot.get("existed")
    if not isinstance(existed, bool):
        raise ValueError("Transaction file snapshot existed must be boolean")

    if not existed:
        if destination.exists() and not destination.is_file():
            raise ValueError(
                f"Cannot roll back non-file destination: {destination}"
            )
        return destination, None

    backup_text = str(snapshot.get("backup") or "").strip()
    expected_hash = str(snapshot.get("backup_sha256") or "").strip()
    if not backup_text or not expected_hash:
        raise ValueError("Transaction file snapshot is missing backup metadata")
    backup = Path(backup_text).resolve()
    if not _is_within(backup, allowed_backup_root):
        raise ValueError("Transaction backup path escapes backup root")
    if not backup.is_file():
        raise ValueError(f"Cannot recover transaction: missing backup {backup}")
    if sha256_file(backup) != expected_hash:
        raise ValueError("Transaction backup hash changed")
    return destination, backup


def _restore_file_snapshot(
    snapshot: dict[str, Any],
    *,
    allowed_backup_root: Path,
) -> None:
    destination, backup = _validated_snapshot_paths(
        snapshot,
        allowed_backup_root=allowed_backup_root,
    )
    if backup is None:
        if destination.exists():
            destination.unlink()
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(destination, backup.read_bytes())
    expected_before = str(snapshot.get("sha256_before") or "").strip()
    if expected_before and sha256_file(destination) != expected_before:
        raise ValueError("Transaction recovery did not restore exact file bytes")


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
    """Roll back a PREPARED/IN_PROGRESS script-edit transaction from backups."""
    transaction_path = transaction_path.resolve()
    transaction = load_json(transaction_path)
    status = str(transaction.get("status") or "")
    if status not in {"PREPARED", "IN_PROGRESS"}:
        return transaction

    snapshots = transaction.get("file_snapshots")
    if isinstance(snapshots, dict):
        if not snapshots:
            raise ValueError("Script edit transaction has no file snapshots")
        allowed_backup_root = transaction_path.parent / "backups"
        # Preflight every snapshot before changing any destination.
        for key in sorted(snapshots):
            _validated_snapshot_paths(
                snapshots[key],
                allowed_backup_root=allowed_backup_root,
            )
        for key in sorted(snapshots):
            _restore_file_snapshot(
                snapshots[key],
                allowed_backup_root=allowed_backup_root,
            )
    else:
        # Legacy transaction compatibility for pre-Slice-5 journals.
        backups = transaction.get("backups")
        destinations = transaction.get("destinations")
        if not isinstance(backups, dict) or not isinstance(destinations, dict):
            raise ValueError("Script edit transaction is missing backup metadata")
        if not backups or set(backups) != set(destinations):
            raise ValueError(
                "Script edit transaction backup metadata is inconsistent"
            )

        for key in sorted(destinations):
            backup = Path(str(backups.get(key) or "")).resolve()
            destination = Path(str(destinations.get(key) or "")).resolve()
            if not backup.is_file():
                raise ValueError(
                    f"Cannot recover script edit transaction: missing {key} backup"
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
        transactions_dir.glob(f"{branch}.*transaction.json")
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
    *,
    operation_label: str = "Selected alternative",
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
            f"{operation_label} fails full script validation: "
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
    action_label: str = "SELECT_ALTERNATIVE",
    selection_id: str | None = None,
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
    history_item = {
        "state_version": new_state["state_version"],
        "reviewed_at": new_state["updated_at"],
        "reviewer": reviewer,
        "target_id": selected_target_id,
        "action": action_label,
    }
    if selection_id is not None:
        history_item["selection_id"] = selection_id
    history.append(history_item)
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


def _manual_edit_transaction_paths(
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
    transaction = transactions_dir / f"{stem}.manual_edit_transaction.json"
    backups = transactions_dir / "backups" / f"{stem}.manual_edit"
    return transaction, backups


def _bound_script_request_from_draft(
    draft: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    provenance = draft.get("draft_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Script draft is missing draft_provenance")

    request_path = Path(
        str(provenance.get("request_source") or "")
    ).resolve()
    expected_hash = str(provenance.get("request_sha256") or "")
    if not request_path.is_file() or not expected_hash:
        raise ValueError("Script draft is missing its bound script request")
    if sha256_file(request_path) != expected_hash:
        raise ValueError("STALE_SCRIPT_REQUEST: original script request changed")

    request = load_json(request_path)
    if str(request.get("concept_id") or "") != str(
        draft.get("concept_id") or ""
    ):
        raise ValueError("Script request concept_id mismatch")
    if str(request.get("format") or "") != str(draft.get("format") or ""):
        raise ValueError("Script request format mismatch")
    return request_path, request


def _text_for_target(draft: dict[str, Any], target_id: str) -> str:
    if target_id == "hook:opening":
        return str(draft.get("opening_hook") or "")
    if target_id == "closing:closing":
        return str(draft.get("closing") or "")
    if target_id.startswith("section:"):
        section_id = target_id.split(":", 1)[1]
        for section in draft.get("sections", []):
            if (
                isinstance(section, dict)
                and str(section.get("section_id") or "") == section_id
            ):
                return str(section.get("narration") or "")
    raise ValueError(f"Unsupported or missing script target: {target_id}")


def _previous_version_path(
    *,
    concept_id: str,
    fmt: str,
    revision: int,
    versions_dir: Path,
) -> Path:
    return (
        versions_dir
        / _branch_key(concept_id, fmt)
        / f"revision_{revision - 1:04d}.script_draft.json"
    )


def _save_previous_version(
    old_draft: dict[str, Any],
    source_draft_path: Path,
    *,
    concept_id: str,
    fmt: str,
    revision: int,
    versions_dir: Path,
) -> Path:
    source_draft_path = source_draft_path.resolve()
    if load_json(source_draft_path) != old_draft:
        raise ValueError("Previous-version source does not match old draft payload")

    version_path = _previous_version_path(
        concept_id=concept_id,
        fmt=fmt,
        revision=revision,
        versions_dir=versions_dir,
    )
    source_bytes = source_draft_path.read_bytes()
    if version_path.exists():
        if not version_path.is_file() or version_path.read_bytes() != source_bytes:
            raise ValueError("Script version collision with different content")
    else:
        _atomic_write_bytes(version_path, source_bytes)

    if sha256_file(version_path) != sha256_file(source_draft_path):
        raise ValueError("Previous version is not an exact copy of parent draft")
    return version_path


def _apply_manual_edit_unlocked(
    draft_path: Path,
    state_path: Path,
    *,
    target_id: str,
    replacement_text: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Apply one human-written target replacement with full validation."""
    draft_path = draft_path.resolve()
    state_path = state_path.resolve()
    if not draft_path.is_file():
        raise FileNotFoundError(draft_path)
    if not state_path.is_file():
        raise FileNotFoundError(state_path)

    reviewer_value = str(reviewer or "").strip()
    if not reviewer_value:
        raise ValueError("reviewer is required")
    target_value = str(target_id or "").strip()
    if not target_value:
        raise ValueError("target_id is required")
    replacement = str(replacement_text or "").strip()
    if not replacement:
        raise ValueError("Manual edit requires non-empty replacement_text")

    initial_draft = load_json(draft_path)
    concept_id = str(initial_draft.get("concept_id") or "").strip()
    fmt = str(initial_draft.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Script draft identity is incomplete")

    recover_incomplete_transactions(
        concept_id,
        fmt,
        transactions_dir=transactions_dir,
    )

    old_draft = load_json(draft_path)
    old_state = load_json(state_path)
    assert_state_matches_draft(old_state, draft_path)

    state_target = next(
        (
            item
            for item in old_state.get("targets", [])
            if isinstance(item, dict)
            and item.get("target_id") == target_value
        ),
        None,
    )
    if not isinstance(state_target, dict):
        raise ValueError(f"Unknown script edit target: {target_value}")
    if state_target.get("locked") is True:
        raise ValueError("Locked target cannot be manually edited until unlocked")

    original_text = _text_for_target(old_draft, target_value)
    if " ".join(original_text.split()) == " ".join(replacement.split()):
        raise ValueError("Manual edit must change the selected target text")

    script_request_path, original_script_request = (
        _bound_script_request_from_draft(old_draft)
    )

    revised_draft = copy.deepcopy(old_draft)
    _replace_target_text(
        revised_draft,
        target_id=target_value,
        replacement_text=replacement,
    )
    _assert_only_selected_target_changed(
        old_draft,
        revised_draft,
        target_id=target_value,
        old_state=old_state,
    )
    validation = _validate_revised_script(
        revised_draft,
        original_script_request,
        operation_label="Manual edit",
    )

    prior_revision = (
        int(old_draft.get("human_revision", {}).get("revision", 0))
        if isinstance(old_draft.get("human_revision"), dict)
        else 0
    )
    revision = prior_revision + 1

    transaction_path, backup_dir = _manual_edit_transaction_paths(
        concept_id=concept_id,
        fmt=fmt,
        state_version=int(old_state.get("state_version") or 0),
        target_id=target_value,
        transactions_dir=transactions_dir,
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_draft = backup_dir / "draft.json"
    backup_state = backup_dir / "state.json"
    atomic_write_json(backup_draft, old_draft)
    atomic_write_json(backup_state, old_state)

    transaction = {
        "artifact": "script_section_manual_edit_transaction",
        "status": "PREPARED",
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_value,
        "reviewer": reviewer_value,
        "prepared_at": _utc_now(),
        "backups": {
            "draft": str(backup_draft.resolve()),
            "state": str(backup_state.resolve()),
        },
        "destinations": {
            "draft": str(draft_path),
            "state": str(state_path),
        },
    }
    transaction_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(transaction_path, transaction)

    try:
        transaction["status"] = "IN_PROGRESS"
        transaction["started_at"] = _utc_now()
        atomic_write_json(transaction_path, transaction)

        version_path = _save_previous_version(
            old_draft,
            draft_path,
            concept_id=concept_id,
            fmt=fmt,
            revision=revision,
            versions_dir=versions_dir,
        )

        parent_hash = sha256_file(draft_path)
        revised_draft["validation"] = validation
        revised_draft["human_revision"] = {
            "revision": revision,
            "parent_draft_sha256": parent_hash,
            "edit_type": "MANUAL_TARGET_EDIT",
            "edited_target_id": target_value,
            "edited_by": reviewer_value,
            "edited_at": _utc_now(),
            "previous_version": str(version_path.resolve()),
            "script_request": str(script_request_path),
            "script_request_sha256": sha256_file(script_request_path),
        }
        atomic_write_json(draft_path, revised_draft)

        new_state = _rebase_state(
            old_state,
            revised_draft,
            draft_path,
            selected_target_id=target_value,
            reviewer=reviewer_value,
            action_label="MANUAL_EDIT",
        )
        atomic_write_json(state_path, new_state)

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
        atomic_write_json(transaction_path, transaction)

    except Exception:
        recover_prepared_transaction(transaction_path)
        raise

    return {
        "status": "MANUAL_EDIT_APPLIED",
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_value,
        "revision": revision,
        "script_draft": str(draft_path),
        "section_state": str(state_path),
        "previous_version": str(version_path),
        "transaction": str(transaction_path),
    }


def _version_id_number(version_id: str) -> int:
    value = str(version_id or "").strip()
    if not re.fullmatch(r"revision_\d{4}", value):
        raise ValueError("version_id must match revision_NNNN")
    return int(value.split("_", 1)[1])


def _saved_version_path(
    concept_id: str,
    fmt: str,
    version_id: str,
    *,
    versions_dir: Path,
) -> Path:
    _version_id_number(version_id)
    return (
        versions_dir
        / _branch_key(concept_id, fmt)
        / f"{version_id}.script_draft.json"
    )


def list_saved_versions(
    current_draft: dict[str, Any],
    *,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
) -> list[dict[str, Any]]:
    """List branch-owned saved versions without exposing filesystem paths."""
    concept_id = str(current_draft.get("concept_id") or "").strip()
    fmt = str(current_draft.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Script draft identity is incomplete")

    current_provenance = current_draft.get("draft_provenance")
    current_request_hash = (
        str(current_provenance.get("request_sha256") or "")
        if isinstance(current_provenance, dict)
        else ""
    )
    current_request_source = (
        str(Path(str(current_provenance.get("request_source") or "")).resolve())
        if isinstance(current_provenance, dict)
        and str(current_provenance.get("request_source") or "").strip()
        else ""
    )

    branch_dir = versions_dir / _branch_key(concept_id, fmt)
    if not branch_dir.exists():
        return []

    versions: list[dict[str, Any]] = []
    for path in sorted(
        branch_dir.glob("revision_????.script_draft.json"),
        reverse=True,
    ):
        version_id = path.name.removesuffix(".script_draft.json")
        try:
            revision = _version_id_number(version_id)
            saved = load_json(path)
        except (ValueError, OSError, json.JSONDecodeError):
            continue

        saved_provenance = saved.get("draft_provenance")
        saved_request_hash = (
            str(saved_provenance.get("request_sha256") or "")
            if isinstance(saved_provenance, dict)
            else ""
        )
        saved_request_source = (
            str(Path(str(saved_provenance.get("request_source") or "")).resolve())
            if isinstance(saved_provenance, dict)
            and str(saved_provenance.get("request_source") or "").strip()
            else ""
        )
        compatible = bool(
            str(saved.get("concept_id") or "") == concept_id
            and str(saved.get("format") or "") == fmt
            and current_request_hash
            and saved_request_hash == current_request_hash
            and current_request_source
            and saved_request_source == current_request_source
        )
        human_revision = saved.get("human_revision")
        edit_type = (
            str(human_revision.get("edit_type") or "")
            if isinstance(human_revision, dict)
            else ""
        )
        versions.append(
            {
                "version_id": version_id,
                "revision": revision,
                "sha256": sha256_file(path),
                "compatible": compatible,
                "edit_type": edit_type or "MODEL_DRAFT",
                "opening_hook": saved.get("opening_hook"),
                "closing": saved.get("closing"),
            }
        )
    return versions


def _restore_transaction_paths(
    *,
    concept_id: str,
    fmt: str,
    state_version: int,
    version_id: str,
    transactions_dir: Path,
) -> tuple[Path, Path]:
    stem = (
        f"{_branch_key(concept_id, fmt)}."
        f"v{state_version}.{safe_slug(version_id)}"
    )
    transaction = transactions_dir / f"{stem}.restore_version_transaction.json"
    backups = transactions_dir / "backups" / f"{stem}.restore_version"
    return transaction, backups


def _reset_state_for_restored_draft(
    old_state: dict[str, Any],
    restored_draft: dict[str, Any],
    draft_path: Path,
    *,
    reviewer: str,
    version_id: str,
) -> dict[str, Any]:
    validation = validate_state(old_state)
    if not validation["valid"]:
        raise ValueError("Invalid section state: " + "; ".join(validation["errors"]))

    now = _utc_now()
    history = list(old_state.get("history", []))
    new_version = int(old_state.get("state_version") or 0) + 1
    history.append(
        {
            "state_version": new_version,
            "reviewed_at": now,
            "reviewer": reviewer,
            "action": "RESTORE_VERSION",
            "version_id": version_id,
            "decisions_reset": True,
        }
    )
    return {
        "artifact": "script_section_state",
        "schema_version": 1,
        "status": "READY_FOR_SECTION_REVIEW",
        "concept_id": restored_draft.get("concept_id"),
        "format": restored_draft.get("format"),
        "source_draft": str(draft_path.resolve()),
        "source_draft_sha256": sha256_file(draft_path),
        "state_version": new_version,
        "created_at": old_state.get("created_at") or now,
        "updated_at": now,
        "targets": build_targets(restored_draft),
        "history": history,
    }


def _restore_saved_version_unlocked(
    draft_path: Path,
    state_path: Path,
    *,
    version_id: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Restore one compatible saved branch as a new monotonic revision."""
    draft_path = draft_path.resolve()
    state_path = state_path.resolve()
    if not draft_path.is_file():
        raise FileNotFoundError(draft_path)
    if not state_path.is_file():
        raise FileNotFoundError(state_path)

    reviewer_value = str(reviewer or "").strip()
    if not reviewer_value:
        raise ValueError("reviewer is required")
    version_value = str(version_id or "").strip()
    _version_id_number(version_value)

    initial_draft = load_json(draft_path)
    concept_id = str(initial_draft.get("concept_id") or "").strip()
    fmt = str(initial_draft.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Script draft identity is incomplete")

    recover_incomplete_transactions(
        concept_id,
        fmt,
        transactions_dir=transactions_dir,
    )

    current_draft = load_json(draft_path)
    old_state = load_json(state_path)
    assert_state_matches_draft(old_state, draft_path)

    script_request_path, script_request = _bound_script_request_from_draft(
        current_draft
    )
    saved_path = _saved_version_path(
        concept_id,
        fmt,
        version_value,
        versions_dir=versions_dir,
    )
    if not saved_path.is_file():
        raise ValueError("Saved script version not found")
    saved_draft = load_json(saved_path)

    if str(saved_draft.get("concept_id") or "") != concept_id:
        raise ValueError("Saved version concept_id mismatch")
    if str(saved_draft.get("format") or "") != fmt:
        raise ValueError("Saved version format mismatch")

    saved_provenance = saved_draft.get("draft_provenance")
    current_provenance = current_draft.get("draft_provenance")
    if not isinstance(saved_provenance, dict) or not isinstance(
        current_provenance, dict
    ):
        raise ValueError("Saved/current draft provenance is missing")
    if str(saved_provenance.get("request_sha256") or "") != str(
        current_provenance.get("request_sha256") or ""
    ):
        raise ValueError("Saved version belongs to a different script request")
    saved_request_source = Path(
        str(saved_provenance.get("request_source") or "")
    ).resolve()
    if saved_request_source != script_request_path:
        raise ValueError("Saved version belongs to a different script request")

    validation = _validate_revised_script(
        saved_draft,
        script_request,
        operation_label="Saved version",
    )

    current_targets = _target_map(build_targets(current_draft))
    saved_targets = _target_map(build_targets(saved_draft))
    if set(current_targets) == set(saved_targets) and all(
        str(current_targets[target_id].get("target_sha256") or "")
        == str(saved_targets[target_id].get("target_sha256") or "")
        for target_id in current_targets
    ):
        raise ValueError("Selected saved version matches the current script")

    prior_revision = (
        int(current_draft.get("human_revision", {}).get("revision", 0))
        if isinstance(current_draft.get("human_revision"), dict)
        else 0
    )
    new_revision = prior_revision + 1

    transaction_path, backup_dir = _restore_transaction_paths(
        concept_id=concept_id,
        fmt=fmt,
        state_version=int(old_state.get("state_version") or 0),
        version_id=version_value,
        transactions_dir=transactions_dir,
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_draft = backup_dir / "draft.json"
    backup_state = backup_dir / "state.json"
    atomic_write_json(backup_draft, current_draft)
    atomic_write_json(backup_state, old_state)

    transaction: dict[str, Any] = {
        "artifact": "script_version_restore_transaction",
        "status": "PREPARED",
        "concept_id": concept_id,
        "format": fmt,
        "version_id": version_value,
        "reviewer": reviewer_value,
        "prepared_at": _utc_now(),
        "backups": {
            "draft": str(backup_draft.resolve()),
            "state": str(backup_state.resolve()),
        },
        "destinations": {
            "draft": str(draft_path),
            "state": str(state_path),
        },
    }
    transaction_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(transaction_path, transaction)

    try:
        transaction["status"] = "IN_PROGRESS"
        transaction["started_at"] = _utc_now()
        atomic_write_json(transaction_path, transaction)

        pre_restore_version = _save_previous_version(
            current_draft,
            draft_path,
            concept_id=concept_id,
            fmt=fmt,
            revision=new_revision,
            versions_dir=versions_dir,
        )

        parent_hash = sha256_file(draft_path)
        restored_draft = copy.deepcopy(saved_draft)
        restored_draft["draft_provenance"] = copy.deepcopy(
            current_draft.get("draft_provenance", {})
        )
        restored_draft["validation"] = validation
        restored_draft["human_revision"] = {
            "revision": new_revision,
            "parent_draft_sha256": parent_hash,
            "edit_type": "RESTORE_VERSION",
            "restored_version_id": version_value,
            "restored_version_sha256": sha256_file(saved_path),
            "restored_by": reviewer_value,
            "restored_at": _utc_now(),
            "pre_restore_version": str(pre_restore_version.resolve()),
            "script_request": str(script_request_path),
            "script_request_sha256": sha256_file(script_request_path),
        }
        atomic_write_json(draft_path, restored_draft)

        reset_state = _reset_state_for_restored_draft(
            old_state,
            restored_draft,
            draft_path,
            reviewer=reviewer_value,
            version_id=version_value,
        )
        atomic_write_json(state_path, reset_state)

        _invalidate_and_refresh_script_gate(
            restored_draft,
            draft_path,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )

        transaction["status"] = "COMMITTED"
        transaction["committed_at"] = _utc_now()
        transaction["resulting_draft_sha256"] = sha256_file(draft_path)
        transaction["resulting_state_sha256"] = sha256_file(state_path)
        transaction["new_revision"] = new_revision
        atomic_write_json(transaction_path, transaction)

    except Exception:
        recover_prepared_transaction(transaction_path)
        raise

    return {
        "status": "VERSION_RESTORED",
        "concept_id": concept_id,
        "format": fmt,
        "version_id": version_value,
        "revision": new_revision,
        "script_draft": str(draft_path),
        "section_state": str(state_path),
        "pre_restore_version": str(pre_restore_version),
        "transaction": str(transaction_path),
    }


def _apply_selection_unlocked(
    alternatives_path: Path,
    *,
    selection_id: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
    rework_responses_dir: Path = REWORK_RESPONSES_DIR,
) -> dict[str, Any]:
    """Apply ORIGINAL/A/B/C only after verifying all bound artifacts are current."""
    alternatives_path = alternatives_path.resolve()
    if not alternatives_path.is_file():
        raise FileNotFoundError(alternatives_path)

    artifact = load_json(alternatives_path)
    if artifact.get("artifact") != "script_section_alternatives":
        raise ValueError("Not a script_section_alternatives artifact")

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

    response_path = (
        rework_responses_dir
        / (
            f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
            f"{safe_slug(target_id)}.json"
        )
    ).resolve()
    integrity_errors = alternatives_artifact_integrity_errors(
        artifact,
        rework_request,
        request_path=request_path,
        response_path=response_path,
        contract_hash=rework_validation_contract_sha256(),
    )
    if integrity_errors:
        raise ValueError(
            "Alternatives artifact integrity check failed: "
            + "; ".join(integrity_errors)
        )

    if str(artifact.get("concept_id") or "") != str(
        rework_request.get("concept_id") or ""
    ):
        raise ValueError("STALE_ALTERNATIVES: concept_id mismatch")
    if str(artifact.get("format") or "") != str(
        rework_request.get("format") or ""
    ):
        raise ValueError("STALE_ALTERNATIVES: format mismatch")
    if str(artifact.get("target_id") or "") != str(
        rework_request.get("target_id") or ""
    ):
        raise ValueError("STALE_ALTERNATIVES: target_id mismatch")
    if str(artifact.get("target_sha256") or "") != str(
        rework_request.get("target_sha256") or ""
    ):
        raise ValueError("STALE_ALTERNATIVES: target hash mismatch")
    if int(artifact.get("state_version") or 0) != int(
        rework_request.get("state_version") or -1
    ):
        raise ValueError("STALE_ALTERNATIVES: state version mismatch")
    if artifact.get("original", {}).get("text") != rework_request.get(
        "selected_target", {}
    ).get("original_text"):
        raise ValueError("STALE_ALTERNATIVES: original text mismatch")
    if artifact.get("original", {}).get(
        "immutable_metadata", {}
    ) != rework_request.get("selected_target", {}).get(
        "immutable_metadata", {}
    ):
        raise ValueError("STALE_ALTERNATIVES: immutable metadata mismatch")

    regenerated_response = {
        "concept_id": artifact.get("concept_id"),
        "format": artifact.get("format"),
        "target_id": artifact.get("target_id"),
        "alternatives": artifact.get("alternatives", []),
    }
    regenerated_validation = validate_rework_response(
        regenerated_response,
        rework_request,
    )
    if not regenerated_validation["valid"]:
        raise ValueError(
            "Alternatives artifact failed revalidation: "
            + "; ".join(regenerated_validation["errors"])
        )

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

    # _alternative_by_id returns None exactly when the selection is ORIGINAL.
    selected = _alternative_by_id(artifact, selection)
    replacement_text = (
        str(artifact.get("original", {}).get("text") or "")
        if selected is None
        else str(selected.get("replacement_text") or "")
    )
    selected_claim_ids: list[Any] = (
        [] if selected is None else list(selected.get("claim_ids_used", []))
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

    branch = _branch_key(concept_id, fmt)
    review_request_path = (
        review_requests_dir / f"{branch}.script_review_request.json"
    ).resolve()
    review_response_path = (
        review_responses_dir / f"{branch}.script_review_response.json"
    ).resolve()
    approved_path = (
        approved_dir / f"{safe_slug(concept_id)}.approved_script.json"
    ).resolve()
    version_path = (
        _previous_version_path(
            concept_id=concept_id,
            fmt=fmt,
            revision=revision,
            versions_dir=versions_dir,
        ).resolve()
        if selection != "ORIGINAL"
        else None
    )

    mutable_files: dict[str, Path] = {
        "draft": draft_path,
        "state": state_path,
        "alternatives": alternatives_path,
        "script_review_request": review_request_path,
        "script_review_response": review_response_path,
        "approved_script": approved_path,
    }
    if version_path is not None:
        mutable_files["previous_version"] = version_path

    file_snapshots = {
        key: _snapshot_file(
            destination,
            backup_dir=backup_dir,
            key=key,
        )
        for key, destination in mutable_files.items()
    }
    parent_draft_sha256 = sha256_file(draft_path)
    parent_state_sha256 = sha256_file(state_path)
    alternatives_sha256_before_selection = sha256_file(alternatives_path)

    transaction = {
        "artifact": "script_section_selection_transaction",
        "schema_version": 2,
        "status": "PREPARED",
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_id,
        "selection_id": selection,
        "reviewer": reviewer_value,
        "prepared_at": _utc_now(),
        "parent_draft_sha256": parent_draft_sha256,
        "parent_state_sha256": parent_state_sha256,
        "alternatives_sha256_before_selection": (
            alternatives_sha256_before_selection
        ),
        "rework_request": str(request_path),
        "rework_request_sha256": sha256_file(request_path),
        "model_response": str(response_path),
        "model_response_sha256": sha256_file(response_path),
        "file_snapshots": file_snapshots,
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

            saved_version_path = _save_previous_version(
                old_draft,
                draft_path,
                concept_id=concept_id,
                fmt=fmt,
                revision=revision,
                versions_dir=versions_dir,
            )
            if version_path is None or saved_version_path.resolve() != version_path:
                raise ValueError("Previous-version path changed during selection")
            previous_version_sha256 = sha256_file(saved_version_path)
            if previous_version_sha256 != parent_draft_sha256:
                raise ValueError(
                    "Previous version hash does not match parent draft hash"
                )

            revised_draft["validation"] = validation
            revised_draft["human_revision"] = {
                "revision": revision,
                "parent_draft_sha256": parent_draft_sha256,
                "parent_state_sha256": parent_state_sha256,
                "selected_target_id": target_id,
                "selection_id": selection,
                "selected_by": reviewer_value,
                "selected_at": _utc_now(),
                "selected_replacement_sha256": _sha256_text(replacement_text),
                "selected_claim_ids_used": list(selected_claim_ids),
                "rework_request": str(request_path),
                "rework_request_sha256": sha256_file(request_path),
                "model_response": str(response_path),
                "model_response_sha256": sha256_file(response_path),
                "alternatives_artifact": str(alternatives_path),
                "alternatives_artifact_sha256_before_selection": (
                    alternatives_sha256_before_selection
                ),
                "previous_version": str(saved_version_path.resolve()),
                "previous_version_sha256": previous_version_sha256,
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
            "replacement_text_sha256": _sha256_text(replacement_text),
            "claim_ids_used": list(selected_claim_ids),
            "reviewer": reviewer_value,
            "selected_at": _utc_now(),
            "parent_draft_sha256": parent_draft_sha256,
            "parent_state_sha256": parent_state_sha256,
            "rework_request_sha256": sha256_file(request_path),
            "model_response_sha256": sha256_file(response_path),
            "resulting_draft_sha256": sha256_file(draft_path),
            "resulting_state_version": new_state.get("state_version"),
            "revision": revision,
        }
        atomic_write_json(alternatives_path, artifact)

        persisted_draft = load_json(draft_path)
        persisted_state = load_json(state_path)
        assert_state_matches_draft(persisted_state, draft_path)
        if selection == "ORIGINAL":
            if sha256_file(draft_path) != parent_draft_sha256:
                raise ValueError("ORIGINAL selection changed the Script Draft")
        else:
            _assert_only_selected_target_changed(
                old_draft,
                persisted_draft,
                target_id=target_id,
                old_state=old_state,
            )
            if version_path is None or sha256_file(version_path) != parent_draft_sha256:
                raise ValueError(
                    "Previous version does not preserve exact parent draft"
                )

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
        transaction["resulting_script_review_request_sha256"] = sha256_file(
            review_request_path
        )
        transaction["previous_version_sha256"] = (
            sha256_file(version_path)
            if version_path is not None and version_path.is_file()
            else None
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

def apply_manual_edit(
    draft_path: Path,
    state_path: Path,
    *,
    target_id: str,
    replacement_text: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Serialize a human manual target edit with all section-state mutations."""
    with SECTION_STATE_ACTION_LOCK:
        return _apply_manual_edit_unlocked(
            draft_path,
            state_path,
            target_id=target_id,
            replacement_text=replacement_text,
            reviewer=reviewer,
            versions_dir=versions_dir,
            transactions_dir=transactions_dir,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )


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
    rework_responses_dir: Path = REWORK_RESPONSES_DIR,
) -> dict[str, Any]:
    """Serialize ORIGINAL/A/B/C selection with all section-state mutations."""
    with SECTION_STATE_ACTION_LOCK:
        return _apply_selection_unlocked(
            alternatives_path,
            selection_id=selection_id,
            reviewer=reviewer,
            versions_dir=versions_dir,
            transactions_dir=transactions_dir,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
            rework_responses_dir=rework_responses_dir,
        )



def restore_saved_version(
    draft_path: Path,
    state_path: Path,
    *,
    version_id: str,
    reviewer: str,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path = SCRIPT_REVIEW_REQUESTS_DIR,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Serialize a saved-version restore with all section-state mutations."""
    with SECTION_STATE_ACTION_LOCK:
        return _restore_saved_version_unlocked(
            draft_path,
            state_path,
            version_id=version_id,
            reviewer=reviewer,
            versions_dir=versions_dir,
            transactions_dir=transactions_dir,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )
