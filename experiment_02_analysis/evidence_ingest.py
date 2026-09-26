"""Offline evidence ingestion for Experiment 02.

Imports user-supplied transcripts, registered image evidence, and structured
timestamped notes into an Experiment 02 profile. No network requests are made.
Prepared profiles are never overwritten by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from experiment_02 import (
    OUTPUT_DIR,
    load_config,
    load_json,
    safe_filename,
    validate_profile,
)

ENRICHED_DIR = OUTPUT_DIR / "profiles_enriched"
INGESTION_REPORTS_DIR = OUTPUT_DIR / "ingestion_reports"

TIMECODE_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})$"
)
TAG_RE = re.compile(r"<[^>]+>")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_bundle_path(bundle_path: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = bundle_path.parent / path
    return path.resolve()


def parse_timecode(value: str) -> float:
    match = TIMECODE_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timecode: {value!r}")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    milliseconds = int(match.group("ms"))
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def format_seconds(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def transcript_evidence_id(start: float, end: float, ordinal: int) -> str:
    start_ms = int(round(start * 1000))
    end_ms = int(round(end * 1000))
    return f"transcript.t{start_ms:09d}_{end_ms:09d}_{ordinal:04d}"


def strip_subtitle_markup(text: str) -> str:
    return TAG_RE.sub("", text).strip()


def parse_subtitle_file(path: Path) -> list[dict[str, Any]]:
    """Parse SRT/VTT cues into stable citeable transcript evidence."""

    raw = path.read_text(encoding="utf-8-sig")
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    evidence: list[dict[str, Any]] = []
    index = 0
    cue_ordinal = 0

    while index < len(lines):
        line = lines[index].strip()
        if not line or line.upper() == "WEBVTT":
            index += 1
            continue

        if line.isdigit() and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if "-->" in next_line:
                index += 1
                line = next_line

        if "-->" not in line:
            index += 1
            continue

        timing = line.split("-->", 1)
        start_text = timing[0].strip().split()[0]
        end_text = timing[1].strip().split()[0]
        try:
            start = parse_timecode(start_text)
            end = parse_timecode(end_text)
        except ValueError:
            index += 1
            continue

        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].rstrip())
            index += 1

        observation = " ".join(
            stripped
            for stripped in (
                strip_subtitle_markup(item) for item in text_lines
            )
            if stripped
        ).strip()
        if not observation:
            continue

        cue_ordinal += 1
        evidence.append(
            {
                "evidence_id": transcript_evidence_id(start, end, cue_ordinal),
                "type": "transcript",
                "locator": f"{format_seconds(start)}-{format_seconds(end)}",
                "observation": observation,
                "source_file": str(path),
                "source_sha256": sha256_file(path),
            }
        )

    return evidence


def parse_text_transcript(path: Path) -> list[dict[str, Any]]:
    """Split a plain-text transcript into citeable paragraphs."""

    raw = path.read_text(encoding="utf-8-sig").strip()
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", raw)
        if paragraph.strip()
    ]
    digest = sha256_file(path)
    return [
        {
            "evidence_id": f"transcript.p{index:04d}",
            "type": "transcript",
            "locator": f"paragraph {index}",
            "observation": paragraph,
            "source_file": str(path),
            "source_sha256": digest,
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def parse_transcript(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix in {".srt", ".vtt"}:
        return parse_subtitle_file(path)
    if suffix in {".txt", ".md"}:
        return parse_text_transcript(path)
    raise ValueError(
        f"Unsupported transcript format {path.suffix!r}; expected .srt, .vtt, .txt, or .md"
    )


def note_evidence_id(note_type: str, ordinal: int, start_seconds: float | None) -> str:
    prefix = {
        "visual_note": "visual",
        "timing_note": "timing",
        "audio_note": "audio",
    }[note_type]
    if start_seconds is None:
        return f"{prefix}.n{ordinal:04d}"
    return f"{prefix}.t{int(round(start_seconds * 1000)):09d}_{ordinal:04d}"


def parse_notes_file(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    notes = payload.get("notes") if isinstance(payload, dict) else payload
    if not isinstance(notes, list):
        raise ValueError("Notes file must be a JSON list or an object with a 'notes' list")

    digest = sha256_file(path)
    evidence: list[dict[str, Any]] = []

    for ordinal, note in enumerate(notes, start=1):
        if not isinstance(note, dict):
            raise ValueError(f"Note {ordinal} must be an object")

        note_type = str(note.get("type", "")).strip()
        if note_type not in {"visual_note", "timing_note", "audio_note"}:
            raise ValueError(
                f"Note {ordinal} has unsupported type {note_type!r}; "
                "expected visual_note, timing_note, or audio_note"
            )

        observation = str(note.get("observation", "")).strip()
        if not observation:
            raise ValueError(f"Note {ordinal} requires a non-empty observation")

        start_seconds = note.get("start_seconds")
        end_seconds = note.get("end_seconds")
        if start_seconds is not None:
            start_seconds = float(start_seconds)
        if end_seconds is not None:
            end_seconds = float(end_seconds)
        if (
            start_seconds is not None
            and end_seconds is not None
            and end_seconds < start_seconds
        ):
            raise ValueError(f"Note {ordinal} ends before it starts")

        if note.get("locator"):
            locator = str(note["locator"])
        elif start_seconds is not None and end_seconds is not None:
            locator = f"{format_seconds(start_seconds)}-{format_seconds(end_seconds)}"
        elif start_seconds is not None:
            locator = format_seconds(start_seconds)
        else:
            locator = f"note {ordinal}"

        evidence.append(
            {
                "evidence_id": str(
                    note.get("evidence_id")
                    or note_evidence_id(note_type, ordinal, start_seconds)
                ),
                "type": note_type,
                "locator": locator,
                "observation": observation,
                "source_file": str(path),
                "source_sha256": digest,
            }
        )

    return evidence


def register_image(
    *,
    kind: str,
    path: Path,
    observation: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if kind not in {"thumbnail", "opening_frame"}:
        raise ValueError(f"Unsupported image kind: {kind}")

    digest = sha256_file(path)
    mime_type, _ = mimetypes.guess_type(path.name)
    source_input = {
        "status": "PROVIDED" if observation and observation.strip() else "REGISTERED_UNOBSERVED",
        "source": str(path),
        "sha256": digest,
        "mime_type": mime_type,
    }

    if not observation or not observation.strip():
        return source_input, None

    evidence = {
        "evidence_id": f"{kind}.image",
        "type": kind,
        "locator": path.name,
        "observation": observation.strip(),
        "source_file": str(path),
        "source_sha256": digest,
        "mime_type": mime_type,
    }
    return source_input, evidence


def merge_evidence(
    profile: dict[str, Any],
    new_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    result = deepcopy(profile)
    existing = {
        str(item.get("evidence_id")): item
        for item in result.get("evidence", [])
        if item.get("evidence_id")
    }

    for item in new_evidence:
        evidence_id = str(item.get("evidence_id", "")).strip()
        if not evidence_id:
            raise ValueError("Every imported evidence item requires evidence_id")
        if evidence_id in existing:
            if existing[evidence_id] != item:
                raise ValueError(f"Conflicting duplicate evidence_id: {evidence_id}")
            continue
        result.setdefault("evidence", []).append(item)
        existing[evidence_id] = item

    return result


def ingest_bundle(bundle_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = load_json(bundle_path)
    if not isinstance(bundle, dict):
        raise ValueError("Bundle manifest must be a JSON object")

    profile_path = resolve_bundle_path(bundle_path, bundle.get("profile"))
    if profile_path is None:
        raise ValueError("Bundle manifest requires 'profile'")

    profile = load_json(profile_path)
    bundle_video_id = str(bundle.get("video_id", "")).strip()
    profile_video_id = str(profile.get("video_id", "")).strip()
    if bundle_video_id and bundle_video_id != profile_video_id:
        raise ValueError(
            f"Bundle video_id {bundle_video_id!r} does not match profile video_id "
            f"{profile_video_id!r}"
        )

    imported: list[dict[str, Any]] = []
    imported_sources: list[dict[str, Any]] = []
    source_inputs = deepcopy(profile.get("source_inputs", {}))

    transcript_path = resolve_bundle_path(bundle_path, bundle.get("transcript"))
    if transcript_path is not None:
        transcript_items = parse_transcript(transcript_path)
        imported.extend(transcript_items)
        source_inputs["transcript"] = {
            "status": "PROVIDED",
            "source": str(transcript_path),
            "sha256": sha256_file(transcript_path),
            "format": transcript_path.suffix.casefold().lstrip("."),
            "segment_count": len(transcript_items),
        }
        imported_sources.append(source_inputs["transcript"])

    notes_path = resolve_bundle_path(bundle_path, bundle.get("notes"))
    if notes_path is not None:
        note_items = parse_notes_file(notes_path)
        imported.extend(note_items)
        by_type: dict[str, int] = {
            "visual_note": 0,
            "timing_note": 0,
            "audio_note": 0,
        }
        for item in note_items:
            by_type[item["type"]] += 1

        mapping = {
            "visual_note": "visual_notes",
            "timing_note": "timing_notes",
            "audio_note": "audio_notes",
        }
        for note_type, count in by_type.items():
            if count:
                source_inputs[mapping[note_type]] = {
                    "status": "PROVIDED",
                    "source": str(notes_path),
                    "sha256": sha256_file(notes_path),
                    "item_count": count,
                }
        imported_sources.append(
            {
                "status": "PROVIDED",
                "source": str(notes_path),
                "sha256": sha256_file(notes_path),
                "item_count": len(note_items),
            }
        )

    for kind in ("thumbnail", "opening_frame"):
        spec = bundle.get(kind)
        if spec is None:
            continue
        if not isinstance(spec, dict) or not spec.get("path"):
            raise ValueError(f"Bundle {kind} must contain a path")
        image_path = resolve_bundle_path(bundle_path, str(spec["path"]))
        if image_path is None:
            raise ValueError(f"Bundle {kind} path is invalid")
        source_input, evidence = register_image(
            kind=kind,
            path=image_path,
            observation=spec.get("observation"),
        )
        source_inputs[kind] = source_input
        imported_sources.append(source_input)
        if evidence is not None:
            imported.append(evidence)

    result = merge_evidence(profile, imported)
    result["source_inputs"] = source_inputs
    result["evidence_ingestion"] = {
        "bundle_manifest": str(bundle_path.resolve()),
        "bundle_sha256": sha256_file(bundle_path),
        "profile_source": str(profile_path),
        "profile_source_sha256": sha256_file(profile_path),
        "imported_evidence_count": len(imported),
        "registered_sources": imported_sources,
    }

    config = load_config()
    validation = validate_profile(result, config)
    report = {
        "video_id": profile_video_id,
        "profile_source": str(profile_path),
        "bundle": str(bundle_path.resolve()),
        "imported_evidence_count": len(imported),
        "final_evidence_count": len(result.get("evidence", [])),
        "validation": validation,
    }
    return result, report


def run_ingest(bundle_path: Path, output_path: Path | None) -> None:
    enriched, report = ingest_bundle(bundle_path)

    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    INGESTION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    video_id = safe_filename(str(enriched.get("video_id", "unknown")))
    destination = (
        output_path.resolve()
        if output_path is not None
        else (ENRICHED_DIR / f"{video_id}.json").resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report["output_profile"] = str(destination)
    report_path = INGESTION_REPORTS_DIR / f"{video_id}.ingestion.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02 EVIDENCE INGESTION")
    print("=" * 60)
    print(f"Video:             {enriched.get('video_id')}")
    print(f"Imported evidence: {report['imported_evidence_count']:,}")
    print(f"Total evidence:    {report['final_evidence_count']:,}")
    print(f"Profile valid:     {report['validation']['valid']}")
    print(f"Output profile:    {destination}")
    print(f"Ingestion report:  {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline Experiment 02 evidence ingestion"
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_ingest(args.bundle.resolve(), args.output)


if __name__ == "__main__":
    main()
