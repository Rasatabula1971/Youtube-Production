"""Render a zero-cost local structural edit preview with FFmpeg.

Uses the deterministic edit manifest. Current local visual assets are rendered;
missing visuals become neutral placeholders. QC-passed narration segments are
placed at their actual timing-map positions.

No paid provider calls, music generation, SFX generation, upload or publish
actions occur here.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from edit_manifest import manifest_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
EDIT_DIR = OUTPUT / "edit_manifests"
PREVIEW_DIR = OUTPUT / "edit_previews"
WORK_DIR = OUTPUT / "edit_preview_work"
RESULT_DIR = OUTPUT / "edit_preview_results"
SUMMARY_FILE = OUTPUT / "edit_preview_render_summary.json"
NARRATION_CONFIG = HERE / "narration_render_config.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def ffmpeg_binary() -> str:
    if NARRATION_CONFIG.exists():
        try:
            payload = load_json(NARRATION_CONFIG)
            value = str(
                payload.get("audio_qc", {}).get("ffmpeg_binary") or ""
            ).strip()
            if value:
                return value
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return os.getenv("FFMPEG_BINARY", "ffmpeg")


def ffmpeg_available() -> bool:
    binary = ffmpeg_binary()
    return shutil.which(binary) is not None or Path(binary).is_file()

def _run(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            "FFmpeg preview command failed "
            f"({completed.returncode}): {detail}"
        )


def _video_filter(width: int, height: int, fps: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )


def preview_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    visuals = sorted(
        [
            item
            for item in manifest.get("visual_track", [])
            if isinstance(item, dict)
        ],
        key=lambda item: (
            float(item.get("start_seconds") or 0),
            int(item.get("scene_index") or 0),
        ),
    )
    total = float(
        manifest.get("duration", {}).get("preview_seconds") or 0
    )
    if total <= 0:
        raise ValueError("Edit preview duration must be positive")

    segments: list[dict[str, Any]] = []
    cursor = 0.0
    for item in visuals:
        start = float(item.get("start_seconds") or 0)
        end = float(item.get("end_seconds") or start)
        if start + 0.05 < cursor:
            raise ValueError("Visual edit timeline contains overlapping scenes")
        if start > cursor + 0.01:
            segments.append({
                "kind": "PLACEHOLDER",
                "start_seconds": cursor,
                "end_seconds": start,
                "duration_seconds": start - cursor,
                "reason": "TIMELINE_GAP",
            })
        segments.append({
            **item,
            "kind": (
                "ASSET"
                if item.get("preview_mode") == "ASSET"
                and item.get("asset_file")
                else "PLACEHOLDER"
            ),
        })
        cursor = end

    if cursor < total - 0.01:
        segments.append({
            "kind": "PLACEHOLDER",
            "start_seconds": cursor,
            "end_seconds": total,
            "duration_seconds": total - cursor,
            "reason": "TIMELINE_TAIL",
        })
    return segments


def _render_segment(
    *,
    segment: dict[str, Any],
    destination: Path,
    profile: dict[str, Any],
    binary: str,
) -> None:
    width = int(profile["width"])
    height = int(profile["height"])
    fps = int(profile["fps"])
    duration = float(segment.get("duration_seconds") or 0)
    if duration <= 0:
        raise ValueError("Preview segment duration must be positive")

    vf = _video_filter(width, height, fps)
    destination.parent.mkdir(parents=True, exist_ok=True)
    asset_value = str(segment.get("asset_file") or "").strip()
    asset = Path(asset_value) if asset_value else None

    if (
        segment.get("kind") == "ASSET"
        and asset is not None
        and asset.exists()
        and asset.is_file()
    ):
        if asset.suffix.lower() in IMAGE_EXTENSIONS:
            command = [
                binary,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-i",
                str(asset),
                "-t",
                f"{duration:.6f}",
                "-vf",
                vf,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                str(destination),
            ]
        else:
            command = [
                binary,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-stream_loop",
                "-1",
                "-i",
                str(asset),
                "-t",
                f"{duration:.6f}",
                "-vf",
                vf,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                str(destination),
            ]
    else:
        command = [
            binary,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            (
                f"color=c=0x111827:s={width}x{height}:"
                f"r={fps}:d={duration:.6f}"
            ),
            "-t",
            f"{duration:.6f}",
            "-vf",
            "format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            str(destination),
        ]
    _run(command)
    if not destination.exists() or destination.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create preview scene")


def _concat_visuals(
    *,
    segment_paths: list[Path],
    destination: Path,
    work_dir: Path,
    binary: str,
) -> None:
    if not segment_paths:
        raise ValueError("No visual preview segments were rendered")
    concat_path = work_dir / "concat.txt"
    lines = []
    for path in segment_paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run([
        binary,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-c",
        "copy",
        str(destination),
    ])


def narration_mix_filter(
    narration_track: list[dict[str, Any]],
) -> tuple[list[str], str]:
    filters: list[str] = []
    labels: list[str] = []
    for index, item in enumerate(narration_track, start=1):
        delay_ms = max(
            0,
            int(round(float(item.get("audio_start_seconds") or 0) * 1000)),
        )
        label = f"a{index}"
        filters.append(
            f"[{index}:a]adelay={delay_ms}:all=1[{label}]"
        )
        labels.append(f"[{label}]")
    if not labels:
        raise ValueError("Narration track is empty")
    if len(labels) == 1:
        return filters, labels[0]
    mix_label = "narration"
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:"
        "normalize=0"
        + f"[{mix_label}]"
    )
    return filters, f"[{mix_label}]"


def _mux_narration(
    *,
    visual_path: Path,
    narration_track: list[dict[str, Any]],
    duration: float,
    destination: Path,
    binary: str,
) -> None:
    command = [
        binary,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(visual_path),
    ]
    for item in narration_track:
        command.extend(["-i", str(item["audio_file"])])

    filters, audio_label = narration_mix_filter(narration_track)
    command.extend([
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v:0",
        "-map",
        audio_label,
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{duration:.6f}",
        "-movflags",
        "+faststart",
        str(destination),
    ])
    _run(command)


def render_one(
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    current = manifest_is_current(manifest_path)
    if current is None or current != manifest:
        raise ValueError("STALE_EDIT_MANIFEST")
    if manifest.get("status") != "READY_FOR_LOCAL_PREVIEW_RENDER":
        raise ValueError("Edit manifest is not preview-render ready")

    concept_id = str(manifest.get("concept_id") or "")
    fmt = str(manifest.get("format") or "")
    if not concept_id or not fmt:
        raise ValueError("Edit manifest identity is missing")
    key = _key(concept_id, fmt)

    binary = ffmpeg_binary()
    if not ffmpeg_available():
        raise RuntimeError(f"FFmpeg binary not found: {binary}")

    profile = manifest.get("video_profile", {})
    if not isinstance(profile, dict):
        raise ValueError("Edit manifest video profile is invalid")
    try:
        width = int(profile.get("width") or 0)
        height = int(profile.get("height") or 0)
        fps = int(profile.get("fps") or 0)
        duration = float(
            manifest.get("duration", {}).get("preview_seconds") or 0
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Edit preview profile/duration is invalid") from exc
    if width <= 0 or height <= 0 or fps <= 0 or duration <= 0:
        raise ValueError("Edit preview profile/duration must be positive")

    work_dir = WORK_DIR / key
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    segments = preview_segments(manifest)
    for index, segment in enumerate(segments):
        destination = work_dir / f"scene_{index:04d}.mp4"
        _render_segment(
            segment=segment,
            destination=destination,
            profile=profile,
            binary=binary,
        )
        segment_paths.append(destination)

    visual_path = work_dir / "visual_track.mp4"
    _concat_visuals(
        segment_paths=segment_paths,
        destination=visual_path,
        work_dir=work_dir,
        binary=binary,
    )

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = PREVIEW_DIR / f"{key}.structural_preview.mp4"
    _mux_narration(
        visual_path=visual_path,
        narration_track=manifest["narration_track"],
        duration=duration,
        destination=preview_path,
        binary=binary,
    )
    if not preview_path.is_file() or preview_path.stat().st_size <= 0:
        raise RuntimeError("Structural preview render did not create output")

    result = {
        "artifact": "edit_preview_render_result",
        "concept_id": concept_id,
        "format": fmt,
        "status": "READY_FOR_HUMAN_EDIT_PREVIEW_GATE",
        "preview_file": str(preview_path.resolve()),
        "preview_sha256": sha256_file(preview_path),
        "preview_bytes": preview_path.stat().st_size,
        "duration_seconds": duration,
        "placeholder_segments": sum(
            item.get("kind") == "PLACEHOLDER"
            for item in segments
        ),
        "render_policy": {
            "structural_preview_only": True,
            "publish_ready": False,
            "paid_provider_calls": 0,
            "music_or_sfx_generated": False,
            "local_ffmpeg_only": True,
        },
        "provenance": {
            "edit_manifest": str(manifest_path.resolve()),
            "edit_manifest_sha256": sha256_file(manifest_path),
        },
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULT_DIR / f"{key}.edit_preview_result.json"
    atomic_write_json(result_path, result)
    return {**result, "result_file": str(result_path)}


def batch() -> dict[str, Any]:
    paths = (
        sorted(EDIT_DIR.glob("*.edit_manifest.json"))
        if EDIT_DIR.exists()
        else []
    )
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    current_results: set[Path] = set()
    current_previews: set[Path] = set()

    for path in paths:
        manifest = manifest_is_current(path)
        if manifest is None:
            failures.append({
                "manifest": str(path),
                "error_type": "ValueError",
                "error": "STALE_EDIT_MANIFEST",
            })
            continue
        try:
            result = render_one(path, manifest)
            items.append(result)
            current_results.add(Path(result["result_file"]).resolve())
            current_previews.add(Path(result["preview_file"]).resolve())
        except Exception as exc:
            failures.append({
                "manifest": str(path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    if RESULT_DIR.exists():
        for stale in RESULT_DIR.glob("*.edit_preview_result.json"):
            if stale.resolve() not in current_results:
                stale.unlink()

    if PREVIEW_DIR.exists():
        for stale in PREVIEW_DIR.glob("*.structural_preview.mp4"):
            if stale.resolve() not in current_previews:
                stale.unlink()

    summary = {
        "status": (
            "READY_FOR_HUMAN_EDIT_PREVIEW_GATE"
            if items and not failures
            else "PARTIAL"
            if items
            else "FAILED"
            if failures
            else "WAITING_FOR_EDIT_MANIFESTS"
        ),
        "rendered": len(items),
        "failed": len(failures),
        "paid_provider_calls": 0,
        "media_rendered_locally": bool(items),
        "items": items,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render local structural edit previews"
    )
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.parse_args()
    result = batch()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if int(result.get("failed") or 0) > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
