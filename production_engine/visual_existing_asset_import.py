"""Register human-supplied local files for approved existing visuals.

This path is primarily for creator/editorial excerpts that the app deliberately
does not download automatically. It may also recover an approved stock/library
selection when automatic acquisition failed.

Registration does not determine copyright/fair-use legality. For editorial
selections it requires the existing Human Rights/Context Gate approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
RESULT_DIR = OUTPUT / "visual_search_results"
REVIEW_DIR = OUTPUT / "visual_candidate_reviews"
RIGHTS_DIR = OUTPUT / "visual_rights_reviews"
ASSET_DIR = OUTPUT / "managed_visual_assets"
REGISTRY_DIR = OUTPUT / "managed_visual_asset_registry"
ASSEMBLY_DIR = OUTPUT / "visual_assembly_plans"
SUMMARY_FILE = OUTPUT / "managed_visual_asset_snapshot.json"

MAX_ASSET_BYTES = 250 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".mkv",
    ".jpg", ".jpeg", ".png", ".webp",
}


def _hash_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _candidate(
    result: dict[str, Any],
    shot_id: str,
    candidate_id: str,
) -> dict[str, Any] | None:
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
    return next(
        (
            item
            for item in shot.get("candidates", [])
            if isinstance(item, dict)
            and str(item.get("candidate_id") or "") == candidate_id
        ),
        None,
    )


def _registry_path(
    concept_id: str,
    fmt: str,
    shot_id: str,
) -> Path:
    return REGISTRY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.managed_visual_asset.json"
    )


def _asset_path(
    concept_id: str,
    fmt: str,
    shot_id: str,
    extension: str,
) -> Path:
    return ASSET_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}{extension}"
    )


def _validate_review(
    review_path: Path,
    shot_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    if (
        not review_path.exists()
        or review_path.parent.resolve() != REVIEW_DIR.resolve()
    ):
        raise ValueError("Invalid visual candidate review")

    review = load_json(review_path)
    if str(review.get("status") or "") != "READY_FOR_ROUGH_CUT":
        raise ValueError("Visual candidate review is incomplete")

    result_path = Path(str(review.get("source_result") or ""))
    if (
        not result_path.exists()
        or result_path.parent.resolve() != RESULT_DIR.resolve()
        or review.get("source_result_sha256") != sha256_file(result_path)
    ):
        raise ValueError("STALE_VISUAL_CANDIDATE_REVIEW")

    decision = review.get("decisions", {}).get(shot_id)
    if not isinstance(decision, dict):
        raise ValueError("Shot has no approved visual selection")
    status = str(decision.get("status") or "")
    if status not in {
        "SELECTED",
        "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
    }:
        raise ValueError("Shot selection is not eligible for local asset supply")

    result = load_json(result_path)
    candidate_id = str(decision.get("candidate_id") or "")
    candidate = _candidate(result, shot_id, candidate_id)
    if candidate is None:
        raise ValueError("Current selected candidate cannot be found")
    if decision.get("candidate_fingerprint") != _hash_json(candidate):
        raise ValueError("STALE_SELECTED_VISUAL_CANDIDATE")

    if status == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
        rights_path = RIGHTS_DIR / review_path.name.replace(
            ".visual_candidate_review.json",
            ".visual_rights_review.json",
        )
        if not rights_path.exists():
            raise ValueError("Human Rights/Context Gate approval is required")
        rights = load_json(rights_path)
        if (
            rights.get("source_candidate_review_sha256")
            != sha256_file(review_path)
        ):
            raise ValueError("STALE_VISUAL_RIGHTS_REVIEW")
        rights_decision = rights.get("decisions", {}).get(shot_id)
        if (
            not isinstance(rights_decision, dict)
            or rights_decision.get("approved_for_rough_cut") is not True
            or str(rights_decision.get("candidate_id") or "") != candidate_id
        ):
            raise ValueError(
                "Human Rights/Context Gate approval is required"
            )

    return review, result, candidate, result_path


def register(
    *,
    candidate_review_file: str,
    shot_id: str,
    asset_file: str,
    note: str = "",
) -> dict[str, Any]:
    review_path = Path(candidate_review_file).resolve()
    review, result, candidate, result_path = _validate_review(
        review_path,
        str(shot_id),
    )

    source = Path(asset_file).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError("Local visual asset file does not exist")
    extension = source.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported local visual asset type")
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("Local visual asset file is empty")
    if size > MAX_ASSET_BYTES:
        raise ValueError("Local visual asset exceeds size limit")

    concept_id = str(result.get("concept_id") or "")
    fmt = str(result.get("format") or "")
    shot = str(shot_id)
    destination = _asset_path(
        concept_id,
        fmt,
        shot,
        extension,
    )
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if source != destination.resolve():
        shutil.copy2(source, destination)

    provenance: dict[str, Any] = {
        "search_result": str(result_path.resolve()),
        "search_result_sha256": sha256_file(result_path),
        "candidate_review": str(review_path.resolve()),
        "candidate_review_sha256": sha256_file(review_path),
    }
    rights_path = RIGHTS_DIR / review_path.name.replace(
        ".visual_candidate_review.json",
        ".visual_rights_review.json",
    )
    if rights_path.exists():
        provenance["rights_review"] = str(rights_path.resolve())
        provenance["rights_review_sha256"] = sha256_file(rights_path)

    record = {
        "artifact": "managed_visual_asset",
        "status": "ACQUIRED_CURRENT",
        "concept_id": concept_id,
        "format": fmt,
        "shot_id": shot,
        "candidate_id": candidate.get("candidate_id"),
        "source_tier": candidate.get("source_tier"),
        "search_provider": candidate.get("search_provider"),
        "source_url": candidate.get("source_url"),
        "license": candidate.get("license"),
        "creator": candidate.get("creator"),
        "acquisition_method": "MANUAL_HUMAN_SUPPLIED_FILE",
        "asset_file": str(destination.resolve()),
        "asset_sha256": sha256_file(destination),
        "asset_bytes": destination.stat().st_size,
        "paid_provider_call_executed": False,
        "estimated_cost_usd": 0.0,
        "candidate_fingerprint": _hash_json(candidate),
        "human_note": str(note or "").strip(),
        "policy_note": (
            "Registration records the local asset and prior human context "
            "decision; it is not a legal determination of fair use."
        ),
        "provenance": provenance,
    }

    registry_path = _registry_path(concept_id, fmt, shot)
    atomic_write_json(registry_path, record)

    assembly_path = ASSEMBLY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        "visual_assembly_plan.json"
    )
    if assembly_path.exists():
        assembly_path.unlink()

    return record


def _record_current(record: dict[str, Any]) -> bool:
    provenance = record.get("provenance", {})
    if not isinstance(provenance, dict):
        return False
    result_path = Path(str(provenance.get("search_result") or ""))
    review_path = Path(str(provenance.get("candidate_review") or ""))
    asset_path = Path(str(record.get("asset_file") or ""))
    if (
        not result_path.exists()
        or not review_path.exists()
        or not asset_path.exists()
        or provenance.get("search_result_sha256") != sha256_file(result_path)
        or provenance.get("candidate_review_sha256")
        != sha256_file(review_path)
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return False

    rights_source = str(provenance.get("rights_review") or "")
    if rights_source:
        rights_path = Path(rights_source)
        if (
            not rights_path.exists()
            or provenance.get("rights_review_sha256")
            != sha256_file(rights_path)
        ):
            return False
    return True


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    stale = 0
    paths = (
        sorted(REGISTRY_DIR.glob("*.managed_visual_asset.json"))
        if REGISTRY_DIR.exists()
        else []
    )
    for path in paths:
        record = load_json(path)
        if _record_current(record):
            items.append({**record, "registry_file": str(path)})
        else:
            stale += 1

    out = {
        "status": "MANAGED_VISUAL_ASSETS_READY" if items else "NO_CURRENT_MANAGED_VISUAL_ASSETS",
        "current": len(items),
        "stale": stale,
        "manual": sum(
            item.get("acquisition_method") == "MANUAL_HUMAN_SUPPLIED_FILE"
            for item in items
        ),
        "automatic": sum(
            item.get("acquisition_method") != "MANUAL_HUMAN_SUPPLIED_FILE"
            for item in items
        ),
        "items": items,
    }
    atomic_write_json(SUMMARY_FILE, out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register human-supplied approved visual asset"
    )
    parser.add_argument("--mode", choices=("register", "status"), required=True)
    parser.add_argument("--candidate-review-file")
    parser.add_argument("--shot-id")
    parser.add_argument("--asset-file")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if args.mode == "status":
        result = snapshot()
    else:
        if (
            not args.candidate_review_file
            or not args.shot_id
            or not args.asset_file
        ):
            raise SystemExit(
                "--candidate-review-file, --shot-id and --asset-file are required"
            )
        result = register(
            candidate_review_file=args.candidate_review_file,
            shot_id=args.shot_id,
            asset_file=args.asset_file,
            note=args.note,
        )
        snapshot()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
