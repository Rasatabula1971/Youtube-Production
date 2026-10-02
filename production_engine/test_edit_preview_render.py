from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import edit_preview_render as module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class EditPreviewRenderTests(unittest.TestCase):
    def test_preview_segments_fill_gap_and_tail(self):
        manifest = {
            "duration": {"preview_seconds": 5.0},
            "visual_track": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "start_seconds": 1.0,
                    "end_seconds": 2.0,
                    "duration_seconds": 1.0,
                    "preview_mode": "PLACEHOLDER",
                },
                {
                    "scene_index": 1,
                    "shot_id": "s2",
                    "start_seconds": 2.0,
                    "end_seconds": 4.0,
                    "duration_seconds": 2.0,
                    "preview_mode": "ASSET",
                    "asset_file": "x.mp4",
                },
            ],
        }

        segments = module.preview_segments(manifest)

        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[0]["kind"], "PLACEHOLDER")
        self.assertEqual(segments[0]["reason"], "TIMELINE_GAP")
        self.assertEqual(segments[1]["shot_id"], "s1")
        self.assertEqual(segments[2]["shot_id"], "s2")
        self.assertEqual(segments[3]["reason"], "TIMELINE_TAIL")
        self.assertEqual(segments[3]["duration_seconds"], 1.0)

    def test_preview_segments_reject_overlap(self):
        manifest = {
            "duration": {"preview_seconds": 3.0},
            "visual_track": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "start_seconds": 0.0,
                    "end_seconds": 2.0,
                    "duration_seconds": 2.0,
                    "preview_mode": "PLACEHOLDER",
                },
                {
                    "scene_index": 1,
                    "shot_id": "s2",
                    "start_seconds": 1.5,
                    "end_seconds": 3.0,
                    "duration_seconds": 1.5,
                    "preview_mode": "PLACEHOLDER",
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "overlapping scenes"):
            module.preview_segments(manifest)

    def test_narration_mix_filter_uses_absolute_delays(self):
        filters, label = module.narration_mix_filter([
            {"audio_start_seconds": 0.25},
            {"audio_start_seconds": 2.0},
        ])

        self.assertIn("[1:a]adelay=250:all=1[a1]", filters)
        self.assertIn("[2:a]adelay=2000:all=1[a2]", filters)
        self.assertTrue(
            any("amix=inputs=2" in item for item in filters)
        )
        self.assertEqual(label, "[narration]")

    def test_render_one_rejects_stale_manifest_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = write_json(
                root / "edit" / "c1.short.edit_manifest.json",
                {
                    "artifact": "edit_manifest",
                    "status": "READY_FOR_LOCAL_PREVIEW_RENDER",
                    "concept_id": "c1",
                    "format": "short",
                },
            )
            with (
                patch.object(
                    module,
                    "manifest_is_current",
                    return_value=None,
                ),
                patch.object(module, "_run") as run,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_EDIT_MANIFEST",
                ):
                    module.render_one(
                        manifest_path,
                        json.loads(
                            manifest_path.read_text(encoding="utf-8")
                        ),
                    )

        run.assert_not_called()

    def test_preview_result_requires_current_manifest_and_exact_media(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            ExitStack() as stack,
        ):
            root = Path(tmp)
            edit_dir = root / "edit"
            preview_dir = root / "preview"
            result_dir = root / "result"
            stack.enter_context(
                patch.object(module, "EDIT_DIR", edit_dir)
            )
            stack.enter_context(
                patch.object(module, "PREVIEW_DIR", preview_dir)
            )
            stack.enter_context(
                patch.object(module, "RESULT_DIR", result_dir)
            )

            manifest = {
                "artifact": "edit_manifest",
                "status": "READY_FOR_LOCAL_PREVIEW_RENDER",
                "concept_id": "c1",
                "format": "short",
            }
            manifest_path = write_json(
                edit_dir / "c1.short.edit_manifest.json",
                manifest,
            )
            preview = preview_dir / "c1.short.structural_preview.mp4"
            preview.parent.mkdir(parents=True, exist_ok=True)
            preview.write_bytes(b"preview-v1")
            result_path = write_json(
                result_dir / "c1.short.edit_preview_result.json",
                {
                    "artifact": "edit_preview_render_result",
                    "concept_id": "c1",
                    "format": "short",
                    "status": "READY_FOR_HUMAN_EDIT_PREVIEW_GATE",
                    "preview_file": str(preview.resolve()),
                    "preview_sha256": module.sha256_file(preview),
                    "preview_bytes": preview.stat().st_size,
                    "provenance": {
                        "edit_manifest": str(manifest_path.resolve()),
                        "edit_manifest_sha256": module.sha256_file(
                            manifest_path
                        ),
                    },
                },
            )
            stack.enter_context(
                patch.object(
                    module,
                    "manifest_is_current",
                    side_effect=lambda path: (
                        manifest
                        if path.resolve() == manifest_path.resolve()
                        else None
                    ),
                )
            )

            self.assertIsNotNone(
                module.preview_result_is_current(result_path)
            )
            preview.write_bytes(b"preview-v2")

            self.assertIsNone(
                module.preview_result_is_current(result_path)
            )


if __name__ == "__main__":
    unittest.main()
