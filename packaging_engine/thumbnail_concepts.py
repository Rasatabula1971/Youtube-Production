"""Slice 25 thumbnail concept generation contracts.

Consumes current psychological packaging angles and current Slice 24 Packaging
Briefs. Produces one thumbnail concept per angle. This is concept planning only:
no image generation, download, paid provider call, pairing, scoring or approval.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_STORY = _ROOT / "story_script_engine"
if str(_STORY) not in sys.path:
    sys.path.insert(0, str(_STORY))

from pipeline_integrity import atomic_write_json
from packaging_brief import brief_is_current, load_json
from psychological_angles import (
    ANGLES_FILE,
    item_is_current as angle_item_is_current,
    snapshot as angle_snapshot,
)
from story_script_engine import safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_config.json"
OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "thumbnail_concept_requests"
RESPONSES_DIR = OUTPUT_DIR / "thumbnail_concept_responses"
CONCEPTS_FILE = OUTPUT_DIR / "thumbnail_concepts.json"
SUMMARY_FILE = OUTPUT_DIR / "thumbnail_concept_summary.json"

SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "thumbnail-concepts-v1.0"

NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[$£€]?\d+(?:[.,]\d+)*(?:\s?%|\s?[xX])?)(?![A-Za-z0-9])"
)
RISKY_CLAIM_WORDS = {
    "fastest", "slowest", "best", "worst", "first", "only", "never",
    "impossible", "dangerous", "secret",
}


def load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    block = payload.get("thumbnail_concepts")
    if not isinstance(block, dict):
        raise ValueError("Missing thumbnail_concepts config")
    if int(block.get("concepts_per_angle") or 0) != 1:
        raise ValueError("Slice 25 requires one thumbnail concept per angle")
    if str(block.get("aspect_ratio") or "") != "16:9":
        raise ValueError("Slice 25 thumbnail aspect ratio must be 16:9")
    if int(block.get("primary_focal_points") or 0) != 1:
        raise ValueError("Slice 25 requires one primary focal point")
    if int(block.get("maximum_meaningful_visual_elements") or 0) != 3:
        raise ValueError("Slice 25 supports at most three meaningful visual elements")
    if int(block.get("maximum_text_words") or 0) != 4:
        raise ValueError("Slice 25 supports at most four thumbnail text words")
    return payload


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _angle_payloads() -> list[dict[str, Any]]:
    if not ANGLES_FILE.is_file():
        return []
    payload = load_json(ANGLES_FILE)
    if not isinstance(payload, dict) or payload.get("artifact") != "psychological_packaging_angles":
        raise ValueError("INVALID_PSYCHOLOGICAL_ANGLES")
    result = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        if angle_item_is_current(item):
            result.append(item)
    return result


def build_request(angle_item: dict[str, Any]) -> dict[str, Any]:
    if not angle_item_is_current(angle_item):
        raise ValueError("STALE_PSYCHOLOGICAL_ANGLES")
    request_path = Path(str(angle_item.get("request_file") or ""))
    angle_request = load_json(request_path)
    prov = angle_request.get("request_provenance", {})
    if not isinstance(prov, dict):
        raise ValueError("STALE_PSYCHOLOGICAL_ANGLES")
    brief_path = Path(str(prov.get("packaging_brief") or ""))
    brief = brief_is_current(brief_path)
    if brief is None:
        raise ValueError("STALE_PACKAGING_BRIEF")

    config = load_config()["thumbnail_concepts"]
    angles = angle_item.get("angles", [])
    if not isinstance(angles, list) or not angles:
        raise ValueError("INVALID_PSYCHOLOGICAL_ANGLES")

    return {
        "artifact": "thumbnail_concept_request",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "video_id": angle_item.get("video_id"),
        "concept_id": angle_item.get("concept_id"),
        "format": angle_item.get("format"),
        "search_vs_browse_intent": angle_item.get("search_vs_browse_intent"),
        "selected_title_direction": brief.get("selected_title"),
        "viewer_promise_contract": brief.get("viewer_promise_contract"),
        "opening_hook": brief.get("opening_hook"),
        "central_question": brief.get("central_question"),
        "video_payoff": brief.get("video_payoff"),
        "strongest_visual_event": brief.get("strongest_visual_event"),
        "strongest_fact": brief.get("strongest_fact"),
        "strongest_consequence": brief.get("strongest_consequence"),
        "strongest_transformation": brief.get("strongest_transformation"),
        "approved_claims": brief.get("approved_claims", []),
        "approved_numbers": brief.get("approved_numbers", []),
        "allowed_evidence_refs": [
            str(item.get("claim_id"))
            for item in brief.get("approved_claims", [])
            if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
        ],
        "prohibited_or_unsupported_claims": brief.get(
            "prohibited_or_unsupported_claims", []
        ),
        "angles": angles,
        "thumbnail_contract": {
            "aspect_ratio": str(config["aspect_ratio"]),
            "primary_focal_points": int(config["primary_focal_points"]),
            "maximum_meaningful_visual_elements": int(
                config["maximum_meaningful_visual_elements"]
            ),
            "preferred_text_words": int(config["preferred_text_words"]),
            "maximum_text_words": int(config["maximum_text_words"]),
            "require_timestamp_safe": bool(config["require_timestamp_safe"]),
            "require_mobile_legibility_intent": bool(
                config["require_mobile_legibility_intent"]
            ),
            "prohibit_critical_bottom_right_content": bool(
                config["prohibit_critical_bottom_right_content"]
            ),
        },
        "instructions": [
            "Create exactly one thumbnail concept for every supplied psychological angle.",
            "Base the thumbnail on the Packaging Brief and angle, not solely on the selected title wording.",
            "One thumbnail must communicate one visual proposition.",
            "Use one primary focal point and no more than three meaningful visual elements.",
            "Thumbnail text should preferably be zero to three words; four is allowed only when necessary.",
            "Thumbnail text must add information rather than merely repeat the selected title direction.",
            "Visual anomaly is preferred when truthful, but may be null when another visual strategy is stronger.",
            "Faces are optional; do not manufacture facial emotion that the content does not support.",
            "Critical content must stay out of the bottom-right timestamp zone.",
            "Every factual visual/text claim must remain inside approved evidence.",
            "Do not invent numbers, records, superlatives, danger, scientific claims or performance claims.",
            "Do not predict CTR, virality, views or retention.",
            "Do not generate an image. Return structured thumbnail concepts only.",
        ],
        "request_provenance": {
            "psychological_angles": str(ANGLES_FILE.resolve()),
            "psychological_angles_sha256": sha256_file(ANGLES_FILE),
            "angle_request": str(request_path.resolve()),
            "angle_request_sha256": sha256_file(request_path),
            "packaging_brief": str(brief_path.resolve()),
            "packaging_brief_sha256": sha256_file(brief_path),
        },
    }


def _allowed_numbers(request: dict[str, Any]) -> set[str]:
    return {
        str(item.get("value")).strip().lower()
        for item in request.get("approved_numbers", [])
        if isinstance(item, dict) and str(item.get("value") or "").strip()
    }


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
    for number in NUMBER_RE.findall(text):
        if number.strip().lower() not in _allowed_numbers(request):
            raise ValueError(f"{path} invents unsupported number {number!r}")
    lower = text.lower()
    cited = " ".join(_claims_by_id(request).get(ref, "") for ref in refs).lower()
    for word in RISKY_CLAIM_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lower) and not re.search(
            rf"\b{re.escape(word)}\b", cited
        ):
            raise ValueError(f"{path} uses unsupported high-risk claim word {word!r}")


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9%+.-]+", text)


def _redundant_with_selected_title(text: str, request: dict[str, Any]) -> bool:
    words = [x.lower() for x in _word_tokens(text)]
    if len(words) < 2:
        return False
    selected = request.get("selected_title_direction", {})
    title = (
        str(selected.get("title_text") or "")
        if isinstance(selected, dict)
        else ""
    )
    title_words = {x.lower() for x in _word_tokens(title)}
    return bool(title_words) and all(word in title_words for word in words)


def validate_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if str(response.get("video_id") or "") != str(request.get("video_id") or ""):
        raise ValueError("Thumbnail response video_id mismatch")
    concepts = response.get("thumbnail_concepts")
    angles = request.get("angles", [])
    if not isinstance(concepts, list) or len(concepts) != len(angles):
        raise ValueError("thumbnail_concepts must contain exactly one item per angle")
    angle_by_id = {
        str(item.get("angle_id")): item
        for item in angles
        if isinstance(item, dict) and str(item.get("angle_id") or "").strip()
    }
    if len(angle_by_id) != len(angles):
        raise ValueError("Thumbnail request has invalid angle IDs")

    contract = request.get("thumbnail_contract", {})
    allowed_refs = set(str(x) for x in request.get("allowed_evidence_refs", []))
    seen_ids: set[str] = set()
    seen_angles: set[str] = set()
    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(concepts):
        if not isinstance(item, dict):
            raise ValueError(f"thumbnail_concepts[{index}] must be an object")
        angle_id = _required_text(item.get("angle_id"), f"thumbnail_concepts[{index}].angle_id")
        if angle_id not in angle_by_id:
            raise ValueError(f"Unknown thumbnail angle_id: {angle_id}")
        thumbnail_id = _required_text(
            item.get("thumbnail_id"), f"thumbnail_concepts[{index}].thumbnail_id"
        )
        expected_id = f"thumbnail-{angle_id}"
        if thumbnail_id != expected_id:
            raise ValueError(f"thumbnail_id must be stable ID {expected_id!r}")
        if thumbnail_id in seen_ids or angle_id in seen_angles:
            raise ValueError("Duplicate thumbnail_id or angle_id")

        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"{thumbnail_id} requires evidence_refs")
        refs = [str(x) for x in refs]
        unknown = sorted(set(refs) - allowed_refs)
        if unknown:
            raise ValueError(f"{thumbnail_id} invents evidence_refs: {', '.join(unknown)}")
        angle_refs = {
            str(x) for x in angle_by_id[angle_id].get("evidence_refs", [])
        }
        if angle_refs and not (set(refs) & angle_refs):
            raise ValueError(f"{thumbnail_id} is not evidence-linked to its angle")

        hero = _required_text(item.get("hero_subject"), f"{thumbnail_id}.hero_subject")
        secondary_raw = item.get("secondary_element")
        secondary = str(secondary_raw).strip() if secondary_raw is not None else None
        if secondary == "":
            secondary = None
        anomaly_raw = item.get("visual_anomaly")
        anomaly = str(anomaly_raw).strip() if anomaly_raw is not None else None
        if anomaly == "":
            anomaly = None

        fields = {}
        for key in (
            "visual_action",
            "emotion",
            "composition",
            "background",
            "subject_separation_method",
            "viewer_visual_question",
            "mobile_legibility_intent",
        ):
            fields[key] = _required_text(item.get(key), f"{thumbnail_id}.{key}")

        text = str(item.get("text") or "").strip()
        words = _word_tokens(text)
        max_words = int(contract.get("maximum_text_words") or 4)
        if len(words) > max_words:
            raise ValueError(f"{thumbnail_id} thumbnail text exceeds {max_words} words")
        if int(item.get("text_word_count") or 0) != len(words):
            raise ValueError(f"{thumbnail_id} text_word_count is incorrect")
        if _redundant_with_selected_title(text, request):
            raise ValueError(f"{thumbnail_id} repeats selected title information")

        aspect_ratio = str(item.get("aspect_ratio") or "")
        if aspect_ratio != str(contract.get("aspect_ratio") or "16:9"):
            raise ValueError(f"{thumbnail_id} must use 16:9")
        focal = item.get("primary_focal_points")
        if focal != int(contract.get("primary_focal_points") or 1):
            raise ValueError(f"{thumbnail_id} must use one primary focal point")
        elements = item.get("meaningful_visual_elements")
        if (
            not isinstance(elements, int)
            or isinstance(elements, bool)
            or not 1 <= elements <= int(
                contract.get("maximum_meaningful_visual_elements") or 3
            )
        ):
            raise ValueError(f"{thumbnail_id} has too many meaningful visual elements")
        if item.get("timestamp_safe") is not True:
            raise ValueError(f"{thumbnail_id} places critical content in timestamp zone")
        if item.get("critical_bottom_right_content") is not False:
            raise ValueError(f"{thumbnail_id} has critical bottom-right content")
        face_present = item.get("face_present")
        if not isinstance(face_present, bool):
            raise ValueError(f"{thumbnail_id}.face_present must be boolean")

        claim_texts = [hero, text, fields["viewer_visual_question"]]
        if secondary:
            claim_texts.append(secondary)
        if anomaly:
            claim_texts.append(anomaly)
        for value in claim_texts:
            _validate_claim_language(value, refs, request, thumbnail_id)

        seen_ids.add(thumbnail_id)
        seen_angles.add(angle_id)
        normalized.append(
            {
                "thumbnail_id": thumbnail_id,
                "angle_id": angle_id,
                "hero_subject": hero,
                "secondary_element": secondary,
                "visual_anomaly": anomaly,
                **fields,
                "text": text,
                "text_word_count": len(words),
                "aspect_ratio": aspect_ratio,
                "primary_focal_points": focal,
                "meaningful_visual_elements": elements,
                "timestamp_safe": True,
                "critical_bottom_right_content": False,
                "face_present": face_present,
                "evidence_refs": refs,
            }
        )

    if seen_angles != set(angle_by_id):
        raise ValueError("Every psychological angle requires one thumbnail concept")

    return {
        "artifact": "thumbnail_concept_set",
        "schema_version": SCHEMA_VERSION,
        "video_id": request.get("video_id"),
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "search_vs_browse_intent": request.get("search_vs_browse_intent"),
        "thumbnail_concepts": normalized,
    }


def run_prepare() -> dict[str, Any]:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    items = _angle_payloads()
    current_paths: set[Path] = set()
    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for angle_item in items:
        try:
            request = build_request(angle_item)
            destination = REQUESTS_DIR / (
                f"{safe_slug(str(request['video_id']))}.thumbnail_concept_request.json"
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
                    "video_id": angle_item.get("video_id"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale in REQUESTS_DIR.glob("*.thumbnail_concept_request.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    angle_state = angle_snapshot()
    expected = int(angle_state.get("current") or 0) if angle_state.get("ready") else 0
    result = {
        "status": (
            "THUMBNAIL_CONCEPT_REQUESTS_READY"
            if expected > 0 and len(prepared) == expected and not failures
            else "PARTIAL"
            if prepared
            else "FAILED"
            if failures
            else "WAITING_FOR_PSYCHOLOGICAL_ANGLES"
        ),
        "expected": expected,
        "prepared": len(prepared),
        "failed": len(failures),
        "items": prepared,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def request_is_current(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.parent.resolve() != REQUESTS_DIR.resolve():
        return None
    try:
        request = load_json(path)
        items = _angle_payloads()
        item = next(
            (
                x for x in items
                if str(x.get("video_id") or "") == str(request.get("video_id") or "")
            ),
            None,
        )
        if not isinstance(item, dict):
            return None
        rebuilt = build_request(item)
        return request if rebuilt == request else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None



def request_snapshot() -> dict[str, Any]:
    angle_state = angle_snapshot()
    expected = int(angle_state.get("current") or 0) if angle_state.get("ready") else 0
    current = 0
    stale = 0
    if REQUESTS_DIR.exists():
        for path in REQUESTS_DIR.glob("*.thumbnail_concept_request.json"):
            if request_is_current(path) is not None:
                current += 1
            else:
                stale += 1
    ready = expected > 0 and current == expected and stale == 0
    return {
        "status": (
            "THUMBNAIL_CONCEPT_REQUESTS_READY"
            if ready
            else "THUMBNAIL_CONCEPT_REQUESTS_STALE"
            if stale
            else "WAITING_FOR_THUMBNAIL_CONCEPT_REQUESTS"
        ),
        "ready": ready,
        "expected": expected,
        "current": current,
        "stale": stale,
    }


def run_apply() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for request_path in sorted(REQUESTS_DIR.glob("*.thumbnail_concept_request.json")):
        request = request_is_current(request_path)
        if request is None:
            rejected.append(
                {"request": str(request_path), "error": "STALE_THUMBNAIL_REQUEST"}
            )
            continue
        slug = safe_slug(str(request.get("video_id") or ""))
        response_path = RESPONSES_DIR / f"{slug}.thumbnail_concept_response.json"
        if not response_path.is_file():
            continue
        try:
            response = load_json(response_path)
            prov = response.get("response_provenance", {})
            if (
                not isinstance(prov, dict)
                or prov.get("request_sha256") != sha256_file(request_path)
            ):
                raise ValueError("STALE_THUMBNAIL_RESPONSE")
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
        "artifact": "thumbnail_concepts",
        "schema_version": SCHEMA_VERSION,
        "count": len(items),
        "items": items,
        "rejected": rejected,
    }
    atomic_write_json(CONCEPTS_FILE, artifact)
    angle_state = angle_snapshot()
    expected = int(angle_state.get("current") or 0) if angle_state.get("ready") else 0
    result = {
        "status": (
            "THUMBNAIL_CONCEPTS_READY"
            if expected > 0 and len(items) == expected and not rejected
            else "PARTIAL"
            if items
            else "WAITING_FOR_THUMBNAIL_RESPONSES"
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
                "search_vs_browse_intent", "thumbnail_concepts",
            )
        }
        return rebuilt == comparable
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def snapshot() -> dict[str, Any]:
    angle_state = angle_snapshot()
    expected = int(angle_state.get("current") or 0) if angle_state.get("ready") else 0
    current: list[dict[str, Any]] = []
    stale = 0
    if CONCEPTS_FILE.is_file():
        try:
            payload = load_json(CONCEPTS_FILE)
            for item in payload.get("items", []) if isinstance(payload, dict) else []:
                if isinstance(item, dict) and item_is_current(item):
                    current.append(
                        {
                            "video_id": item.get("video_id"),
                            "format": item.get("format"),
                            "concept_count": len(item.get("thumbnail_concepts", [])),
                            "thumbnail_concepts": item.get("thumbnail_concepts", []),
                        }
                    )
                else:
                    stale += 1
        except (OSError, ValueError, json.JSONDecodeError):
            stale += 1

    ready = expected > 0 and len(current) == expected and stale == 0
    return {
        "status": (
            "THUMBNAIL_CONCEPTS_READY"
            if ready
            else "THUMBNAIL_CONCEPTS_STALE"
            if stale
            else "WAITING_FOR_THUMBNAIL_CONCEPTS"
        ),
        "ready": ready,
        "expected": expected,
        "current": len(current),
        "stale": stale,
        "items": current,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice 25 thumbnail concepts")
    parser.add_argument("--mode", choices=("prepare", "apply", "status"), required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = run_prepare()
    elif args.mode == "apply":
        result = run_apply()
    else:
        result = snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") in {"FAILED", "PARTIAL", "THUMBNAIL_CONCEPTS_STALE"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
