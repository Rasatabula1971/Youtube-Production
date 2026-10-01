from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_production_handoff as handoff


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalProductionHandoffTests(unittest.TestCase):
    def build_chain(self, root: Path, *, missing_visual: bool = False):
        visual = root / "visual.mp4"
        visual.write_bytes(b"visual")
        audio = root / "narration.wav"
        audio.write_bytes(b"audio")

        manifest = {
            "artifact": "edit_manifest",
            "status": "READY_FOR_LOCAL_PREVIEW_RENDER",
            "concept_id": "c1",
            "format": "short",
            "video_profile": {
                "width": 1080,
                "height": 1920,
                "fps": 30,
            },
            "duration": {"preview_seconds": 5.0},
            "visual_track": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "beat_id": "b1",
                    "start_seconds": 0.0,
                    "end_seconds": 5.0,
                    "duration_seconds": 5.0,
                    "story_purpose": "hook",
                    "cinematic_direction": {},
                    "preview_mode": (
                        "PLACEHOLDER" if missing_visual else "ASSET"
                    ),
                    "asset_file": (
                        None if missing_visual else str(visual)
                    ),
                    "asset_sha256": (
                        None
                        if missing_visual
                        else handoff.sha256_file(visual)
                    ),
                    "source_visual_status": (
                        "PREMIUM_GENERATION_PENDING"
                        if missing_visual
                        else "GENERATED_ASSET_READY"
                    ),
                }
            ],
            "narration_track": [
                {
                    "segment_id": "b1",
                    "audio_file": str(audio),
                    "audio_sha256": handoff.sha256_file(audio),
                    "audio_start_seconds": 0.0,
                    "audio_end_seconds": 4.8,
                }
            ],
        }
        manifest_path = write_json(root / "edit_manifest.json", manifest)

        preview = root / "preview.mp4"
        preview.write_bytes(b"preview")
        result = {
            "artifact": "edit_preview_render_result",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_HUMAN_EDIT_PREVIEW_GATE",
            "preview_file": str(preview),
            "preview_sha256": handoff.sha256_file(preview),
            "provenance": {
                "edit_manifest": str(manifest_path),
                "edit_manifest_sha256": handoff.sha256_file(manifest_path),
            },
        }
        result_path = write_json(
            root / "results" / "c1.short.edit_preview_result.json",
            result,
        )
        approval_path = write_json(
            root / "approved" / "c1.short.approved_edit_preview.json",
            {
                "artifact": "approved_edit_preview",
                "status": "EDIT_DIRECTION_APPROVED",
                "concept_id": "c1",
                "format": "short",
                "placeholder_segments_at_approval": (
                    1 if missing_visual else 0
                ),
                "source_preview_result": str(result_path),
                "source_preview_result_sha256": handoff.sha256_file(
                    result_path
                ),
            },
        )
        sound_path = write_json(
            root / "sound" / "c1.short.sound_design_brief.json",
            {
                "artifact": "approved_sound_design_brief",
                "directions": [
                    {
                        "segment_id": "b1",
                        "music_direction": "rising tension",
                        "sfx_direction": ["impact"],
                    }
                ],
            },
        )
        return approval_path, sound_path

    def test_complete_current_media_reaches_final_sound_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval_path, _ = self.build_chain(root)

            with (
                patch.object(handoff, "EDIT_RESULT_DIR", root / "results"),
                patch.object(handoff, "SOUND_DIR", root / "sound"),
                patch.object(
                    handoff,
                    "GENERATED_VISUAL_REGISTRY",
                    root / "generated_registry",
                ),
            ):
                result = handoff.build_handoff(approval_path)

        self.assertEqual(
            result["status"],
            "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION",
        )
        self.assertEqual(
            result["blockers"],
            ["FINAL_MUSIC_SFX_ASSETS_NOT_CONNECTED"],
        )
        self.assertEqual(len(result["visual_track"]), 1)
        self.assertEqual(len(result["narration_track"]), 1)
        self.assertFalse(
            result["provider_handoff"]["provider_call_authorized"]
        )
        self.assertFalse(
            result["provider_handoff"]["paid_execution_performed"]
        )

    def test_missing_final_visual_keeps_handoff_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval_path, _ = self.build_chain(
                root,
                missing_visual=True,
            )

            with (
                patch.object(handoff, "EDIT_RESULT_DIR", root / "results"),
                patch.object(handoff, "SOUND_DIR", root / "sound"),
                patch.object(
                    handoff,
                    "GENERATED_VISUAL_REGISTRY",
                    root / "generated_registry",
                ),
            ):
                result = handoff.build_handoff(approval_path)

        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(
            any(
                blocker.endswith("FINAL_VISUAL_ASSET_MISSING")
                for blocker in result["blockers"]
            )
        )

    def test_changed_preview_result_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval_path, _ = self.build_chain(root)
            approval = json.loads(
                approval_path.read_text(encoding="utf-8")
            )
            result_path = Path(approval["source_preview_result"])
            result_path.write_text(
                json.dumps({"changed": True}),
                encoding="utf-8",
            )

            with patch.object(
                handoff,
                "EDIT_RESULT_DIR",
                root / "results",
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_EDIT_DIRECTION_APPROVAL",
                ):
                    handoff.build_handoff(approval_path)


if __name__ == "__main__":
    unittest.main()
