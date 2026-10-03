from __future__ import annotations

import unittest

import title_direction_model_runner as runner


class TitleDirectionModelRunnerTests(unittest.TestCase):
    def request(self):
        return {
            "concept_id": "c1",
            "psychological_angles": [
                "curiosity",
                "stakes",
                "unexpected",
                "mystery",
                "payoff",
            ],
            "allowed_evidence_refs": ["clm001"],
            "title_role": "PREFERRED_DIRECTION_NOT_FINAL_WORDING",
            "approved_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Temperature changes braking behavior.",
                }
            ],
            "story_context": {
                "branches": [
                    {
                        "format": "short",
                        "opening_hook": "Cold race brakes can feel worse.",
                    }
                ]
            },
        }

    def test_schema_requires_exact_five_candidates_per_format(self):
        schema = runner.response_schema(self.request())
        titles = schema["properties"]["titles"]["properties"]
        for fmt in ("short", "long_form"):
            self.assertEqual(titles[fmt]["minItems"], 5)
            self.assertEqual(titles[fmt]["maxItems"], 5)

    def test_prompt_states_post_script_truth_boundary_and_no_viral_score(self):
        prompt = runner.build_prompt(self.request(), 100000)
        self.assertIn("POST-SCRIPT", prompt)
        self.assertIn("approved script is the truth boundary", prompt)
        self.assertIn("Do not produce a viral score", prompt)
        self.assertIn("not permanently locked final wording", prompt)


if __name__ == "__main__":
    unittest.main()
