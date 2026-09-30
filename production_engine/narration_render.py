"""Narration render preparation and cost boundary.

This module consumes Human Performance Gate approved voice specifications and
prepares immutable, provider-bound narration render requests. It never calls a
paid provider. A provider contract and a current provider quote must be supplied
before a human spend gate can authorize rendering.

The Higgsfield narration API contract is intentionally fail-closed until a
documented endpoint and request schema are verified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug, sha256_file, sha256_text
from voice_review import APPROVED_DIR as APPROVED_VOICE_DIR

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "narration_render_config.json"
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "narration_render_requests"
QUOTE_TEMPLATES_DIR = OUTPUT_DIR / "narration_provider_quote_templates"
QUOTES_DIR = OUTPUT_DIR / "narration_provider_quotes"
ESTIMATES_DIR = OUTPUT_DIR / "narration_cost_estimates"
SUMMARY_FILE = OUTPUT_DIR / "narration_render_summary.json"

APPROVED_STATUS = "PERFORMANCE_SPEC_APPROVED"


def _number(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict):
        raise ValueError("Narration render config must be an object")
    required = {
        "provider",
        "provider_contract",
        "max_regenerations_per_segment",
        "quote_currency",
        "require_provider_quote",
        "audio_qc",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Narration render config is missing: " + ", ".join(missing))

    provider = str(config["provider"]).strip()
    if not provider:
        raise ValueError("provider is required")
    contract = config["provider_contract"]
    if not isinstance(contract, dict):
        raise ValueError("provider_contract must be an object")
    regenerations = int(config["max_regenerations_per_segment"])
    if regenerations < 0 or regenerations > 10:
        raise ValueError("max_regenerations_per_segment must be between 0 and 10")
    currency = str(config["quote_currency"]).strip().upper()
    if currency != "USD":
        raise ValueError("quote_currency must currently be USD")
    qc = config["audio_qc"]
    if not isinstance(qc, dict):
        raise ValueError("audio_qc must be an object")

    result = dict(config)
    result["provider"] = provider
    result["max_regenerations_per_segment"] = regenerations
    result["quote_currency"] = currency
    return result


def artifact_key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def provider_contract_verified(config: dict[str, Any]) -> bool:
    contract = config.get("provider_contract", {})
    if not isinstance(contract, dict):
        return False
    return bool(
        contract.get("schema_verified") is True
        and str(contract.get("endpoint") or "").strip()
        and str(contract.get("documentation_url") or "").strip()
        and str(contract.get("verified_at") or "").strip()
    )


def _voice_prerequisites(spec: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    gate = spec.get("performance_gate", {})
    if not isinstance(gate, dict) or gate.get("status") != APPROVED_STATUS:
        blockers.append("HUMAN_PERFORMANCE_GATE_NOT_APPROVED")

    identity = spec.get("voice_identity", {})
    if not isinstance(identity, dict):
        blockers.append("VOICE_IDENTITY_MISSING")
        return blockers

    required = {
        "voice_id": "VOICE_ID_MISSING",
        "license_reference": "VOICE_LICENSE_REFERENCE_MISSING",
        "calibration_artifact": "VOICE_CALIBRATION_ARTIFACT_MISSING",
    }
    for field, blocker in required.items():
        if not str(identity.get(field) or "").strip():
            blockers.append(blocker)
    return blockers


def build_render_request(
    spec: dict[str, Any],
    spec_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(spec.get("concept_id") or "").strip()
    fmt = str(spec.get("format") or "").strip()
    title = str(spec.get("title") or "").strip()
    if not concept_id or not fmt or not title:
        raise ValueError("Approved Voice Performance spec requires concept_id, format and title")

    validation = spec.get("validation", {})
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise ValueError("Approved Voice Performance spec must pass deterministic validation")

    beats = spec.get("beats", [])
    directions = spec.get("directions", [])
    if not isinstance(beats, list) or not beats:
        raise ValueError("Approved Voice Performance spec requires beats")
    if not isinstance(directions, list) or len(directions) != len(beats):
        raise ValueError("Voice Performance directions must cover every beat exactly")

    beat_ids = [str(item.get("beat_id") or "") for item in beats if isinstance(item, dict)]
    direction_ids = [
        str(item.get("beat_id") or "")
        for item in directions
        if isinstance(item, dict)
    ]
    if len(beat_ids) != len(beats) or beat_ids != direction_ids or len(set(beat_ids)) != len(beat_ids):
        raise ValueError("Voice Performance beat and direction order must match exactly")

    segments: list[dict[str, Any]] = []
    key = artifact_key(concept_id, fmt)
    for beat, direction in zip(beats, directions, strict=True):
        beat_id = str(beat["beat_id"])
        narration = str(beat.get("immutable_narration") or "")
        expected_hash = str(beat.get("immutable_narration_sha256") or "")
        if not narration or not expected_hash or sha256_text(narration) != expected_hash:
            raise ValueError(f"{beat_id} immutable narration provenance is invalid")
        segments.append(
            {
                "segment_id": beat_id,
                "beat_index": int(beat.get("beat_index") or 0),
                "purpose": str(beat.get("purpose") or ""),
                "claim_ids": [str(item) for item in beat.get("claim_ids", [])],
                "source_section_ids": [
                    str(item) for item in beat.get("source_section_ids", [])
                ],
                "immutable_narration": narration,
                "immutable_narration_sha256": expected_hash,
                "delivery": {
                    "emotion": direction.get("emotion"),
                    "intensity": direction.get("intensity"),
                    "speed": direction.get("speed"),
                    "pause_before_ms": direction.get("pause_before_ms"),
                    "pause_after_ms": direction.get("pause_after_ms"),
                    "emphasis_terms": list(direction.get("emphasis_terms", [])),
                },
                "planned_audio_file": str(
                    Path("narration_audio") / key / f"{safe_slug(beat_id)}.wav"
                ),
            }
        )

    blockers = _voice_prerequisites(spec)
    identity = spec.get("voice_identity", {})
    if str(identity.get("provider") or "").strip() != str(config["provider"]):
        blockers.append("VOICE_PROVIDER_MISMATCH")
    if not provider_contract_verified(config):
        blockers.append("PROVIDER_NARRATION_CONTRACT_UNVERIFIED")

    return {
        "artifact": "narration_render_request",
        "concept_id": concept_id,
        "format": fmt,
        "title": title,
        "provider": config["provider"],
        "voice_identity": identity,
        "segments": segments,
        "max_regenerations_per_segment": config["max_regenerations_per_segment"],
        "max_attempts_per_segment": 1 + config["max_regenerations_per_segment"],
        "provider_contract": dict(config["provider_contract"]),
        "render_blockers": blockers,
        "status": "READY_FOR_PROVIDER_QUOTE" if not blockers else "BLOCKED",
        "paid_render_authorized": False,
        "render_provenance": {
            "approved_voice_spec": str(spec_path.resolve()),
            "approved_voice_spec_sha256": sha256_file(spec_path),
            "approved_provenance": spec.get("approved_provenance", {}),
        },
    }


def quote_template(request: dict[str, Any], request_path: Path) -> dict[str, Any]:
    return {
        "artifact": "narration_provider_quote",
        "concept_id": request["concept_id"],
        "format": request["format"],
        "provider": request["provider"],
        "render_request_sha256": sha256_file(request_path),
        "currency": "USD",
        "initial_estimate_usd": None,
        "worst_case_estimate_usd": None,
        "attempts_per_segment": request["max_attempts_per_segment"],
        "quote_reference": None,
        "quoted_at": None,
        "quote_source": None,
        "instructions": (
            "Populate only from the provider's current quote/dry-run mechanism or "
            "documented pricing. Do not guess a price."
        ),
    }


def validate_quote(
    quote: dict[str, Any],
    request: dict[str, Any],
    request_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    if quote.get("artifact") != "narration_provider_quote":
        raise ValueError("Quote artifact type is invalid")
    for field in ("concept_id", "format", "provider"):
        if str(quote.get(field) or "") != str(request.get(field) or ""):
            raise ValueError(f"Quote {field} mismatch")
    if str(quote.get("render_request_sha256") or "") != sha256_file(request_path):
        raise ValueError("Quote is stale for the current narration render request")
    if str(quote.get("currency") or "").upper() != str(config["quote_currency"]):
        raise ValueError("Quote currency mismatch")
    if int(quote.get("attempts_per_segment") or 0) != int(
        request["max_attempts_per_segment"]
    ):
        raise ValueError("Quote attempts_per_segment does not match current policy")

    initial = _number(quote.get("initial_estimate_usd"), label="initial_estimate_usd")
    worst = _number(
        quote.get("worst_case_estimate_usd"),
        label="worst_case_estimate_usd",
    )
    if initial < 0 or worst < 0 or worst < initial:
        raise ValueError("Quote cost values are invalid")
    reference = str(quote.get("quote_reference") or "").strip()
    quoted_at = str(quote.get("quoted_at") or "").strip()
    source = str(quote.get("quote_source") or "").strip()
    if not reference or not quoted_at or not source:
        raise ValueError("Quote requires quote_reference, quoted_at and quote_source")

    return {
        **quote,
        "currency": str(config["quote_currency"]),
        "initial_estimate_usd": initial,
        "worst_case_estimate_usd": worst,
        "quote_reference": reference,
        "quoted_at": quoted_at,
        "quote_source": source,
    }


def build_cost_estimate(
    request: dict[str, Any],
    request_path: Path,
    config: dict[str, Any],
    quote_path: Path | None,
) -> dict[str, Any]:
    base = {
        "artifact": "narration_cost_estimate",
        "concept_id": request["concept_id"],
        "format": request["format"],
        "provider": request["provider"],
        "currency": config["quote_currency"],
        "segment_count": len(request["segments"]),
        "max_attempts_per_segment": request["max_attempts_per_segment"],
        "render_request_sha256": sha256_file(request_path),
        "render_blockers": list(request.get("render_blockers", [])),
    }
    if request.get("render_blockers"):
        return {
            **base,
            "status": "BLOCKED_RENDER_PREREQUISITES",
            "initial_estimate_usd": None,
            "worst_case_estimate_usd": None,
            "provider_quote": None,
        }
    if quote_path is None or not quote_path.exists():
        return {
            **base,
            "status": "WAITING_FOR_PROVIDER_QUOTE",
            "initial_estimate_usd": None,
            "worst_case_estimate_usd": None,
            "provider_quote": None,
        }

    quote = validate_quote(load_json(quote_path), request, request_path, config)
    return {
        **base,
        "status": "READY_FOR_SPEND_GATE",
        "initial_estimate_usd": quote["initial_estimate_usd"],
        "worst_case_estimate_usd": quote["worst_case_estimate_usd"],
        "provider_quote": {
            "path": str(quote_path.resolve()),
            "sha256": sha256_file(quote_path),
            "quote_reference": quote["quote_reference"],
            "quoted_at": quote["quoted_at"],
            "quote_source": quote["quote_source"],
        },
    }


def prepare(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    for directory in (
        REQUESTS_DIR,
        QUOTE_TEMPLATES_DIR,
        QUOTES_DIR,
        ESTIMATES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    paths = (
        sorted(APPROVED_VOICE_DIR.glob("*.approved_voice_spec.json"))
        if APPROVED_VOICE_DIR.exists()
        else []
    )
    prepared: list[dict[str, Any]] = []
    current_requests: set[Path] = set()
    current_templates: set[Path] = set()
    current_estimates: set[Path] = set()

    for spec_path in paths:
        spec = load_json(spec_path)
        request = build_render_request(spec, spec_path, config)
        key = artifact_key(request["concept_id"], request["format"])
        request_path = REQUESTS_DIR / f"{key}.narration_render_request.json"
        atomic_write_json(request_path, request)
        current_requests.add(request_path.resolve())

        template_path = (
            QUOTE_TEMPLATES_DIR / f"{key}.narration_provider_quote.template.json"
        )
        atomic_write_json(template_path, quote_template(request, request_path))
        current_templates.add(template_path.resolve())

        quote_path = QUOTES_DIR / f"{key}.narration_provider_quote.json"
        estimate = build_cost_estimate(
            request,
            request_path,
            config,
            quote_path if quote_path.exists() else None,
        )
        estimate_path = ESTIMATES_DIR / f"{key}.narration_cost_estimate.json"
        atomic_write_json(estimate_path, estimate)
        current_estimates.add(estimate_path.resolve())
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "format": request["format"],
                "request": str(request_path),
                "estimate": str(estimate_path),
                "status": estimate["status"],
                "blockers": request["render_blockers"],
            }
        )

    stale_patterns = (
        (REQUESTS_DIR, "*.narration_render_request.json", current_requests),
        (
            QUOTE_TEMPLATES_DIR,
            "*.narration_provider_quote.template.json",
            current_templates,
        ),
        (ESTIMATES_DIR, "*.narration_cost_estimate.json", current_estimates),
    )
    for directory, pattern, current in stale_patterns:
        for stale in directory.glob(pattern):
            if stale.resolve() not in current:
                stale.unlink()

    statuses = [str(item["status"]) for item in prepared]
    result = {
        "status": (
            "READY_FOR_SPEND_GATE"
            if prepared and all(item == "READY_FOR_SPEND_GATE" for item in statuses)
            else "NARRATION_PREPARED_WITH_BLOCKERS"
            if prepared
            else "WAITING_FOR_APPROVED_VOICE_SPECS"
        ),
        "prepared": len(prepared),
        "ready_for_spend_gate": sum(
            item == "READY_FOR_SPEND_GATE" for item in statuses
        ),
        "items": prepared,
    }
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, result)
    return result


def snapshot() -> dict[str, Any]:
    if not ESTIMATES_DIR.exists():
        return {
            "status": "WAITING_FOR_APPROVED_VOICE_SPECS",
            "prepared": 0,
            "ready_for_spend_gate": 0,
            "items": [],
        }
    items: list[dict[str, Any]] = []
    for path in sorted(ESTIMATES_DIR.glob("*.narration_cost_estimate.json")):
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "concept_id": payload.get("concept_id"),
                "format": payload.get("format"),
                "status": payload.get("status"),
                "initial_estimate_usd": payload.get("initial_estimate_usd"),
                "worst_case_estimate_usd": payload.get("worst_case_estimate_usd"),
                "render_blockers": payload.get("render_blockers", []),
                "estimate": str(path),
            }
        )
    ready = sum(item.get("status") == "READY_FOR_SPEND_GATE" for item in items)
    return {
        "status": (
            "READY_FOR_SPEND_GATE"
            if items and ready == len(items)
            else "NARRATION_PREPARED_WITH_BLOCKERS"
            if items
            else "WAITING_FOR_APPROVED_VOICE_SPECS"
        ),
        "prepared": len(items),
        "ready_for_spend_gate": ready,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Narration render preparation")
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    payload = prepare() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
