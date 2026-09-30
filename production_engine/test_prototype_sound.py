from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
