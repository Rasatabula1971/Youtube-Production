"""The Short's package, built from its brief without the 25-pair matrix (D-190).

The Final Packaging Gate locks one title, thumbnail, hook and promise per
format after a 25-pair matrix and an approved thumbnail image. For a Short
that was most of a day of decisions for a 45-second video, and Shorts are
shown with a frame of the video anyway. A Short's package is therefore the
title chosen at the Title Direction step and the approved opening hook and
Viewer Promise from its Packaging Brief. Its thumbnail is made by the owner
from the generated prompt and uploaded (D-191). It has the same shape as an accepted Final Packaging bundle, so the
Format stage and publishing read it the same way.

Nothing here calls a model or invents wording: every field is copied from the
current brief, and the bundle carries no timestamp, so its hash changes only
when the brief does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.hashing import sha256_file
from core.request_memo import memoized
from packaging_engine import short_lane
from packaging_engine.packaging_brief import brief_is_current
from packaging_engine.packaging_brief import snapshot as packaging_brief_snapshot

SCHEMA_VERSION = "1.0"
DECIDER = "GATE_POLICY"


def build_bundle(brief_path: Path, brief: dict[str, Any]) -> dict[str, Any]:
    """The accepted package for one Short; raises when the brief lacks a chosen title."""
    if not short_lane.is_short_lane(brief):
        raise ValueError("Only a Short brief takes the Short lane")
    title = brief.get("selected_title")
    if not isinstance(title, dict) or not str(title.get("title_text") or "").strip():
        raise ValueError("MISSING_SELECTED_TITLE: choose the Short's title at the Title Direction step")
    promise = brief.get("viewer_promise_contract")
    promise = promise if isinstance(promise, dict) else {}
    video_id = str(brief.get("video_id") or "")
    title_id = str(title.get("title_id") or "")
    package = {
        "video_id": video_id,
        "format": "short",
        "package_id": f"{video_id}::short-lane::{title_id}",
        "title_id": title_id,
        "title_text": str(title["title_text"]).strip(),
        "title_search_intent": brief.get("search_vs_browse_intent"),
        "thumbnail_id": None,
        "thumbnail_text": None,
        "thumbnail_source": short_lane.UPLOADED,
        "thumbnail_concept": {
            "source": short_lane.UPLOADED,
            "note": "Made by the owner from the thumbnail prompt and uploaded.",
        },
        "thumbnail_image": None,
        "psychological_angle": title.get("psychological_angle"),
        "opening_hook": brief.get("opening_hook"),
        "viewer_promise": promise.get("viewer_expectation"),
        "title_evidence_refs": list(title.get("evidence_refs") or []),
        "validation_status": "SHORT_LANE",
        "diagnostics": {},
        "decision": {
            "decided_by": DECIDER,
            "criteria": {},
            "note": (
                "Short lane (D-190): the title chosen at Title Direction and the approved "
                "hook and promise; the thumbnail is made from its prompt and uploaded (D-191)."
            ),
        },
        "provenance": {
            "packaging_brief": str(brief_path.resolve()),
            "packaging_brief_sha256": sha256_file(brief_path),
        },
    }
    return {
        "artifact": "final_package_bundle",
        "schema_version": SCHEMA_VERSION,
        "status": "FINAL_PACKAGE_APPROVED",
        "concept_id": str(brief.get("concept_id") or ""),
        "contract": short_lane.CONTRACT,
        "formats": ["short"],
        "packages": {"short": package},
    }


@memoized
def current_bundles() -> dict[str, dict[str, Any]]:
    """The Short-lane bundle of every current Short brief, keyed by concept_id."""
    out: dict[str, dict[str, Any]] = {}
    if not short_lane.enabled():
        return out
    for item in packaging_brief_snapshot().get("briefs", []):
        if not isinstance(item, dict) or not item.get("short_lane"):
            continue
        path = Path(str(item.get("brief_file") or ""))
        brief = brief_is_current(path)
        if brief is None:
            continue
        try:
            bundle = build_bundle(path, brief)
        except ValueError:
            continue
        out[bundle["concept_id"]] = bundle
    return out


def lane_state() -> dict[str, Any]:
    """Which packaging work remains: the long-form steps, the Short packages, or both."""
    briefs = packaging_brief_snapshot()
    bundles = current_bundles()
    short_ids = sorted(
        str(item.get("concept_id"))
        for item in briefs.get("briefs", [])
        if isinstance(item, dict) and item.get("short_lane")
    )
    missing = [concept_id for concept_id in short_ids if concept_id not in bundles]
    return {
        "chain_needed": int(briefs.get("chain_current") or 0) > 0,
        "short_concept_ids": short_ids,
        "short_ready": not missing,
        "short_missing": missing,
        "short_packages": [
            {
                "concept_id": concept_id,
                "title_text": bundle["packages"]["short"]["title_text"],
                "thumbnail_source": short_lane.UPLOADED,
            }
            for concept_id, bundle in sorted(bundles.items())
        ],
    }
