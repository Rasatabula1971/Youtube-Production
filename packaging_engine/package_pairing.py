"""Slice 26 title-thumbnail pairing and package validation.

Builds the full 5-title x 5-thumbnail compatibility matrix per approved format,
evaluates it in resumable five-pair chunks, and deterministically derives
PASS / REWORK / REJECT without producing a viral score or automatic winner.

The successful Slice 26 boundary is PACKAGE_VALIDATION_READY. The Final
Packaging Human Gate remains a later slice.
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
_STORY = _ROOT / "story_script_engine"
if str(_STORY) not in sys.path:
    sys.path.insert(0, str(_STORY))

from pipeline_integrity import atomic_write_json
from packaging_brief import (
    BRIEF_DIR,
    brief_is_current,
    load_json,
    snapshot as packaging_brief_snapshot,
)
from psychological_angles import (
    ANGLES_FILE,
    item_is_current as angle_item_is_current,
)
from thumbnail_concepts import (
    CONCEPTS_FILE,
    item_is_current as thumbnail_item_is_current,
    snapshot as thumbnail_snapshot,
)
from title_direction import CANDIDATES_FILE as TITLE_CANDIDATES_FILE
from title_direction_review import snapshot as title_direction_snapshot
from story_script_engine import safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_config.json"
OUTPUT_DIR = HERE / "output"
MATURE_DIR = OUTPUT_DIR / "mature_packaging"
REQUESTS_DIR = MATURE_DIR / "package_pairing_requests"
RESPONSES_DIR = MATURE_DIR / "package_pairing_responses"
PACKAGE_CANDIDATES_FILE = MATURE_DIR / "package_candidates.json"
PACKAGE_VALIDATION_FILE = MATURE_DIR / "package_validation.json"
PROMISE_ALIGNMENT_FILE = MATURE_DIR / "promise_alignment.json"
SUMMARY_FILE = MATURE_DIR / "package_validation_summary.json"

SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "package-pairing-validation-v1.0"

REDUNDANCY_LEVELS = {"NONE", "LOW", "MODERATE", "HIGH"}
PROMISE_STATUSES = {
    "PASS",
    "UNDERPROMISE",
    "OVERPROMISE",
    "WRONG_PROMISE",
    "DELAYED_ACKNOWLEDGEMENT",
    "MISSING_PAYOFF",
}
HOOK_STATUSES = {"PASS", "REWORK", "FAIL"}
CLAIM_STATUSES = {
    "VERIFIED",
    "SUPPORTED_WITH_QUALIFICATION",
    "UNSUPPORTED",
    "CONFLICTING",
}
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[$£€]?\\d+(?:[.,]\\d+)*(?:\\s?%|\\s?[xX])?)(?![A-Za-z0-9])"
)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
    "when", "why", "with", "you", "your",
}


def load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    block = payload.get("package_pairing_validation")
    if not isinstance(block, dict):
        raise ValueError("Missing package_pairing_validation config")
    if str(block.get("pairing_mode") or "") != "FULL_CROSS_PRODUCT":
        raise ValueError("Slice 26 requires FULL_CROSS_PRODUCT pairing")
    if int(block.get("titles_per_format") or 0) != 5:
        raise ValueError("Slice 26 requires five titles per format")
    if int(block.get("thumbnails_per_format") or 0) != 5:
        raise ValueError("Slice 26 requires five thumbnails per format")
    if int(block.get("pairs_per_format") or 0) != 25:
        raise ValueError("Slice 26 requires 25 title-thumbnail pairs per format")
    diagnostics = [str(x) for x in block.get("diagnostics", [])]
    if len(diagnostics) != 11 or len(diagnostics) != len(set(diagnostics)):
        raise ValueError("Slice 26 requires exactly 11 unique diagnostic dimensions")
    return payload


def _hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _meaningful_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9%+.-]+", text.lower())
        if token not in STOP_WORDS and len(token) > 1
    ]


def lexical_redundancy(title: str, thumbnail_text: str) -> dict[str, Any]:
    title_tokens = _meaningful_tokens(title)
    thumb_tokens = _meaningful_tokens(thumbnail_text)
    if not thumb_tokens:
        return {"level": "NONE", "shared_tokens": [], "ratio": 0.0}

    title_set = set(title_tokens)
    shared = sorted(set(thumb_tokens) & title_set)
    ratio = len(shared) / max(1, len(set(thumb_tokens)))
    normalized_title = " ".join(title_tokens)
    normalized_thumb = " ".join(thumb_tokens)

    if len(thumb_tokens) >= 2 and (
        normalized_thumb and normalized_thumb in normalized_title
        or ratio >= 0.75
    ):
        level = "HIGH"
    elif shared and ratio >= 0.5:
        level = "MODERATE"
    elif shared:
        level = "LOW"
    else:
        level = "NONE"
    return {
        "level": level,
        "shared_tokens": shared,
        "ratio": round(ratio, 3),
    }


def _current_briefs() -> dict[str, tuple[Path, dict[str, Any]]]:
    state = packaging_brief_snapshot()
    if not state.get("ready"):
        raise ValueError("WAITING_FOR_PACKAGING_BRIEF")
    out: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(BRIEF_DIR.glob("*.packaging_brief.json")):
        brief = brief_is_current(path)
        if brief is None:
            continue
        video_id = _required_text(brief.get("video_id"), "video_id")
        if video_id in out:
            raise ValueError("DUPLICATE_PACKAGING_BRIEF")
        out[video_id] = (path, brief)
    if len(out) != int(state.get("current") or 0):
        raise ValueError("STALE_PACKAGING_BRIEF")
    return out


def _current_angle_items() -> dict[str, dict[str, Any]]:
    if not ANGLES_FILE.is_file():
        raise ValueError("WAITING_FOR_PSYCHOLOGICAL_ANGLES")
    payload = load_json(ANGLES_FILE)
    if (
        not isinstance(payload, dict)
        or payload.get("artifact") != "psychological_packaging_angles"
    ):
        raise ValueError("INVALID_PSYCHOLOGICAL_ANGLES")
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict) or not angle_item_is_current(item):
            continue
        video_id = _required_text(item.get("video_id"), "video_id")
        if video_id in out:
            raise ValueError("DUPLICATE_PSYCHOLOGICAL_ANGLES")
        out[video_id] = item
    return out


def _current_thumbnail_items() -> dict[str, dict[str, Any]]:
    state = thumbnail_snapshot()
    if not state.get("ready"):
        raise ValueError("WAITING_FOR_THUMBNAIL_CONCEPTS")
    if not CONCEPTS_FILE.is_file():
        raise ValueError("WAITING_FOR_THUMBNAIL_CONCEPTS")
    payload = load_json(CONCEPTS_FILE)
    if not isinstance(payload, dict) or payload.get("artifact") != "thumbnail_concepts":
        raise ValueError("INVALID_THUMBNAIL_CONCEPTS")
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict) or not thumbnail_item_is_current(item):
            continue
        video_id = _required_text(item.get("video_id"), "video_id")
        if video_id in out:
            raise ValueError("DUPLICATE_THUMBNAIL_CONCEPTS")
        out[video_id] = item
    if len(out) != int(state.get("current") or 0):
        raise ValueError("STALE_THUMBNAIL_CONCEPTS")
    return out


def _title_concepts() -> dict[str, dict[str, Any]]:
    gate = title_direction_snapshot()
    if gate.get("status") != "TITLE_DIRECTION_SELECTED" or not gate.get("ready"):
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    if not TITLE_CANDIDATES_FILE.is_file():
        raise ValueError("WAITING_FOR_TITLE_DIRECTION_CANDIDATES")
    payload = load_json(TITLE_CANDIDATES_FILE)
    if (
        not isinstance(payload, dict)
        or payload.get("artifact") != "title_direction_candidates"
    ):
        raise ValueError("INVALID_TITLE_DIRECTION_CANDIDATES")
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("concepts", []):
        if not isinstance(item, dict):
            continue
        concept_id = _required_text(item.get("concept_id"), "concept_id")
        if concept_id in out:
            raise ValueError("DUPLICATE_TITLE_DIRECTION_CONCEPT")
        out[concept_id] = item
    return out


def _titles_for(
    title_item: dict[str, Any],
    fmt: str,
    brief: dict[str, Any],
) -> list[dict[str, Any]]:
    titles = title_item.get("titles", {})
    values = titles.get(fmt, []) if isinstance(titles, dict) else []
    if not isinstance(values, list) or len(values) != 5:
        raise ValueError("TITLE_POOL_MUST_HAVE_FIVE_CANDIDATES")
    ids: set[str] = set()
    out: list[dict[str, Any]] = []
    approved_refs = {
        str(item.get("claim_id"))
        for item in brief.get("approved_claims", [])
        if isinstance(item, dict)
    }
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("INVALID_TITLE_DIRECTION_CANDIDATE")
        title_id = _required_text(item.get("title_id"), "title_id")
        if title_id in ids:
            raise ValueError("DUPLICATE_TITLE_ID")
        refs = [str(x) for x in item.get("evidence_refs", [])]
        if set(refs) - approved_refs:
            raise ValueError("TITLE_EVIDENCE_CONFLICT")
        out.append(
            {
                "title_id": title_id,
                "title_text": _required_text(item.get("title_text"), "title_text"),
                "psychological_angle": item.get("psychological_angle"),
                "primary_driver": item.get("primary_driver"),
                "secondary_driver": item.get("secondary_driver"),
                "core_claim": _required_text(item.get("core_claim"), "core_claim"),
                "evidence_refs": refs,
                "character_count": int(item.get("character_count") or len(str(item.get("title_text") or ""))),
                "search_intent": item.get("search_intent"),
            }
        )
        ids.add(title_id)

    selected = brief.get("selected_title", {})
    selected_id = (
        str(selected.get("title_id") or "")
        if isinstance(selected, dict)
        else ""
    )
    if selected_id not in ids:
        raise ValueError("SELECTED_TITLE_NO_LONGER_MATCHES_FINAL_SCRIPT")
    selected_text = (
        str(selected.get("title_text") or "").strip()
        if isinstance(selected, dict)
        else ""
    )
    if not selected_text:
        raise ValueError("MISSING_SELECTED_TITLE_DIRECTION")
    for candidate in out:
        if candidate["title_id"] == selected_id:
            candidate["title_text"] = selected_text
            candidate["character_count"] = len(selected_text)
            candidate["human_selected_wording"] = True
        else:
            candidate["human_selected_wording"] = False
    return out


def _angle_map(angle_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = angle_item.get("angles", [])
    if not isinstance(values, list) or len(values) != 5:
        raise ValueError("PSYCHOLOGICAL_ANGLE_SET_MUST_HAVE_FIVE")
    out: dict[str, dict[str, Any]] = {}
    for angle in values:
        if not isinstance(angle, dict):
            raise ValueError("INVALID_PSYCHOLOGICAL_ANGLE")
        angle_id = _required_text(angle.get("angle_id"), "angle_id")
        if angle_id in out:
            raise ValueError("DUPLICATE_ANGLE_ID")
        out[angle_id] = angle
    return out


def _hook_id(video_id: str) -> str:
    return f"{safe_slug(video_id)}-approved-opening-hook"


def _unsupported_numbers(text: str, brief: dict[str, Any]) -> list[str]:
    allowed = {
        str(item.get("value") or "").strip().lower()
        for item in brief.get("approved_numbers", [])
        if isinstance(item, dict) and str(item.get("value") or "").strip()
    }
    return [
        value
        for value in NUMBER_RE.findall(text)
        if value.strip().lower() not in allowed
    ]


def _pair(
    *,
    brief: dict[str, Any],
    title: dict[str, Any],
    thumbnail: dict[str, Any],
    angle: dict[str, Any],
) -> dict[str, Any]:
    title_id = str(title["title_id"])
    thumbnail_id = str(thumbnail["thumbnail_id"])
    package_id = f"package-{title_id}--{thumbnail_id}"
    selected = brief.get("selected_title", {})
    selected_id = (
        str(selected.get("title_id") or "")
        if isinstance(selected, dict)
        else ""
    )
    return {
        "package_id": package_id,
        "video_id": brief.get("video_id"),
        "concept_id": brief.get("concept_id"),
        "format": brief.get("format"),
        "title_id": title_id,
        "title_text": title.get("title_text"),
        "title_psychological_angle": title.get("psychological_angle"),
        "title_primary_driver": title.get("primary_driver"),
        "title_secondary_driver": title.get("secondary_driver"),
        "title_core_claim": title.get("core_claim"),
        "title_evidence_refs": list(title.get("evidence_refs", [])),
        "title_character_count": int(title.get("character_count") or 0),
        "title_search_intent": title.get("search_intent"),
        "unsupported_title_numbers": _unsupported_numbers(
            str(title.get("title_text") or ""), brief
        ),
        "thumbnail_id": thumbnail_id,
        "thumbnail_text": thumbnail.get("text"),
        "thumbnail_text_word_count": int(thumbnail.get("text_word_count") or 0),
        "thumbnail_hero_subject": thumbnail.get("hero_subject"),
        "thumbnail_secondary_element": thumbnail.get("secondary_element"),
        "thumbnail_visual_anomaly": thumbnail.get("visual_anomaly"),
        "thumbnail_visual_action": thumbnail.get("visual_action"),
        "thumbnail_viewer_visual_question": thumbnail.get("viewer_visual_question"),
        "thumbnail_evidence_refs": list(thumbnail.get("evidence_refs", [])),
        "angle_id": angle.get("angle_id"),
        "angle_primary_driver": angle.get("primary_driver"),
        "angle_secondary_driver": angle.get("secondary_driver"),
        "angle_viewer_question": angle.get("viewer_question"),
        "angle_expected_click_reason": angle.get("expected_click_reason"),
        "psychological_angle": angle.get("primary_driver"),
        "viewer_promise": brief.get("viewer_promise_contract", {}).get(
            "viewer_expectation"
        ),
        "hook_id": _hook_id(str(brief.get("video_id") or "")),
        "opening_hook": brief.get("opening_hook"),
        "selected_title_direction_match": title_id == selected_id,
        "lexical_redundancy": lexical_redundancy(
            str(title.get("title_text") or ""),
            str(thumbnail.get("text") or ""),
        ),
        "title_length_guidance": {
            "preferred_range": [45, 60],
            "within_preferred_range": 45 <= int(title.get("character_count") or 0) <= 60,
            "hard_rejection": False,
        },
    }


def build_inputs() -> list[dict[str, Any]]:
    briefs = _current_briefs()
    angles = _current_angle_items()
    thumbnails = _current_thumbnail_items()
    titles = _title_concepts()

    config = load_config()["package_pairing_validation"]
    inputs: list[dict[str, Any]] = []
    for video_id in sorted(briefs):
        brief_path, brief = briefs[video_id]
        concept_id = _required_text(brief.get("concept_id"), "concept_id")
        fmt = _required_text(brief.get("format"), "format")
        angle_item = angles.get(video_id)
        thumbnail_item = thumbnails.get(video_id)
        title_item = titles.get(concept_id)
        if not isinstance(angle_item, dict):
            raise ValueError(f"MISSING_PSYCHOLOGICAL_ANGLES:{video_id}")
        if not isinstance(thumbnail_item, dict):
            raise ValueError(f"MISSING_THUMBNAIL_CONCEPTS:{video_id}")
        if not isinstance(title_item, dict):
            raise ValueError(f"MISSING_TITLE_CANDIDATES:{concept_id}")

        title_values = _titles_for(title_item, fmt, brief)
        angle_by_id = _angle_map(angle_item)
        thumbnail_values = thumbnail_item.get("thumbnail_concepts", [])
        if not isinstance(thumbnail_values, list) or len(thumbnail_values) != 5:
            raise ValueError("THUMBNAIL_POOL_MUST_HAVE_FIVE_CONCEPTS")

        pairs: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        seen_thumbs: set[str] = set()
        for thumbnail in thumbnail_values:
            if not isinstance(thumbnail, dict):
                raise ValueError("INVALID_THUMBNAIL_CONCEPT")
            thumbnail_id = _required_text(thumbnail.get("thumbnail_id"), "thumbnail_id")
            angle_id = _required_text(thumbnail.get("angle_id"), "angle_id")
            if thumbnail_id in seen_thumbs:
                raise ValueError("DUPLICATE_THUMBNAIL_ID")
            angle = angle_by_id.get(angle_id)
            if not isinstance(angle, dict):
                raise ValueError("THUMBNAIL_ANGLE_MISMATCH")
            chunk_pairs = [
                _pair(
                    brief=brief,
                    title=title,
                    thumbnail=thumbnail,
                    angle=angle,
                )
                for title in title_values
            ]
            if len(chunk_pairs) != int(config["evaluations_per_request"]):
                raise ValueError("PAIRING_CHUNK_SIZE_MISMATCH")
            pairs.extend(chunk_pairs)
            chunks.append(
                {
                    "video_id": video_id,
                    "thumbnail_id": thumbnail_id,
                    "thumbnail": thumbnail,
                    "angle": angle,
                    "pairs": chunk_pairs,
                }
            )
            seen_thumbs.add(thumbnail_id)

        if len(pairs) != int(config["pairs_per_format"]):
            raise ValueError("PAIRING_MATRIX_SIZE_MISMATCH")
        if len({x["package_id"] for x in pairs}) != len(pairs):
            raise ValueError("DUPLICATE_PACKAGE_ID")

        inputs.append(
            {
                "video_id": video_id,
                "concept_id": concept_id,
                "format": fmt,
                "brief_path": brief_path,
                "brief": brief,
                "title_item": title_item,
                "angle_item": angle_item,
                "thumbnail_item": thumbnail_item,
                "pairs": pairs,
                "chunks": chunks,
            }
        )
    return inputs


def _request_for_chunk(
    input_item: dict[str, Any],
    chunk: dict[str, Any],
) -> dict[str, Any]:
    brief = input_item["brief"]
    config = load_config()["package_pairing_validation"]
    return {
        "artifact": "package_pairing_validation_request",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "video_id": input_item["video_id"],
        "concept_id": input_item["concept_id"],
        "format": input_item["format"],
        "thumbnail_id": chunk["thumbnail_id"],
        "search_vs_browse_intent": brief.get("search_vs_browse_intent"),
        "viewer_promise_contract": brief.get("viewer_promise_contract"),
        "opening_hook": brief.get("opening_hook"),
        "central_question": brief.get("central_question"),
        "video_payoff": brief.get("video_payoff"),
        "approved_claims": brief.get("approved_claims", []),
        "approved_numbers": brief.get("approved_numbers", []),
        "prohibited_or_unsupported_claims": brief.get(
            "prohibited_or_unsupported_claims", []
        ),
        "thumbnail": chunk["thumbnail"],
        "angle": chunk["angle"],
        "pair_candidates": chunk["pairs"],
        "diagnostic_dimensions": list(config["diagnostics"]),
        "hard_reject_codes": list(config["hard_reject_codes"]),
        "rework_codes": list(config["rework_codes"]),
        "instructions": [
            "Evaluate every supplied title-thumbnail pair independently.",
            "Do not rank packages and do not select a winner.",
            "Do not produce a viral score, CTR forecast, view forecast or retention forecast.",
            "Assess semantic redundancy across title text, thumbnail text and thumbnail visual proposition.",
            "Assess whether title and thumbnail add different information that strengthens one unresolved question.",
            "Check the package against the exact Viewer Promise, opening hook and script payoff.",
            "A hook should acknowledge why the viewer clicked without prematurely resolving the open loop.",
            "Material title and thumbnail claims must remain supported by approved evidence.",
            "Use hard reject findings only for unsupported/false/misrepresentative/conflicting/prohibited claims.",
            "Use rework findings for redundancy, weak/delayed hook confirmation, excessive complexity, text length, timestamp risk, unclear subject or stale selected-title direction.",
            "Score each diagnostic from 0 to 5 as decision support only. Scores are not predictions.",
        ],
        "request_provenance": {
            "packaging_brief": str(input_item["brief_path"].resolve()),
            "packaging_brief_sha256": sha256_file(input_item["brief_path"]),
            "title_direction_candidates": str(TITLE_CANDIDATES_FILE.resolve()),
            "title_direction_candidates_sha256": sha256_file(TITLE_CANDIDATES_FILE),
            "psychological_angles": str(ANGLES_FILE.resolve()),
            "psychological_angles_sha256": sha256_file(ANGLES_FILE),
            "thumbnail_concepts": str(CONCEPTS_FILE.resolve()),
            "thumbnail_concepts_sha256": sha256_file(CONCEPTS_FILE),
        },
    }


def _candidate_artifact(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for input_item in inputs:
        items.append(
            {
                "video_id": input_item["video_id"],
                "concept_id": input_item["concept_id"],
                "format": input_item["format"],
                "pairing_mode": "FULL_CROSS_PRODUCT",
                "pair_count": len(input_item["pairs"]),
                "packages": input_item["pairs"],
            }
        )
    return {
        "artifact": "package_candidates",
        "schema_version": SCHEMA_VERSION,
        "pairing_mode": "FULL_CROSS_PRODUCT",
        "count": sum(item["pair_count"] for item in items),
        "items": items,
    }


def run_prepare() -> dict[str, Any]:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    inputs = build_inputs()
    candidate_artifact = _candidate_artifact(inputs)
    atomic_write_json(PACKAGE_CANDIDATES_FILE, candidate_artifact)

    current_paths: set[Path] = set()
    prepared: list[dict[str, Any]] = []
    for input_item in inputs:
        for chunk in input_item["chunks"]:
            request = _request_for_chunk(input_item, chunk)
            slug = safe_slug(
                f"{input_item['video_id']}--{chunk['thumbnail_id']}"
            )
            destination = REQUESTS_DIR / f"{slug}.package_pairing_request.json"
            atomic_write_json(destination, request)
            current_paths.add(destination.resolve())
            prepared.append(
                {
                    "video_id": input_item["video_id"],
                    "thumbnail_id": chunk["thumbnail_id"],
                    "pair_count": len(chunk["pairs"]),
                    "request": str(destination.resolve()),
                    "request_sha256": sha256_file(destination),
                }
            )

    for stale in REQUESTS_DIR.glob("*.package_pairing_request.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    expected_formats = len(inputs)
    expected_requests = expected_formats * 5
    expected_pairs = expected_formats * 25
    result = {
        "status": (
            "PACKAGE_PAIRING_REQUESTS_READY"
            if expected_formats > 0
            and len(prepared) == expected_requests
            and candidate_artifact["count"] == expected_pairs
            else "FAILED"
        ),
        "formats": expected_formats,
        "expected_requests": expected_requests,
        "prepared_requests": len(prepared),
        "expected_pairs": expected_pairs,
        "candidate_pairs": candidate_artifact["count"],
        "items": prepared,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def _current_request_map() -> dict[tuple[str, str], dict[str, Any]]:
    inputs = build_inputs()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for input_item in inputs:
        for chunk in input_item["chunks"]:
            request = _request_for_chunk(input_item, chunk)
            key = (
                str(input_item["video_id"]),
                str(chunk["thumbnail_id"]),
            )
            out[key] = request
    return out


def request_is_current(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.parent.resolve() != REQUESTS_DIR.resolve():
        return None
    try:
        saved = load_json(path)
        key = (
            str(saved.get("video_id") or ""),
            str(saved.get("thumbnail_id") or ""),
        )
        current = _current_request_map().get(key)
        return saved if current is not None and saved == current else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def request_snapshot() -> dict[str, Any]:
    try:
        current_map = _current_request_map()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        current_map = {}
    expected = len(current_map)
    current = 0
    stale = 0
    if REQUESTS_DIR.exists():
        for path in REQUESTS_DIR.glob("*.package_pairing_request.json"):
            if request_is_current(path) is not None:
                current += 1
            else:
                stale += 1
    ready = expected > 0 and current == expected and stale == 0
    return {
        "status": (
            "PACKAGE_PAIRING_REQUESTS_READY"
            if ready
            else "PACKAGE_PAIRING_REQUESTS_STALE"
            if stale
            else "WAITING_FOR_PACKAGE_PAIRING_REQUESTS"
        ),
        "ready": ready,
        "expected": expected,
        "current": current,
        "stale": stale,
    }


def _validate_diagnostics(value: Any, request: dict[str, Any]) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("diagnostics must be an object")
    expected = [str(x) for x in request.get("diagnostic_dimensions", [])]
    if set(value) != set(expected):
        raise ValueError("diagnostics must contain exactly the configured dimensions")
    out: dict[str, int] = {}
    for key in expected:
        score = value.get(key)
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or score < 0
            or score > 5
        ):
            raise ValueError(f"diagnostics.{key} must be integer 0-5")
        out[key] = score
    return out


def _validate_findings(
    value: Any,
    *,
    allowed_codes: set[str],
    allowed_refs: set[str],
    field: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{field}[{index}] must be an object")
        code = _required_text(item.get("code"), f"{field}[{index}].code")
        if code not in allowed_codes:
            raise ValueError(f"Unsupported {field} code: {code}")
        if code in seen:
            raise ValueError(f"Duplicate {field} code: {code}")
        reason = _required_text(item.get("reason"), f"{field}[{index}].reason")
        refs = item.get("evidence_refs", [])
        if not isinstance(refs, list):
            raise ValueError(f"{field}[{index}].evidence_refs must be a list")
        refs = [str(x) for x in refs]
        unknown = sorted(set(refs) - allowed_refs)
        if unknown:
            raise ValueError(
                f"{field}[{index}] invents evidence_refs: {', '.join(unknown)}"
            )
        out.append({"code": code, "reason": reason, "evidence_refs": refs})
        seen.add(code)
    return out


def _validate_claim_assessment(
    value: Any,
    *,
    allowed_refs: set[str],
    package_refs: set[str],
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    status = _required_text(value.get("status"), f"{field}.status").upper()
    if status not in CLAIM_STATUSES:
        raise ValueError(f"{field}.status is invalid")
    reason = _required_text(value.get("reason"), f"{field}.reason")
    refs = value.get("evidence_refs", [])
    if not isinstance(refs, list):
        raise ValueError(f"{field}.evidence_refs must be a list")
    refs = [str(x) for x in refs]
    if set(refs) - allowed_refs:
        raise ValueError(f"{field} invents evidence refs")
    if set(refs) - package_refs:
        raise ValueError(f"{field} cites evidence outside the paired component")
    if status in {"VERIFIED", "SUPPORTED_WITH_QUALIFICATION"} and not refs:
        raise ValueError(f"{field} supported status requires evidence")
    return {"status": status, "reason": reason, "evidence_refs": refs}


def _final_status(
    package: dict[str, Any],
    evaluation: dict[str, Any],
    request: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    hard = list(evaluation["hard_validation_findings"])
    rework = list(evaluation["rework_findings"])
    hard_codes = {item["code"] for item in hard}
    rework_codes = {item["code"] for item in rework}

    def add_hard(code: str, reason: str) -> None:
        if code not in hard_codes:
            hard.append({"code": code, "reason": reason, "evidence_refs": []})
            hard_codes.add(code)

    def add_rework(code: str, reason: str) -> None:
        if code not in rework_codes:
            rework.append({"code": code, "reason": reason, "evidence_refs": []})
            rework_codes.add(code)

    if not package.get("title_evidence_refs"):
        add_hard(
            "unsupported_material_claim",
            "The title's required core claim has no approved evidence reference.",
        )

    unsupported_numbers = package.get("unsupported_title_numbers", [])
    if isinstance(unsupported_numbers, list) and unsupported_numbers:
        add_hard(
            "unsupported_material_claim",
            "The title introduces unapproved numeric material: "
            + ", ".join(str(x) for x in unsupported_numbers),
        )

    for field in ("title_claim_validation", "thumbnail_claim_validation"):
        status = str(evaluation[field]["status"])
        if status == "UNSUPPORTED":
            add_hard(
                "unsupported_material_claim",
                f"{field} is unsupported by the paired approved evidence.",
            )
        elif status == "CONFLICTING":
            add_hard(
                "evidence_conflict",
                f"{field} conflicts with the paired approved evidence.",
            )

    promise = str(evaluation["promise_consistency"])
    if promise == "OVERPROMISE":
        add_hard(
            "title_misrepresents_video",
            "The combined package overpromises beyond the approved Viewer Promise.",
        )
    elif promise in {"WRONG_PROMISE", "MISSING_PAYOFF"}:
        add_hard(
            "thumbnail_misrepresents_video",
            "The combined package creates a promise the approved payoff does not fulfill.",
        )
    elif promise == "UNDERPROMISE":
        add_rework(
            "selected_title_no_longer_matches_final_script",
            "The package undersells or obscures the approved payoff.",
        )
    elif promise == "DELAYED_ACKNOWLEDGEMENT":
        add_rework(
            "promise_not_addressed_early",
            "The package promise is not acknowledged early enough by the approved opening.",
        )

    hook_status = str(evaluation["hook_alignment_status"])
    if hook_status != "PASS":
        add_rework(
            "weak_hook_alignment",
            "The approved opening does not strongly confirm why this package was clicked.",
        )

    lexical = package.get("lexical_redundancy", {})
    if (
        isinstance(lexical, dict)
        and lexical.get("level") == "HIGH"
    ):
        add_rework(
            "title_thumbnail_redundancy",
            "Thumbnail text repeats substantial meaningful information from the title.",
        )
    if (
        evaluation["semantic_redundancy"] == "HIGH"
        or evaluation["visual_text_redundancy"] == "HIGH"
    ):
        add_rework(
            "title_thumbnail_redundancy",
            "Title and thumbnail contribute too much of the same information.",
        )

    if hard:
        return "REJECT", hard, rework
    if rework:
        return "REWORK", hard, rework
    return "PASS", hard, rework


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    if str(response.get("video_id") or "") != str(request.get("video_id") or ""):
        raise ValueError("Package validation response video_id mismatch")
    if str(response.get("thumbnail_id") or "") != str(request.get("thumbnail_id") or ""):
        raise ValueError("Package validation response thumbnail_id mismatch")

    evaluations = response.get("evaluations")
    pairs = request.get("pair_candidates", [])
    if not isinstance(evaluations, list) or len(evaluations) != len(pairs):
        raise ValueError("evaluations must contain exactly one result per pair")
    pair_by_id = {
        str(item.get("package_id")): item
        for item in pairs
        if isinstance(item, dict) and str(item.get("package_id") or "").strip()
    }
    if len(pair_by_id) != len(pairs):
        raise ValueError("Invalid or duplicate package_id in request")

    approved_refs = {
        str(item.get("claim_id"))
        for item in request.get("approved_claims", [])
        if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
    }
    hard_codes = set(str(x) for x in request.get("hard_reject_codes", []))
    rework_codes = set(str(x) for x in request.get("rework_codes", []))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for index, item in enumerate(evaluations):
        if not isinstance(item, dict):
            raise ValueError(f"evaluations[{index}] must be an object")
        package_id = _required_text(
            item.get("package_id"), f"evaluations[{index}].package_id"
        )
        package = pair_by_id.get(package_id)
        if package is None or package_id in seen:
            raise ValueError("Unknown or duplicate package_id in evaluation")

        semantic = _required_text(
            item.get("semantic_redundancy"),
            f"{package_id}.semantic_redundancy",
        ).upper()
        visual_text = _required_text(
            item.get("visual_text_redundancy"),
            f"{package_id}.visual_text_redundancy",
        ).upper()
        if semantic not in REDUNDANCY_LEVELS or visual_text not in REDUNDANCY_LEVELS:
            raise ValueError("Redundancy status must be NONE/LOW/MODERATE/HIGH")

        complementarity = item.get("psychological_complementarity")
        information_gain = item.get("information_gain")
        for name, score in (
            ("psychological_complementarity", complementarity),
            ("information_gain", information_gain),
        ):
            if (
                not isinstance(score, int)
                or isinstance(score, bool)
                or score < 0
                or score > 5
            ):
                raise ValueError(f"{package_id}.{name} must be integer 0-5")

        promise = _required_text(
            item.get("promise_consistency"),
            f"{package_id}.promise_consistency",
        ).upper()
        if promise not in PROMISE_STATUSES:
            raise ValueError(f"{package_id}.promise_consistency is invalid")
        promise_reason = _required_text(
            item.get("promise_alignment_reason"),
            f"{package_id}.promise_alignment_reason",
        )
        hook_status = _required_text(
            item.get("hook_alignment_status"),
            f"{package_id}.hook_alignment_status",
        ).upper()
        if hook_status not in HOOK_STATUSES:
            raise ValueError(f"{package_id}.hook_alignment_status is invalid")
        hook_reason = _required_text(
            item.get("hook_alignment_reason"),
            f"{package_id}.hook_alignment_reason",
        )

        title_refs = set(str(x) for x in package.get("title_evidence_refs", []))
        thumb_refs = set(str(x) for x in package.get("thumbnail_evidence_refs", []))
        title_claim = _validate_claim_assessment(
            item.get("title_claim_validation"),
            allowed_refs=approved_refs,
            package_refs=title_refs,
            field=f"{package_id}.title_claim_validation",
        )
        thumbnail_claim = _validate_claim_assessment(
            item.get("thumbnail_claim_validation"),
            allowed_refs=approved_refs,
            package_refs=thumb_refs,
            field=f"{package_id}.thumbnail_claim_validation",
        )

        hard = _validate_findings(
            item.get("hard_validation_findings"),
            allowed_codes=hard_codes,
            allowed_refs=approved_refs,
            field=f"{package_id}.hard_validation_findings",
        )
        rework = _validate_findings(
            item.get("rework_findings"),
            allowed_codes=rework_codes,
            allowed_refs=approved_refs,
            field=f"{package_id}.rework_findings",
        )
        diagnostics = _validate_diagnostics(item.get("diagnostics"), request)

        evaluation = {
            "semantic_redundancy": semantic,
            "semantic_redundancy_reason": _required_text(
                item.get("semantic_redundancy_reason"),
                f"{package_id}.semantic_redundancy_reason",
            ),
            "visual_text_redundancy": visual_text,
            "psychological_complementarity": complementarity,
            "information_gain": information_gain,
            "promise_consistency": promise,
            "promise_alignment_reason": promise_reason,
            "hook_alignment_status": hook_status,
            "hook_alignment_reason": hook_reason,
            "title_claim_validation": title_claim,
            "thumbnail_claim_validation": thumbnail_claim,
            "hard_validation_findings": hard,
            "rework_findings": rework,
            "diagnostics": diagnostics,
        }
        status, hard_final, rework_final = _final_status(package, evaluation, request)

        out.append(
            {
                **package,
                "validation_status": status,
                **evaluation,
                "hard_validation_findings": hard_final,
                "rework_findings": rework_final,
                "diagnostics_are_predictions": False,
                "viral_score": None,
            }
        )
        seen.add(package_id)

    if seen != set(pair_by_id):
        raise ValueError("Every pair must receive exactly one evaluation")
    return out


def _response_path_for(request: dict[str, Any]) -> Path:
    slug = safe_slug(
        f"{request.get('video_id')}--{request.get('thumbnail_id')}"
    )
    return RESPONSES_DIR / f"{slug}.package_pairing_response.json"


def _collect_current() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validations: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if not REQUESTS_DIR.exists():
        return validations, rejected

    for request_path in sorted(REQUESTS_DIR.glob("*.package_pairing_request.json")):
        request = request_is_current(request_path)
        if request is None:
            rejected.append(
                {"request": str(request_path), "error": "STALE_PACKAGE_PAIRING_REQUEST"}
            )
            continue
        response_path = _response_path_for(request)
        if not response_path.is_file():
            continue
        try:
            response = load_json(response_path)
            prov = response.get("response_provenance", {})
            if (
                not isinstance(prov, dict)
                or prov.get("request_sha256") != sha256_file(request_path)
            ):
                raise ValueError("STALE_PACKAGE_PAIRING_RESPONSE")
            values = validate_response(response, request)
            for item in values:
                item["request_file"] = str(request_path.resolve())
                item["request_sha256"] = sha256_file(request_path)
                item["response_file"] = str(response_path.resolve())
                item["response_sha256"] = sha256_file(response_path)
                item["response_provenance"] = prov
                validations.append(item)
        except Exception as exc:
            rejected.append(
                {
                    "video_id": request.get("video_id"),
                    "thumbnail_id": request.get("thumbnail_id"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return validations, rejected


def run_apply() -> dict[str, Any]:
    validations, rejected = _collect_current()
    artifact = {
        "artifact": "package_validation",
        "schema_version": SCHEMA_VERSION,
        "count": len(validations),
        "packages": validations,
        "rejected_chunks": rejected,
        "diagnostic_policy": {
            "scale": [0, 5],
            "single_viral_score_prohibited": True,
            "scores_are_predictions": False,
        },
    }
    atomic_write_json(PACKAGE_VALIDATION_FILE, artifact)
    atomic_write_json(
        PROMISE_ALIGNMENT_FILE,
        {
            "artifact": "promise_alignment",
            "schema_version": SCHEMA_VERSION,
            "count": len(validations),
            "items": [
                {
                    "package_id": item.get("package_id"),
                    "video_id": item.get("video_id"),
                    "promise_consistency": item.get("promise_consistency"),
                    "promise_alignment_reason": item.get(
                        "promise_alignment_reason"
                    ),
                    "hook_alignment_status": item.get(
                        "hook_alignment_status"
                    ),
                    "hook_alignment_reason": item.get(
                        "hook_alignment_reason"
                    ),
                }
                for item in validations
            ],
        },
    )

    try:
        inputs = build_inputs()
        expected = len(inputs) * 25
    except Exception:
        expected = 0
    status = (
        "PACKAGE_VALIDATION_READY"
        if expected > 0 and len(validations) == expected and not rejected
        else "PARTIAL"
        if validations
        else "WAITING_FOR_PACKAGE_VALIDATION_RESPONSES"
    )
    result = {
        "status": status,
        "expected": expected,
        "current": len(validations),
        "rejected_chunks": len(rejected),
        "pass": sum(x["validation_status"] == "PASS" for x in validations),
        "rework": sum(x["validation_status"] == "REWORK" for x in validations),
        "reject": sum(x["validation_status"] == "REJECT" for x in validations),
        "viral_score_produced": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def snapshot() -> dict[str, Any]:
    request_state = request_snapshot()
    expected_requests = int(request_state.get("expected") or 0)
    expected_pairs = expected_requests * 5
    validations, rejected = _collect_current()
    ready = (
        expected_requests > 0
        and bool(request_state.get("ready"))
        and len(validations) == expected_pairs
        and not rejected
    )
    packages = [
        {
            "package_id": item.get("package_id"),
            "video_id": item.get("video_id"),
            "format": item.get("format"),
            "title_id": item.get("title_id"),
            "title_text": item.get("title_text"),
            "thumbnail_id": item.get("thumbnail_id"),
            "thumbnail_text": item.get("thumbnail_text"),
            "thumbnail_hero_subject": item.get("thumbnail_hero_subject"),
            "angle_id": item.get("angle_id"),
            "angle_primary_driver": item.get("angle_primary_driver"),
            "selected_title_direction_match": item.get(
                "selected_title_direction_match"
            ),
            "validation_status": item.get("validation_status"),
            "semantic_redundancy": item.get("semantic_redundancy"),
            "psychological_complementarity": item.get(
                "psychological_complementarity"
            ),
            "information_gain": item.get("information_gain"),
            "promise_consistency": item.get("promise_consistency"),
            "hook_alignment_status": item.get("hook_alignment_status"),
            "diagnostics": item.get("diagnostics"),
            "hard_validation_findings": item.get(
                "hard_validation_findings", []
            ),
            "rework_findings": item.get("rework_findings", []),
        }
        for item in validations
    ]
    return {
        "status": (
            "PACKAGE_VALIDATION_READY"
            if ready
            else "PACKAGE_VALIDATION_STALE"
            if rejected
            else "WAITING_FOR_PACKAGE_VALIDATION"
        ),
        "ready": ready,
        "expected_requests": expected_requests,
        "current_requests": int(request_state.get("current") or 0),
        "expected_pairs": expected_pairs,
        "current_pairs": len(validations),
        "rejected_chunks": len(rejected),
        "pass": sum(x["validation_status"] == "PASS" for x in validations),
        "rework": sum(x["validation_status"] == "REWORK" for x in validations),
        "reject": sum(x["validation_status"] == "REJECT" for x in validations),
        "viral_score_produced": False,
        "packages": packages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Slice 26 title-thumbnail pairing and validation"
    )
    parser.add_argument("--mode", choices=("prepare", "apply", "status"), required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = run_prepare()
    elif args.mode == "apply":
        result = run_apply()
    else:
        result = snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") in {"FAILED", "PARTIAL", "PACKAGE_VALIDATION_STALE"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
