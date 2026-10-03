from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pre_render_engagement
from pre_render_engagement import validate_spec


def spec(fmt: str = "long_form") -> dict:
    return {
        "concept_id": "c1",
        "format": fmt,
        "duration_intent_seconds": 45 if "short" in fmt else 480,
        "performance_gate": {"status": "PERFORMANCE_SPEC_APPROVED"},
        "script_psychology_profile": {
            "first_spoken_hook_target_seconds": 3,
            "meaningful_reward_refresh_hypothesis_seconds": "4-6",
        },
        "beats": [
            {"beat_id": "b1", "purpose": "opening hook tension", "immutable_narration": "Something here should not be possible."},
            {"beat_id": "b2", "purpose": "problem stakes", "immutable_narration": "The obvious explanation creates a second problem."},
            {"beat_id": "b3", "purpose": "progressive proof", "immutable_narration": "The evidence changes what the viewer expects."},
            {"beat_id": "b4", "purpose": "solution reveal payoff", "immutable_narration": "Here is the answer and why it works."},
        ],
        "directions": [
            {"emotion": "curious", "intensity": .4, "speed": 1.08, "pause_before_ms": 0, "pause_after_ms": 120},
            {"emotion": "concerned", "intensity": .6, "speed": 1.0, "pause_before_ms": 80, "pause_after_ms": 180},
            {"emotion": "focused", "intensity": .5, "speed": .96, "pause_before_ms": 100, "pause_after_ms": 220},
            {"emotion": "satisfied", "intensity": .7, "speed": .92, "pause_before_ms": 160, "pause_after_ms": 300},
        ],
    }


class PreRenderEngagementTests(unittest.TestCase):
    def test_hook_problem_payoff_and_delivery_variation_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text("{}", encoding="utf-8")
            result = validate_spec(spec(), source)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["policy"]["predicts_retention"])
        self.assertFalse(result["policy"]["claims_dopamine_measurement"])

    def test_snapshot_rejects_pass_for_changed_approved_voice_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved = root / "approved"
            results = root / "results"
            approved.mkdir()
            results.mkdir()
            source = approved / "c1.long_form.approved_voice_spec.json"
            source.write_text(json.dumps(spec()), encoding="utf-8")
            result = validate_spec(spec(), source)
            result_path = results / f"{source.stem}.engagement.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with (
                patch.object(pre_render_engagement, "APPROVED_DIR", approved),
                patch.object(pre_render_engagement, "RESULTS_DIR", results),
            ):
                current = pre_render_engagement.snapshot()
                changed = spec()
                changed["title"] = "Changed after old engagement pass"
                source.write_text(json.dumps(changed), encoding="utf-8")
                stale = pre_render_engagement.snapshot()

            self.assertEqual(current["status"], "PASS")
            self.assertTrue(current["current"])
            self.assertEqual(stale["status"], "STALE_ENGAGEMENT_VALIDATION")
            self.assertFalse(stale["current"])
            self.assertEqual(stale["stale"], 1)

    def test_flat_lecture_delivery_is_blocked(self) -> None:
        payload = spec()
        for item in payload["directions"]:
            item.update({"emotion": "neutral", "intensity": .4, "speed": 1.0})
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text("{}", encoding="utf-8")
            result = validate_spec(payload, source)
        self.assertIn("DELIVERY_CURVE_IS_FLAT", result["errors"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_missing_payoff_is_blocked(self) -> None:
        payload = spec()
        payload["beats"][-1]["purpose"] = "more explanation"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text("{}", encoding="utf-8")
            result = validate_spec(payload, source)
        self.assertIn("NO_EXPLICIT_PAYOFF_OR_RESOLUTION_BEAT", result["errors"])

    def test_shorts_exposition_limit_is_stricter(self) -> None:
        payload = spec("shorts")
        payload["beats"][1]["immutable_narration"] = "word " * 60
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text("{}", encoding="utf-8")
            result = validate_spec(payload, source)
        self.assertIn("EXPOSITION_BEAT_TOO_LONG_WITHOUT_STRUCTURAL_RESET", result["errors"])


if __name__ == "__main__":
    unittest.main()
