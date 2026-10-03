from __future__ import annotations

import unittest

import package_pairing_model_runner as runner


class PackagePairingModelRunnerTests(unittest.TestCase):
    def request(self):
        diagnostics = [
            "scroll_stop",
            "clarity",
            "curiosity",
            "stakes",
            "specificity",
            "visual_simplicity",
            "title_strength",
            "complementarity",
            "credibility",
            "promise_alignment",
            "hook_alignment",
        ]
        pairs = [
            {
                "package_id": f"package-short-{index}--thumbnail-angle-curiosity",
                "title_id": f"short-{index}",
                "title_text": f"Title {index}",
                "title_core_claim": "Supported claim.",
                "title_evidence_refs": ["clm001"],
                "thumbnail_id": "thumbnail-angle-curiosity",
                "thumbnail_text": "NO GRIP",
                "thumbnail_evidence_refs": ["clm001"],
            }
            for index in range(5)
        ]
        return {
            "video_id": "c1:short",
            "thumbnail_id": "thumbnail-angle-curiosity",
            "approved_claims": [
                {"claim_id": "clm001", "statement": "Supported claim."}
            ],
            "hard_reject_codes": [
                "unsupported_material_claim",
                "factually_false_claim",
                "thumbnail_misrepresents_video",
                "title_misrepresents_video",
                "evidence_conflict",
                "prohibited_claim",
            ],
            "rework_codes": [
                "title_thumbnail_redundancy",
                "weak_hook_alignment",
                "promise_not_addressed_early",
                "thumbnail_too_complex",
                "thumbnail_text_too_long",
                "critical_content_in_timestamp_zone",
                "unclear_primary_subject",
                "selected_title_no_longer_matches_final_script",
            ],
            "diagnostic_dimensions": diagnostics,
            "pair_candidates": pairs,
        }

    def test_schema_requires_one_evaluation_per_pair(self):
        schema = runner.response_schema(self.request())
        evaluations = schema["properties"]["evaluations"]
        self.assertEqual(evaluations["minItems"], 5)
        self.assertEqual(evaluations["maxItems"], 5)
        diagnostics = evaluations["items"]["properties"]["diagnostics"]
        self.assertEqual(len(diagnostics["required"]), 11)

    def test_prompt_forbids_winner_and_viral_score(self):
        prompt = runner.build_prompt(self.request(), 100000)
        self.assertIn("Do not rank them", prompt)
        self.assertIn("do not select a winner", prompt)
        self.assertIn("Do not create new title wording", prompt)
        self.assertIn("not virality", prompt)
        self.assertIn("45-60 characters is not automatically bad", prompt)

    def test_schema_keeps_hard_and_rework_codes_separate(self):
        schema = runner.response_schema(self.request())
        item = schema["properties"]["evaluations"]["items"]["properties"]
        hard = item["hard_validation_findings"]["items"]["properties"]["code"]["enum"]
        rework = item["rework_findings"]["items"]["properties"]["code"]["enum"]
        self.assertIn("unsupported_material_claim", hard)
        self.assertNotIn("unsupported_material_claim", rework)
        self.assertIn("title_thumbnail_redundancy", rework)


if __name__ == "__main__":
    unittest.main()
