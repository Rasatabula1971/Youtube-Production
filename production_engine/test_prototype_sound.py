from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prototype_sound
import sound_design_brief


class PrototypeSoundBoundaryTests(unittest.TestCase):
    def test_reference_plan_is_explicitly_non_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "preview.json"
            source.write_text("{}", encoding="utf-8")
            plan = prototype_sound.build_plan({
                "concept_id": "c1",
                "format": "shorts",
                "segments": [{
                    "segment_id": "b1",
                    "sound_design": {
                        "music_mood": "opening_tension",
                        "sfx_suggestions": ["subtle_impact"],
                        "duck_under_narration": True,
                    },
                }],
            }, source)
        self.assertTrue(plan["reference_only"])
        self.assertFalse(plan["commercial_final_use_allowed"])
        self.assertFalse(plan["final_export_allowed"])

    def test_final_brief_contains_instructions_not_reference_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            approval_path = Path(tmp) / "approval.json"
            approval_path.write_text("{}", encoding="utf-8")
            brief = sound_design_brief.build_brief(
                {"decision": "APPROVE_FINAL"},
                {
                    "concept_id": "c1",
                    "format": "shorts",
                    "segments": [{
                        "segment_id": "b1",
                        "delivery": {"pause_before_ms": 0, "pause_after_ms": 250},
                        "sound_design": {
                            "music_mood": "payoff_lift",
                            "sfx_suggestions": ["reveal_accent"],
                            "duck_under_narration": True,
                        },
                    }],
                },
                approval_path,
            )
        policy = brief["provider_handoff_policy"]
        self.assertTrue(policy["descriptive_instructions_only"])
        self.assertFalse(policy["prototype_audio_attached"])
        self.assertFalse(policy["audiogen_output_attached"])
        self.assertFalse(policy["musicgen_output_attached"])


    def test_sound_brief_becomes_stale_when_preview_approval_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approvals = root / "approvals"
            manifests = root / "manifests"
            briefs = root / "briefs"
            approvals.mkdir()
            manifests.mkdir()
            briefs.mkdir()

            approval_path = approvals / "c1.shorts.approved_preview.json"
            manifest_path = manifests / "c1.shorts.narration_preview.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "format": "shorts",
                        "segments": [],
                        "provenance": {
                            "approved_voice_spec_sha256": "voice-sha",
                        },
                    }
                ),
                encoding="utf-8",
            )
            approval = {
                "decision": "APPROVE_FINAL",
                "concept_id": "c1",
                "format": "shorts",
                "preview_manifest_sha256": sound_design_brief.sha256_file(
                    manifest_path
                ),
                "preview_audio_sha256": "audio-sha",
                "approved_voice_spec_sha256": "voice-sha",
            }
            approval_path.write_text(json.dumps(approval), encoding="utf-8")

            with (
                patch.object(sound_design_brief, "APPROVED_DIR", approvals),
                patch.object(sound_design_brief, "PREVIEW_DIR", manifests),
                patch.object(sound_design_brief, "BRIEF_DIR", briefs),
                patch.object(
                    sound_design_brief,
                    "current_preview_render",
                    return_value={"audio_sha256": "audio-sha"},
                ),
            ):
                prepared = sound_design_brief.prepare()
                current = sound_design_brief.snapshot()
                approval["preview_audio_sha256"] = "changed-audio"
                approval_path.write_text(
                    json.dumps(approval),
                    encoding="utf-8",
                )
                stale = sound_design_brief.snapshot()

            self.assertEqual(
                prepared["status"],
                "READY_FOR_FINAL_PROVIDER_HANDOFF",
            )
            self.assertEqual(
                current["status"],
                "READY_FOR_FINAL_PROVIDER_HANDOFF",
            )
            self.assertNotEqual(
                stale["status"],
                "READY_FOR_FINAL_PROVIDER_HANDOFF",
            )

if __name__ == "__main__":
    unittest.main()
