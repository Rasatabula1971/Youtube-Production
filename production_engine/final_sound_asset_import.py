"""Register human-supplied final music/SFX against the current Slice 21 plan.

No provider is called here. A human may supply an already licensed/owned local
sound asset, or explicitly omit a planned sound requirement. Paid external
purchases are only recorded after the human confirms they already occurred;
this module never authorizes or initiates spend.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from final_sound_plan import PLAN_DIR, plan_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
ASSET_DIR = OUTPUT / "final_sound_assets"
REGISTRY_DIR = OUTPUT / "final_sound_asset_registry"
SUMMARY_FILE = OUTPUT / "final_sound_asset_summary.json"

ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _requirement(
    plan: dict[str, Any],
    requirement_id: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in plan.get("requirements", [])
        if isinstance(item, dict)
        and str(item.get("requirement_id") or "") == requirement_id
    ]
    if len(matches) != 1:
        raise ValueError("Final sound requirement was not found uniquely")
    return matches[0]


def _resolution_path(
    plan: dict[str, Any],
    requirement: dict[str, Any],
) -> Path:
    return REGISTRY_DIR / (
        f"{_key(str(plan.get('concept_id') or ''), str(plan.get('format') or ''))}."
        f"{safe_slug(str(requirement.get('requirement_id') or ''))}."
        "final_sound_resolution.json"
    )


def _managed_asset_path(
    plan: dict[str, Any],
    requirement: dict[str, Any],
    source: Path,
) -> Path:
    return ASSET_DIR / (
        f"{_key(str(plan.get('concept_id') or ''), str(plan.get('format') or ''))}."
        f"{safe_slug(str(requirement.get('requirement_id') or ''))}"
        f"{source.suffix.lower()}"
    )


def _current_plan(plan_file: str) -> tuple[Path, dict[str, Any]]:
    path = Path(plan_file).expanduser().resolve()
    plan = plan_is_current(path)
    if plan is None:
        raise ValueError("STALE_FINAL_SOUND_PLAN")
    return path, plan


def _finite_cost(value: float) -> float:
    cost = float(value)
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("actual_cost_usd must be finite and non-negative")
    return round(cost, 2)


def _cleanup_old_assets(
    plan: dict[str, Any],
    requirement: dict[str, Any],
    *,
    keep: Path | None = None,
) -> None:
    if not ASSET_DIR.exists():
        return
    prefix = (
        f"{_key(str(plan.get('concept_id') or ''), str(plan.get('format') or ''))}."
        f"{safe_slug(str(requirement.get('requirement_id') or ''))}"
    )
    keep_resolved = keep.resolve() if keep is not None and keep.exists() else None
    for candidate in ASSET_DIR.glob(prefix + ".*"):
        if keep_resolved is not None and candidate.resolve() == keep_resolved:
            continue
        if candidate.is_file():
            candidate.unlink()


def register(
    *,
    plan_file: str,
    requirement_id: str,
    asset_file: str,
    licence_reference: str,
    commercial_use_confirmed: bool,
    actual_cost_usd: float = 0,
    external_purchase_confirmed: bool = False,
    source_name: str = "human_supplied",
    provider_job_id: str = "",
    attribution_required: bool = False,
    attribution_text: str = "",
    note: str = "",
) -> dict[str, Any]:
    plan_path, plan = _current_plan(plan_file)
    requirement = _requirement(plan, str(requirement_id or "").strip())

    if commercial_use_confirmed is not True:
        raise ValueError("Commercial-use rights must be explicitly confirmed")
    licence = str(licence_reference or "").strip()
    if not licence:
        raise ValueError("licence_reference is required")

    cost = _finite_cost(actual_cost_usd)
    if cost > 0 and external_purchase_confirmed is not True:
        raise ValueError(
            "Paid final sound may only be registered after explicit confirmation "
            "that the human completed the external purchase"
        )

    source_label = str(source_name or "").strip()
    if not source_label:
        raise ValueError("source_name is required")

    source = Path(asset_file).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Final sound asset file does not exist")
    if source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported final sound asset type: " + source.suffix.lower()
        )
    if source.stat().st_size <= 0:
        raise ValueError("Final sound asset file is empty")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    destination = _managed_asset_path(plan, requirement, source)
    if source != destination.resolve():
        staging = destination.with_name(
            destination.name + f".staging-{uuid.uuid4().hex}"
        )
        try:
            shutil.copy2(source, staging)
            if not staging.is_file() or staging.stat().st_size <= 0:
                raise ValueError("Managed final sound staging copy failed")
            os.replace(staging, destination)
        finally:
            if staging.exists():
                staging.unlink()
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise ValueError("Managed final sound asset copy failed")

    resolution = {
        "artifact": "final_sound_resolution",
        "status": "REGISTERED_CURRENT",
        "concept_id": plan.get("concept_id"),
        "format": plan.get("format"),
        "requirement_id": requirement.get("requirement_id"),
        "requirement_fingerprint": requirement.get("fingerprint"),
        "segment_id": requirement.get("segment_id"),
        "kind": requirement.get("kind"),
        "direction": requirement.get("direction"),
        "asset_file": str(destination.resolve()),
        "asset_sha256": sha256_file(destination),
        "asset_bytes": destination.stat().st_size,
        "rights": {
            "commercial_use_confirmed": True,
            "licence_reference": licence,
            "attribution_required": bool(attribution_required),
            "attribution_text": str(attribution_text or "").strip(),
        },
        "source": {
            "name": source_label,
            "provider_job_id": str(provider_job_id or "").strip() or None,
        },
        "cost": {
            "currency": "USD",
            "actual_cost_usd": cost,
            "external_purchase_confirmed": (
                bool(external_purchase_confirmed) if cost > 0 else False
            ),
            "app_spend_authorized": False,
            "app_provider_call_executed": False,
        },
        "note": str(note or "").strip(),
        "provenance": {
            "final_sound_plan": str(plan_path.resolve()),
            "final_sound_plan_sha256": sha256_file(plan_path),
            "requirement_fingerprint": requirement.get("fingerprint"),
        },
    }
    path = _resolution_path(plan, requirement)
    atomic_write_json(path, resolution)
    _cleanup_old_assets(plan, requirement, keep=destination)
    return resolution


def omit(
    *,
    plan_file: str,
    requirement_id: str,
    note: str,
) -> dict[str, Any]:
    plan_path, plan = _current_plan(plan_file)
    requirement = _requirement(plan, str(requirement_id or "").strip())
    clean_note = str(note or "").strip()
    if not clean_note:
        raise ValueError("Explicit final sound omission requires a human note")

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    resolution = {
        "artifact": "final_sound_resolution",
        "status": "OMITTED_BY_HUMAN",
        "concept_id": plan.get("concept_id"),
        "format": plan.get("format"),
        "requirement_id": requirement.get("requirement_id"),
        "requirement_fingerprint": requirement.get("fingerprint"),
        "segment_id": requirement.get("segment_id"),
        "kind": requirement.get("kind"),
        "direction": requirement.get("direction"),
        "asset_file": None,
        "asset_sha256": None,
        "asset_bytes": 0,
        "rights": None,
        "cost": {
            "currency": "USD",
            "actual_cost_usd": 0.0,
            "external_purchase_confirmed": False,
            "app_spend_authorized": False,
            "app_provider_call_executed": False,
        },
        "note": clean_note,
        "provenance": {
            "final_sound_plan": str(plan_path.resolve()),
            "final_sound_plan_sha256": sha256_file(plan_path),
            "requirement_fingerprint": requirement.get("fingerprint"),
        },
    }
    path = _resolution_path(plan, requirement)
    atomic_write_json(path, resolution)
    _cleanup_old_assets(plan, requirement)
    return resolution


def resolution_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != REGISTRY_DIR.resolve()
    ):
        return None
    try:
        resolution = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(resolution, dict)
        or resolution.get("artifact") != "final_sound_resolution"
        or resolution.get("status")
        not in {"REGISTERED_CURRENT", "OMITTED_BY_HUMAN"}
    ):
        return None

    provenance = resolution.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    plan_path = Path(str(provenance.get("final_sound_plan") or ""))
    if (
        not plan_path.is_file()
        or plan_path.parent.resolve() != PLAN_DIR.resolve()
        or provenance.get("final_sound_plan_sha256")
        != sha256_file(plan_path)
    ):
        return None
    plan = plan_is_current(plan_path)
    if plan is None:
        return None

    try:
        requirement = _requirement(
            plan,
            str(resolution.get("requirement_id") or ""),
        )
    except ValueError:
        return None
    if (
        resolution.get("requirement_fingerprint")
        != requirement.get("fingerprint")
        or provenance.get("requirement_fingerprint")
        != requirement.get("fingerprint")
        or str(resolution.get("concept_id") or "")
        != str(plan.get("concept_id") or "")
        or str(resolution.get("format") or "")
        != str(plan.get("format") or "")
    ):
        return None

    if resolution.get("status") == "OMITTED_BY_HUMAN":
        return resolution if str(resolution.get("note") or "").strip() else None

    asset_path = Path(str(resolution.get("asset_file") or ""))
    rights = resolution.get("rights", {})
    cost = resolution.get("cost", {})
    if (
        not asset_path.is_file()
        or asset_path.parent.resolve() != ASSET_DIR.resolve()
        or resolution.get("asset_sha256") != sha256_file(asset_path)
        or int(resolution.get("asset_bytes") or 0) != asset_path.stat().st_size
        or not isinstance(rights, dict)
        or rights.get("commercial_use_confirmed") is not True
        or not str(rights.get("licence_reference") or "").strip()
        or not isinstance(cost, dict)
        or cost.get("app_spend_authorized") is not False
        or cost.get("app_provider_call_executed") is not False
    ):
        return None
    try:
        actual_cost = float(cost.get("actual_cost_usd") or 0)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(actual_cost) or actual_cost < 0:
        return None
    if actual_cost > 0 and cost.get("external_purchase_confirmed") is not True:
        return None
    return resolution


def snapshot() -> dict[str, Any]:
    plans = (
        sorted(PLAN_DIR.glob("*.final_sound_plan.json"))
        if PLAN_DIR.exists()
        else []
    )
    items: list[dict[str, Any]] = []
    expected = 0
    resolved = 0
    pending = 0
    stale = 0
    actual_cost_total = 0.0
    current_plan_count = 0

    for plan_path in plans:
        plan = plan_is_current(plan_path)
        if plan is None:
            stale += 1
            continue
        current_plan_count += 1
        requirements = [
            item
            for item in plan.get("requirements", [])
            if isinstance(item, dict)
        ]
        for requirement in requirements:
            expected += 1
            resolution_path = _resolution_path(plan, requirement)
            resolution = (
                resolution_is_current(resolution_path)
                if resolution_path.exists()
                else None
            )
            if resolution is None:
                if resolution_path.exists():
                    stale += 1
                pending += 1
            else:
                resolved += 1
                cost = resolution.get("cost", {})
                if isinstance(cost, dict):
                    actual_cost_total += float(cost.get("actual_cost_usd") or 0)
            items.append(
                {
                    "concept_id": plan.get("concept_id"),
                    "format": plan.get("format"),
                    "plan_file": str(plan_path.resolve()),
                    "requirement": requirement,
                    "resolution_file": (
                        str(resolution_path.resolve())
                        if resolution_path.exists()
                        else None
                    ),
                    "resolution": resolution,
                    "resolved": resolution is not None,
                }
            )

    ready = (
        current_plan_count > 0
        and pending == 0
        and stale == 0
        and resolved == expected
    )
    return {
        "status": (
            "FINAL_SOUND_ASSETS_READY"
            if ready
            else "WAITING_FOR_FINAL_SOUND_ASSETS"
            if current_plan_count > 0
            else "WAITING_FOR_FINAL_SOUND_PLANS"
        ),
        "ready": ready,
        "plans": current_plan_count,
        "expected": expected,
        "resolved": resolved,
        "pending": pending,
        "stale": stale,
        "currency": "USD",
        "actual_cost_total_usd": round(actual_cost_total, 2),
        "app_provider_calls": 0,
        "final_renders": 0,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register or omit final sound requirements"
    )
    parser.add_argument(
        "--mode",
        choices=("register", "omit", "status"),
        required=True,
    )
    parser.add_argument("--plan-file")
    parser.add_argument("--requirement-id")
    parser.add_argument("--asset-file")
    parser.add_argument("--licence-reference")
    parser.add_argument("--commercial-use-confirmed", action="store_true")
    parser.add_argument("--actual-cost-usd", type=float, default=0)
    parser.add_argument("--external-purchase-confirmed", action="store_true")
    parser.add_argument("--source-name", default="human_supplied")
    parser.add_argument("--provider-job-id", default="")
    parser.add_argument("--attribution-required", action="store_true")
    parser.add_argument("--attribution-text", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if args.mode == "status":
        result = snapshot()
    elif args.mode == "omit":
        if not args.plan_file or not args.requirement_id:
            raise SystemExit("--plan-file and --requirement-id are required")
        result = omit(
            plan_file=args.plan_file,
            requirement_id=args.requirement_id,
            note=args.note,
        )
    else:
        if (
            not args.plan_file
            or not args.requirement_id
            or not args.asset_file
        ):
            raise SystemExit(
                "--plan-file, --requirement-id and --asset-file are required"
            )
        result = register(
            plan_file=args.plan_file,
            requirement_id=args.requirement_id,
            asset_file=args.asset_file,
            licence_reference=args.licence_reference or "",
            commercial_use_confirmed=args.commercial_use_confirmed,
            actual_cost_usd=args.actual_cost_usd,
            external_purchase_confirmed=args.external_purchase_confirmed,
            source_name=args.source_name,
            provider_job_id=args.provider_job_id,
            attribution_required=args.attribution_required,
            attribution_text=args.attribution_text,
            note=args.note,
        )

    atomic_write_json(SUMMARY_FILE, snapshot())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
