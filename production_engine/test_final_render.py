from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_render


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalRenderTests(unittest.TestCase):
    def manifest(self, root: Path) -> dict:
        narration = root / "narration.wav"
        music = root / "music.wav"
        narration.write_bytes(b"narration")
        music.write_bytes(b"music")
        return {
            "artifact": "final_render_manifest",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_LOCAL_FINAL_RENDER",
            "duration_seconds": 4.0,
            "narration_track": [{
                "segment_id": "seg1",
                "audio_file": str(narration),
                "audio_start_seconds": 0.25,
            }],
            "sound_track": [{
                "requirement_id": "seg1:music",
                "kind": "MUSIC",
                "asset_file": str(music),
                "start_seconds": 0.0,
                "max_duration_seconds": 4.0,
                "loop_to_fill": True,
                "volume": 0.18,
            }],
            "omitted_sound_requirements": [],
        }

    def test_audio_filter_mixes_narration_and_music(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest(Path(tmp))
            inputs, filters = final_render.build_audio_filter(manifest)

        self.assertEqual(len(inputs), 2)
        self.assertFalse(inputs[0]["loop"])
        self.assertTrue(inputs[1]["loop"])
        self.assertIn("adelay=250:all=1", filters)
        self.assertIn("volume=0.180000", filters)
        self.assertIn("amix=inputs=2", filters)
        self.assertIn("alimiter=limit=0.95", filters)

    def test_audio_filter_supports_narration_only_after_omissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest(Path(tmp))
            manifest["sound_track"] = []
            inputs, filters = final_render.build_audio_filter(manifest)

        self.assertEqual(len(inputs), 1)
        self.assertIn("alimiter=limit=0.95", filters)
        self.assertNotIn("amix=inputs=2", filters)

    def test_final_visual_segments_reject_timeline_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "v.mp4"
            asset.write_bytes(b"video")
            manifest = {
                "duration_seconds": 3.0,
                "visual_track": [{
                    "scene_index": 0,
                    "start_seconds": 0.5,
                    "end_seconds": 3.0,
                    "asset_file": str(asset),
                    "asset_sha256": final_render.sha256_file(asset),
                }],
            }
            with self.assertRaisesRegex(ValueError, "gap"):
                final_render._final_visual_segments(manifest)

    def test_final_visual_tail_holds_last_asset_to_render_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "v.mp4"
            asset.write_bytes(b"video")
            manifest = {
                "duration_seconds": 4.0,
                "visual_track": [{
                    "scene_index": 0,
                    "start_seconds": 0.0,
                    "end_seconds": 3.0,
                    "asset_file": str(asset),
                    "asset_sha256": final_render.sha256_file(asset),
                }],
            }
            segments = final_render._final_visual_segments(manifest)

        self.assertEqual(segments[-1]["end_seconds"], 4.0)
        self.assertEqual(segments[-1]["duration_seconds"], 4.0)

    def test_result_currentness_detects_render_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir = root / "results"
            render_dir = root / "renders"
            manifest_dir = root / "manifests"
            manifest_path = write_json(
                manifest_dir / "c1.short.final_render_manifest.json",
                {"artifact": "final_render_manifest"},
            )
            render_path = render_dir / "c1.short.final_candidate.mp4"
            render_path.parent.mkdir(parents=True, exist_ok=True)
            render_path.write_bytes(b"candidate")
            result = {
                "artifact": "final_render_result",
                "concept_id": "c1",
                "format": "short",
                "status": "READY_FOR_HUMAN_FINAL_EXPORT_GATE",
                "render_file": str(render_path),
                "render_sha256": final_render.sha256_file(render_path),
                "render_bytes": render_path.stat().st_size,
                "provenance": {
                    "final_render_manifest": str(manifest_path),
                    "final_render_manifest_sha256": final_render.sha256_file(
                        manifest_path
                    ),
                },
            }
            result_path = write_json(
                result_dir / "c1.short.final_render_result.json",
                result,
            )
            with (
                patch.object(final_render, "RESULT_DIR", result_dir),
                patch.object(final_render, "RENDER_DIR", render_dir),
                patch.object(
                    final_render,
                    "manifest_is_current",
                    return_value={
                        "concept_id": "c1",
                        "format": "short",
                        "duration_seconds": 4.0,
                    },
                ),
            ):
                self.assertIsNotNone(
                    final_render.result_is_current(result_path)
                )
                render_path.write_bytes(b"changed")
                self.assertIsNone(
                    final_render.result_is_current(result_path)
                )


if __name__ == "__main__":
    unittest.main()
