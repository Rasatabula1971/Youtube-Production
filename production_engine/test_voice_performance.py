from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import voice_performance


def approved_plan() -> dict:
    return {
        "concept_id": "concept-1",
        "format_gate": {"status": "READY_FOR_PRODUCTION_ENGINE"},
        "package": {"title": "The Locked Title"},
        "branch_story_packages": {
            "long_form": {
                "format": "long_form",
                "title": "The Locked Title",
                "opening_hook": "Long hook.",
                "sections": [
                    {
                        "section_id": "lf1",
                        "narration": "The first fact changes what we expect.",
                    },
                    {
                        "section_id": "lf2",
                        "narration": "Then the reveal explains why it happened.",
                    },
                ],
                "closing": "Long close.",
                "psychology_profile": {"reward_density": "MODERATE"},
            },
            "short": {
                "format": "short",
                "title": "The Locked Title",
                "opening_hook": "Short hook.",
                "sections": [
                    {
                        "section_id": "sh1",
                        "narration": "Short proof hits immediately.",
                    },
                    {
                        "section_id": "sh2",
                        "narration": "Short payoff lands fast.",
                    },
                ],
                "closing": "Short close.",
                "psychology_profile": {
                    "reward_density": "HIGH",
                    "hook_target_seconds": 3,
                },
            },
        },
        "branches": [
            {
                "format": "long_form",
                "duration_intent_seconds": 180,
                "promise_delivery": "Deliver the promise",
                "payoff": "Explain the reveal",
                "beats": [
                    {
                        "beat_id": "b1",
                        "purpose": "setup",
                        "treatment": "Build curiosity",
                        "claim_ids": ["c1"],
                        "source_section_ids": ["lf1"],
                    },
                    {
                        "beat_id": "b2",
                        "purpose": "reveal",
                        "treatment": "Reveal the cause",
                        "claim_ids": ["c2"],
                        "source_section_ids": ["lf2"],
                    },
                ],
            },
            {
                "format": "short",
                "duration_intent_seconds": 30,
                "promise_delivery": "Deliver the promise fast",
                "payoff": "Land the mechanism",
                "beats": [
                    {
                        "beat_id": "s1",
                        "purpose": "proof",
                        "treatment": "Immediate proof",
                        "claim_ids": ["c1"],
                        "source_section_ids": ["sh1"],
                    },
                    {
                        "beat_id": "s2",
                        "purpose": "reveal",
                        "treatment": "Fast reveal",
                        "claim_ids": ["c2"],
                        "source_section_ids": ["sh2"],
                    },
                ],
            },
        ],
    }


def config() -> dict:
    return {
        "provider": "higgsfield",
        "planning_policy": "FAIR_FREE_ONLY",
        "allowed_emotions": [
            "neutral",
            "curious",
            "serious",
            "concerned",
            "tense",
            "reflective",
            "surprised",
        ],
        "surprised_requires_reveal_beat": True,
        "max_intensity": 0.7,
        "max_adjacent_intensity_delta": 0.3,
        "speed_min": 0.9,
        "speed_max": 1.1,
        "pause_ms_max": 1200,
        "emphasis_terms_max": 4,
        "voice_identity": {
            "voice_id": None,
            "license_reference": None,
            "calibration_artifact": None,
        },
    }


class VoicePerformanceTests(unittest.TestCase):
    def build(self, fmt="long_form") -> dict:
        plan = approved_plan()
        branch = next(item for item in plan["branches"] if item["format"] == fmt)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "concept.approved_format_plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            return voice_performance.build_request(
                plan,
                path,
                branch,
                config(),
            )

    def valid_response(self) -> dict:
        return {
            "concept_id": "concept-1",
            "format": "long_form",
            "directions": [
                {
                    "beat_id": "b1",
                    "emotion": "curious",
                    "intensity": 0.3,
                    "speed": 1.0,
                    "pause_before_ms": 100,
                    "pause_after_ms": 250,
                    "emphasis_terms": ["first fact"],
                },
                {
                    "beat_id": "b2",
                    "emotion": "surprised",
                    "intensity": 0.5,
                    "speed": 0.98,
                    "pause_before_ms": 300,
                    "pause_after_ms": 400,
                    "emphasis_terms": ["reveal"],
                },
            ],
        }

    def test_request_carries_only_matching_branch_narration(self) -> None:
        long_request = self.build("long_form")
        short_request = self.build("short")
        self.assertEqual(long_request["title"], "The Locked Title")
        self.assertEqual(
            long_request["beats"][0]["immutable_narration"],
            "The first fact changes what we expect.",
        )
        self.assertEqual(
            short_request["beats"][0]["immutable_narration"],
            "Short proof hits immediately.",
        )
        self.assertEqual(short_request["opening_hook"], "Short hook.")
        self.assertEqual(
            short_request["script_psychology_profile"]["hook_target_seconds"],
            3,
        )
        self.assertFalse(long_request["render_prerequisites_configured"])

    def test_valid_response_passes(self) -> None:
        result = voice_performance.validate_response(
            self.valid_response(),
            self.build(),
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_surprised_is_reveal_only(self) -> None:
        response = self.valid_response()
        response["directions"][0]["emotion"] = "surprised"
        result = voice_performance.validate_response(response, self.build())
        self.assertFalse(result["valid"])
        self.assertTrue(any("reveal beat" in item for item in result["errors"]))

    def test_adjacent_intensity_jump_is_rejected(self) -> None:
        response = self.valid_response()
        response["directions"][0]["intensity"] = 0.1
        response["directions"][1]["intensity"] = 0.7
        result = voice_performance.validate_response(response, self.build())
        self.assertFalse(result["valid"])
        self.assertTrue(any("too sharply" in item for item in result["errors"]))

    def test_emphasis_must_exist_in_immutable_narration(self) -> None:
        response = self.valid_response()
        response["directions"][0]["emphasis_terms"] = ["words not present"]
        result = voice_performance.validate_response(response, self.build())
        self.assertFalse(result["valid"])
        self.assertTrue(any("not in immutable narration" in item for item in result["errors"]))

    def test_missing_matching_branch_context_fails_closed(self) -> None:
        plan = approved_plan()
        plan["branch_story_packages"].pop("long_form")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "long_form script context"):
                voice_performance.build_request(
                    plan,
                    path,
                    plan["branches"][0],
                    config(),
                )


if __name__ == "__main__":
    unittest.main()
