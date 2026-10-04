"""Register externally generated premium visual assets.

The app never calls a paid provider here. A human may generate/download an
asset externally, then register it against the exact current generation request.
The importer verifies request provenance, spend ceiling, file type and content
hash before copying the asset into managed project output.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
import video_budget
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
REQUEST_DIR = OUTPUT / "visual_generation_requests"
ASSET_DIR = OUTPUT / "generated_visual_assets"
REGISTRY_DIR = OUTPUT / "generated_visual_asset_registry"
ASSEMBLY_DIR = OUTPUT / "visual_assembly_plans"
SUMMARY_FILE = OUTPUT / "generated_visual_asset_summary.json"

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def _request_identity(request: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(request.get("concept_id") or ""),
        str(request.get("format") or ""),
        str(request.get("shot_id") or ""),
    )


def _registry_path(request: dict[str, Any]) -> Path:
    concept_id, fmt, shot_id = _request_identity(request)
    return REGISTRY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.generated_visual_asset.json"
    )


def _managed_asset_path(
    request: dict[str, Any],
    source: Path,
) -> Path:
    concept_id, fmt, shot_id = _request_identity(request)
    ext = source.suffix.lower()
    return ASSET_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}{ext}"
    )


def _assert_current_request(request_path: Path) -> dict[str, Any]:
    if (
        not request_path.exists()
        or request_path.parent.resolve() != REQUEST_DIR.resolve()
    ):
        raise ValueError("Invalid visual generation request")

    request = load_json(request_path)
    if request.get("artifact") != "visual_generation_request":
        raise ValueError("Not a visual generation request")

    authorization = request.get("spend_authorization", {})
    if (
        not isinstance(authorization, dict)
        or authorization.get("human_authorized") is not True
        or float(authorization.get("max_cost_usd") or 0) <= 0
    ):
        raise ValueError("Generation request is not human-authorized")

    provenance = request.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Generation request provenance is missing")

    gap_path = Path(str(provenance.get("gap_plan") or ""))
    spend_path = Path(str(provenance.get("visual_spend_review") or ""))
    if (
        not gap_path.exists()
        or not spend_path.exists()
        or provenance.get("gap_plan_sha256") != sha256_file(gap_path)
        or provenance.get("visual_spend_review_sha256")
        != sha256_file(spend_path)
    ):
        raise ValueError("STALE_VISUAL_GENERATION_REQUEST")

    return request


def register(
    *,
    request_file: str,
    asset_file: str,
    actual_cost_usd: float,
    provider: str,
    provider_job_id: str = "",
    note: str = "",
) -> dict[str, Any]:
    request_path = Path(request_file).resolve()
    request = _assert_current_request(request_path)

    source = Path(asset_file).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError("Generated asset file does not exist")
    if source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported generated asset type: " + source.suffix.lower()
        )
    if source.stat().st_size <= 0:
        raise ValueError("Generated asset file is empty")

    authorization = request["spend_authorization"]
    max_cost = round(float(authorization.get("max_cost_usd") or 0), 2)
    cost = round(float(actual_cost_usd), 2)
    if cost < 0:
        raise ValueError("actual_cost_usd cannot be negative")
    if cost > max_cost:
        raise ValueError(
            f"Actual visual cost {cost:.2f} USD exceeds the human-authorized "
            f"{max_cost:.2f} USD ceiling"
        )

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise ValueError("provider is required")
    video_budget.record_actual(
        video=video_budget.video_id(request.get("concept_id"), request.get("format")),
        category="visual",
        ref=f"shot:{request.get('shot_id')}",
        total_usd=cost,
        note=f"Generated asset from {provider_name}",
        ledger=video_budget.ledger_in(REGISTRY_DIR.parent),
    )

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    destination = _managed_asset_path(request, source)

    if source != destination.resolve():
        shutil.copy2(source, destination)
    if not destination.exists() or destination.stat().st_size <= 0:
        raise ValueError("Managed generated asset copy failed")

    record = {
        "artifact": "generated_visual_asset",
        "status": "REGISTERED_CURRENT",
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "shot_id": request.get("shot_id"),
        "provider": provider_name,
        "provider_job_id": str(provider_job_id or "").strip() or None,
        "actual_cost_usd": cost,
        "authorized_max_cost_usd": max_cost,
        "asset_file": str(destination.resolve()),
        "asset_sha256": sha256_file(destination),
        "asset_bytes": destination.stat().st_size,
        "note": str(note or "").strip(),
        "execution_origin": "EXTERNAL_HUMAN_PROVIDER_ACTION",
        "app_provider_call_executed": False,
        "provenance": {
            "visual_generation_request": str(request_path),
            "visual_generation_request_sha256": sha256_file(request_path),
        },
    }
    registry = _registry_path(request)
    atomic_write_json(registry, record)

    concept_id, fmt, _shot_id = _request_identity(request)
    assembly_path = ASSEMBLY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}.visual_assembly_plan.json"
    )
    if assembly_path.exists():
        assembly_path.unlink()

    return record


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    stale = 0
    total_cost = 0.0

    paths = (
        sorted(REGISTRY_DIR.glob("*.generated_visual_asset.json"))
        if REGISTRY_DIR.exists()
        else []
    )
    for path in paths:
        record = load_json(path)
        provenance = record.get("provenance", {})
        request_path = Path(
            str(
                provenance.get("visual_generation_request")
                if isinstance(provenance, dict)
                else ""
            )
        )
        asset_path = Path(str(record.get("asset_file") or ""))

        current = True
        if (
            not request_path.exists()
            or not isinstance(provenance, dict)
            or provenance.get("visual_generation_request_sha256")
            != sha256_file(request_path)
        ):
            current = False
        if (
            not asset_path.exists()
            or record.get("asset_sha256") != sha256_file(asset_path)
        ):
            current = False

        if current:
            try:
                request = _assert_current_request(request_path)
                max_cost = round(
                    float(
                        request.get("spend_authorization", {}).get(
                            "max_cost_usd", 0
                        )
                    ),
                    2,
                )
                if round(float(record.get("actual_cost_usd") or 0), 2) > max_cost:
                    current = False
            except ValueError:
                current = False

        if not current:
            stale += 1
            continue

        total_cost += float(record.get("actual_cost_usd") or 0)
        items.append(record)

    return {
        "status": "GENERATED_VISUAL_ASSETS_REGISTERED" if items else "NO_CURRENT_GENERATED_VISUAL_ASSETS",
        "current": len(items),
        "stale": stale,
        "actual_cost_total_usd": round(total_cost, 2),
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register externally generated premium visual assets"
    )
    parser.add_argument(
        "--mode",
        choices=("register", "status"),
        required=True,
    )
    parser.add_argument("--request-file")
    parser.add_argument("--asset-file")
    parser.add_argument("--actual-cost-usd", type=float, default=0)
    parser.add_argument("--provider", default="higgsfield")
    parser.add_argument("--provider-job-id", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if args.mode == "status":
        result = snapshot()
    else:
        if not args.request_file or not args.asset_file:
            raise SystemExit("--request-file and --asset-file are required")
        result = register(
            request_file=args.request_file,
            asset_file=args.asset_file,
            actual_cost_usd=args.actual_cost_usd,
            provider=args.provider,
            provider_job_id=args.provider_job_id,
            note=args.note,
        )

    atomic_write_json(SUMMARY_FILE, snapshot())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
