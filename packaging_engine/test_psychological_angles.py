from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import psychological_angles as module


class PsychologicalAnglesTests(unittest.TestCase):
    def request(self):
        return {
            "video_id": "c1:short",
            "concept_id": "c1",
            "format": "short",
            "search_vs_browse_intent": "BROWSE",
            "angle_count": 5,
            "allowed_primary_drivers": [
                "curiosity_gap",
                "danger",
                "consequence",
                "surprise",
                "contradiction",
                "specificity",
            ],
            "approved_numbers": [
                {"value": "500", "claim_id": "clm001"}
            ],
            "approved_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Brake temperature can exceed 500 C.",
                },
                {
                    "claim_id": "clm002",
                    "statement": "Cold braking behavior differs from the hot operating window.",
                },
            ],
            "allowed_evidence_refs": ["clm001", "clm002"],
        }

    def response(self):
        drivers = [
            "curiosity_gap",
            "danger",
            "consequence",
            "surprise",
            "contradiction",
        ]
        values = []
        for index, driver in enumerate(drivers):
            values.append(
                {
                    "angle_id": f"angle-{driver}",
                    "primary_driver": driver,
                    "secondary_driver": "specificity",
                    "viewer_question": f"What does angle {index} reveal about the brake?",
                    "emotional_trigger": f"Tension from mechanism {index}.",
                    "stakes": f"The viewer needs to understand consequence {index}.",
                    "information_given": "Temperature changes braking behavior.",
                    "information_withheld": f"Why the design accepts tradeoff {index}.",
                    "expected_click_reason": f"Resolve a different question {index}.",
                    "evidence_refs": ["clm001"],
                    "selected_title_direction_alignment": (
                        "ANCHOR" if index == 0 else "ALTERNATIVE"
                    ),
                }
            )
        return {"video_id": "c1:short", "angles": values}

    def test_requires_five_distinct_primary_drivers_and_one_anchor(self):
        result = module.validate_response(self.response(), self.request())
        self.assertEqual(result["artifact"], "psychological_packaging_angle_set")
        self.assertEqual(len(result["angles"]), 5)
        self.assertEqual(
            len({x["primary_driver"] for x in result["angles"]}),
            5,
        )
        self.assertEqual(
            sum(
                x["selected_title_direction_alignment"] == "ANCHOR"
                for x in result["angles"]
            ),
            1,
        )

    def test_duplicate_primary_driver_is_rejected(self):
        response = self.response()
        response["angles"][1]["primary_driver"] = "curiosity_gap"
        response["angles"][1]["angle_id"] = "angle-curiosity_gap"
        with self.assertRaisesRegex(ValueError, "Duplicate angle"):
            module.validate_response(response, self.request())

    def test_duplicate_viewer_question_is_rejected(self):
        response = self.response()
        response["angles"][1]["viewer_question"] = response["angles"][0][
            "viewer_question"
        ]
        with self.assertRaisesRegex(ValueError, "repeat the same viewer question"):
            module.validate_response(response, self.request())

    def test_invented_evidence_ref_is_rejected(self):
        response = self.response()
        response["angles"][0]["evidence_refs"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "invents evidence_refs"):
            module.validate_response(response, self.request())

    def test_unsupported_number_is_rejected(self):
        response = self.response()
        response["angles"][0]["stakes"] = "At 900 C the brake fails."
        with self.assertRaisesRegex(ValueError, "unsupported number"):
            module.validate_response(response, self.request())

    def test_supported_number_is_allowed(self):
        response = self.response()
        response["angles"][0]["information_given"] = (
            "Approved evidence says temperature can exceed 500 C."
        )
        result = module.validate_response(response, self.request())
        self.assertEqual(len(result["angles"]), 5)

    def test_unsupported_high_risk_claim_word_is_rejected(self):
        response = self.response()
        response["angles"][0]["expected_click_reason"] = (
            "Discover why these are the best brakes."
        )
        with self.assertRaisesRegex(ValueError, "high-risk claim word"):
            module.validate_response(response, self.request())

    def test_build_request_preserves_search_browse_strategy_and_selected_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c1.short.packaging_brief.json"
            path.write_text("{}", encoding="utf-8")
            brief = {
                "status": "PACKAGING_BRIEF_READY",
                "video_id": "c1:short",
                "concept_id": "c1",
                "format": "short",
                "search_vs_browse_intent": "BROWSE",
                "selected_title": {
                    "title_id": "short-curiosity",
                    "title_text": "Why Cold Race Brakes Feel Wrong",
                    "psychological_angle": "curiosity",
                    "primary_driver": "curiosity_gap",
                    "secondary_driver": "specificity",
                    "core_claim": "Temperature changes braking behavior.",
                    "evidence_refs": ["clm001"],
                },
                "viewer_promise_contract": {
                    "viewer_expectation": "Expected.",
                    "promise_subject": "Brakes",
                    "promise_question": "Why?",
                    "promise_stakes": "Grip matters.",
                    "promise_payoff": "Explain heat.",
                },
                "opening_hook": "Cold race brakes can feel worse.",
                "central_question": "Why do racing brakes need heat?",
                "video_payoff": "Explain the thermal tradeoff.",
                "strongest_visual_event": "Glowing brake disc.",
                "strongest_fact": {
                    "claim_id": "clm001",
                    "statement": "Brake temperature can exceed 500 C.",
                },
                "strongest_consequence": "Cold grip changes braking margin.",
                "strongest_transformation": "Understand the heat tradeoff.",
                "approved_numbers": [{"value": "500", "claim_id": "clm001"}],
                "approved_claims": [
                    {
                        "claim_id": "clm001",
                        "statement": "Brake temperature can exceed 500 C.",
                        "role": "core",
                    }
                ],
                "prohibited_or_unsupported_claims": [],
            }
            with patch.object(module, "brief_is_current", return_value=brief):
                request = module.build_request(path, brief)

        self.assertEqual(request["format_strategy"]["intent"], "BROWSE")
        self.assertIn("attention", request["format_strategy"]["priorities"])
        self.assertEqual(
            request["selected_title_direction"]["title_id"],
            "short-curiosity",
        )
        self.assertEqual(request["angle_count"], 5)


if __name__ == "__main__":
    unittest.main()
