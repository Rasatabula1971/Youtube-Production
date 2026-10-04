"""Slice 27 Final Packaging Human Gate.

Turns the Slice 26 validation matrix into one human-chosen package per format:
an exact title + thumbnail concept (and, by default, its approved thumbnail
image) + opening hook + Viewer Promise. Only validated PASS pairs can be
accepted. When no pair is good enough the reviewer routes targeted rework to
the layer that is actually weak: the title directions, the thumbnail concepts
or the script branch.

The reviewer is shown a 2–3 title shortlist first (D-134): every title is
ranked from its pair validations, and accepting a title outside the shortlist
needs a note. Accepted packages for every format of a concept form a hash-bound final
package bundle. Format planning consumes that bundle and goes stale when it
changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_STORY = _ROOT / "story_script_engine"
if str(_STORY) not in sys.path:
    sys.path.insert(0, str(_STORY))

from pipeline_integrity import atomic_write_json
import package_pairing
from packaging_brief import load_json
from story_script_engine import safe_slug
from title_shortlist import build_shortlist, shortlist_settings

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "final_packaging_gate_config.json"
MATURE_DIR = package_pairing.MATURE_DIR
STATE_FILE = MATURE_DIR / "final_packaging_gate_state.json"
FINAL_PACKAGES_DIR = MATURE_DIR / "final_packages"
HISTORY_DIR = MATURE_DIR / "final_packaging_history"
PRODUCTION_DIR = _ROOT / "production_engine"

SCHEMA_VERSION = "1.0"
DECISIONS = {"ACCEPT", "REWORK", "REJECT"}
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"
REWORK_SOURCE = "FINAL_PACKAGING_GATE"


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "acceptable_validation_statuses",
        "require_approved_thumbnail_image",
        "required_accept_criteria",
        "image_criterion",
        "rework_targets",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Final packaging gate config is missing: " + ", ".join(missing))
    return config


def required_criteria(config: dict[str, Any]) -> list[str]:
    criteria = [str(x) for x in config["required_accept_criteria"]]
    if config["require_approved_thumbnail_image"]:
        criteria.append(str(config["image_criterion"]))
    return criteria


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def render_id_for(video_id: str, thumbnail_id: str) -> str:
    """Same identity the thumbnail renderer gives a concept (D-098)."""
    return f"{video_id}--{thumbnail_id}"


def reviewer_id() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


# ------------------------------------------------------------------ inputs


def current_validations() -> list[dict[str, Any]] | None:
    """The complete current Slice 26 matrix, or None while it is not ready."""
    requests = package_pairing.request_snapshot()
    expected_pairs = int(requests.get("expected") or 0) * int(
        package_pairing.load_config()["package_pairing_validation"][
            "evaluations_per_request"
        ]
    )
    if expected_pairs <= 0 or not requests.get("ready"):
        return None
    validations, rejected = package_pairing._collect_current()
    if rejected or len(validations) != expected_pairs:
        return None
    return validations


def thumbnail_approvals() -> dict[str, dict[str, Any]]:
    """Current Human Thumbnail Gate approvals keyed by render_id."""
    if str(PRODUCTION_DIR) not in sys.path:
        sys.path.insert(0, str(PRODUCTION_DIR))
    import thumbnail_render

    return thumbnail_render.current_approvals()


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.is_file():
        return {"decisions": {}, "reworks": []}
    state = load_json(STATE_FILE)
    if not isinstance(state, dict):
        return {"decisions": {}, "reworks": []}
    if not isinstance(state.get("decisions"), dict):
        state["decisions"] = {}
    if not isinstance(state.get("reworks"), list):
        state["reworks"] = []
    return state


def _save_state(state: dict[str, Any]) -> None:
    atomic_write_json(
        STATE_FILE,
        {
            "artifact": "final_packaging_gate_state",
            "schema_version": SCHEMA_VERSION,
            "decisions": state.get("decisions", {}),
            "reworks": state.get("reworks", []),
        },
    )


def _archive(record: dict[str, Any]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(record.get("reviewed_at") or "").replace(":", "-")
    name = f"{safe_slug(str(record.get('video_id') or 'unknown'))}.{stamp}.final_packaging_decision.json"
    atomic_write_json(HISTORY_DIR / name, record)


# ------------------------------------------------------------------ snapshot


STATUS_ORDER = {"PASS": 0, "REWORK": 1, "REJECT": 2}


def _package_view(
    package: dict[str, Any],
    *,
    config: dict[str, Any],
    approvals: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    video_id = str(package.get("video_id") or "")
    thumbnail_id = str(package.get("thumbnail_id") or "")
    render_id = render_id_for(video_id, thumbnail_id)
    approval = approvals.get(render_id)
    status = str(package.get("validation_status") or "")
    blocked: list[str] = []
    if status not in set(config["acceptable_validation_statuses"]):
        blocked.append(f"Slice 26 validation is {status}, not PASS")
    if config["require_approved_thumbnail_image"] and approval is None:
        blocked.append("thumbnail image is not approved at the Thumbnail Gate")
    return {
        "package_id": package.get("package_id"),
        "fingerprint": content_hash(package),
        "title_id": package.get("title_id"),
        "title_text": package.get("title_text"),
        "title_character_count": package.get("title_character_count"),
        "title_search_intent": package.get("title_search_intent"),
        "selected_title_direction_match": package.get("selected_title_direction_match"),
        "thumbnail_id": thumbnail_id,
        "thumbnail_text": package.get("thumbnail_text"),
        "thumbnail_hero_subject": package.get("thumbnail_hero_subject"),
        "thumbnail_secondary_element": package.get("thumbnail_secondary_element"),
        "thumbnail_visual_anomaly": package.get("thumbnail_visual_anomaly"),
        "thumbnail_viewer_visual_question": package.get("thumbnail_viewer_visual_question"),
        "angle_primary_driver": package.get("angle_primary_driver"),
        "validation_status": status,
        "promise_consistency": package.get("promise_consistency"),
        "promise_alignment_reason": package.get("promise_alignment_reason"),
        "hook_alignment_status": package.get("hook_alignment_status"),
        "hook_alignment_reason": package.get("hook_alignment_reason"),
        "semantic_redundancy": package.get("semantic_redundancy"),
        "diagnostics": package.get("diagnostics", {}),
        "hard_validation_findings": package.get("hard_validation_findings", []),
        "rework_findings": package.get("rework_findings", []),
        "render_id": render_id,
        "image_approved": approval is not None,
        "image_sha256": approval.get("image_sha256") if approval else None,
        "acceptable": not blocked,
        "blocked_reasons": blocked,
    }


def _decision_view(
    decision: dict[str, Any] | None,
    *,
    packages: list[dict[str, Any]],
    matrix_fingerprint: str,
) -> tuple[str, dict[str, Any], bool]:
    """Return (decision, record, stale) for the saved decision on one format."""
    if not isinstance(decision, dict):
        return "PENDING", {}, False
    value = str(decision.get("decision") or "")
    if value == "ACCEPT":
        chosen = next(
            (p for p in packages if p["package_id"] == decision.get("package_id")),
            None,
        )
        if (
            chosen is not None
            and chosen["acceptable"]
            and chosen["fingerprint"] == decision.get("package_fingerprint")
            and chosen["image_sha256"] == decision.get("image_sha256")
        ):
            return "ACCEPT", decision, False
        return "PENDING", {}, True
    if value == "REJECT":
        if decision.get("matrix_fingerprint") == matrix_fingerprint:
            return "REJECT", decision, False
        return "PENDING", {}, True
    return "PENDING", {}, False


def _items(
    validations: list[dict[str, Any]],
    *,
    config: dict[str, Any],
    approvals: dict[str, dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for package in validations:
        grouped.setdefault(str(package.get("video_id") or ""), []).append(package)

    last_rework: dict[str, dict[str, Any]] = {}
    for record in state.get("reworks", []):
        if isinstance(record, dict):
            last_rework[str(record.get("video_id") or "")] = record

    items: list[dict[str, Any]] = []
    for video_id in sorted(grouped):
        raw = grouped[video_id]
        first = raw[0]
        views = [_package_view(p, config=config, approvals=approvals) for p in raw]
        shortlist = build_shortlist(views, shortlist_settings(config))
        rank = {title_id: index for index, title_id in enumerate(shortlist["title_ids"])}
        for view in views:
            view["in_title_shortlist"] = view["title_id"] in rank
        # Shortlisted titles first (PASS pairs first, then shortlist order); the
        # rest stay reachable.
        packages = sorted(
            views,
            key=lambda p: (
                not p["in_title_shortlist"],
                STATUS_ORDER.get(p["validation_status"], 3),
                rank.get(p["title_id"], len(rank)),
                not p["selected_title_direction_match"],
                str(p["package_id"]),
            ),
        )
        matrix_fingerprint = content_hash(sorted(p["fingerprint"] for p in packages))
        decision, record, stale = _decision_view(
            state["decisions"].get(video_id),
            packages=packages,
            matrix_fingerprint=matrix_fingerprint,
        )
        items.append(
            {
                "video_id": video_id,
                "concept_id": first.get("concept_id"),
                "format": first.get("format"),
                "viewer_promise": first.get("viewer_promise"),
                "opening_hook": first.get("opening_hook"),
                "matrix_fingerprint": matrix_fingerprint,
                "pass": sum(p["validation_status"] == "PASS" for p in packages),
                "rework": sum(p["validation_status"] == "REWORK" for p in packages),
                "reject": sum(p["validation_status"] == "REJECT" for p in packages),
                "acceptable": sum(p["acceptable"] for p in packages),
                "title_shortlist": shortlist,
                "packages": packages,
                "decision": decision,
                "selected_package_id": record.get("package_id"),
                "criteria": record.get("criteria", {}),
                "note": record.get("note", ""),
                "reviewer": record.get("reviewer"),
                "reviewed_at": record.get("reviewed_at"),
                "stale_decision": stale,
                "last_rework": last_rework.get(video_id),
            }
        )
    return items


def snapshot() -> dict[str, Any]:
    config = load_config()
    state = _load_state()
    validations = current_validations()
    base = {
        "required_criteria": required_criteria(config),
        "require_approved_thumbnail_image": bool(
            config["require_approved_thumbnail_image"]
        ),
        "rework_targets": list(config["rework_targets"]),
        "last_reworks": state.get("reworks", [])[-5:],
    }
    if validations is None:
        return {
            **base,
            "status": "WAITING_FOR_PACKAGE_VALIDATION",
            "ready": False,
            "complete": False,
            "items": [],
            "concepts": [],
        }
    approvals = (
        thumbnail_approvals() if config["require_approved_thumbnail_image"] else {}
    )
    items = _items(validations, config=config, approvals=approvals, state=state)
    pending = sum(item["decision"] == "PENDING" for item in items)
    accepted = sum(item["decision"] == "ACCEPT" for item in items)
    rejected = sum(item["decision"] == "REJECT" for item in items)
    complete = bool(items) and pending == 0
    ready = complete and accepted == len(items)

    concepts: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        concepts.setdefault(str(item["concept_id"] or ""), []).append(item)
    concept_rows = [
        {
            "concept_id": concept_id,
            "formats": sorted(str(x["format"]) for x in rows),
            "approved": all(x["decision"] == "ACCEPT" for x in rows),
        }
        for concept_id, rows in sorted(concepts.items())
    ]
    return {
        **base,
        "status": (
            "FINAL_PACKAGING_APPROVED"
            if ready
            else "FINAL_PACKAGING_REJECTED"
            if complete and rejected
            else "AWAITING_HUMAN_FINAL_PACKAGING"
        ),
        "ready": ready,
        "complete": complete,
        "pending": pending,
        "accepted": accepted,
        "rejected": rejected,
        "items": items,
        "concepts": concept_rows,
        "_validations": validations,
    }


def public_snapshot() -> dict[str, Any]:
    payload = snapshot()
    payload.pop("_validations", None)
    return payload


# ------------------------------------------------------------------ bundles


def _bundle_for(
    concept_id: str,
    items: list[dict[str, Any]],
    validations: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any] | None:
    rows = [item for item in items if str(item["concept_id"]) == concept_id]
    if not rows or any(item["decision"] != "ACCEPT" for item in rows):
        return None
    by_id = {str(p.get("package_id")): p for p in validations}
    approvals: dict[str, dict[str, Any]] | None = None
    packages: dict[str, Any] = {}
    for item in rows:
        decision = state["decisions"][item["video_id"]]
        package = by_id[str(decision["package_id"])]
        view = next(p for p in item["packages"] if p["package_id"] == decision["package_id"])
        image = None
        if view["image_approved"]:
            if approvals is None:
                approvals = thumbnail_approvals()
            record = approvals[view["render_id"]]
            image = {
                "render_id": view["render_id"],
                "image": record.get("image"),
                "image_sha256": record.get("image_sha256"),
                "width": record.get("width"),
                "height": record.get("height"),
                "template_id": record.get("template_id"),
                "subject_image": record.get("subject_image"),
            }
        packages[str(item["format"])] = {
            "video_id": item["video_id"],
            "format": item["format"],
            "package_id": package.get("package_id"),
            "title_id": package.get("title_id"),
            "title_text": package.get("title_text"),
            "title_search_intent": package.get("title_search_intent"),
            "thumbnail_id": package.get("thumbnail_id"),
            "thumbnail_text": package.get("thumbnail_text"),
            "thumbnail_concept": {
                "hero_subject": package.get("thumbnail_hero_subject"),
                "secondary_element": package.get("thumbnail_secondary_element"),
                "visual_anomaly": package.get("thumbnail_visual_anomaly"),
                "visual_action": package.get("thumbnail_visual_action"),
                "viewer_visual_question": package.get("thumbnail_viewer_visual_question"),
                "evidence_refs": package.get("thumbnail_evidence_refs", []),
            },
            "thumbnail_image": image,
            "psychological_angle": package.get("angle_primary_driver"),
            "opening_hook": package.get("opening_hook"),
            "viewer_promise": package.get("viewer_promise"),
            "title_evidence_refs": package.get("title_evidence_refs", []),
            "validation_status": package.get("validation_status"),
            "diagnostics": package.get("diagnostics", {}),
            "decision": {
                "reviewer": decision.get("reviewer"),
                "reviewed_at": decision.get("reviewed_at"),
                "criteria": decision.get("criteria", {}),
                "note": decision.get("note", ""),
            },
            "provenance": {
                "package_fingerprint": decision.get("package_fingerprint"),
                "package_validation_request_sha256": package.get("request_sha256"),
                "package_validation_response_sha256": package.get("response_sha256"),
            },
        }
    return {
        "artifact": "final_package_bundle",
        "schema_version": SCHEMA_VERSION,
        "status": "FINAL_PACKAGE_APPROVED",
        "concept_id": concept_id,
        "contract": "EXACT_TITLE_THUMBNAIL_HOOK_PROMISE_UNIT",
        "formats": sorted(packages),
        "packages": packages,
    }


def bundle_path(concept_id: str) -> Path:
    return FINAL_PACKAGES_DIR / f"{safe_slug(concept_id)}.final_package.json"


def current_bundles(payload: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Current approved bundles keyed by concept_id (computed, not read from disk)."""
    payload = payload or snapshot()
    validations = payload.get("_validations")
    if not isinstance(validations, list):
        return {}
    state = _load_state()
    out: dict[str, dict[str, Any]] = {}
    for row in payload.get("concepts", []):
        concept_id = str(row.get("concept_id") or "")
        if not row.get("approved"):
            continue
        bundle = _bundle_for(concept_id, payload["items"], validations, state)
        if bundle is not None:
            out[concept_id] = bundle
    return out


