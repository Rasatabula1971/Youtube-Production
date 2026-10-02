"""Slice 25 psychological packaging angle generation.

Creates model requests from current Slice 24 Packaging Briefs, then validates
five meaningfully different psychological hypotheses per approved format.

Creative framing may be generated. Facts may not be invented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from packaging_brief import (
    BRIEF_DIR,
    brief_is_current,
    load_json,
    snapshot as packaging_brief_snapshot,
)
from story_script_engine.story_script_engine import safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_config.json"
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "psychological_angle_requests"
RESPONSES_DIR = OUTPUT_DIR / "psychological_angle_responses"
ANGLES_FILE = OUTPUT_DIR / "psychological_angles.json"
SUMMARY_FILE = OUTPUT_DIR / "psychological_angle_summary.json"

SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "psychological-packaging-angles-v1.0"

NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[$£€]?\d+(?:[.,]\d+)*(?:\s?%|\s?[xX])?)(?![A-Za-z0-9])"
)
RISKY_CLAIM_WORDS = {
    "fastest", "slowest", "best", "worst", "first", "only", "never",
    "impossible", "dangerous", "secret",
}


def load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    block = payload.get("psychological_packaging")
    if not isinstance(block, dict):
        raise ValueError("Missing psychological_packaging config")
    count = int(block.get("angles_per_format") or 0)
    drivers = [str(x) for x in block.get("allowed_primary_drivers", [])]
    if count != 5:
        raise ValueError("Slice 25 requires exactly five psychological angles")
    if len(drivers) < count or len(drivers) != len(set(drivers)):
        raise ValueError("Slice 25 psychological drivers must be unique and sufficient")
    return payload


def fingerprint(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _strategy(intent: str, fmt: str) -> dict[str, Any]:
    if intent == "SEARCH":
        priorities = ["subject", "keyword", "problem", "solution_or_payoff", "clarity"]
    elif intent == "BROWSE":
        priorities = [
            "attention", "curiosity", "stakes", "unexpected_information",
            "emotion", "consequence",
        ]
    else:
        priorities = [
            "semantic_clarity", "psychological_attraction", "subject_context",
            "curiosity", "stakes",
        ]
    return {
        "intent": intent,
        "format": fmt,
        "priorities": priorities,
        "shorts_policy": (
            "instant comprehension, rapid promise confirmation, high information density"
            if fmt == "short"
            else None
        ),
        "long_form_policy": (
            "allow deeper mystery, stakes, open loops, transformation and comparison"
            if fmt == "long_form"
            else None
        ),
    }


def build_request(brief_path: Path, brief: dict[str, Any]) -> dict[str, Any]:
    current = brief_is_current(brief_path)
    if current is None or current != brief:
        raise ValueError("STALE_PACKAGING_BRIEF")
    if brief.get("status") != "PACKAGING_BRIEF_READY":
        raise ValueError("INVALID_PACKAGING_BRIEF")

    video_id = _required_text(brief.get("video_id"), "video_id")
    fmt = _required_text(brief.get("format"), "format")
    if fmt not in {"short", "long_form"}:
        raise ValueError("Invalid packaging format")
    intent = _required_text(
        brief.get("search_vs_browse_intent"), "search_vs_browse_intent"
    ).upper()
    if intent not in {"SEARCH", "BROWSE", "HYBRID"}:
        raise ValueError("INVALID_SEARCH_BROWSE_INTENT")

    claims = brief.get("approved_claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("MISSING_EVIDENCE")
    approved_claims: list[dict[str, Any]] = []
    refs: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("MISSING_EVIDENCE")
        claim_id = _required_text(claim.get("claim_id"), "claim_id")
        statement = _required_text(claim.get("statement"), "statement")
        if claim_id in refs:
            raise ValueError("DUPLICATE_EVIDENCE_ID")
        refs.add(claim_id)
        approved_claims.append(
            {
                "claim_id": claim_id,
                "statement": statement,
                "role": claim.get("role"),
            }
        )

    selected = brief.get("selected_title")
    promise = brief.get("viewer_promise_contract")
    if not isinstance(selected, dict) or not isinstance(promise, dict):
        raise ValueError("INVALID_PACKAGING_BRIEF")

    config = load_config()["psychological_packaging"]
    return {
        "artifact": "psychological_packaging_angle_request",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "video_id": video_id,
        "concept_id": brief.get("concept_id"),
        "format": fmt,
        "search_vs_browse_intent": intent,
        "format_strategy": _strategy(intent, fmt),
        "angle_count": int(config["angles_per_format"]),
        "allowed_primary_drivers": list(config["allowed_primary_drivers"]),
        "selected_title_direction": {
            "title_id": selected.get("title_id"),
            "title_text": selected.get("title_text"),
            "psychological_angle": selected.get("psychological_angle"),
            "primary_driver": selected.get("primary_driver"),
            "secondary_driver": selected.get("secondary_driver"),
            "core_claim": selected.get("core_claim"),
            "evidence_refs": selected.get("evidence_refs", []),
        },
        "viewer_promise_contract": promise,
        "opening_hook": brief.get("opening_hook"),
        "central_question": brief.get("central_question"),
        "video_payoff": brief.get("video_payoff"),
        "strongest_visual_event": brief.get("strongest_visual_event"),
        "strongest_fact": brief.get("strongest_fact"),
        "strongest_consequence": brief.get("strongest_consequence"),
        "strongest_transformation": brief.get("strongest_transformation"),
        "approved_numbers": brief.get("approved_numbers", []),
        "approved_claims": approved_claims,
        "allowed_evidence_refs": sorted(refs),
        "prohibited_or_unsupported_claims": brief.get(
            "prohibited_or_unsupported_claims", []
        ),
        "instructions": [
            "Generate exactly five psychological packaging hypotheses.",
            "Use five different primary_driver values from allowed_primary_drivers.",
            "Exactly one hypothesis must be ANCHOR: it should preserve the selected human title direction's underlying psychology and promise without copying its wording.",
            "The other four must be ALTERNATIVE hypotheses with meaningfully different viewer questions and click reasons.",
            "Creative framing is allowed; factual invention is not.",
            "Every hypothesis must cite at least one allowed evidence ref.",
            "Do not invent numbers, records, superlatives, danger, scientific certainty or unsupported outcomes.",
            "SEARCH, BROWSE and HYBRID require different emphasis as specified in format_strategy.",
            "Do not predict CTR, virality, views, retention or recommendation performance.",
        ],
        "request_provenance": {
            "packaging_brief": str(brief_path.resolve()),
            "packaging_brief_sha256": sha256_file(brief_path),
        },
    }


def _allowed_numbers(request: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for item in request.get("approved_numbers", []) or []:
        if isinstance(item, dict) and str(item.get("value") or "").strip():
            values.add(str(item["value"]).strip().lower())
    return values


def _claims_by_id(request: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("claim_id")): str(item.get("statement") or "")
        for item in request.get("approved_claims", [])
        if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
    }


def _validate_claim_language(
    text: str,
    refs: list[str],
    request: dict[str, Any],
    path: str,
) -> None:
    allowed_numbers = _allowed_numbers(request)
    for number in NUMBER_RE.findall(text):
        if number.strip().lower() not in allowed_numbers:
            raise ValueError(f"{path} invents unsupported number {number!r}")

    lower = text.lower()
    claims = _claims_by_id(request)
    cited = " ".join(claims.get(ref, "") for ref in refs).lower()
    for word in RISKY_CLAIM_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lower) and not re.search(
            rf"\b{re.escape(word)}\b", cited
        ):
            raise ValueError(f"{path} uses unsupported high-risk claim word {word!r}")


def validate_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if str(response.get("video_id") or "") != str(request.get("video_id") or ""):
        raise ValueError("Psychological angle response video_id mismatch")
    values = response.get("angles")
    expected = int(request.get("angle_count") or 0)
    if not isinstance(values, list) or len(values) != expected:
        raise ValueError(f"angles must contain exactly {expected} hypotheses")

    allowed_drivers = set(str(x) for x in request.get("allowed_primary_drivers", []))
    allowed_refs = set(str(x) for x in request.get("allowed_evidence_refs", []))
    seen_ids: set[str] = set()
    seen_primary: set[str] = set()
    seen_questions: set[str] = set()
    seen_reasons: set[str] = set()
    anchor_count = 0
    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise ValueError(f"angles[{index}] must be an object")
        primary = _required_text(item.get("primary_driver"), f"angles[{index}].primary_driver")
        if primary not in allowed_drivers:
            raise ValueError(f"Unsupported primary_driver: {primary}")
        secondary = str(item.get("secondary_driver") or "").strip() or None
        if secondary is not None and secondary not in allowed_drivers:
            raise ValueError(f"Unsupported secondary_driver: {secondary}")
        if secondary == primary:
            raise ValueError("secondary_driver must differ from primary_driver")
        angle_id = _required_text(item.get("angle_id"), f"angles[{index}].angle_id")
        expected_id = f"angle-{primary}"
        if angle_id != expected_id:
            raise ValueError(f"angle_id must be stable ID {expected_id!r}")
        if angle_id in seen_ids or primary in seen_primary:
            raise ValueError("Duplicate angle ID or primary psychological driver")

        alignment = _required_text(
            item.get("selected_title_direction_alignment"),
            f"angles[{index}].selected_title_direction_alignment",
        ).upper()
        if alignment not in {"ANCHOR", "ALTERNATIVE"}:
            raise ValueError("selected_title_direction_alignment must be ANCHOR or ALTERNATIVE")
        if alignment == "ANCHOR":
            anchor_count += 1

        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"{angle_id} requires evidence_refs")
        refs = [str(x) for x in refs]
        unknown = sorted(set(refs) - allowed_refs)
        if unknown:
            raise ValueError(f"{angle_id} invents evidence_refs: {', '.join(unknown)}")

        fields = {}
        for key in (
            "viewer_question",
            "emotional_trigger",
            "stakes",
            "information_given",
            "information_withheld",
            "expected_click_reason",
        ):
            value = _required_text(item.get(key), f"{angle_id}.{key}")
            _validate_claim_language(value, refs, request, f"{angle_id}.{key}")
            fields[key] = value

        question_key = re.sub(r"\W+", " ", fields["viewer_question"].lower()).strip()
        reason_key = re.sub(r"\W+", " ", fields["expected_click_reason"].lower()).strip()
        if question_key in seen_questions:
            raise ValueError("Psychological hypotheses repeat the same viewer question")
        if reason_key in seen_reasons:
            raise ValueError("Psychological hypotheses repeat the same expected click reason")

        seen_ids.add(angle_id)
        seen_primary.add(primary)
        seen_questions.add(question_key)
        seen_reasons.add(reason_key)
        normalized.append(
            {
                "angle_id": angle_id,
                "primary_driver": primary,
                "secondary_driver": secondary,
                **fields,
                "evidence_refs": refs,
                "selected_title_direction_alignment": alignment,
            }
        )

    if anchor_count != 1:
        raise ValueError("Exactly one psychological hypothesis must be ANCHOR")

    return {
        "artifact": "psychological_packaging_angle_set",
        "schema_version": SCHEMA_VERSION,
        "video_id": request["video_id"],
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "search_vs_browse_intent": request.get("search_vs_browse_intent"),
        "angles": normalized,
        "source_request_fingerprint": fingerprint(request),
    }


def request_is_current(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.parent.resolve() != REQUESTS_DIR.resolve():
        return None
    try:
        request = load_json(path)
        prov = request.get("request_provenance", {})
        if not isinstance(prov, dict):
            return None
        brief_path = Path(str(prov.get("packaging_brief") or ""))
        brief = brief_is_current(brief_path)
        if brief is None:
            return None
        rebuilt = build_request(brief_path, brief)
        return request if rebuilt == request else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def run_prepare() -> dict[str, Any]:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    current_paths: set[Path] = set()
    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    paths = sorted(BRIEF_DIR.glob("*.packaging_brief.json")) if BRIEF_DIR.exists() else []
    for brief_path in paths:
        try:
            brief = brief_is_current(brief_path)
            if brief is None:
                raise ValueError("STALE_PACKAGING_BRIEF")
            request = build_request(brief_path, brief)
            destination = REQUESTS_DIR / (
                f"{safe_slug(str(request['video_id']))}.psychological_angle_request.json"
            )
            atomic_write_json(destination, request)
            current_paths.add(destination.resolve())
            prepared.append(
                {
                    "video_id": request["video_id"],
                    "format": request["format"],
                    "request": str(destination.resolve()),
                    "request_sha256": sha256_file(destination),
                }
            )
        except Exception as exc:
            failures.append(
                {
                    "brief": str(brief_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale in REQUESTS_DIR.glob("*.psychological_angle_request.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    brief_state = packaging_brief_snapshot()
    expected = int(brief_state.get("current") or 0)
    status = (
        "PSYCHOLOGICAL_ANGLE_REQUESTS_READY"
        if expected > 0 and len(prepared) == expected and not failures
        else "PARTIAL"
        if prepared
        else "FAILED"
        if failures
        else "WAITING_FOR_PACKAGING_BRIEF"
    )
    result = {
        "status": status,
        "expected": expected,
        "prepared": len(prepared),
        "failed": len(failures),
        "items": prepared,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def run_apply() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for request_path in sorted(REQUESTS_DIR.glob("*.psychological_angle_request.json")):
        request = request_is_current(request_path)
        if request is None:
            rejected.append({"request": str(request_path), "error": "STALE_ANGLE_REQUEST"})
            continue
        slug = safe_slug(str(request.get("video_id") or ""))
        response_path = RESPONSES_DIR / f"{slug}.psychological_angle_response.json"
        if not response_path.is_file():
            continue
        try:
            response = load_json(response_path)
            prov = response.get("response_provenance", {})
            if (
                not isinstance(prov, dict)
                or prov.get("request_sha256") != sha256_file(request_path)
            ):
                raise ValueError("STALE_ANGLE_RESPONSE")
            normalized = validate_response(response, request)
            normalized["request_file"] = str(request_path.resolve())
            normalized["request_sha256"] = sha256_file(request_path)
            normalized["response_file"] = str(response_path.resolve())
            normalized["response_sha256"] = sha256_file(response_path)
            normalized["response_provenance"] = prov
            items.append(normalized)
        except Exception as exc:
            rejected.append(
                {
                    "video_id": request.get("video_id"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    artifact = {
        "artifact": "psychological_packaging_angles",
        "schema_version": SCHEMA_VERSION,
        "count": len(items),
        "items": items,
        "rejected": rejected,
    }
    atomic_write_json(ANGLES_FILE, artifact)
    brief_state = packaging_brief_snapshot()
    expected = int(brief_state.get("current") or 0)
    result = {
        "status": (
            "PSYCHOLOGICAL_ANGLES_READY"
            if expected > 0 and len(items) == expected and not rejected
            else "PARTIAL"
            if items
            else "WAITING_FOR_ANGLE_RESPONSES"
        ),
        "expected": expected,
        "current": len(items),
        "rejected": len(rejected),
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def item_is_current(item: dict[str, Any]) -> bool:
    try:
        request_path = Path(str(item.get("request_file") or ""))
        request = request_is_current(request_path)
        if request is None or item.get("request_sha256") != sha256_file(request_path):
            return False
        response_path = Path(str(item.get("response_file") or ""))
        if (
            not response_path.is_file()
            or response_path.parent.resolve() != RESPONSES_DIR.resolve()
            or item.get("response_sha256") != sha256_file(response_path)
        ):
            return False
        response = load_json(response_path)
        prov = response.get("response_provenance", {})
        if not isinstance(prov, dict) or prov.get("request_sha256") != sha256_file(request_path):
            return False
        rebuilt = validate_response(response, request)
        comparable = {
            key: item.get(key)
            for key in (
                "artifact", "schema_version", "video_id", "concept_id", "format",
                "search_vs_browse_intent", "angles", "source_request_fingerprint",
            )
        }
        return rebuilt == comparable
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def snapshot() -> dict[str, Any]:
    brief_state = packaging_brief_snapshot()
    expected = int(brief_state.get("current") or 0) if brief_state.get("ready") else 0
    current: list[dict[str, Any]] = []
    stale = 0
    if ANGLES_FILE.is_file():
        try:
            payload = load_json(ANGLES_FILE)
            for item in payload.get("items", []) if isinstance(payload, dict) else []:
                if isinstance(item, dict) and item_is_current(item):
                    current.append(
                        {
                            "video_id": item.get("video_id"),
                            "format": item.get("format"),
                            "angle_count": len(item.get("angles", [])),
                            "primary_drivers": [
                                x.get("primary_driver")
                                for x in item.get("angles", [])
                                if isinstance(x, dict)
                            ],
                            "angles": item.get("angles", []),
                        }
                    )
                else:
                    stale += 1
        except (OSError, ValueError, json.JSONDecodeError):
            stale += 1

    ready = expected > 0 and len(current) == expected and stale == 0
    return {
        "status": (
            "PSYCHOLOGICAL_ANGLES_READY"
            if ready
            else "PSYCHOLOGICAL_ANGLES_STALE"
            if stale
            else "WAITING_FOR_PSYCHOLOGICAL_ANGLES"
        ),
        "ready": ready,
        "expected": expected,
        "current": len(current),
        "stale": stale,
        "items": current,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice 25 psychological packaging angles")
    parser.add_argument("--mode", choices=("prepare", "apply", "status"), required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = run_prepare()
    elif args.mode == "apply":
        result = run_apply()
    else:
        result = snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") in {"FAILED", "PARTIAL", "PSYCHOLOGICAL_ANGLES_STALE"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
