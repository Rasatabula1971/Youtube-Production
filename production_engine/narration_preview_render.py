"""Render zero-cost narration previews locally with Kokoro.

No network API fallback exists. Missing local dependencies fail closed.
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
MANIFEST_DIR = OUTPUT_DIR / "narration_preview_manifests"
AUDIO_DIR = OUTPUT_DIR / "narration_preview_audio"
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


def render_manifest(manifest: dict[str, Any], destination: Path) -> dict[str, Any]:
    try:
        import numpy as np
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "LOCAL_KOKORO_NOT_INSTALLED: install kokoro, soundfile and espeak-ng; "
            "paid fallback is forbidden"
        ) from exc

    pipeline = KPipeline(lang_code="a")
    chunks: list[Any] = []
    for segment in manifest.get("segments", []):
        delivery = segment.get("delivery", {})
        before = int(delivery.get("pause_before_ms") or 0)
        after = int(delivery.get("pause_after_ms") or 0)
        speed = float(delivery.get("speed") or 1.0)
        chunks.append(_silence(before))
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

    if not chunks:
        raise RuntimeError("Preview manifest contains no renderable segments")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_wav(destination, np.concatenate(chunks))
    return {
        "status": "FREE_PREVIEW_RENDERED",
        "renderer": "kokoro_local",
        "voice": DEFAULT_VOICE,
        "sample_rate": SAMPLE_RATE,
        "audio": str(destination),
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
            items.append({
                "concept_id": manifest.get("concept_id"),
                "format": manifest.get("format"),
                **render_manifest(manifest, destination),
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
