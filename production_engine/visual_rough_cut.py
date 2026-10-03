"""Build provenance-bound rough-cut manifests from reviewed visual candidates.

A selected visual is treated as usable media only when a current managed local
asset record exists and its file/provenance hashes remain current. Editorial
selections that passed the Human Rights/Context Gate but have not been supplied
locally remain explicit placeholders. Paid visual generation stays locked.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from visual_search import shot_fingerprint

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
STORYBOARD_DIR = OUTPUT / "storyboards"
RESULT_DIR = OUTPUT / "visual_search_results"
REVIEW_DIR = OUTPUT / "visual_candidate_reviews"
RIGHTS_DIR = OUTPUT / "visual_rights_reviews"
REGISTRY_DIR = OUTPUT / "managed_visual_asset_registry"
ROUGH_DIR = OUTPUT / "visual_rough_cuts"
SUMMARY = OUTPUT / "visual_rough_cut_summary.json"


def _key(cid: str, fmt: str) -> str:
    return f"{safe_slug(cid)}.{safe_slug(fmt)}"


def _registry_path(
    concept_id: str,
    fmt: str,
    shot_id: str,
) -> Path:
    return REGISTRY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.managed_visual_asset.json"
    )


def _managed_asset_current(
    record: dict[str, Any],
    *,
    decision: dict[str, Any],
) -> bool:
    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    result_path = Path(str(provenance.get("search_result") or ""))
    review_path = Path(str(provenance.get("candidate_review") or ""))
    if (
        not isinstance(provenance, dict)
        or not asset_path.is_file()
        or not result_path.is_file()
        or not review_path.is_file()
    ):
        return False
    if (
        record.get("candidate_id") != decision.get("candidate_id")
        or record.get("candidate_fingerprint")
        != decision.get("candidate_fingerprint")
        or record.get("asset_sha256") != sha256_file(asset_path)
        or provenance.get("search_result_sha256")
        != sha256_file(result_path)
        or provenance.get("candidate_review_sha256")
        != sha256_file(review_path)
    ):
        return False

    rights_source = str(provenance.get("rights_review") or "")
    if rights_source:
        rights_path = Path(rights_source)
        if (
            not rights_path.is_file()
            or provenance.get("rights_review_sha256")
            != sha256_file(rights_path)
        ):
            return False
    return True


def _managed_assets_for_branch(
    concept_id: str,
    fmt: str,
    review: dict[str, Any],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    assets: dict[str, tuple[Path, dict[str, Any]]] = {}
    decisions = review.get("decisions", {})
    if not isinstance(decisions, dict):
        return assets
    for shot_id, decision in decisions.items():
        if not isinstance(decision, dict):
            continue
        path = _registry_path(concept_id, fmt, str(shot_id))
        if not path.is_file():
            continue
        try:
            record = load_json(path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if (
            isinstance(record, dict)
            and _managed_asset_current(record, decision=decision)
        ):
            assets[str(shot_id)] = (path, record)
    return assets


def build(
    board: dict[str, Any],
    review: dict[str, Any],
    rights: dict[str, Any] | None,
    board_path: Path,
    review_path: Path,
    rights_path: Path | None = None,
    managed_assets: dict[str, tuple[Path, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if board.get("status") != "READY_FOR_VISUAL_SEARCH":
        raise ValueError("Storyboard is not current for rough cut")
    if review.get("status") != "READY_FOR_ROUGH_CUT":
        raise ValueError("Candidate review is incomplete")
    if (
        board.get("concept_id"),
        board.get("format"),
    ) != (
        review.get("concept_id"),
        review.get("format"),
    ):
        raise ValueError("Storyboard/review identity mismatch")

    decisions = review.get("decisions", {})
    if not isinstance(decisions, dict):
        raise ValueError("Candidate review decisions must be an object")
    rights_decisions = (
        (rights or {}).get("decisions", {})
        if isinstance(rights or {}, dict)
        else {}
    )
    if not isinstance(rights_decisions, dict):
        rights_decisions = {}
    managed_assets = managed_assets or {}

    scenes: list[dict[str, Any]] = []
    registry_provenance: dict[str, dict[str, Any]] = {}
    for index, card in enumerate(board.get("cards", [])):
        if not isinstance(card, dict):
            continue
        shot_id = str(card.get("shot_id") or "")
        decision = decisions.get(shot_id, {})
        if not isinstance(decision, dict):
            decision = {}
        if (
            decision
            and decision.get("shot_fingerprint")
            != shot_fingerprint(card)
        ):
            raise ValueError(
                "STALE_CANDIDATE_REVIEW: storyboard shot changed after visual decision"
            )

        assignment: dict[str, Any] = {
            "status": "PLACEHOLDER",
            "candidate_id": None,
            "source_url": None,
            "asset_file": None,
            "asset_sha256": None,
            "reason": "UNRESOLVED_VISUAL_GAP",
        }

        selected_status = str(decision.get("status") or "")
        registry_state = managed_assets.get(shot_id)
        registry_path: Path | None = None
        registry: dict[str, Any] | None = None
        if registry_state is not None:
            registry_path, registry = registry_state
            if not _managed_asset_current(
                registry,
                decision=decision,
            ):
                registry_path = None
                registry = None

        if selected_status == "SELECTED":
            if registry is not None and registry_path is not None:
                assignment = {
                    "status": "MANAGED_EXISTING_ASSET",
                    "candidate_id": decision.get("candidate_id"),
                    "source_url": decision.get("candidate_source_url"),
                    "asset_file": registry.get("asset_file"),
                    "asset_sha256": registry.get("asset_sha256"),
                    "reason": "CURRENT_MANAGED_ASSET",
                }
                registry_provenance[shot_id] = {
                    "registry_file": str(registry_path.resolve()),
                    "registry_sha256": sha256_file(registry_path),
                    "asset_file": registry.get("asset_file"),
                    "asset_sha256": registry.get("asset_sha256"),
                }
            else:
                assignment.update(
                    {
                        "candidate_id": decision.get("candidate_id"),
                        "source_url": decision.get("candidate_source_url"),
                        "reason": "SELECTED_ASSET_NOT_ACQUIRED_CURRENT",
                    }
                )
        elif selected_status == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
            rights_decision = rights_decisions.get(shot_id, {})
            if (
                isinstance(rights_decision, dict)
                and rights_decision.get("approved_for_rough_cut") is True
            ):
                if registry is not None and registry_path is not None:
                    assignment = {
                        "status": "MANAGED_EDITORIAL_ASSET",
                        "candidate_id": decision.get("candidate_id"),
                        "source_url": decision.get("candidate_source_url"),
                        "asset_file": registry.get("asset_file"),
                        "asset_sha256": registry.get("asset_sha256"),
                        "reason": "CURRENT_MANAGED_EDITORIAL_ASSET",
                    }
                    registry_provenance[shot_id] = {
                        "registry_file": str(registry_path.resolve()),
                        "registry_sha256": sha256_file(registry_path),
                        "asset_file": registry.get("asset_file"),
                        "asset_sha256": registry.get("asset_sha256"),
                    }
                else:
                    assignment.update(
                        {
                            "candidate_id": decision.get("candidate_id"),
                            "source_url": decision.get("candidate_source_url"),
                            "reason": "EDITORIAL_ASSET_REQUIRES_MANUAL_SUPPLY",
                        }
                    )
            else:
                assignment.update(
                    {
                        "candidate_id": decision.get("candidate_id"),
                        "source_url": decision.get("candidate_source_url"),
                        "reason": "RIGHTS_CONTEXT_APPROVAL_REQUIRED_OR_REJECTED",
                    }
                )
        elif selected_status in {"REJECT_ALL", "NEEDS_BETTER_VISUAL"}:
            assignment["reason"] = selected_status

        scenes.append(
            {
                "scene_index": index,
                "shot_id": shot_id,
                "beat_id": card.get("beat_id"),
                "time_range": card.get("time_range"),
                "story_purpose": card.get("story_purpose"),
                "desired_visual": card.get("desired_visual"),
                "cinematic_direction": card.get(
                    "cinematic_direction",
                    {},
                ),
                "visual_value_score": card.get(
                    "visual_value_score",
                    {},
                ),
                "premium_generation_candidate": card.get(
                    "premium_generation_candidate",
                    False,
                ),
                "visual_assignment": assignment,
            }
        )

    gaps = [
        scene
        for scene in scenes
        if scene["visual_assignment"]["status"] == "PLACEHOLDER"
    ]
    managed_count = len(scenes) - len(gaps)
    return {
        "artifact": "visual_rough_cut_manifest",
        "concept_id": board.get("concept_id"),
        "format": board.get("format"),
        "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE",
        "premium_generation_allowed": False,
        "scenes": scenes,
        "summary": {
            "scenes": len(scenes),
            "placeholders": len(gaps),
            "managed_assets": managed_count,
            "manual_asset_gaps": sum(
                scene["visual_assignment"]["reason"]
                == "EDITORIAL_ASSET_REQUIRES_MANUAL_SUPPLY"
                for scene in gaps
            ),
        },
        "gate_policy": {
            "human_review_required_before_premium_visual_generation": True,
            "paid_visual_calls_allowed": False,
        },
        "provenance": {
            "storyboard": str(board_path.resolve()),
            "storyboard_sha256": sha256_file(board_path),
            "candidate_review": str(review_path.resolve()),
            "candidate_review_sha256": sha256_file(review_path),
            "rights_review": (
                str(rights_path.resolve())
                if rights_path is not None and rights_path.exists()
                else None
            ),
            "rights_review_sha256": (
                sha256_file(rights_path)
                if rights_path is not None and rights_path.exists()
                else None
            ),
            "managed_asset_registry": registry_provenance,
        },
    }


def prepare() -> dict[str, Any]:
    ROUGH_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    current_paths: set[Path] = set()
    board_paths = (
        sorted(STORYBOARD_DIR.glob("*.storyboard.json"))
        if STORYBOARD_DIR.exists()
        else []
    )

    for board_path in board_paths:
        board = load_json(board_path)
        concept_id = str(board.get("concept_id") or "")
        fmt = str(board.get("format") or "")
        key = _key(concept_id, fmt)
        review_path = REVIEW_DIR / f"{key}.visual_candidate_review.json"
        if not review_path.exists():
            continue
        review = load_json(review_path)
        rights_path = RIGHTS_DIR / f"{key}.visual_rights_review.json"
        rights = load_json(rights_path) if rights_path.exists() else None

        managed_assets = _managed_assets_for_branch(
            concept_id,
            fmt,
            review,
        )
        rough = build(
            board,
            review,
            rights,
            board_path,
            review_path,
            rights_path if rights_path.exists() else None,
            managed_assets,
        )
        destination = ROUGH_DIR / f"{key}.visual_rough_cut.json"
        atomic_write_json(destination, rough)
        current_paths.add(destination.resolve())
        items.append(
            {
                "concept_id": rough["concept_id"],
                "format": rough["format"],
                "rough_cut": str(destination),
                **rough["summary"],
            }
        )

    for stale in ROUGH_DIR.glob("*.visual_rough_cut.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    out = {
        "status": (
            "READY_FOR_HUMAN_ROUGH_CUT_GATE"
            if items
            else "WAITING_FOR_REVIEWED_VISUALS"
        ),
        "prepared": len(items),
        "items": items,
        "paid_visual_calls_allowed": False,
    }
    atomic_write_json(SUMMARY, out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build provenance-bound visual rough cuts"
    )
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
