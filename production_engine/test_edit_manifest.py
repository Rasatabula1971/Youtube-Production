from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import edit_manifest as module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class EditManifestTests(unittest.TestCase):
    def test_build_manifest_uses_qc_audio_and_allows_visual_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "seg.wav"
            audio.write_bytes(b"audio")
            assembly_path = write_json(root / "assembly.json", {"v": 1})
            qc_path = write_json(root / "qc.json", {"v": 1})
            timing_path = write_json(root / "timing.json", {"v": 1})
            sound_path = write_json(
                root / "sound.json",
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

            assembly = {
                "concept_id": "c1",
                "format": "short",
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
                        "visual_status": "PREMIUM_GENERATION_PENDING",
                        "cinematic_direction": {},
                    }
                ],
            }
            qc = {
                "concept_id": "c1",
                "format": "short",
                "status": "PASS",
                "checks": [
                    {
                        "segment_id": "b1",
                        "status": "PASS",
                        "audio_file": str(audio),
                    }
                ],
            }
            timing = {
                "concept_id": "c1",
                "format": "short",
                "status": "READY_FOR_ROUGH_CUT",
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

            manifest = module.build_manifest(
                assembly_path=assembly_path,
                assembly=assembly,
                qc_path=qc_path,
                qc=qc,
                timing_path=timing_path,
                timing=timing,
                sound_path=sound_path,
            )

        self.assertEqual(
            manifest["status"],
            "READY_FOR_LOCAL_PREVIEW_RENDER",
        )
        self.assertEqual(manifest["video_profile"]["aspect_ratio"], "9:16")
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
        self.assertFalse(manifest["preview_policy"]["publish_ready"])

    def test_qc_failure_blocks_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assembly_path = write_json(root / "assembly.json", {"v": 1})
            qc_path = write_json(root / "qc.json", {"v": 1})
            timing_path = write_json(root / "timing.json", {"v": 1})
            with self.assertRaisesRegex(
                ValueError,
                "Audio QC must PASS",
            ):
                module.build_manifest(
                    assembly_path=assembly_path,
                    assembly={
                        "concept_id": "c1",
                        "format": "short",
                        "timeline": [{
                            "shot_id": "s1",
                            "time_range": {
                                "start_seconds": 0,
                                "end_seconds": 1,
                            },
                        }],
                    },
                    qc_path=qc_path,
                    qc={
                        "concept_id": "c1",
                        "format": "short",
                        "status": "FAIL",
                    },
                    timing_path=timing_path,
                    timing={
                        "concept_id": "c1",
                        "format": "short",
                        "status": "READY_FOR_ROUGH_CUT",
                    },
                    sound_path=root / "missing.json",
                )


if __name__ == "__main__":
    unittest.main()