def current_bundle_hashes() -> dict[str, str]:
    return {cid: content_hash(bundle) for cid, bundle in current_bundles().items()}


def sync_bundles(payload: dict[str, Any] | None = None) -> dict[str, Path]:
    """Write current bundles and remove any that are no longer current."""
    bundles = current_bundles(payload)
    written: dict[str, Path] = {}
    for concept_id, bundle in bundles.items():
        path = bundle_path(concept_id)
        existing = load_json(path) if path.is_file() else None
        if existing != bundle:
            atomic_write_json(path, bundle)
        written[concept_id] = path
    if FINAL_PACKAGES_DIR.exists():
        keep = {path.resolve() for path in written.values()}
        for path in FINAL_PACKAGES_DIR.glob("*.final_package.json"):
            if path.resolve() not in keep:
                path.unlink()
    return written


def approved_bundle(concept_id: str) -> tuple[Path, dict[str, Any], str] | None:
    """The current bundle for one concept, written to disk, with its content hash."""
    bundle = current_bundles().get(concept_id)
    if bundle is None:
        stale = bundle_path(concept_id)
        if stale.is_file():
            stale.unlink()
        return None
    path = bundle_path(concept_id)
    if not path.is_file() or load_json(path) != bundle:
        atomic_write_json(path, bundle)
    return path, bundle, content_hash(bundle)


