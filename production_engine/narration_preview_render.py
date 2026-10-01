"""Render zero-cost narration previews locally with Kokoro.

No network API fallback exists. Missing local dependencies fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
MANIFEST_DIR = OUTPUT_DIR / "narration_preview_manifests"
AUDIO_DIR = OUTPUT_DIR / "narration_preview_audio"
SEGMENT_AUDIO_DIR = OUTPUT_DIR / "narration_preview_segments"
SUMMARY_FILE = OUTPUT_DIR / "narration_preview_render_summary.json"
SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"


def _write_wav(path: Path, samples: Any) -> None:
    import numpy as np

    pcm = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


def _silence(milliseconds: int) -> Any:
    import numpy as np

    count = max(0, int(SAMPLE_RATE * milliseconds / 1000))
    return np.zeros(count, dtype=np.float32)


def _segment_fingerprint(segment: dict[str, Any]) -> str:
    payload = {
        "renderer": "kokoro_local",
        "voice": DEFAULT_VOICE,
        "sample_rate": SAMPLE_RATE,
        "immutable_narration": str(segment.get("immutable_narration") or ""),
        "delivery": segment.get("delivery", {}),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _segment_metadata_path(audio_path: Path) -> Path:
    return audio_path.with_suffix(".meta.json")


def _segment_cache_current(
    audio_path: Path,
    fingerprint: str,
) -> bool:
    metadata_path = _segment_metadata_path(audio_path)
    if not audio_path.exists() or not metadata_path.exists():
        return False
    try:
        metadata = load_json(metadata_path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(metadata, dict)
        and metadata.get("segment_fingerprint") == fingerprint
        and metadata.get("audio_sha256") == sha256_file(audio_path)
    )


def _load_local_pipeline() -> Any:
    try:
        import numpy  # noqa: F401
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "LOCAL_KOKORO_NOT_INSTALLED: install kokoro, soundfile and espeak-ng; "
            "paid fallback is forbidden"
        ) from exc
    return KPipeline(lang_code="a")


def _render_segment(
    segment: dict[str, Any],
    destination: Path,
    pipeline: Any,
) -> None:
    import numpy as np

    delivery = segment.get("delivery", {})
    before = int(delivery.get("pause_before_ms") or 0)
    after = int(delivery.get("pause_after_ms") or 0)
    speed = float(delivery.get("speed") or 1.0)
    chunks: list[Any] = [_silence(before)]
    generated = list(
        pipeline(
            str(segment.get("immutable_narration") or ""),
            voice=DEFAULT_VOICE,
            speed=speed,
        )
    )
    if not generated:
        raise RuntimeError("Kokoro returned no preview audio")
    chunks.extend(np.asarray(item[2], dtype=np.float32) for item in generated)
    chunks.append(_silence(after))
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_wav(destination, np.concatenate(chunks))


def _concatenate_segment_wavs(
    segment_paths: list[Path],
    destination: Path,
) -> None:
    frames: list[bytes] = []
    for path in segment_paths:
        with wave.open(str(path), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() != SAMPLE_RATE
            ):
                raise RuntimeError(
                    "Cached preview segment has an incompatible WAV format"
                )
            frames.append(handle.readframes(handle.getnframes()))

    if not frames:
        raise RuntimeError("Preview manifest contains no renderable segments")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(b"".join(frames))


def render_manifest(
    manifest: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    segments = manifest.get("segments", [])
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("Preview manifest contains no renderable segments")

    key = destination.name
    if key.endswith(".preview.wav"):
        key = key[: -len(".preview.wav")]
    else:
        key = destination.stem

    SEGMENT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []
    current_cache_files: set[Path] = set()
    pipeline: Any | None = None
    rendered = 0
    reused = 0

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("Preview segment must be an object")
        segment_id = str(segment.get("segment_id") or index)
        fingerprint = _segment_fingerprint(segment)
        segment_path = SEGMENT_AUDIO_DIR / (
            f"{safe_slug(key)}.{index:03d}.{safe_slug(segment_id)}.segment.wav"
        )
        metadata_path = _segment_metadata_path(segment_path)
        current_cache_files.add(segment_path.resolve())
        current_cache_files.add(metadata_path.resolve())

        if _segment_cache_current(segment_path, fingerprint):
            reused += 1
        else:
            if pipeline is None:
                pipeline = _load_local_pipeline()
            _render_segment(segment, segment_path, pipeline)
            metadata = {
                "artifact": "narration_preview_segment_render",
                "concept_id": manifest.get("concept_id"),
                "format": manifest.get("format"),
                "segment_id": segment_id,
                "segment_index": index,
                "segment_fingerprint": fingerprint,
                "audio": str(segment_path.resolve()),
                "audio_sha256": sha256_file(segment_path),
                "renderer": "kokoro_local",
                "voice": DEFAULT_VOICE,
                "sample_rate": SAMPLE_RATE,
                "paid_call": False,
            }
            atomic_write_json(metadata_path, metadata)
            rendered += 1
        segment_paths.append(segment_path)

    _concatenate_segment_wavs(segment_paths, destination)

    # Remove obsolete cache entries for this preview only after a complete
    # reassembly succeeds.
    prefix = f"{safe_slug(key)}."
    for cached in SEGMENT_AUDIO_DIR.iterdir():
        if (
            cached.is_file()
            and cached.name.startswith(prefix)
            and cached.resolve() not in current_cache_files
            and (
                cached.name.endswith(".segment.wav")
                or cached.name.endswith(".segment.meta.json")
            )
        ):
            cached.unlink()

    return {
        "status": "FREE_PREVIEW_RENDERED",
        "renderer": "kokoro_local",
        "voice": DEFAULT_VOICE,
        "sample_rate": SAMPLE_RATE,
        "audio": str(destination),
        "segments_total": len(segment_paths),
        "segments_rendered": rendered,
        "segments_reused": reused,
        "paid_call": False,
    }


def batch() -> dict[str, Any]:
    manifests = sorted(MANIFEST_DIR.glob("*.narration_preview.json")) if MANIFEST_DIR.exists() else []
    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in manifests:
        manifest = load_json(path)
        key = f"{safe_slug(str(manifest.get('concept_id') or ''))}.{safe_slug(str(manifest.get('format') or ''))}"
        destination = AUDIO_DIR / f"{key}.preview.wav"
        try:
            render_result = render_manifest(manifest, destination)
            manifest_hash = sha256_file(path)
            audio_hash = sha256_file(destination)
            metadata_path = destination.with_suffix(".meta.json")
            metadata = {
                "artifact": "narration_preview_render_metadata",
                "concept_id": manifest.get("concept_id"),
                "format": manifest.get("format"),
                "manifest": str(path.resolve()),
                "manifest_sha256": manifest_hash,
                "audio": str(destination.resolve()),
                "audio_sha256": audio_hash,
                "renderer": render_result.get("renderer"),
                "voice": render_result.get("voice"),
                "sample_rate": render_result.get("sample_rate"),
                "paid_call": False,
            }
            atomic_write_json(metadata_path, metadata)
            items.append({
                "concept_id": manifest.get("concept_id"),
                "format": manifest.get("format"),
                **render_result,
                "manifest_sha256": manifest_hash,
                "audio_sha256": audio_hash,
                "render_metadata": str(metadata_path),
            })
        except (RuntimeError, ValueError, OSError) as exc:
            failures.append({"manifest": str(path), "error": str(exc)})
    result = {
        "status": "READY_FOR_LISTEN_GATE" if items and not failures else "LOCAL_PREVIEW_BLOCKED" if failures else "WAITING_FOR_PREVIEW_MANIFESTS",
        "rendered": len(items),
        "failures": failures,
        "items": items,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Render local Kokoro narration preview")
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.parse_args()
    result = batch()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "LOCAL_PREVIEW_BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
