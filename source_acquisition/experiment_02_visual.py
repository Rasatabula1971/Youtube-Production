"""Acquire objective visual-structure evidence for Experiment 02.

The visual stage streams a low-resolution public YouTube rendition, never saves
the full video, and uses ffmpeg to:

- extract an opening frame;
- detect candidate visual scene transitions;
- retain a bounded set of representative scene frames; and
- generate timestamped timing notes plus a whole-video pacing summary.

Frames are registered as source artifacts only. Without a human/vision
observation they are not claim evidence. The generated timing notes are
objective detector outputs and can support pacing analysis.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

import experiment_02_evidence as base

PROJECT_ROOT = base.PROJECT_ROOT
PREPARED_DIR = base.PREPARED_DIR
ENRICHED_DIR = base.ENRICHED_DIR
ACQUISITION_ROOT = base.ACQUISITION_ROOT
INGEST_SCRIPT = base.INGEST_SCRIPT

VISUAL_SUMMARY_FILE = ACQUISITION_ROOT / "visual_summary.json"

SCENE_THRESHOLD = 0.28
MAX_RETAINED_SCENE_FRAMES = 24
OPENING_FRAME_SECONDS = 0.25
PTS_TIME_RE = re.compile(r"pts_time:(?P<time>\d+(?:\.\d+)?)")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def redact_urls(value: str) -> str:
    return URL_RE.sub("<redacted-url>", value)


def info_duration(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None
    try:
        payload = base.load_json(path)
        value = payload.get("duration")
        if value is None:
            return None
        duration = float(value)
        return duration if duration > 0 else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def stream_url_command(yt_dlp: str, url: str) -> list[str]:
    return [
        yt_dlp,
        "--no-playlist",
        "--format",
        "best[height<=360]/best",
        "--get-url",
        url,
    ]


def resolve_stream_url(
    yt_dlp: str,
    url: str,
) -> tuple[str | None, subprocess.CompletedProcess[str]]:
    completed = subprocess.run(
        stream_url_command(yt_dlp, url),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None, completed

    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if candidate.startswith("https://") or candidate.startswith("http://"):
            return candidate, completed
    return None, completed


def opening_frame_command(
    ffmpeg: str,
    *,
    stream_url: str,
    destination: Path,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        stream_url,
        "-ss",
        f"{OPENING_FRAME_SECONDS:.2f}",
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        "-q:v",
        "3",
        "-an",
        "-y",
        str(destination),
    ]


def scene_detection_command(
    ffmpeg: str,
    *,
    stream_url: str,
    destination_pattern: Path,
    threshold: float,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        stream_url,
        "-vf",
        (
            "scale=640:-2,"
            f"select=gt(scene\\,{threshold:.4f}),"
            "showinfo"
        ),
        "-fps_mode",
        "vfr",
        "-q:v",
        "4",
        "-an",
        "-y",
        str(destination_pattern),
    ]


def parse_scene_times(stderr: str) -> list[float]:
    values: list[float] = []
    for match in PTS_TIME_RE.finditer(stderr):
        try:
            value = float(match.group("time"))
        except ValueError:
            continue
        if value < 0:
            continue
        if not values or not math.isclose(values[-1], value, abs_tol=0.001):
            values.append(value)
    return values


def evenly_selected_indexes(total: int, maximum: int) -> set[int]:
    if total <= 0 or maximum <= 0:
        return set()
    if total <= maximum:
        return set(range(total))
    if maximum == 1:
        return {0}
    return {
        round(index * (total - 1) / (maximum - 1))
        for index in range(maximum)
    }


def prune_scene_frames(
    directory: Path,
    *,
    scene_times: list[float],
    maximum: int,
) -> list[dict[str, Any]]:
    paths = sorted(directory.glob("scene_*.jpg"))
    pair_count = min(len(paths), len(scene_times))
    keep_indexes = evenly_selected_indexes(pair_count, maximum)
    retained: list[dict[str, Any]] = []

    for index, path in enumerate(paths):
        if index < pair_count and index in keep_indexes:
            retained.append(
                {
                    "path": str(path),
                    "timestamp_seconds": round(scene_times[index], 3),
                }
            )
        else:
            path.unlink()
    return retained


def timing_summary(
    scene_times: list[float],
    *,
    duration: float | None,
) -> dict[str, Any]:
    intervals = [
        round(scene_times[index] - scene_times[index - 1], 3)
        for index in range(1, len(scene_times))
        if scene_times[index] >= scene_times[index - 1]
    ]

    denominator = duration
    if denominator is None and scene_times:
        denominator = scene_times[-1]

    per_minute = None
    if denominator and denominator > 0:
        per_minute = round(len(scene_times) / (denominator / 60.0), 2)

    return {
        "scene_transition_candidate_count": len(scene_times),
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "transition_candidates_per_minute": per_minute,
        "median_candidate_interval_seconds": (
            round(statistics.median(intervals), 3) if intervals else None
        ),
        "mean_candidate_interval_seconds": (
            round(statistics.fmean(intervals), 3) if intervals else None
        ),
        "scene_threshold": SCENE_THRESHOLD,
    }


def timing_notes_payload(
    scene_times: list[float],
    *,
    duration: float | None,
) -> dict[str, Any]:
    summary = timing_summary(scene_times, duration=duration)

    notes: list[dict[str, Any]] = [
        {
            "evidence_id": "timing.scene_change_summary",
            "type": "timing_note",
            "locator": "whole video",
            "observation": (
                "Automated scene-change detection flagged "
                f"{summary['scene_transition_candidate_count']} visual transition "
                "candidate(s)"
                + (
                    f" across {summary['duration_seconds']:.3f} seconds"
                    if summary["duration_seconds"] is not None
                    else ""
                )
                + (
                    "; "
                    f"{summary['transition_candidates_per_minute']:.2f} candidates/minute"
                    if summary["transition_candidates_per_minute"] is not None
                    else ""
                )
                + (
                    "; median spacing "
                    f"{summary['median_candidate_interval_seconds']:.3f} seconds"
                    if summary["median_candidate_interval_seconds"] is not None
                    else ""
                )
                + (
                    f". Detector threshold={SCENE_THRESHOLD:.2f}; "
                    "candidates are objective detector events, not semantic shot labels."
                )
            ),
        }
    ]

    for ordinal, value in enumerate(scene_times, start=1):
        notes.append(
            {
                "evidence_id": f"timing.scene_change_{ordinal:04d}",
                "type": "timing_note",
                "start_seconds": round(value, 3),
                "end_seconds": round(value, 3),
                "observation": (
                    "Automated scene-change detector flagged a visual transition "
                    f"candidate at {value:.3f} seconds."
                ),
            }
        )

    return {
        "detector": {
            "name": "ffmpeg_scene_score",
            "threshold": SCENE_THRESHOLD,
            "semantic_interpretation": False,
        },
        "summary": summary,
        "notes": notes,
    }


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def visual_report_current(
    report_path: Path,
    prepared_profile: Path,
) -> bool:
    if not report_path.exists():
        return False
    enriched_path = ENRICHED_DIR / f"{prepared_profile.stem}.json"
    if not enriched_path.exists():
        return False
    try:
        report = base.load_json(report_path)
        enriched = base.load_json(enriched_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    timing_present = any(
        isinstance(item, dict)
        and item.get("evidence_id") == "timing.scene_change_summary"
        and item.get("type") == "timing_note"
        for item in enriched.get("evidence", [])
    )
    return (
        timing_present
        and report.get("status") in {"READY", "READY_NO_OPENING_FRAME"}
        and report.get("profile_sha256") == base.sha256_file(prepared_profile)
    )


def build_combined_bundle(
    *,
    profile_path: Path,
    video_id: str,
    transcript: Path,
    thumbnail: Path | None,
    opening_frame: Path | None,
    notes: Path,
    destination: Path,
) -> Path:
    payload: dict[str, Any] = {
        "video_id": video_id,
        "profile": str(profile_path.resolve()),
        "transcript": str(transcript.resolve()),
        "notes": str(notes.resolve()),
    }
    if thumbnail is not None:
        payload["thumbnail"] = {
            "path": str(thumbnail.resolve()),
            "observation": None,
        }
    if opening_frame is not None:
        payload["opening_frame"] = {
            "path": str(opening_frame.resolve()),
            "observation": None,
        }
    return write_json(destination, payload)


def acquire_visual_one(
    profile_path: Path,
    *,
    yt_dlp: str,
    ffmpeg: str,
    python_executable: str,
    force: bool = False,
) -> dict[str, Any]:
    profile = base.load_json(profile_path)
    video_id = base.safe_name(str(profile.get("video_id") or profile_path.stem))
    url = base.youtube_url(profile)
    output_dir = ACQUISITION_ROOT / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "visual_analysis.json"
    prepared_hash = base.sha256_file(profile_path)

    if not force and visual_report_current(report_path, profile_path):
        return base.load_json(report_path)

    transcript = base.find_transcript(output_dir, video_id)
    thumbnail = base.find_thumbnail(output_dir, video_id)
    info_json = base.find_info_json(output_dir, video_id)
    if transcript is None:
        result = {
            "video_id": video_id,
            "status": "WAITING_FOR_TRANSCRIPT",
            "profile_sha256": prepared_hash,
            "message": "Run Acquire Source Evidence before visual analysis.",
        }
        write_json(report_path, result)
        return result

    for old in output_dir.glob("scene_*.jpg"):
        old.unlink()
    opening_frame = output_dir / "opening_frame.jpg"
    if force and opening_frame.exists():
        opening_frame.unlink()

    stream_url, stream_result = resolve_stream_url(yt_dlp, url)
    if stream_url is None:
        result = {
            "video_id": video_id,
            "status": "STREAM_URL_FAILED",
            "profile_sha256": prepared_hash,
            "yt_dlp_return_code": stream_result.returncode,
            "error_tail": redact_urls(stream_result.stderr[-4000:]),
        }
        write_json(report_path, result)
        return result

    opening_result = subprocess.run(
        opening_frame_command(
            ffmpeg,
            stream_url=stream_url,
            destination=opening_frame,
        ),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if opening_result.returncode != 0 or not opening_frame.exists():
        if opening_frame.exists():
            opening_frame.unlink()
        opening_frame_value: Path | None = None
    else:
        opening_frame_value = opening_frame

    scene_result = subprocess.run(
        scene_detection_command(
            ffmpeg,
            stream_url=stream_url,
            destination_pattern=output_dir / "scene_%04d.jpg",
            threshold=SCENE_THRESHOLD,
        ),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if scene_result.returncode != 0:
        result = {
            "video_id": video_id,
            "status": "SCENE_DETECTION_FAILED",
            "profile_sha256": prepared_hash,
            "ffmpeg_return_code": scene_result.returncode,
            "error_tail": redact_urls(scene_result.stderr[-4000:]),
        }
        write_json(report_path, result)
        return result

    scene_times = parse_scene_times(scene_result.stderr)
    retained_frames = prune_scene_frames(
        output_dir,
        scene_times=scene_times,
        maximum=MAX_RETAINED_SCENE_FRAMES,
    )
    duration = info_duration(info_json)
    notes_payload = timing_notes_payload(
        scene_times,
        duration=duration,
    )
    notes_path = write_json(
        output_dir / "visual_timing_notes.json",
        notes_payload,
    )

    bundle = build_combined_bundle(
        profile_path=profile_path,
        video_id=video_id,
        transcript=transcript,
        thumbnail=thumbnail,
        opening_frame=opening_frame_value,
        notes=notes_path,
        destination=output_dir / "evidence_bundle_visual.json",
    )
    ingest = base.run_ingest(
        bundle,
        python_executable=python_executable,
    )

    enriched_path = ENRICHED_DIR / f"{video_id}.json"
    status = (
        "READY"
        if ingest.returncode == 0 and opening_frame_value is not None
        else "READY_NO_OPENING_FRAME"
        if ingest.returncode == 0
        else "INGEST_FAILED"
    )
    result = {
        "video_id": video_id,
        "status": status,
        "profile_sha256": prepared_hash,
        "duration_seconds": duration,
        "scene_transition_candidate_count": len(scene_times),
        "scene_threshold": SCENE_THRESHOLD,
        "retained_scene_frames": retained_frames,
        "opening_frame": (
            {
                "path": str(opening_frame_value),
                "timestamp_seconds": OPENING_FRAME_SECONDS,
            }
            if opening_frame_value is not None
            else None
        ),
        "timing_notes": str(notes_path),
        "bundle": str(bundle),
        "ingest_return_code": ingest.returncode,
        "enriched_profile": (
            str(enriched_path)
            if enriched_path.exists()
            else None
        ),
        "full_video_saved": False,
    }
    if opening_result.returncode != 0:
        result["opening_frame_error_tail"] = redact_urls(
            opening_result.stderr[-2000:]
        )
    if ingest.returncode != 0:
        result["ingest_error_tail"] = redact_urls(ingest.stderr[-4000:])
    write_json(report_path, result)
    return result


def run_batch(
    *,
    yt_dlp: str,
    ffmpeg: str,
    python_executable: str,
    force: bool = False,
) -> dict[str, Any]:
    profiles = base.current_prepared_profiles()
    if not profiles:
        raise SystemExit(
            "No Experiment 02 prepared profiles found. "
            "Run Prepare Experiment 02 Profiles first."
        )

    results = [
        acquire_visual_one(
            profile,
            yt_dlp=yt_dlp,
            ffmpeg=ffmpeg,
            python_executable=python_executable,
            force=force,
        )
        for profile in profiles
    ]
    ready_statuses = {"READY", "READY_NO_OPENING_FRAME"}
    ready = sum(result.get("status") in ready_statuses for result in results)
    status = "COMPLETE" if ready == len(results) else "PARTIAL"
    summary = {
        "status": status,
        "profiles_found": len(profiles),
        "ready": ready,
        "failed": len(results) - ready,
        "full_video_saved": False,
        "results": results,
    }
    write_json(VISUAL_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire objective visual-structure evidence for Experiment 02"
    )
    parser.add_argument("--mode", choices=("doctor", "acquire"), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    yt_dlp = shutil.which("yt-dlp")
    ffmpeg = shutil.which("ffmpeg")

    if args.mode == "doctor":
        result = {
            "status": (
                "READY"
                if yt_dlp and ffmpeg
                else "MISSING_DEPENDENCY"
            ),
            "yt_dlp": yt_dlp,
            "ffmpeg": ffmpeg,
            "prepared_profiles": len(base.current_prepared_profiles()),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if not yt_dlp:
        raise SystemExit("yt-dlp is required for visual structure acquisition.")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required for visual structure acquisition.")

    summary = run_batch(
        yt_dlp=yt_dlp,
        ffmpeg=ffmpeg,
        python_executable=sys.executable,
        force=args.force,
    )

    print("\nEXPERIMENT 02 VISUAL STRUCTURE EVIDENCE")
    print("=" * 60)
    print(f"Status:           {summary['status']}")
    print(f"Prepared profiles:{summary['profiles_found']}")
    print(f"Visual ready:     {summary['ready']}")
    print(f"Needs attention:  {summary['failed']}")
    print("Full video saved: NO")
    for result in summary["results"]:
        print(
            f"  {result['video_id']}: {result['status']}"
            + (
                f" · transitions={result.get('scene_transition_candidate_count', '—')}"
                if result.get("status") in {"READY", "READY_NO_OPENING_FRAME"}
                else ""
            )
        )
    print(f"Summary:          {VISUAL_SUMMARY_FILE}")

    if summary["status"] != "COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