# ------------------------------------------------------------------ actions


def _route_rework(item: dict[str, Any], target: str, note: str) -> None:
    tagged = f"Final Packaging Gate ({item['format']}): {note}"
    concept_id = str(item["concept_id"])
    if target == "TITLE_DIRECTIONS":
        from title_direction_review import reopen_for_rework

        reopen_for_rework(concept_id=concept_id, note=tagged)
    elif target == "THUMBNAIL_CONCEPTS":
        from thumbnail_concepts import request_rework

        concepts = package_pairing._current_thumbnail_items().get(item["video_id"], {})
        request_rework(
            video_id=str(item["video_id"]),
            note=tagged,
            source=REWORK_SOURCE,
            previous_concepts=list(concepts.get("thumbnail_concepts", [])),
        )
    elif target == "SCRIPT":
        import script_review

        script_review.apply_action(
            concept_id=concept_id,
            format=str(item["format"]),
            decision="REWORK",
            criteria={},
            note=tagged,
        )
    else:
        raise ValueError(f"Unknown rework target: {target}")


def apply_action(
    *,
    video_id: str,
    decision: str,
    package_id: str | None = None,
    criteria: dict[str, Any] | None = None,
    note: str = "",
    rework_target: str | None = None,
) -> dict[str, Any]:
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Decision must be ACCEPT, REWORK, or REJECT")
    payload = snapshot()
    if payload["status"] == "WAITING_FOR_PACKAGE_VALIDATION":
        raise ValueError("Final Packaging Gate is waiting for a complete current package validation")
    item = next((x for x in payload["items"] if x["video_id"] == str(video_id)), None)
    if item is None:
        raise ValueError("Unknown video_id for the Final Packaging Gate")
    config = load_config()
    clean_note = str(note or "").strip()
    state = _load_state()
    record: dict[str, Any] = {
        "artifact": "final_packaging_decision",
        "schema_version": SCHEMA_VERSION,
        "video_id": item["video_id"],
        "concept_id": item["concept_id"],
        "format": item["format"],
        "decision": value,
        "note": clean_note,
        "reviewer": reviewer_id(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "matrix_fingerprint": item["matrix_fingerprint"],
    }

    if value == "ACCEPT":
        chosen = next(
            (p for p in item["packages"] if p["package_id"] == str(package_id or "")),
            None,
        )
        if chosen is None:
            raise ValueError("ACCEPT requires one package_id from the current matrix")
        if not chosen["acceptable"]:
            raise ValueError(
                "Package cannot be accepted: " + "; ".join(chosen["blocked_reasons"])
            )
        if not chosen.get("in_title_shortlist") and not clean_note:
            raise ValueError(
                "This title is outside the shortlist; add a note saying why you chose it"
            )
        given = criteria or {}
        normalized = {name: given.get(name) is True for name in required_criteria(config)}
        missing = [name for name, passed in normalized.items() if not passed]
        if missing:
            raise ValueError("ACCEPT requires " + ", ".join(missing))
        record.update(
            {
                "package_id": chosen["package_id"],
                "package_fingerprint": chosen["fingerprint"],
                "image_sha256": chosen["image_sha256"],
                "render_id": chosen["render_id"] if chosen["image_approved"] else None,
                "criteria": normalized,
                "title_in_shortlist": bool(chosen.get("in_title_shortlist")),
            }
        )
        state["decisions"][item["video_id"]] = record
    elif value == "REWORK":
        target = str(rework_target or "").strip().upper()
        if target not in set(config["rework_targets"]):
            raise ValueError(
                "REWORK requires a target: " + ", ".join(config["rework_targets"])
            )
        if not clean_note:
            raise ValueError("REWORK requires an authoritative human note")
        _route_rework(item, target, clean_note)
        record["rework_target"] = target
        state["decisions"].pop(item["video_id"], None)
        state["reworks"].append(
            {
                key: record[key]
                for key in (
                    "video_id", "concept_id", "format", "rework_target",
                    "note", "reviewer", "reviewed_at",
                )
            }
        )
    else:
        state["decisions"][item["video_id"]] = record

    _save_state(state)
    _archive(record)
    sync_bundles()
    return public_snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Final Packaging Human Gate")
    parser.add_argument("--mode", choices=("status", "sync"), required=True)
    args = parser.parse_args()
    if args.mode == "sync":
        paths = sync_bundles()
        result = {"status": "SYNCED", "bundles": {k: str(v) for k, v in paths.items()}}
    else:
        result = public_snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
