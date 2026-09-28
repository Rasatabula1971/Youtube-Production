import unittest
from concept_triage import validate_triage, build_shortlist_payload

class ConceptTriageTests(unittest.TestCase):
    def candidates(self):
        return {
            "concepts": [
                {"concept_id":"c1","working_title":"A"},
                {"concept_id":"c2","working_title":"B"},
                {"concept_id":"c3","working_title":"C"},
                {"concept_id":"c4","working_title":"D"},
            ]
        }

    def response(self):
        dims={
            "channel_fit":5,"viewer_problem":5,"promise_clarity":5,
            "feasibility":4,"researchability":4,"originality":4,
            "overclaim_safety":4
        }
        return {
            "decisions":[
                {"concept_id":"c1","decision":"SHORTLIST","overall_score":90,"dimension_scores":dims,"strengths":["fit"],"risks":[],"rationale":"strong"},
                {"concept_id":"c2","decision":"SHORTLIST","overall_score":85,"dimension_scores":dims,"strengths":["fit"],"risks":[],"rationale":"strong"},
                {"concept_id":"c3","decision":"SHORTLIST","overall_score":80,"dimension_scores":dims,"strengths":["fit"],"risks":[],"rationale":"strong"},
                {"concept_id":"c4","decision":"DROP","overall_score":40,"dimension_scores":dims,"strengths":[],"risks":["off channel"],"rationale":"weak"},
            ],
            "shortlist_ids":["c1","c2","c3"],
            "summary":"three strongest"
        }

    def test_valid_triage_requires_all_candidates(self):
        result=validate_triage(self.response(),self.candidates()["concepts"])
        self.assertEqual(len(result["decisions"]),4)
        self.assertEqual(result["shortlist_ids"],["c1","c2","c3"])

    def test_shortlist_must_match_decisions(self):
        bad=self.response()
        bad["shortlist_ids"]=["c1","c2","c4"]
        with self.assertRaises(ValueError):
            validate_triage(bad,self.candidates()["concepts"])

    def test_shortlist_payload_preserves_llm_reason(self):
        triage=validate_triage(self.response(),self.candidates()["concepts"])
        payload=build_shortlist_payload(self.candidates(),triage,"abc")
        self.assertEqual(payload["concept_count"],3)
        self.assertEqual(payload["concepts"][0]["llm_triage"]["decision"],"SHORTLIST")

if __name__=="__main__":
    unittest.main()
