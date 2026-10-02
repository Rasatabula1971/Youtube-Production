from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
                        "drama_level": 7,
                        "tempo_level": 6,
                        "claim_ids": ["c1"],
                        "source_section_ids": ["lf1"],
                    },
                    {
                        "beat_id": "b2",
                        "purpose": "reveal",
                        "treatment": "Reveal the cause",
                        "drama_level": 8,
                        "tempo_level": 4,
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
                        "drama_level": 7,
                        "tempo_level": 8,
                        "claim_ids": ["c1"],
                        "source_section_ids": ["sh1"],
                    },
                    {
                        "beat_id": "s2",
                        "purpose": "reveal",
                        "treatment": "Fast reveal",
                        "drama_level": 8,
                        "tempo_level": 7,
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
        self.assertEqual(long_request["beats"][0]["drama_level"], 7)
        self.assertEqual(long_request["beats"][0]["tempo_level"], 6)
        self.assertEqual(long_request["beats"][1]["drama_level"], 8)
        self.assertEqual(long_request["beats"][1]["tempo_level"], 4)

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


    def test_changed_format_handoff_prunes_stale_voice_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved = root / "approved"
            requests = root / "requests"
            responses = root / "responses"
            specs = root / "specs"
            model_runs = root / "model_runs"
            raw = root / "raw"
            review_requests = root / "review_requests"
            review_responses = root / "review_responses"
            approved_voice = root / "approved_voice"
            for directory in (
                approved,
                requests,
                responses,
                specs,
                model_runs,
                raw,
                review_requests,
                review_responses,
                approved_voice,
            ):
                directory.mkdir()

            plan_path = approved / "concept-1.approved_format_plan.json"
            plan_path.write_text(json.dumps(approved_plan()), encoding="utf-8")
            old_request = requests / "concept-1.long_form.voice_request.json"
            old_request.write_text(json.dumps({"old": True}), encoding="utf-8")

            stale = [
                responses / "concept-1.long_form.json",
                specs / "concept-1.long_form.voice_performance_spec.json",
                model_runs / "concept-1.long_form.model_run.json",
                raw / "concept-1.long_form.txt",
                review_requests / "concept-1.long_form.voice_review_request.json",
                review_responses / "concept-1.long_form.voice_review_response.json",
                approved_voice / "concept-1.long_form.approved_voice_spec.json",
            ]
            for path in stale:
                path.write_text("old", encoding="utf-8")

            model_summary = root / "voice_performance_model_batch_summary.json"
            gate_summary = root / "voice_performance_gate_summary.json"
            model_summary.write_text("old", encoding="utf-8")
            gate_summary.write_text("old", encoding="utf-8")

            with (
                patch.object(voice_performance, "REQUESTS_DIR", requests),
                patch.object(voice_performance, "RESPONSES_DIR", responses),
                patch.object(voice_performance, "SPECS_DIR", specs),
                patch.object(voice_performance, "MODEL_RUNS_DIR", model_runs),
                patch.object(voice_performance, "RAW_OUTPUTS_DIR", raw),
                patch.object(voice_performance, "REVIEW_REQUESTS_DIR", review_requests),
                patch.object(voice_performance, "REVIEW_RESPONSES_DIR", review_responses),
                patch.object(voice_performance, "APPROVED_VOICE_SPECS_DIR", approved_voice),
                patch.object(voice_performance, "MODEL_BATCH_SUMMARY_FILE", model_summary),
                patch.object(voice_performance, "VOICE_GATE_SUMMARY_FILE", gate_summary),
                patch.object(voice_performance, "OUTPUT_DIR", root),
                patch.object(voice_performance, "SUMMARY_FILE", root / "summary.json"),
            ):
                result = voice_performance.run_prepare(approved, config())

            self.assertIn(
                "concept-1.long_form",
                result["stale_cleanup"]["changed_requests"][
                    "invalidated_voice_keys"
                ],
            )
            self.assertTrue(all(not path.exists() for path in stale))
            self.assertFalse(model_summary.exists())
            self.assertFalse(gate_summary.exists())
            self.assertTrue(
                (requests / "concept-1.long_form.voice_request.json").exists()
            )
            self.assertTrue(
                (requests / "concept-1.short.voice_request.json").exists()
            )

    def test_voice_request_uses_format_specific_selected_title(self) -> None:
        plan = approved_plan()
        plan["package"]["selected_titles"] = {
            "long_form": {
                "candidate_id": "long-curiosity",
                "title": "The Locked Title",
            },
            "short": {
                "candidate_id": "short-stakes",
                "title": "The Fast Locked Title",
            },
        }
        plan["branch_story_packages"]["short"]["title"] = "The Fast Locked Title"
        branch = next(
            item for item in plan["branches"] if item["format"] == "short"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "concept.approved_format_plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            request = voice_performance.build_request(
                plan,
                path,
                branch,
                config(),
            )

        self.assertEqual(request["title"], "The Fast Locked Title")



if __name__ == "__main__":
    unittest.main()
