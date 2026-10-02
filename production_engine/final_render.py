"""Render the Slice 22 final candidate locally with FFmpeg.

Only a rebuild-current final render manifest may be rendered. The output is a
publish-quality candidate, but it is not approved for export, upload, or
publishing until the Human Final Export Gate accepts the exact rendered bytes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from edit_preview_render import ffmpeg_available, ffmpeg_binary
from final_render_manifest import MANIFEST_DIR, manifest_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
WORK_DIR = OUTPUT / "final_render_work"
RENDER_DIR = OUTPUT / "final_renders"
RESULT_DIR = OUTPUT / "final_render_results"
SUMMARY_FILE = OUTPUT / "final_render_summary.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


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
            f"FFmpeg final render failed ({completed.returncode}): {detail}"
        )


def _video_filter(width: int, height: int, fps: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )


def _final_visual_segments(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    total = float(manifest.get("duration_seconds") or 0)
    visuals = sorted(
        [
            dict(item)
            for item in manifest.get("visual_track", [])
            if isinstance(item, dict)
        ],
        key=lambda item: (
            float(item.get("start_seconds") or 0),
            int(item.get("scene_index") or 0),
        ),
    )
    if total <= 0 or not visuals:
        raise ValueError("Final render requires a positive visual timeline")

    cursor = 0.0
    for item in visuals:
        start = float(item.get("start_seconds") or 0)
        end = float(item.get("end_seconds") or start)
        path = Path(str(item.get("asset_file") or ""))
        if start < cursor - 0.02:
            raise ValueError("Final visual timeline overlaps")
        if start > cursor + 0.02:
            raise ValueError("Final visual timeline contains a gap")
        if end <= start:
            raise ValueError("Final visual segment has invalid duration")
        if (
            not path.is_file()
            or item.get("asset_sha256") != sha256_file(path)
        ):
            raise ValueError("Final visual asset is stale or missing")
        item["duration_seconds"] = end - start
        cursor = end

    if cursor < total - 0.02:
        raise ValueError("Final visual timeline does not cover render duration")
    return visuals


def _render_visual_segment(
    *,
    item: dict[str, Any],
    destination: Path,
    profile: dict[str, Any],
    binary: str,
) -> None:
    width = int(profile.get("width") or 0)
    height = int(profile.get("height") or 0)
    fps = int(profile.get("fps") or 0)
    duration = float(item.get("duration_seconds") or 0)
    source = Path(str(item.get("asset_file") or ""))
    if (
        width <= 0
        or height <= 0
        or fps <= 0
        or duration <= 0
        or not source.is_file()
    ):
        raise ValueError("Invalid final visual render input")

    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, "-y", "-hide_banner", "-loglevel", "error"]
    if source.suffix.lower() in IMAGE_EXTENSIONS:
        command.extend(["-loop", "1", "-i", str(source)])
    else:
        command.extend(["-stream_loop", "-1", "-i", str(source)])
    command.extend([
        "-t",
        f"{duration:.6f}",
        "-vf",
        _video_filter(width, height, fps),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        str(destination),
    ])
    _run(command)
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("Final visual segment render produced no media")


def _concat_visuals(
    paths: list[Path],
    destination: Path,
    work_dir: Path,
    binary: str,
) -> None:
    concat_path = work_dir / "concat.txt"
    concat_path.write_text(
        "\n".join(
            "file '" + str(path.resolve()).replace("'", "'\\''") + "'"
            for path in paths
        )
        + "\n",
        encoding="utf-8",
    )
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


def build_audio_filter(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    narration = [
        dict(item)
        for item in manifest.get("narration_track", [])
        if isinstance(item, dict)
    ]
    sound = [
        dict(item)
        for item in manifest.get("sound_track", [])
        if isinstance(item, dict)
    ]
    if not narration:
        raise ValueError("Final render has no narration")

    inputs: list[dict[str, Any]] = []
    filters: list[str] = []
    labels: list[str] = []
    input_index = 1

    for number, item in enumerate(narration):
        path = Path(str(item.get("audio_file") or ""))
        if not path.is_file():
            raise ValueError("Final narration file is missing")
        delay_ms = max(
            0,
            int(round(float(item.get("audio_start_seconds") or 0) * 1000)),
        )
        label = f"n{number}"
        inputs.append({
            "path": str(path),
            "loop": False,
            "kind": "NARRATION",
        })
        filters.append(
            f"[{input_index}:a]adelay={delay_ms}:all=1,"
            f"volume=1.0[{label}]"
        )
        labels.append(f"[{label}]")
        input_index += 1

    for number, item in enumerate(sound):
        path = Path(str(item.get("asset_file") or ""))
        if not path.is_file():
            raise ValueError("Final sound file is missing")
        start_ms = max(
            0,
            int(round(float(item.get("start_seconds") or 0) * 1000)),
        )
        max_duration = float(item.get("max_duration_seconds") or 0)
        if max_duration <= 0:
            raise ValueError("Final sound cue duration must be positive")
        volume = float(item.get("volume") or 0)
        if volume <= 0:
            raise ValueError("Final sound cue volume must be positive")
        label = f"s{number}"
        inputs.append({
            "path": str(path),
            "loop": bool(item.get("loop_to_fill")),
            "kind": str(item.get("kind") or ""),
        })
        filters.append(
            f"[{input_index}:a]atrim=0:{max_duration:.6f},"
            "asetpts=PTS-STARTPTS,"
            f"adelay={start_ms}:all=1,volume={volume:.6f}[{label}]"
        )
        labels.append(f"[{label}]")
        input_index += 1

    if len(labels) == 1:
        filters.append(
            f"{labels[0]}alimiter=limit=0.95,aresample=48000[finala]"
        )
    else:
        filters.append(
            "".join(labels)
            + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
            "alimiter=limit=0.95,aresample=48000[finala]"
        )
    return inputs, ";".join(filters)


def _mux_final_audio(
    *,
    visual_path: Path,
    manifest: dict[str, Any],
    destination: Path,
    binary: str,
) -> None:
    inputs, filter_complex = build_audio_filter(manifest)
    command = [
        binary,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(visual_path),
    ]
    for item in inputs:
        if item["loop"]:
            command.extend(["-stream_loop", "-1"])
        command.extend(["-i", item["path"]])

    command.extend([
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v:0",
        "-map",
        "[finala]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-ar",
        "48000",
        "-t",
        f"{float(manifest['duration_seconds']):.6f}",
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
        raise ValueError("STALE_FINAL_RENDER_MANIFEST")
    if manifest.get("status") != "READY_FOR_LOCAL_FINAL_RENDER":
        raise ValueError("Final render manifest is not ready")
    if not ffmpeg_available():
        raise RuntimeError(
            f"Configured FFmpeg binary not found: {ffmpeg_binary()}"
        )

    concept_id = str(manifest.get("concept_id") or "")
    fmt = str(manifest.get("format") or "")
    key = _key(concept_id, fmt)
    profile = manifest.get("video_profile", {})
    if not isinstance(profile, dict):
        raise ValueError("Final video profile is invalid")

    work_dir = WORK_DIR / key
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    binary = ffmpeg_binary()

    segments = _final_visual_segments(manifest)
    rendered: list[Path] = []
    for index, item in enumerate(segments):
        destination = work_dir / f"scene_{index:04d}.mp4"
        _render_visual_segment(
            item=item,
            destination=destination,
            profile=profile,
            binary=binary,
        )
        rendered.append(destination)

    visual_path = work_dir / "visual_track.mp4"
    _concat_visuals(rendered, visual_path, work_dir, binary)

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    destination = RENDER_DIR / f"{key}.final_candidate.mp4"
    _mux_final_audio(
        visual_path=visual_path,
        manifest=manifest,
        destination=destination,
        binary=binary,
    )
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("Local final render did not create output")

    result = {
        "artifact": "final_render_result",
        "concept_id": concept_id,
        "format": fmt,
        "status": "READY_FOR_HUMAN_FINAL_EXPORT_GATE",
        "render_file": str(destination.resolve()),
        "render_sha256": sha256_file(destination),
        "render_bytes": destination.stat().st_size,
        "duration_seconds": float(manifest.get("duration_seconds") or 0),
        "sound_assets_mixed": len(manifest.get("sound_track", [])),
        "sound_omissions": len(
            manifest.get("omitted_sound_requirements", [])
        ),
        "render_policy": {
            "local_ffmpeg_only": True,
            "publish_quality_candidate": True,
            "human_export_approved": False,
            "upload_performed": False,
            "publish_performed": False,
            "paid_provider_calls": 0,
        },
        "provenance": {
            "final_render_manifest": str(manifest_path.resolve()),
            "final_render_manifest_sha256": sha256_file(manifest_path),
        },
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULT_DIR / f"{key}.final_render_result.json"
    atomic_write_json(result_path, result)
    return {**result, "result_file": str(result_path.resolve())}


def result_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != RESULT_DIR.resolve()
    ):
        return None
    try:
        result = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(result, dict)
        or result.get("artifact") != "final_render_result"
        or result.get("status") != "READY_FOR_HUMAN_FINAL_EXPORT_GATE"
    ):
        return None

    provenance = result.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    manifest_path = Path(
        str(provenance.get("final_render_manifest") or "")
    )
    if (
        manifest_is_current(manifest_path) is None
        or provenance.get("final_render_manifest_sha256")
        != sha256_file(manifest_path)
    ):
        return None

    render_path = Path(str(result.get("render_file") or ""))
    if (
        not render_path.is_file()
        or render_path.parent.resolve() != RENDER_DIR.resolve()
        or result.get("render_sha256") != sha256_file(render_path)
        or int(result.get("render_bytes") or 0) != render_path.stat().st_size
    ):
        return None
    return result


def batch() -> dict[str, Any]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    current_results: set[Path] = set()
    current_renders: set[Path] = set()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for manifest_path in (
        sorted(MANIFEST_DIR.glob("*.final_render_manifest.json"))
        if MANIFEST_DIR.exists()
        else []
    ):
        manifest = manifest_is_current(manifest_path)
        if manifest is None:
            failures.append({
                "manifest": str(manifest_path),
                "error_type": "ValueError",
                "error": "STALE_FINAL_RENDER_MANIFEST",
            })
            continue
        try:
            result = render_one(manifest_path, manifest)
            items.append(result)
            current_results.add(Path(result["result_file"]).resolve())
            current_renders.add(Path(result["render_file"]).resolve())
        except Exception as exc:
            failures.append({
                "manifest": str(manifest_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    for stale in RESULT_DIR.glob("*.final_render_result.json"):
        if stale.resolve() not in current_results:
            stale.unlink()
    for stale in RENDER_DIR.glob("*.final_candidate.mp4"):
        if stale.resolve() not in current_renders:
            stale.unlink()

    result = {
        "status": (
            "READY_FOR_HUMAN_FINAL_EXPORT_GATE"
            if items and not failures
            else "PARTIAL"
            if items
            else "FAILED"
            if failures
            else "WAITING_FOR_FINAL_RENDER_MANIFESTS"
        ),
        "rendered": len(items),
        "failed": len(failures),
        "items": items,
        "upload_performed": False,
        "publish_performed": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render local final video candidates"
    )
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.parse_args()
    result = batch()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] in {"FAILED", "PARTIAL"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
