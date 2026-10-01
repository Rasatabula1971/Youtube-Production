"""Acquire approved visual assets into managed project storage.

Automatic downloads are limited to verified zero-cost stock providers with
known direct media URLs. Creator/editorial footage is NEVER auto-downloaded;
it remains a manual human-supplied asset after rights/context review.

No paid provider calls are made here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import urllib.parse
import urllib.request
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
SUMMARY_FILE = OUTPUT / "visual_asset_acquisition_summary.json"

MAX_ASSET_BYTES = 250 * 1024 * 1024
ALLOWED_STOCK_HOST_SUFFIXES = {
    "pexels": ("pexels.com",),
    "pixabay": ("pixabay.com",),
}
ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".mkv",
    ".jpg", ".jpeg", ".png", ".webp",
}


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _result_candidate(
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


def _extension_from_url_or_type(
    url: str,
    media_type: str,
) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in ALLOWED_MEDIA_EXTENSIONS:
        return suffix
    return ".mp4" if media_type == "video" else ".jpg"


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


def _assert_stock_url_allowed(
    url: str,
    provider: str,
) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Automatic stock download requires HTTPS")
    host = (parsed.hostname or "").lower()
    suffixes = ALLOWED_STOCK_HOST_SUFFIXES.get(provider, ())
    if not suffixes or not any(
        host == suffix or host.endswith("." + suffix)
        for suffix in suffixes
    ):
        raise ValueError(
            "Automatic stock download host is not allowed for provider "
            + provider
        )


def _download_stock(
    *,
    url: str,
    provider: str,
    destination: Path,
) -> None:
    _assert_stock_url_allowed(url, provider)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "YouTube-Production/1.0"},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = str(
                response.headers.get("Content-Type") or ""
            ).lower()
            if content_type and not (
                content_type.startswith("video/")
                or content_type.startswith("image/")
                or content_type.startswith("application/octet-stream")
            ):
                raise ValueError(
                    "Automatic stock URL did not return media content"
                )
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    declared_size = int(declared)
                except ValueError:
                    declared_size = 0
                if declared_size > MAX_ASSET_BYTES:
                    raise ValueError("Visual asset exceeds maximum download size")

            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_ASSET_BYTES:
                        raise ValueError(
                            "Visual asset exceeds maximum download size"
                        )
                    handle.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise

    if written <= 0:
        if destination.exists():
            destination.unlink()
        raise ValueError("Downloaded visual asset is empty")


def _copy_local(
    source: Path,
    destination: Path,
) -> None:
    if not source.exists() or not source.is_file():
        raise ValueError("Approved local visual asset is missing")
    if source.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
        raise ValueError("Approved local visual asset type is unsupported")
    if source.stat().st_size <= 0:
        raise ValueError("Approved local visual asset is empty")
    if source.stat().st_size > MAX_ASSET_BYTES:
        raise ValueError("Approved local visual asset exceeds size limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _rights_context_approved(
    review_path: Path,
    shot_id: str,
) -> bool:
    rights_path = RIGHTS_DIR / review_path.name.replace(
        ".visual_candidate_review.json",
        ".visual_rights_review.json",
    )
    if not rights_path.exists():
        return False
    rights = load_json(rights_path)
    decision = rights.get("decisions", {}).get(shot_id, {})
    return bool(
        isinstance(decision, dict)
        and decision.get("approved_for_rough_cut") is True
    )


def _current_registry(
    record: dict[str, Any],
) -> bool:
    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    if not isinstance(provenance, dict):
        return False
    result_path = Path(str(provenance.get("search_result") or ""))
    review_path = Path(str(provenance.get("candidate_review") or ""))
    if (
        not result_path.exists()
        or not review_path.exists()
        or not asset_path.exists()
    ):
        return False
    if (
        provenance.get("search_result_sha256") != sha256_file(result_path)
        or provenance.get("candidate_review_sha256")
        != sha256_file(review_path)
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return False
    return True


def acquire() -> dict[str, Any]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    manual_required: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    current_registry_paths: set[Path] = set()

    review_paths = (
        sorted(REVIEW_DIR.glob("*.visual_candidate_review.json"))
        if REVIEW_DIR.exists()
        else []
    )

    for review_path in review_paths:
        review = load_json(review_path)
        if str(review.get("status") or "") != "READY_FOR_ROUGH_CUT":
            continue

        result_path = Path(str(review.get("source_result") or ""))
        if (
            not result_path.exists()
            or result_path.parent.resolve() != RESULT_DIR.resolve()
        ):
            continue
        if review.get("source_result_sha256") != sha256_file(result_path):
            continue
        result = load_json(result_path)
        concept_id = str(result.get("concept_id") or "")
        fmt = str(result.get("format") or "")

        decisions = review.get("decisions", {})
        if not isinstance(decisions, dict):
            continue

        for shot_id, decision in decisions.items():
            if not isinstance(decision, dict):
                continue
            status = str(decision.get("status") or "")
            if status not in {
                "SELECTED",
                "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
            }:
                continue
            candidate_id = str(decision.get("candidate_id") or "")
            candidate = _result_candidate(
                result,
                str(shot_id),
                candidate_id,
            )
            if candidate is None:
                failures.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": shot_id,
                    "error": "CURRENT_SELECTED_CANDIDATE_NOT_FOUND",
                })
                continue
            if decision.get("candidate_fingerprint") != _hash_json(candidate):
                failures.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": shot_id,
                    "error": "STALE_SELECTED_CANDIDATE",
                })
                continue

            tier = str(candidate.get("source_tier") or "").upper()
            provider = str(candidate.get("search_provider") or "").lower()
            registry_path = _registry_path(
                concept_id,
                fmt,
                str(shot_id),
            )

            if status == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
                if not _rights_context_approved(review_path, str(shot_id)):
                    continue
                manual_required.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": str(shot_id),
                    "candidate_id": candidate_id,
                    "source_url": candidate.get("source_url"),
                    "creator": candidate.get("creator"),
                    "license": candidate.get("license"),
                    "reason": "EDITORIAL_EXCERPT_REQUIRES_MANUAL_ASSET_SUPPLY",
                })
                continue

            if tier not in {
                "OWN_LIBRARY",
                "FREE_COMMERCIAL_LICENSE",
                "PUBLIC_DOMAIN",
                "CREATIVE_COMMONS_ALLOWED",
            }:
                failures.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": shot_id,
                    "error": "SELECTED_ASSET_TIER_NOT_AUTO_ACQUIRABLE",
                })
                continue
            if (
                str(candidate.get("rights_status") or "").upper() != "VERIFIED"
                or candidate.get("commercial_use_allowed") is not True
            ):
                failures.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": shot_id,
                    "error": "SELECTED_ASSET_RIGHTS_NOT_VERIFIED",
                })
                continue

            existing = (
                load_json(registry_path)
                if registry_path.exists()
                else None
            )
            if isinstance(existing, dict) and _current_registry(existing):
                current_registry_paths.add(registry_path.resolve())
                items.append(existing)
                continue

            local_path = str(candidate.get("local_path") or "").strip()
            asset_url = str(candidate.get("asset_url") or "").strip()
            media_type = str(candidate.get("media_type") or "").lower()

            try:
                if local_path:
                    source = Path(local_path).expanduser().resolve()
                    extension = source.suffix.lower()
                    destination = _asset_path(
                        concept_id,
                        fmt,
                        str(shot_id),
                        extension,
                    )
                    _copy_local(source, destination)
                    acquisition_method = "LOCAL_LIBRARY_COPY"
                elif (
                    tier == "FREE_COMMERCIAL_LICENSE"
                    and provider in ALLOWED_STOCK_HOST_SUFFIXES
                    and asset_url
                ):
                    extension = _extension_from_url_or_type(
                        asset_url,
                        media_type,
                    )
                    destination = _asset_path(
                        concept_id,
                        fmt,
                        str(shot_id),
                        extension,
                    )
                    _download_stock(
                        url=asset_url,
                        provider=provider,
                        destination=destination,
                    )
                    acquisition_method = "VERIFIED_STOCK_DIRECT_DOWNLOAD"
                else:
                    manual_required.append({
                        "concept_id": concept_id,
                        "format": fmt,
                        "shot_id": str(shot_id),
                        "candidate_id": candidate_id,
                        "source_url": candidate.get("source_url"),
                        "reason": "NO_APPROVED_AUTOMATIC_ASSET_CHANNEL",
                    })
                    continue
            except Exception as exc:
                failures.append({
                    "concept_id": concept_id,
                    "format": fmt,
                    "shot_id": str(shot_id),
                    "error": type(exc).__name__,
                    "detail": str(exc),
                })
                continue

            record = {
                "artifact": "managed_visual_asset",
                "status": "ACQUIRED_CURRENT",
                "concept_id": concept_id,
                "format": fmt,
                "shot_id": str(shot_id),
                "candidate_id": candidate_id,
                "source_tier": tier,
                "search_provider": provider,
                "source_url": candidate.get("source_url"),
                "license": candidate.get("license"),
                "creator": candidate.get("creator"),
                "acquisition_method": acquisition_method,
                "asset_file": str(destination.resolve()),
                "asset_sha256": sha256_file(destination),
                "asset_bytes": destination.stat().st_size,
                "paid_provider_call_executed": False,
                "estimated_cost_usd": 0.0,
                "candidate_fingerprint": _hash_json(candidate),
                "provenance": {
                    "search_result": str(result_path.resolve()),
                    "search_result_sha256": sha256_file(result_path),
                    "candidate_review": str(review_path.resolve()),
                    "candidate_review_sha256": sha256_file(review_path),
                },
            }
            atomic_write_json(registry_path, record)
            current_registry_paths.add(registry_path.resolve())
            items.append(record)

    for stale in REGISTRY_DIR.glob("*.managed_visual_asset.json"):
        if stale.resolve() not in current_registry_paths:
            stale.unlink()

    summary = {
        "status": (
            "ASSETS_ACQUIRED"
            if items
            else "MANUAL_ASSETS_REQUIRED"
            if manual_required
            else "NO_APPROVED_ASSETS_TO_ACQUIRE"
        ),
        "acquired": len(items),
        "manual_required": len(manual_required),
        "failures": len(failures),
        "paid_provider_calls": 0,
        "items": items,
        "manual_items": manual_required,
        "failure_items": failures,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire approved zero-cost visual assets"
    )
    parser.add_argument("--mode", choices=("acquire",), required=True)
    parser.parse_args()
    print(json.dumps(acquire(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
