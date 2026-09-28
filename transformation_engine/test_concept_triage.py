import unittest

from concept_triage import (
    build_shortlist_payload,
    chunk_concepts,
    merge_full_audit,
    select_finalist_ids,
    validate_triage,
)


class ConceptTriageTests(unittest.TestCase):
    def candidates(self):
        return {
            "concepts": [
                {"concept_id": "c1", "working_title": "A"},
                {"concept_id": "c2", "working_title": "B"},
                {"concept_id": "c3", "working_title": "C"},
                {"concept_id": "c4", "working_title": "D"},
            ]
        }

    def response(self):
        dims = {
            "channel_fit": 5,
            "viewer_problem": 5,
            "promise_clarity": 5,
            "feasibility": 4,
            "researchability": 4,
            "originality": 4,
            "overclaim_safety": 4,
        }
        return {
            "decisions": [
                {
                    "concept_id": "c1",
                    "decision": "SHORTLIST",
                    "overall_score": 90,
                    "dimension_scores": dims,
                    "strengths": ["fit"],
                    "risks": [],
                    "rationale": "strong",
                },
                {
                    "concept_id": "c2",
                    "decision": "SHORTLIST",
                    "overall_score": 85,
                    "dimension_scores": dims,
                    "strengths": ["fit"],
                    "risks": [],
                    "rationale": "strong",
                },
                {
                    "concept_id": "c3",
                    "decision": "SHORTLIST",
                    "overall_score": 80,
                    "dimension_scores": dims,
                    "strengths": ["fit"],
                    "risks": [],
                    "rationale": "strong",
                },
                {
                    "concept_id": "c4",
                    "decision": "DROP",
                    "overall_score": 40,
                    "dimension_scores": dims,
                    "strengths": [],
                    "risks": ["off channel"],
                    "rationale": "weak",
                },
            ],
            "shortlist_ids": ["c1", "c2", "c3"],
            "summary": "three strongest",
        }

    def test_valid_triage_requires_all_candidates(self):
        result = validate_triage(self.response(), self.candidates()["concepts"])
        self.assertEqual(len(result["decisions"]), 4)
        self.assertEqual(result["shortlist_ids"], ["c1", "c2", "c3"])

    def test_shortlist_must_match_decisions(self):
        bad = self.response()
        bad["shortlist_ids"] = ["c1", "c2", "c4"]
        with self.assertRaises(ValueError):
            validate_triage(bad, self.candidates()["concepts"])

    def test_shortlist_payload_preserves_llm_reason(self):
        triage = validate_triage(self.response(), self.candidates()["concepts"])
        payload = build_shortlist_payload(self.candidates(), triage, "abc")
        self.assertEqual(payload["concept_count"], 3)
        self.assertEqual(payload["concepts"][0]["llm_triage"]["decision"], "SHORTLIST")

    def test_zero_shortlist_is_allowed_when_all_concepts_are_weak(self):
        dims = {
            key: 1
            for key in (
                "channel_fit",
                "viewer_problem",
                "promise_clarity",
                "feasibility",
                "researchability",
                "originality",
                "overclaim_safety",
            )
        }
        response = {
            "decisions": [
                {
                    "concept_id": item["concept_id"],
                    "decision": "DROP",
                    "overall_score": 30,
                    "dimension_scores": dims,
                    "strengths": [],
                    "risks": ["weak"],
                    "rationale": "weak",
                }
                for item in self.candidates()["concepts"]
            ],
            "shortlist_ids": [],
            "summary": "none strong enough",
        }
        result = validate_triage(response, self.candidates()["concepts"])
        self.assertEqual(result["shortlist_ids"], [])

    def test_decision_must_match_score_threshold(self):
        bad = self.response()
        bad["decisions"][0]["overall_score"] = 40
        with self.assertRaisesRegex(ValueError, "decision/score mismatch"):
            validate_triage(bad, self.candidates()["concepts"])

    def test_non_shortlisted_concepts_remain_available_for_override(self):
        triage = validate_triage(self.response(), self.candidates()["concepts"])
        payload = build_shortlist_payload(self.candidates(), triage, "abc")
        self.assertEqual(
            [item["concept_id"] for item in payload["override_concepts"]], ["c4"]
        )


    def test_twenty_five_candidates_split_into_five_chunks(self):
        concepts = [{"concept_id": f"c{index}"} for index in range(25)]
        chunks = chunk_concepts(concepts)
        self.assertEqual(len(chunks), 5)
        self.assertTrue(all(len(chunk) == 5 for chunk in chunks))

    def test_finalist_selection_keeps_two_per_chunk_up_to_ten(self):
        chunk_triages = []
        for chunk_index in range(5):
            decisions = []
            for item_index in range(5):
                concept_id = f"c{chunk_index}_{item_index}"
                decisions.append(
                    {
                        "concept_id": concept_id,
                        "overall_score": 100 - item_index,
                        "dimension_scores": {
                            key: 5
                            for key in (
                                "channel_fit",
                                "viewer_problem",
                                "promise_clarity",
                                "feasibility",
                                "researchability",
                                "originality",
                                "overclaim_safety",
                            )
                        },
                    }
                )
            chunk_triages.append({"decisions": decisions})
        finalists = select_finalist_ids(chunk_triages)
        self.assertEqual(len(finalists), 10)
        for chunk_index in range(5):
            selected = {
                cid
                for cid in finalists
                if cid.startswith(f"c{chunk_index}_")
            }
            self.assertEqual(
                selected,
                {f"c{chunk_index}_0", f"c{chunk_index}_1"},
            )

    def test_full_audit_preserves_nonfinalists(self):
        first_pass = [
            {
                "decisions": [
                    {
                        "concept_id": "c1",
                        "decision": "SHORTLIST",
                        "overall_score": 90,
                        "dimension_scores": {},
                        "rationale": "strong",
                    },
                    {
                        "concept_id": "c2",
                        "decision": "SHORTLIST",
                        "overall_score": 80,
                        "dimension_scores": {},
                        "rationale": "good",
                    },
                    {
                        "concept_id": "c3",
                        "decision": "REWORK",
                        "overall_score": 60,
                        "dimension_scores": {},
                        "rationale": "middle",
                    },
                ]
            }
        ]
        final = {
            "shortlist_ids": ["c1"],
            "decisions": [
                {
                    "concept_id": "c1",
                    "decision": "SHORTLIST",
                    "overall_score": 92,
                    "dimension_scores": {},
                    "rationale": "best",
                },
                {
                    "concept_id": "c2",
                    "decision": "REWORK",
                    "overall_score": 68,
                    "dimension_scores": {},
                    "rationale": "not final",
                },
            ],
        }
        merged = merge_full_audit(first_pass, final, ["c1", "c2"])
        by_id = {item["concept_id"]: item for item in merged}
        self.assertEqual(by_id["c1"]["final_selection"], "FINAL_SHORTLIST")
        self.assertEqual(
            by_id["c2"]["final_selection"],
            "FINALIST_NOT_SHORTLISTED",
        )
        self.assertEqual(by_id["c3"]["final_selection"], "NOT_FINALIST")
        self.assertEqual(by_id["c3"]["first_pass_decision"], "REWORK")


if __name__ == "__main__":
    unittest.main()
