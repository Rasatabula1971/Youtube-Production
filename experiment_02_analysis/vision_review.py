"""Experiment 02 visual-observation review.

Frame descriptions are never accepted as evidence automatically.

This module can ask a local Ollama vision model for draft observations, but
those drafts remain PENDING until a human accepts/edits or rejects them. Only
human-approved observations are converted into Experiment 02 visual evidence.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from evidence_ingest import run_ingest, sha256_file
from experiment_02 import OUTPUT_DIR, PROJECT_ROOT, safe_filename

PREPARED_DIR = OUTPUT_DIR / "profiles_to_complete"
ENRICHED_DIR = OUTPUT_DIR / "profiles_enriched"
VISION_REVIEW_DIR = OUTPUT_DIR / "vision_review"
VISION_NOTES_DIR = OUTPUT_DIR / "vision_notes"
SOURCE_VISUAL_ROOT = (
    PROJECT_ROOT / "source_acquisition" / "output" / "experiment_02"
)
ENV_FILE = PROJECT_ROOT / ".env"

MAX_SCENE_REVIEW_FRAMES = 8
OLLAMA_MODEL_ENV = "EXPERIMENT_02_VISION_MODEL"
OLLAMA_HOST_ENV = "OLLAMA_HOST"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
ALLOWED_CONFIDENCE = {"LOW", "MODERATE", "HIGH"}
OBSERVATION_MAX_CHARS = 800

VISION_PROMPT = """Describe only what is directly visible in this single video frame.

Return strict JSON with these keys:
- observation: one concise factual sentence describing visible subjects, layout,
  graphics, captions/text overlays, diagrams, demonstrations, or camera framing.
- visible_text: exact visible text if clearly readable, otherwise an empty string.
- confidence: LOW, MODERATE, or HIGH.
- uncertainty: short note about anything visually ambiguous, otherwise an empty string.

Rules:
- Do not explain why the video performed well.
- Do not infer intent, emotion, causality, identity, brand, location, or events not
  directly visible.
