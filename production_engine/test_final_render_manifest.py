from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_render_manifest as render_manifest


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalRenderManifestTests(unittest.TestCase):
    def fixture(self, root: Path):
        handoff_dir = root / "handoffs"
        plan_dir = root / "plans"
        registry_dir = root / "registry"
        visual = root / "visual.mp4"
        narration = root / "narration.wav"
        music = root / "music.wav"
        visual.write_bytes(b"visual")
        narration.write_bytes(b"narration")
        music.write_bytes(b"music")

        handoff = {
            "artifact": "final_production_handoff",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION",
            "video_profile": {
                "width": 1080,
                "height": 1920,
                "fps": 30,
            },
            "duration": {"preview_seconds": 4.0},
            "visual_track": [{
                "scene_index": 0,
                "shot_id": "s1",
                "start_seconds": 0.0,
                "end_seconds": 4.0,
                "duration_seconds": 4.0,
                "asset_file": str(visual),
                "asset_sha256": render_manifest.sha256_file(visual),
            }],
            "narration_track": [{
                "segment_id": "seg1",
                "audio_file": str(narration),
                "audio_sha256": render_manifest.sha256_file(narration),
                "audio_start_seconds": 0.5,
                "audio_end_seconds": 3.0,
                "timeline_end_seconds": 3.5,
            }],
        }
        handoff_path = write_json(
            handoff_dir / "c1.short.final_production_handoff.json",
            handoff,
        )
        requirement = {
            "requirement_id": "seg1:music",
            "segment_id": "seg1",
            "kind": "MUSIC",
            "index": 0,
            "direction": "tense",
            "duck_under_narration": True,
            "fingerprint": "fp1",
        }
        plan = {
            "artifact": "final_sound_plan",
            "concept_id": "c1",
            "format": "short",
            "status": "WAITING_FOR_FINAL_SOUND_ASSETS",
            "requirements": [requirement],
            "requirements_count": 1,
            "provenance": {
                "final_production_handoff": str(handoff_path),
                "final_production_handoff_sha256": render_manifest.sha256_file(
                    handoff_path
                ),
            },
        }
        plan_path = write_json(
            plan_dir / "c1.short.final_sound_plan.json",
            plan,
        )
        resolution = {
            "artifact": "final_sound_resolution",
            "status": "REGISTERED_CURRENT",
            "concept_id": "c1",
            "format": "short",
            "requirement_id": "seg1:music",
            "requirement_fingerprint": "fp1",
            "asset_file": str(music),
            "asset_sha256": render_manifest.sha256_file(music),
            "rights": {
                "commercial_use_confirmed": True,
                "licence_reference": "lic-1",
            },
            "cost": {"actual_cost_usd": 0},
        }
        resolution_path = write_json(
            registry_dir / "c1.short.seg1-music.final_sound_resolution.json",
            resolution,
        )
        return {
            "handoff_dir": handoff_dir,
            "plan_dir": plan_dir,
            "registry_dir": registry_dir,
            "handoff": handoff,
            "handoff_path": handoff_path,
            "plan": plan,
            "plan_path": plan_path,
            "resolution": resolution,
            "resolution_path": resolution_path,
            "music": music,
        }

    def test_current_inputs_build_final_render_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            with (
                patch.object(render_manifest, "HANDOFF_DIR", fx["handoff_dir"]),
                patch.object(render_manifest, "PLAN_DIR", fx["plan_dir"]),
                patch.object(render_manifest, "REGISTRY_DIR", fx["registry_dir"]),
                patch.object(
                    render_manifest,
                    "plan_is_current",
                    return_value=fx["plan"],
                ),
                patch.object(
                    render_manifest,
                    "handoff_is_current",
                    return_value=fx["handoff"],
                ),
                patch.object(
                    render_manifest,
                    "resolution_is_current",
                    return_value=fx["resolution"],
                ),
            ):
                manifest = render_manifest.build_manifest(
                    fx["plan_path"],
                    fx["plan"],
                )

        self.assertEqual(
            manifest["status"],
            "READY_FOR_LOCAL_FINAL_RENDER",
        )
        self.assertEqual(len(manifest["sound_track"]), 1)
        cue = manifest["sound_track"][0]
        self.assertEqual(cue["start_seconds"], 0.5)
        self.assertEqual(cue["end_seconds"], 3.5)
        self.assertTrue(cue["loop_to_fill"])
        self.assertEqual(
            cue["volume"],
            render_manifest.MUSIC_VOLUME_DUCKED,
        )
        self.assertFalse(
            manifest["render_policy"]["publish_allowed"]
        )

    def test_human_omission_crosses_manifest_without_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            omitted = {
                **fx["resolution"],
                "status": "OMITTED_BY_HUMAN",
                "asset_file": None,
                "asset_sha256": None,
                "note": "Narration only here.",
            }
            with (
                patch.object(render_manifest, "HANDOFF_DIR", fx["handoff_dir"]),
                patch.object(render_manifest, "PLAN_DIR", fx["plan_dir"]),
                patch.object(render_manifest, "REGISTRY_DIR", fx["registry_dir"]),
                patch.object(
                    render_manifest,
                    "plan_is_current",
                    return_value=fx["plan"],
                ),
                patch.object(
                    render_manifest,
                    "handoff_is_current",
                    return_value=fx["handoff"],
                ),
                patch.object(
                    render_manifest,
                    "resolution_is_current",
                    return_value=omitted,
                ),
            ):
                manifest = render_manifest.build_manifest(
                    fx["plan_path"],
                    fx["plan"],
                )

        self.assertEqual(manifest["sound_track"], [])
        self.assertEqual(
            manifest["omitted_sound_requirements"][0]["human_note"],
            "Narration only here.",
        )

    def test_missing_resolution_blocks_final_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            with (
                patch.object(render_manifest, "HANDOFF_DIR", fx["handoff_dir"]),
                patch.object(render_manifest, "PLAN_DIR", fx["plan_dir"]),
                patch.object(render_manifest, "REGISTRY_DIR", fx["registry_dir"]),
                patch.object(
                    render_manifest,
                    "plan_is_current",
                    return_value=fx["plan"],
                ),
                patch.object(
                    render_manifest,
                    "handoff_is_current",
                    return_value=fx["handoff"],
                ),
                patch.object(
                    render_manifest,
                    "resolution_is_current",
                    return_value=None,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "INCOMPLETE_OR_STALE",
                ):
                    render_manifest.build_manifest(
                        fx["plan_path"],
                        fx["plan"],
                    )

    def test_changed_sound_asset_invalidates_rebuilt_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx = self.fixture(root)
            manifest_dir = root / "render_manifests"
            with (
                patch.object(render_manifest, "HANDOFF_DIR", fx["handoff_dir"]),
                patch.object(render_manifest, "PLAN_DIR", fx["plan_dir"]),
                patch.object(render_manifest, "REGISTRY_DIR", fx["registry_dir"]),
                patch.object(render_manifest, "MANIFEST_DIR", manifest_dir),
                patch.object(
                    render_manifest,
                    "plan_is_current",
                    return_value=fx["plan"],
                ),
                patch.object(
                    render_manifest,
                    "handoff_is_current",
                    return_value=fx["handoff"],
                ),
                patch.object(
                    render_manifest,
                    "resolution_is_current",
                    return_value=fx["resolution"],
                ),
            ):
                manifest = render_manifest.build_manifest(
                    fx["plan_path"],
                    fx["plan"],
                )
                path = write_json(
                    manifest_dir / "c1.short.final_render_manifest.json",
                    manifest,
                )
                self.assertIsNotNone(
                    render_manifest.manifest_is_current(path)
                )
                fx["music"].write_bytes(b"changed")
                self.assertIsNone(
                    render_manifest.manifest_is_current(path)
                )


if __name__ == "__main__":
    unittest.main()
