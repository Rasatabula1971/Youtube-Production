from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_sound_plan as sound_plan


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalSoundPlanTests(unittest.TestCase):
    def handoff_payload(self) -> dict:
        return {
            "artifact": "final_production_handoff",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION",
            "sound_design_intent": [
                {
                    "segment_id": "seg1",
                    "music_direction": "rising tension",
                    "sfx_direction": ["impact", "whoosh"],
                    "duck_under_narration": True,
                }
            ],
        }

    def test_current_handoff_builds_stable_sound_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = self.handoff_payload()
            handoff_path = write_json(
                root / "handoffs" / "c1.short.final_production_handoff.json",
                handoff,
            )
            with (
                patch.object(sound_plan, "HANDOFF_DIR", root / "handoffs"),
                patch.object(
                    sound_plan,
                    "handoff_is_current",
                    return_value=handoff,
                ),
            ):
                plan = sound_plan.build_plan(handoff_path, handoff)

        self.assertEqual(plan["status"], "WAITING_FOR_FINAL_SOUND_ASSETS")
        self.assertEqual(plan["requirements_count"], 3)
        self.assertEqual(
            [item["requirement_id"] for item in plan["requirements"]],
            ["seg1:music", "seg1:sfx:001", "seg1:sfx:002"],
        )
        self.assertTrue(
            all(item.get("fingerprint") for item in plan["requirements"])
        )
        self.assertFalse(
            plan["execution_policy"]["app_provider_call_authorized"]
        )
        self.assertFalse(plan["execution_policy"]["final_render_allowed"])

    def test_plan_with_no_sound_direction_is_immediately_resolvable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = self.handoff_payload()
            handoff["sound_design_intent"] = []
            handoff_path = write_json(
                root / "handoffs" / "c1.short.final_production_handoff.json",
                handoff,
            )
            with (
                patch.object(sound_plan, "HANDOFF_DIR", root / "handoffs"),
                patch.object(
                    sound_plan,
                    "handoff_is_current",
                    return_value=handoff,
                ),
            ):
                plan = sound_plan.build_plan(handoff_path, handoff)

        self.assertEqual(plan["status"], "FINAL_SOUND_NOT_REQUIRED")
        self.assertEqual(plan["requirements"], [])

    def test_stale_handoff_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = self.handoff_payload()
            handoff_path = write_json(
                root / "handoffs" / "c1.short.final_production_handoff.json",
                handoff,
            )
            with (
                patch.object(sound_plan, "HANDOFF_DIR", root / "handoffs"),
                patch.object(
                    sound_plan,
                    "handoff_is_current",
                    return_value=None,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_FINAL_PRODUCTION_HANDOFF",
                ):
                    sound_plan.build_plan(handoff_path, handoff)

    def test_plan_currentness_fails_after_handoff_bytes_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff_dir = root / "handoffs"
            plan_dir = root / "plans"
            handoff = self.handoff_payload()
            handoff_path = write_json(
                handoff_dir / "c1.short.final_production_handoff.json",
                handoff,
            )

            with (
                patch.object(sound_plan, "HANDOFF_DIR", handoff_dir),
                patch.object(sound_plan, "PLAN_DIR", plan_dir),
                patch.object(
                    sound_plan,
                    "handoff_is_current",
                    return_value=handoff,
                ),
            ):
                plan = sound_plan.build_plan(handoff_path, handoff)
                plan_path = write_json(
                    plan_dir / "c1.short.final_sound_plan.json",
                    plan,
                )
                self.assertIsNotNone(sound_plan.plan_is_current(plan_path))
                handoff_path.write_text(
                    json.dumps({**handoff, "changed": True}),
                    encoding="utf-8",
                )
                self.assertIsNone(sound_plan.plan_is_current(plan_path))


if __name__ == "__main__":
    unittest.main()