- Do not guess unreadable text.
- Do not describe audio or narration.
"""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def clean_observation(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        raise ValueError("Visual observation cannot be empty")
    if len(cleaned) > OBSERVATION_MAX_CHARS:
        raise ValueError(
            f"Visual observation exceeds {OBSERVATION_MAX_CHARS} characters"
        )
    return cleaned


def normalize_ollama_host(value: str | None) -> str:
    host = str(value or DEFAULT_OLLAMA_HOST).strip().rstrip("/")
    parsed = urlparse(host)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("OLLAMA_HOST must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "Experiment 02 vision is intentionally restricted to a local Ollama host"
        )
    return host


def ollama_tags(
    host: str,
    *,
    timeout_seconds: float = 2.5,
) -> dict[str, Any]:
    request = urllib.request.Request(
        host + "/api/tags",
        method="GET",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def ollama_model_names(payload: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if name:
            names.add(name)
    return names


def vision_provider_status(
    *,
    model: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    selected_model = str(model or os.environ.get(OLLAMA_MODEL_ENV, "")).strip()
    selected_host = normalize_ollama_host(
        host or os.environ.get(OLLAMA_HOST_ENV)
    )
    if not selected_model:
        return {
            "status": "HUMAN_ONLY",
            "provider": "human",
            "model": None,
            "host": selected_host,
            "message": (
                f"Set {OLLAMA_MODEL_ENV} to an installed local vision model "
                "to generate draft observations automatically."
            ),
        }

    try:
        tags = ollama_tags(selected_host)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "status": "OLLAMA_UNAVAILABLE",
            "provider": "human",
            "model": selected_model,
            "host": selected_host,
            "message": f"Local Ollama unavailable: {type(exc).__name__}",
        }

    installed = ollama_model_names(tags)
    if selected_model not in installed:
        return {
            "status": "MODEL_NOT_INSTALLED",
            "provider": "human",
            "model": selected_model,
            "host": selected_host,
            "installed_models": sorted(installed),
            "message": "Configured vision model is not installed in local Ollama.",
        }

    return {
        "status": "READY",
        "provider": "ollama",
        "model": selected_model,
        "host": selected_host,
        "message": "Local Ollama vision drafts are available.",
    }


def ollama_frame_proposal(
    image_path: Path,
    *,
    model: str,
    host: str,
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": VISION_PROMPT,
                "images": [encoded],
            }
        ],
        "options": {
            "temperature": 0,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        host + "/api/chat",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:
        outer = json.loads(response.read().decode("utf-8"))

    if not isinstance(outer, dict):
        raise ValueError("Ollama response must be a JSON object")
    message = outer.get("message")
    if not isinstance(message, dict):
        raise ValueError("Ollama response is missing message")
    raw_content = str(message.get("content") or "").strip()
    parsed = json.loads(raw_content)
    if not isinstance(parsed, dict):
        raise ValueError("Vision proposal must be a JSON object")

    observation = clean_observation(parsed.get("observation", ""))
    visible_text = re.sub(
        r"\s+",
        " ",
        str(parsed.get("visible_text") or ""),
    ).strip()
    uncertainty = re.sub(
        r"\s+",
        " ",
        str(parsed.get("uncertainty") or ""),
    ).strip()
    confidence = str(parsed.get("confidence") or "LOW").strip().upper()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "LOW"

    if visible_text:
        observation = clean_observation(
            observation + f' Visible text: "{visible_text}".'
        )

    return {
        "observation": observation,
        "visible_text": visible_text,
        "uncertainty": uncertainty,
        "confidence": confidence,
    }


def evenly_selected_indexes(total: int, maximum: int) -> list[int]:
    if total <= 0 or maximum <= 0:
        return []
    if total <= maximum:
        return list(range(total))
    if maximum == 1:
        return [0]
    return sorted(
        {
            round(index * (total - 1) / (maximum - 1))
            for index in range(maximum)
        }
    )


def visual_report_path(video_id: str) -> Path:
    return SOURCE_VISUAL_ROOT / safe_filename(video_id) / "visual_analysis.json"


def prepared_profile_path(video_id: str) -> Path:
    return PREPARED_DIR / f"{safe_filename(video_id)}.json"


def packet_path(video_id: str) -> Path:
    return VISION_REVIEW_DIR / f"{safe_filename(video_id)}.vision_review.json"


def frame_candidates(video_id: str) -> list[dict[str, Any]]:
    report_path = visual_report_path(video_id)
    if not report_path.exists():
        return []
    report = load_json(report_path)
    if report.get("status") not in {"READY", "READY_NO_OPENING_FRAME"}:
        return []

    frames: list[dict[str, Any]] = []
    opening = report.get("opening_frame")
    if isinstance(opening, dict) and opening.get("path"):
        opening_path = Path(str(opening["path"]))
        if opening_path.exists():
            frames.append(
                {
                    "frame_id": "opening_frame",
                    "kind": "opening_frame",
                    "path": str(opening_path.resolve()),
                    "timestamp_seconds": float(
                        opening.get("timestamp_seconds") or 0.0
                    ),
                    "source_sha256": sha256_file(opening_path),
                }
            )

    retained = [
        item
        for item in report.get("retained_scene_frames", [])
        if isinstance(item, dict) and item.get("path")
    ]
    indexes = evenly_selected_indexes(
        len(retained),
        MAX_SCENE_REVIEW_FRAMES,
    )
    for index in indexes:
        item = retained[index]
        path = Path(str(item["path"]))
        if not path.exists():
            continue
        frames.append(
            {
                "frame_id": path.stem,
                "kind": "scene_frame",
                "path": str(path.resolve()),
                "timestamp_seconds": float(
                    item.get("timestamp_seconds") or 0.0
                ),
                "source_sha256": sha256_file(path),
            }
        )
    return frames


def packet_is_current(packet: dict[str, Any]) -> bool:
    video_id = str(packet.get("video_id") or "")
    if not video_id:
        return False
    prepared = prepared_profile_path(video_id)
    report = visual_report_path(video_id)
    if not prepared.exists() or not report.exists():
        return False
    provenance = packet.get("source_provenance", {})
    if not isinstance(provenance, dict):
        return False
    return (
        provenance.get("prepared_profile_sha256") == sha256_file(prepared)
        and provenance.get("visual_report_sha256") == sha256_file(report)
    )


def build_packet(
    video_id: str,
    *,
    provider: str = "auto",
    model: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    prepared = prepared_profile_path(video_id)
    report = visual_report_path(video_id)
    if not prepared.exists():
        raise ValueError(f"Prepared Experiment 02 profile missing for {video_id}")
    if not report.exists():
        raise ValueError(f"Visual structure report missing for {video_id}")

    frames = frame_candidates(video_id)
    if not frames:
        raise ValueError(f"No retained visual frames available for {video_id}")

    provider_status = vision_provider_status(model=model, host=host)
    use_ollama = (
        provider in {"auto", "ollama"}
        and provider_status.get("status") == "READY"
    )
    if provider == "ollama" and not use_ollama:
        raise ValueError(provider_status.get("message") or "Ollama vision unavailable")

    selected_provider = "ollama" if use_ollama else "human"
    selected_model = (
        str(provider_status.get("model"))
        if use_ollama and provider_status.get("model")
        else None
    )
    selected_host = str(provider_status.get("host") or DEFAULT_OLLAMA_HOST)

    items: list[dict[str, Any]] = []
    for frame in frames:
        proposal = None
        proposal_error = None
        if use_ollama and selected_model:
            try:
                proposal = ollama_frame_proposal(
                    Path(frame["path"]),
                    model=selected_model,
                    host=selected_host,
                )
            except Exception as exc:
                proposal_error = f"{type(exc).__name__}: {exc}"

        items.append(
            {
                **frame,
                "proposal": proposal,
                "proposal_error": proposal_error,
                "decision": "PENDING",
                "final_observation": None,
                "reviewed_at": None,
            }
        )

    packet = {
        "schema_version": "1.0",
        "video_id": video_id,
        "status": "AWAITING_HUMAN_REVIEW",
        "provider": selected_provider,
        "model": selected_model,
        "provider_status": provider_status,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "source_provenance": {
            "prepared_profile": str(prepared.resolve()),
            "prepared_profile_sha256": sha256_file(prepared),
            "visual_report": str(report.resolve()),
            "visual_report_sha256": sha256_file(report),
        },
        "frames": items,
        "final_bundle": None,
        "ingestion_status": None,
    }
    write_json(packet_path(video_id), packet)
    return packet


def current_visual_video_ids() -> list[str]:
    if not PREPARED_DIR.exists():
        return []
    result: list[str] = []
    for prepared in sorted(PREPARED_DIR.glob("*.json")):
        video_id = prepared.stem
        if frame_candidates(video_id):
            result.append(video_id)
    return result


def build_all(
    *,
    provider: str = "auto",
    model: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    video_ids = current_visual_video_ids()
    if not video_ids:
        return {
            "status": "NO_VISUAL_FRAMES",
            "prepared": 0,
            "packets": [],
        }

    packets = []
    for video_id in video_ids:
        existing_path = packet_path(video_id)
        if existing_path.exists():
            existing = load_json(existing_path)
            if packet_is_current(existing) and existing.get("status") == "COMPLETE":
                packets.append(
                    {
                        "video_id": video_id,
                        "status": "COMPLETE_EXISTING",
                        "packet": str(existing_path),
                    }
                )
                continue
        packet = build_packet(
            video_id,
            provider=provider,
            model=model,
            host=host,
        )
        packets.append(
            {
                "video_id": video_id,
                "status": packet["status"],
                "provider": packet["provider"],
                "proposal_count": sum(
                    bool(item.get("proposal"))
                    for item in packet["frames"]
                ),
                "frame_count": len(packet["frames"]),
                "packet": str(existing_path),
            }
        )

    return {
        "status": "AWAITING_HUMAN_REVIEW",
        "prepared": len(packets),
        "packets": packets,
    }


def frame_path(video_id: str, frame_id: str) -> Path:
    path = packet_path(video_id)
    if not path.exists():
        raise ValueError("Vision review packet does not exist")
    packet = load_json(path)
    if not packet_is_current(packet):
        raise ValueError("Vision review packet is stale")
    for item in packet.get("frames", []):
        if str(item.get("frame_id")) == frame_id:
            candidate = Path(str(item.get("path") or "")).resolve()
            root = SOURCE_VISUAL_ROOT.resolve()
            if root not in candidate.parents:
                raise ValueError("Vision frame is outside the acquisition root")
            if not candidate.exists():
                raise ValueError("Vision frame file is missing")
            return candidate
    raise ValueError("Unknown vision frame")


def packet_counts(packet: dict[str, Any]) -> dict[str, int]:
    frames = [
        item for item in packet.get("frames", [])
        if isinstance(item, dict)
    ]
    return {
        "total": len(frames),
        "pending": sum(item.get("decision") == "PENDING" for item in frames),
        "accepted": sum(item.get("decision") == "ACCEPT" for item in frames),
        "rejected": sum(item.get("decision") == "REJECT" for item in frames),
        "proposed": sum(bool(item.get("proposal")) for item in frames),
    }


def review_snapshot() -> dict[str, Any]:
    video_ids = current_visual_video_ids()
    packets = []
    missing = []
    stale = []

    for video_id in video_ids:
        path = packet_path(video_id)
        if not path.exists():
            missing.append(video_id)
            continue
        packet = load_json(path)
        if not packet_is_current(packet):
            stale.append(video_id)
            continue
        public = {
            key: value
            for key, value in packet.items()
            if key not in {"source_provenance"}
        }
        public["counts"] = packet_counts(packet)
        for item in public.get("frames", []):
            item.pop("path", None)
            item.pop("source_sha256", None)
        packets.append(public)

    complete = (
        bool(video_ids)
        and not missing
        and not stale
        and all(packet.get("status") == "COMPLETE" for packet in packets)
    )
    awaiting = any(
        packet.get("status") == "AWAITING_HUMAN_REVIEW"
        for packet in packets
    )

    if not video_ids:
        status = "NOT_APPLICABLE"
    elif missing or stale:
        status = "READY_TO_PREPARE"
    elif complete:
        status = "COMPLETE"
    elif awaiting:
        status = "AWAITING_HUMAN_REVIEW"
    else:
        status = "READY_TO_PREPARE"

    return {
        "status": status,
        "video_ids": video_ids,
        "missing_packets": missing,
        "stale_packets": stale,
        "packets": packets,
        "complete": complete,
        "awaiting_human_review": awaiting,
    }


def combined_notes(
    video_id: str,
    accepted_scene_frames: list[dict[str, Any]],
) -> Path:
    source_dir = SOURCE_VISUAL_ROOT / safe_filename(video_id)
    timing_path = source_dir / "visual_timing_notes.json"
    if timing_path.exists():
        timing_payload = load_json(timing_path)
        timing_notes = timing_payload.get("notes", [])
        if not isinstance(timing_notes, list):
            timing_notes = []
    else:
        timing_notes = []

    notes = [
        item
        for item in timing_notes
        if isinstance(item, dict)
    ]
    for frame in accepted_scene_frames:
        notes.append(
            {
                "evidence_id": f"visual.{frame['frame_id']}",
                "type": "visual_note",
                "start_seconds": frame["timestamp_seconds"],
                "end_seconds": frame["timestamp_seconds"],
                "observation": frame["final_observation"],
                "source_image": frame["path"],
            }
        )

    return write_json(
        VISION_NOTES_DIR / f"{safe_filename(video_id)}.vision_notes.json",
        {
            "video_id": video_id,
            "notes": notes,
        },
    )


def finalize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    video_id = str(packet["video_id"])
    source_dir = SOURCE_VISUAL_ROOT / safe_filename(video_id)
    visual_bundle_path = source_dir / "evidence_bundle_visual.json"
    if not visual_bundle_path.exists():
        raise ValueError("Visual evidence bundle is missing")
    bundle = load_json(visual_bundle_path)

    accepted_scene_frames = [
        item
        for item in packet.get("frames", [])
        if (
            isinstance(item, dict)
            and item.get("kind") == "scene_frame"
            and item.get("decision") == "ACCEPT"
            and item.get("final_observation")
        )
    ]
    opening = next(
        (
            item
            for item in packet.get("frames", [])
            if isinstance(item, dict)
            and item.get("kind") == "opening_frame"
        ),
        None,
    )

    notes_path = combined_notes(
        video_id,
        accepted_scene_frames,
    )
    bundle["notes"] = str(notes_path.resolve())

    if (
        opening
        and opening.get("decision") == "ACCEPT"
        and opening.get("final_observation")
    ):
        spec = bundle.get("opening_frame")
        if not isinstance(spec, dict) or not spec.get("path"):
            spec = {"path": opening["path"]}
        spec["observation"] = opening["final_observation"]
        bundle["opening_frame"] = spec
    elif isinstance(bundle.get("opening_frame"), dict):
        bundle["opening_frame"]["observation"] = None

    final_bundle = write_json(
        source_dir / "evidence_bundle_vision.json",
        bundle,
    )
    run_ingest(final_bundle, None)

    packet["status"] = "COMPLETE"
    packet["updated_at"] = utc_now()
    packet["final_bundle"] = str(final_bundle)
    packet["ingestion_status"] = "APPLIED"
    write_json(packet_path(video_id), packet)
    return packet


def apply_review_action(
    *,
    action: str,
    video_id: str,
    frame_id: str | None = None,
    observation: str | None = None,
) -> dict[str, Any]:
    path = packet_path(video_id)
    if not path.exists():
        raise ValueError("Vision review packet does not exist")
    packet = load_json(path)
    if not packet_is_current(packet):
        raise ValueError("Vision review packet is stale; rebuild it first")
    if packet.get("status") == "COMPLETE":
        raise ValueError("Vision review is already complete")

    action = str(action or "").strip().upper()
    if action not in {"ACCEPT_FRAME", "REJECT_FRAME"}:
        raise ValueError("Unsupported vision review action")
    if not frame_id:
        raise ValueError("Vision review action requires frame_id")

    target = None
    for item in packet.get("frames", []):
        if str(item.get("frame_id")) == frame_id:
            target = item
            break
    if target is None:
        raise ValueError("Unknown vision review frame")

    if action == "REJECT_FRAME":
        target["decision"] = "REJECT"
        target["final_observation"] = None
    else:
        proposed = (
            target.get("proposal", {}).get("observation")
            if isinstance(target.get("proposal"), dict)
            else ""
        )
        candidate = proposed if observation is None else observation
        final = clean_observation(candidate or "")
        target["decision"] = "ACCEPT"
        target["final_observation"] = final

    target["reviewed_at"] = utc_now()
    packet["updated_at"] = utc_now()

    counts = packet_counts(packet)
    if counts["pending"] == 0:
        packet = finalize_packet(packet)
    else:
        write_json(path, packet)

    return review_snapshot()


def main() -> None:
    load_env_file(ENV_FILE)
    parser = argparse.ArgumentParser(
        description="Prepare and inspect human-gated Experiment 02 vision review"
    )
    parser.add_argument(
        "--mode",
        choices=("doctor", "prepare", "status"),
        required=True,
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "human", "ollama"),
        default="auto",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--host", default=None)
    args = parser.parse_args()

    if args.mode == "doctor":
        print(
            json.dumps(
                vision_provider_status(
                    model=args.model,
                    host=args.host,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.mode == "status":
        print(
            json.dumps(
                review_snapshot(),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    result = build_all(
        provider=args.provider,
        model=args.model,
        host=args.host,
    )
    print("\nEXPERIMENT 02 VISION REVIEW PREPARATION")
    print("=" * 60)
    print(f"Status:  {result['status']}")
    print(f"Packets: {result['prepared']}")
    for item in result.get("packets", []):
        print(
            f"  {item['video_id']}: {item['status']}"
            + (
                f" · provider={item.get('provider')}"
                if item.get("provider")
                else ""
            )
            + (
                f" · proposals={item.get('proposal_count')}/{item.get('frame_count')}"
                if item.get("frame_count") is not None
                else ""
            )
        )


if __name__ == "__main__":
    main()
