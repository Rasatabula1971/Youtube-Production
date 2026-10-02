from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import edit_manifest as module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class EditManifestTests(unittest.TestCase):
    def setup_current_inputs(
        self,
        stack: ExitStack,
        root: Path,
        *,
        qc_status: str = "PASS",
    ) -> dict[str, Path | dict]:
        assembly_dir = root / "assembly"
        qc_dir = root / "qc"
        timing_dir = root / "timing"
        sound_dir = root / "sound"
        edit_dir = root / "edit"

        stack.enter_context(
            patch.object(module, "ASSEMBLY_DIR", assembly_dir)
        )
        stack.enter_context(patch.object(module, "QC_DIR", qc_dir))
        stack.enter_context(
            patch.object(module, "TIMING_DIR", timing_dir)
        )
        stack.enter_context(
            patch.object(module, "SOUND_DIR", sound_dir)
        )
        stack.enter_context(
            patch.object(module, "EDIT_DIR", edit_dir)
        )

        audio = root / "seg.wav"
        audio.write_bytes(b"audio-v1")
        render_result = write_json(
            root / "render_result.json",
            {
                "artifact": "narration_render_result",
                "concept_id": "c1",
                "format": "short",
            },
        )

        assembly = {
            "artifact": "visual_assembly_plan",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_EDIT_ASSEMBLY",
            "timeline": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "beat_id": "b1",
                    "time_range": {
                        "start_seconds": 0,
                        "end_seconds": 2,
                    },
                    "story_purpose": "hook",
                    "desired_visual": "landing impact",
                    "visual_status": "PLACEHOLDER_APPROVED",
                    "cinematic_direction": {},
                }
            ],
        }
        assembly_path = write_json(
            assembly_dir / "c1.short.visual_assembly_plan.json",
            assembly,
        )

        qc = {
            "artifact": "narration_audio_qc",
            "concept_id": "c1",
            "format": "short",
            "status": qc_status,
            "checks": [
                {
                    "segment_id": "b1",
                    "status": qc_status,
                    "audio_file": str(audio),
                }
            ],
            "provenance": {
                "render_result": str(render_result),
                "render_result_sha256": module.sha256_file(
                    render_result
                ),
            },
        }
        qc_path = write_json(
            qc_dir / "c1.short.narration_audio_qc.json",
            qc,
        )

        timing = {
            "artifact": "narration_timing_map",
            "concept_id": "c1",
            "format": "short",
            "status": (
                "READY_FOR_ROUGH_CUT"
                if qc_status == "PASS"
                else "BLOCKED_BY_AUDIO_QC"
            ),
            "source_audio_qc_status": qc_status,
            "source_render_result_sha256": module.sha256_file(
                render_result
            ),
            "total_duration_seconds": 2.2,
            "segments": [
                {
                    "segment_id": "b1",
                    "pause_before_seconds": 0.1,
                    "audio_start_seconds": 0.1,
                    "audio_end_seconds": 2.0,
                    "pause_after_seconds": 0.2,
                    "timeline_end_seconds": 2.2,
                }
            ],
        }
        timing_path = write_json(
            timing_dir / "c1.short.narration_timing_map.json",
            timing,
        )
        sound_path = write_json(
            sound_dir / "c1.short.sound_design_brief.json",
            {
                "directions": [
                    {
                        "segment_id": "b1",
                        "music_direction": "tense pulse",
                        "sfx_direction": ["impact"],
                    }
                ]
            },
        )

        stack.enter_context(
            patch.object(
                module,
                "assembly_plan_is_current",
                side_effect=lambda path: (
                    json.loads(path.read_text(encoding="utf-8"))
                    if path.exists()
                    else None
                ),
            )
        )
        stack.enter_context(
            patch.object(
                module,
                "current_registered_narration_result",
                side_effect=lambda concept_id, fmt: (
                    (
                        render_result,
                        json.loads(
                            render_result.read_text(encoding="utf-8")
                        ),
                    )
                    if concept_id == "c1" and fmt == "short"
                    else None
                ),
            )
        )

        return {
            "assembly": assembly,
            "assembly_path": assembly_path,
            "qc": qc,
            "qc_path": qc_path,
            "timing": timing,
            "timing_path": timing_path,
            "sound_path": sound_path,
            "audio": audio,
            "render_result": render_result,
            "edit_dir": edit_dir,
        }

    def test_build_manifest_uses_qc_audio_and_allows_visual_placeholder(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            ExitStack() as stack,
        ):
            data = self.setup_current_inputs(stack, Path(tmp))
            manifest = module.build_manifest(
                assembly_path=data["assembly_path"],
                assembly=data["assembly"],
                qc_path=data["qc_path"],
                qc=data["qc"],
                timing_path=data["timing_path"],
                timing=data["timing"],
                sound_path=data["sound_path"],
            )

        self.assertEqual(
            manifest["status"],
            "READY_FOR_LOCAL_PREVIEW_RENDER",
        )
        self.assertEqual(
            manifest["video_profile"]["aspect_ratio"],
            "9:16",
        )
        self.assertEqual(
            manifest["visual_track"][0]["preview_mode"],
            "PLACEHOLDER",
        )
        self.assertEqual(
            manifest["preview_policy"]["placeholder_count"],
            1,
        )
        self.assertEqual(
            manifest["narration_track"][0]["audio_start_seconds"],
            0.1,
        )
        self.assertEqual(
            manifest["sound_design_intent"][0]["music_direction"],
            "tense pulse",
        )
        self.assertFalse(
            manifest["preview_policy"]["publish_ready"]
        )

    def test_qc_failure_blocks_manifest(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            ExitStack() as stack,
        ):
            data = self.setup_current_inputs(
                stack,
                Path(tmp),
                qc_status="FAIL",
            )
            with self.assertRaisesRegex(
                ValueError,
                "Audio QC must PASS",
            ):
                module.build_manifest(
                    assembly_path=data["assembly_path"],
                    assembly=data["assembly"],
                    qc_path=data["qc_path"],
                    qc=data["qc"],
                    timing_path=data["timing_path"],
                    timing=data["timing"],
                    sound_path=data["sound_path"],
                )

    def test_manifest_becomes_stale_when_assembly_changes(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            ExitStack() as stack,
        ):
            data = self.setup_current_inputs(stack, Path(tmp))
            manifest = module.build_manifest(
                assembly_path=data["assembly_path"],
                assembly=data["assembly"],
                qc_path=data["qc_path"],
                qc=data["qc"],
                timing_path=data["timing_path"],
                timing=data["timing"],
                sound_path=data["sound_path"],
            )
            manifest_path = write_json(
                data["edit_dir"] / "c1.short.edit_manifest.json",
                manifest,
            )
            self.assertIsNotNone(
                module.manifest_is_current(manifest_path)
            )

            changed = dict(data["assembly"])
            changed["timeline"] = [
                {
                    **data["assembly"]["timeline"][0],
                    "desired_visual": "changed current visual",
                }
            ]
            write_json(data["assembly_path"], changed)

            self.assertIsNone(
                module.manifest_is_current(manifest_path)
            )

    def test_manifest_becomes_stale_when_audio_file_changes(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            ExitStack() as stack,
        ):
            data = self.setup_current_inputs(stack, Path(tmp))
            manifest = module.build_manifest(
                assembly_path=data["assembly_path"],
                assembly=data["assembly"],
                qc_path=data["qc_path"],
                qc=data["qc"],
                timing_path=data["timing_path"],
                timing=data["timing"],
                sound_path=data["sound_path"],
            )
            manifest_path = write_json(
                data["edit_dir"] / "c1.short.edit_manifest.json",
                manifest,
            )
            self.assertIsNotNone(
                module.manifest_is_current(manifest_path)
            )

            data["audio"].write_bytes(b"audio-v2")

            self.assertIsNone(
                module.manifest_is_current(manifest_path)
            )


if __name__ == "__main__":
    unittest.main()
