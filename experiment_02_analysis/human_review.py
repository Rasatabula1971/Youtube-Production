"""Human review gate for Experiment 02 analyzed profiles.

Prepares evidence-linked review packets and applies explicit ACCEPT/REJECT
decisions. A profile is marked review.completed=true only when every reviewable
item has one decision and the post-review profile passes Experiment 02
validation.

No model or network calls are made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_ingest import sha256_file
from experiment_02 import (
    OUTPUT_DIR,
    evidence_index,
    load_config,
    load_json,
    safe_filename,
    validate_profile,
)

HERE = Path(__file__).resolve().parent
REVIEW_CONFIG_FILE = HERE / "human_review_config.json"

DEFAULT_ANALYZED_DIR = OUTPUT_DIR / "profiles_analyzed"
REVIEW_REQUESTS_DIR = OUTPUT_DIR / "human_review_requests"
REVIEWED_PROFILES_DIR = OUTPUT_DIR / "profiles_reviewed"
REVIEW_REPORTS_DIR = OUTPUT_DIR / "human_review_reports"
REVIEW_RESPONSES_DIR = OUTPUT_DIR / "human_review_responses"
UI_REVIEWER = "local-operator"


def content_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def review_item_id(item: dict[str, Any]) -> str:
    identity = {
        "kind": item.get("kind"),
        "dimension": item.get("dimension"),
        "statement": item.get("statement"),
        "mechanism_ids": item.get("mechanism_ids", []),
        "evidence_refs": item.get("evidence_refs", []),
        "confidence": item.get("confidence"),
    }
    return "review." + content_sha256(identity)[:24]


def load_review_config() -> dict[str, Any]:
    config = load_json(REVIEW_CONFIG_FILE)
    required = {"max_evidence_chars", "require_reviewer_name"}
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Human review config is missing: " + ", ".join(missing))
    return config


def compact_evidence(
    evidence: dict[str, dict[str, Any]],
    refs: list[str],
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    items = []
    for ref in refs:
        item = evidence.get(str(ref))
        if not item:
            continue
        observation = str(item.get("observation", ""))
        truncated = False
        if len(observation) > max_chars:
            observation = observation[: max_chars - 1].rstrip() + "…"
            truncated = True
        items.append(
            {
                "evidence_id": item.get("evidence_id"),
                "type": item.get("type"),
                "locator": item.get("locator"),
                "observation": observation,
                "observation_truncated": truncated,
            }
        )
    return items


def reviewable_items(profile: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for dimension in sorted(profile.get("analysis", {})):
        findings = profile["analysis"][dimension].get("findings", [])
        for index, finding in enumerate(findings):
            row = {
                "item_id": "",
                "kind": "analysis_finding",
                "dimension": dimension,
                "path": ["analysis", dimension, "findings", index],
                "statement": finding.get("finding"),
                "mechanism_ids": list(finding.get("mechanism_ids", [])),
                "evidence_refs": list(finding.get("evidence_refs", [])),
                "confidence": finding.get("confidence"),
            }
            row["item_id"] = review_item_id(row)
            items.append(row)

    transfer_specs = (
        (
            "transferable_mechanisms",
            "transferable_mechanism",
            "description",
        ),
        (
            "source_specific_elements",
            "source_specific_element",
            "element",
        ),
        (
            "transformation_opportunities",
            "transformation_opportunity",
            "new_direction",
        ),
    )
    transfer = profile.get("transfer", {})

    for key, kind, statement_key in transfer_specs:
        for index, item in enumerate(transfer.get(key, [])):
            row = {
                "item_id": "",
                "kind": kind,
                "dimension": "transfer",
                "path": ["transfer", key, index],
                "statement": item.get(statement_key),
                "mechanism_ids": (
                    list(item.get("mechanism_ids", []))
                    if "mechanism_ids" in item
                    else [item.get("mechanism_id")] if item.get("mechanism_id") else []
                ),
                "evidence_refs": list(item.get("evidence_refs", [])),
                "confidence": item.get("confidence"),
            }
            if kind == "transformation_opportunity":
                row["source_dependency_test"] = item.get("source_dependency_test")
            row["item_id"] = review_item_id(row)
            items.append(row)

    return items


def build_review_request(
    profile: dict[str, Any],
    experiment_config: dict[str, Any],
    review_config: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_profile(profile, experiment_config)
    if not validation["valid"]:
        raise ValueError(
            "Profile must pass Experiment 02 validation before human review: "
            + "; ".join(validation["errors"])
        )

    evidence = evidence_index(profile)
    maximum = int(review_config["max_evidence_chars"])
    items = reviewable_items(profile)

    enriched_items = []
    for item in items:
        enriched_items.append(
            {
                **item,
                "supporting_evidence": compact_evidence(
                    evidence,
                    item["evidence_refs"],
                    max_chars=maximum,
                ),
                "decision_schema": {
                    "decision": "ACCEPT|REJECT",
                    "note": "Optional reviewer note",
                },
            }
        )

    return {
        "experiment_id": "02",
        "request_type": "human_review",
        "video_id": profile.get("video_id"),
        "source": profile.get("source", {}),
        "reviewable_item_count": len(enriched_items),
        "items": enriched_items,
        "working_hypotheses": profile.get("working_hypotheses", []),
        "request_provenance": {
            "profile_content_sha256": content_sha256(profile),
        },
        "instructions": [
            "Review every item.",
            "Choose ACCEPT only when the claim is a fair representation of the cited evidence.",
            "Choose REJECT when the claim overstates, misreads, or should not be carried forward.",
            "Do not approve a mechanism because the source video performed well; review the claim against its evidence.",
            "Working hypotheses are shown for context but are not factual review items.",
        ],
        "response_schema": {
            "video_id": profile.get("video_id"),
            "reviewer": "Reviewer name or identifier",
            "decisions": [
                {
                    "item_id": "exact item_id from this packet",
                    "decision": "ACCEPT|REJECT",
                    "note": "Optional note",
                }
            ],
            "overall_note": "Optional overall note",
        },
    }


def decision_map(
    request: dict[str, Any],
    response: dict[str, Any],
    review_config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if str(response.get("video_id", "")) != str(request.get("video_id", "")):
        raise ValueError("Review response video_id does not match request")

    reviewer = str(response.get("reviewer", "")).strip()
    if review_config.get("require_reviewer_name", True) and not reviewer:
        raise ValueError("Review response requires reviewer")

    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Review response decisions must be a list")

    expected_ids = {str(item["item_id"]) for item in request.get("items", [])}
    mapped: dict[str, dict[str, Any]] = {}

    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError(f"Decision {index} must be an object")
        item_id = str(decision.get("item_id", "")).strip()
        value = str(decision.get("decision", "")).strip().upper()

        if item_id not in expected_ids:
            raise ValueError(f"Unknown review item_id: {item_id}")
        if item_id in mapped:
            raise ValueError(f"Duplicate review decision: {item_id}")
        if value not in {"ACCEPT", "REJECT"}:
            raise ValueError(f"Invalid decision for {item_id}: {value!r}")

        mapped[item_id] = {
            "item_id": item_id,
            "decision": value,
            "note": str(decision.get("note", "") or ""),
        }

    missing = sorted(expected_ids - set(mapped))
    if missing:
        raise ValueError(
            "Review is incomplete; missing decisions for: " + ", ".join(missing)
        )

    return mapped


def apply_review(
    profile: dict[str, Any],
    request: dict[str, Any],
    response: dict[str, Any],
    experiment_config: dict[str, Any],
    review_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if str(profile.get("video_id", "")) != str(request.get("video_id", "")):
        raise ValueError("Review request does not match profile video_id")

    provenance = request.get("request_provenance", {})
    expected_hash = (
        provenance.get("profile_content_sha256")
        if isinstance(provenance, dict)
        else None
    )
    if not expected_hash or expected_hash != content_sha256(profile):
        raise ValueError(
            "STALE_REVIEW_REQUEST: analyzed profile changed after review preparation"
        )

    mapped = decision_map(request, response, review_config)
    result = deepcopy(profile)

    rejected_paths: dict[tuple[str, str], list[int]] = {}

    for item in request.get("items", []):
        item_id = str(item["item_id"])
        if mapped[item_id]["decision"] != "REJECT":
            continue

        path = item["path"]
        container_key = (str(path[0]), str(path[1]))
        rejected_paths.setdefault(container_key, []).append(
            int(path[2]) if path[0] == "transfer" else int(path[3])
        )

    for (root, key), indexes in rejected_paths.items():
        if root == "analysis":
            target = result["analysis"][key]["findings"]
        elif root == "transfer":
            target = result["transfer"][key]
        else:
            raise ValueError(f"Unsupported review path root: {root}")

        for index in sorted(indexes, reverse=True):
            if index < 0 or index >= len(target):
                raise ValueError(
                    f"Review item path is out of range: {root}.{key}[{index}]"
                )
            del target[index]

    validation = validate_profile(result, experiment_config)
    if not validation["valid"]:
        return result, {
            "status": "REVIEW_VALIDATION_FAILED",
            "video_id": profile.get("video_id"),
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "completed": False,
        }

    reviewer = str(response.get("reviewer", "")).strip()
    accepted_count = sum(value["decision"] == "ACCEPT" for value in mapped.values())
    rejected_count = sum(value["decision"] == "REJECT" for value in mapped.values())

    result["review"] = {
        "completed": True,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "decision_count": len(mapped),
        "overall_note": str(response.get("overall_note", "") or ""),
        "decisions": [mapped[item_id] for item_id in sorted(mapped)],
    }

    return result, {
        "status": "REVIEW_COMPLETED",
        "video_id": profile.get("video_id"),
        "reviewer": reviewer,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "decision_count": len(mapped),
        "completed": True,
        "warnings": validation["warnings"],
    }


def run_prepare(
    profile_path: Path,
    output_path: Path | None,
) -> dict[str, Any]:
    profile = load_json(profile_path)
    experiment_config = load_config()
    review_config = load_review_config()
    request = build_review_request(
        profile,
        experiment_config,
        review_config,
    )
    request["request_provenance"].update(
        {
            "profile_source": str(profile_path.resolve()),
            "profile_sha256": sha256_file(profile_path),
        }
    )

    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = safe_filename(str(profile.get("video_id", profile_path.stem)))
    destination = (
        output_path.resolve()
        if output_path is not None
        else (REVIEW_REQUESTS_DIR / f"{video_id}.review_request.json").resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(request, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "status": "REVIEW_PREPARED",
        "video_id": profile.get("video_id"),
        "reviewable_items": request["reviewable_item_count"],
        "request": str(destination),
    }


def run_batch_prepare(profiles_dir: Path) -> dict[str, Any]:
    if not profiles_dir.exists():
        return {
            "status": "WAITING_FOR_ANALYZED_PROFILES",
            "profiles_dir": str(profiles_dir),
            "prepared": 0,
        }

    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    prepared = []
    failures = []

    for profile_path in sorted(profiles_dir.glob("*.json")):
        try:
            prepared.append(run_prepare(profile_path, None))
        except (
            Exception
        ) as exc:  # noqa: BLE001 - boundary converts failure to structured status  # noqa: BLE001 - boundary converts failure to structured status
            failures.append(
                {
                    "profile": str(profile_path),
                    "error_type": type(exc).__name__,
                }
            )

    total = len(list(profiles_dir.glob("*.json")))
    status = (
        "COMPLETE"
        if total > 0 and len(prepared) == total and not failures
        else "FAILED" if not prepared and failures else "PARTIAL"
    )
    return {
        "status": status,
        "profiles_found": total,
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REVIEW_REQUESTS_DIR),
    }


def run_apply(
    profile_path: Path,
    request_path: Path,
    response_path: Path,
    output_path: Path | None,
) -> dict[str, Any]:
    profile = load_json(profile_path)
    request = load_json(request_path)
    response = load_json(response_path)
    experiment_config = load_config()
    review_config = load_review_config()

    reviewed, report = apply_review(
        profile,
        request,
        response,
        experiment_config,
        review_config,
    )

    REVIEW_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWED_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    video_id = safe_filename(str(profile.get("video_id", profile_path.stem)))

    report["profile_source"] = str(profile_path.resolve())
    report["profile_sha256"] = sha256_file(profile_path)
    report["request_source"] = str(request_path.resolve())
    report["request_sha256"] = sha256_file(request_path)
    report["response_source"] = str(response_path.resolve())
    report["response_sha256"] = sha256_file(response_path)

    report_path = REVIEW_REPORTS_DIR / f"{video_id}.human_review.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if report["status"] != "REVIEW_COMPLETED":
        report["report"] = str(report_path)
        return report

    destination = (
        output_path.resolve()
        if output_path is not None
        else (REVIEWED_PROFILES_DIR / f"{video_id}.json").resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report["reviewed_profile"] = str(destination)
    report["report"] = str(report_path)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _response_path(video_id: str) -> Path:
    return REVIEW_RESPONSES_DIR / f"{safe_filename(video_id)}.review_response.json"


def _blank_response(video_id: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "reviewer": UI_REVIEWER,
        "decisions": [],
        "overall_note": "",
    }


def _load_partial_response(
    video_id: str,
    *,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _response_path(video_id)
    if not path.exists():
        return _blank_response(video_id)
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("Saved human review response must be a JSON object")
    if request is not None:
        current_hash = request.get("request_provenance", {}).get(
            "profile_content_sha256"
        )
        if payload.get("profile_content_sha256") != current_hash:
            return _blank_response(video_id)
    return payload


def review_snapshot() -> dict[str, Any]:
    packets: list[dict[str, Any]] = []
    if not REVIEW_REQUESTS_DIR.exists():
        return {
            "status": "READY_TO_PREPARE",
            "complete": False,
            "pending": 0,
            "accepted": 0,
            "rejected": 0,
            "packets": [],
            "items": [],
        }

    total_pending = total_accepted = total_rejected = 0
    flattened: list[dict[str, Any]] = []

    for request_path in sorted(REVIEW_REQUESTS_DIR.glob("*.review_request.json")):
        request = load_json(request_path)
        video_id = str(request.get("video_id") or request_path.stem)
        profile_path = DEFAULT_ANALYZED_DIR / f"{safe_filename(video_id)}.json"
        provenance = request.get("request_provenance", {})
        current_packet = False
        if profile_path.exists() and isinstance(provenance, dict):
            file_hash = provenance.get("profile_sha256")
            content_hash = provenance.get("profile_content_sha256")
            current_packet = (
                bool(file_hash) and file_hash == sha256_file(profile_path)
            ) or (
                bool(content_hash)
                and content_hash == content_sha256(load_json(profile_path))
            )
        response = (
            _load_partial_response(video_id, request=request)
            if current_packet
            else _blank_response(video_id)
        )
        decisions = {
            str(item.get("item_id")): item
            for item in response.get("decisions", [])
            if isinstance(item, dict) and item.get("item_id")
        }
        reviewed_path = REVIEWED_PROFILES_DIR / f"{safe_filename(video_id)}.json"
        packet_items: list[dict[str, Any]] = []
        packet_pending = 0

        for item in request.get("items", []):
            item_id = str(item.get("item_id") or "")
            saved = decisions.get(item_id, {})
            decision = str(saved.get("decision") or "PENDING").upper()
            row = {
                **item,
                "video_id": video_id,
                "decision": decision,
                "note": str(saved.get("note") or ""),
            }
            packet_items.append(row)
            flattened.append(row)
            if decision == "ACCEPT":
                total_accepted += 1
            elif decision == "REJECT":
                total_rejected += 1
            else:
                total_pending += 1
                packet_pending += 1

        packets.append(
            {
                "video_id": video_id,
                "source": request.get("source", {}),
                "reviewable_item_count": len(packet_items),
                "complete": current_packet
                and reviewed_path.exists()
                and packet_pending == 0,
                "items": packet_items,
            }
        )

    complete = bool(packets) and all(packet["complete"] for packet in packets)
    stale = any(
        not (
            (
                DEFAULT_ANALYZED_DIR / f"{safe_filename(packet['video_id'])}.json"
            ).exists()
            and (
                (
                    load_json(
                        REVIEW_REQUESTS_DIR
                        / f"{safe_filename(packet['video_id'])}.review_request.json"
                    )
                    .get("request_provenance", {})
                    .get("profile_sha256")
                    == sha256_file(
                        DEFAULT_ANALYZED_DIR
                        / f"{safe_filename(packet['video_id'])}.json"
                    )
                )
                or (
                    load_json(
                        REVIEW_REQUESTS_DIR
                        / f"{safe_filename(packet['video_id'])}.review_request.json"
                    )
                    .get("request_provenance", {})
                    .get("profile_content_sha256")
                    == content_sha256(
                        load_json(
                            DEFAULT_ANALYZED_DIR
                            / f"{safe_filename(packet['video_id'])}.json"
                        )
                    )
                )
            )
        )
        for packet in packets
    )
    return {
        "status": (
            "STALE_REVIEW_REQUEST"
            if stale
            else "COMPLETE" if complete else "AWAITING_HUMAN_DECISION"
        ),
        "complete": complete,
        "pending": total_pending,
        "accepted": total_accepted,
        "rejected": total_rejected,
        "packets": packets,
        "items": flattened,
    }


def apply_review_action(
    *,
    video_id: str,
    item_id: str,
    decision: str,
    note: str | None = None,
) -> dict[str, Any]:
    decision = decision.strip().upper()
    if decision not in {"ACCEPT", "REJECT"}:
        raise ValueError("Decision must be ACCEPT or REJECT")

    request_path = (
        REVIEW_REQUESTS_DIR / f"{safe_filename(video_id)}.review_request.json"
    )
    profile_path = DEFAULT_ANALYZED_DIR / f"{safe_filename(video_id)}.json"
    if not request_path.exists():
        raise ValueError("Human review packet not found for video")
    if not profile_path.exists():
        raise ValueError("Analyzed profile not found for video")

    request = load_json(request_path)
    expected_ids = {
        str(item.get("item_id"))
        for item in request.get("items", [])
        if isinstance(item, dict)
    }
    if item_id not in expected_ids:
        raise ValueError("Unknown human review item")

    response = _load_partial_response(video_id, request=request)
    mapped = {
        str(item.get("item_id")): dict(item)
        for item in response.get("decisions", [])
        if isinstance(item, dict) and item.get("item_id")
    }
    mapped[item_id] = {
        "item_id": item_id,
        "decision": decision,
        "note": str(note or ""),
    }
    response["video_id"] = video_id
    response["reviewer"] = str(response.get("reviewer") or UI_REVIEWER)
    response["decisions"] = [mapped[key] for key in sorted(mapped)]
    response["overall_note"] = str(response.get("overall_note") or "")
    response["profile_content_sha256"] = request.get("request_provenance", {}).get(
        "profile_content_sha256"
    )

    REVIEW_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    response_path = _response_path(video_id)
    response_path.write_text(
        json.dumps(response, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if expected_ids and expected_ids.issubset(mapped):
        run_apply(
            profile_path.resolve(),
            request_path.resolve(),
            response_path.resolve(),
            None,
        )

    return review_snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 02 human review gate")
    parser.add_argument(
        "--mode",
        choices=("prepare", "batch-prepare", "apply"),
        required=True,
    )
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--profiles-dir", type=Path, default=None)
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--response", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.mode == "prepare":
        if args.profile is None:
            raise SystemExit("--profile is required for prepare mode")
        result = run_prepare(
            args.profile.resolve(),
            args.output,
        )
    elif args.mode == "batch-prepare":
        profiles_dir = (
            args.profiles_dir.resolve()
            if args.profiles_dir is not None
            else DEFAULT_ANALYZED_DIR.resolve()
        )
        result = run_batch_prepare(profiles_dir)
    else:
        if args.profile is None or args.request is None or args.response is None:
            raise SystemExit(
                "--profile, --request and --response are required for apply mode"
            )
        result = run_apply(
            args.profile.resolve(),
            args.request.resolve(),
            args.response.resolve(),
            args.output,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.mode == "batch-prepare" and result.get("status") != "COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
