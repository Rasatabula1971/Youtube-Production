from __future__ import annotations

import unittest

import psychological_angle_model_runner as angle_runner
import thumbnail_concept_model_runner as thumb_runner


class Slice25ModelRunnerTests(unittest.TestCase):
    def angle_request(self):
        return {
            "video_id": "c1:short",
            "angle_count": 5,
            "allowed_primary_drivers": [
                "curiosity_gap", "danger", "consequence", "surprise", "contradiction"
            ],
            "allowed_evidence_refs": ["clm001"],
            "selected_title_direction": {
                "title_text": "Why Cold Race Brakes Feel Wrong",
            },
            "format_strategy": {"intent": "BROWSE"},
        }

    def thumbnail_request(self):
        return {
            "video_id": "c1:short",
            "allowed_evidence_refs": ["clm001"],
            "angles": [
                {"angle_id": f"angle-{x}"}
                for x in (
                    "curiosity_gap", "danger", "consequence", "surprise", "contradiction"
                )
            ],
        }

    def test_angle_schema_requires_exactly_five(self):
        schema = angle_runner.response_schema(self.angle_request())
        angles = schema["properties"]["angles"]
        self.assertEqual(angles["minItems"], 5)
        self.assertEqual(angles["maxItems"], 5)

    def test_angle_prompt_requires_diversity_and_no_performance_prediction(self):
        prompt = angle_runner.build_prompt(self.angle_request(), 100000)
        self.assertIn("five DIFFERENT primary_driver", prompt)
        self.assertIn("Exactly one hypothesis is ANCHOR", prompt)
        self.assertIn("Do not predict CTR", prompt)

    def test_thumbnail_schema_requires_one_per_angle_and_mobile_constraints(self):
        schema = thumb_runner.response_schema(self.thumbnail_request())
        concepts = schema["properties"]["thumbnail_concepts"]
        self.assertEqual(concepts["minItems"], 5)
        self.assertEqual(concepts["maxItems"], 5)
        item = concepts["items"]["properties"]
        self.assertEqual(item["aspect_ratio"]["const"], "16:9")
        self.assertEqual(item["primary_focal_points"]["const"], 1)
        self.assertTrue(item["timestamp_safe"]["const"])
        self.assertFalse(item["critical_bottom_right_content"]["const"])

    def test_thumbnail_prompt_says_concepts_only_and_no_ctr_prediction(self):
        prompt = thumb_runner.build_prompt(self.thumbnail_request(), 100000)
        self.assertIn("Do not generate images", prompt)
        self.assertIn("one visual proposition", prompt)
        self.assertIn("Do not predict CTR", prompt)


if __name__ == "__main__":
    unittest.main()
