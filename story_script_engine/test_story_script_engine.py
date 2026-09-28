import tempfile, json, unittest
from pathlib import Path
from story_script_engine import build_script_request, validate_script_response

class StoryScriptTests(unittest.TestCase):
    def package(self):
        return {
          "status":"READY_FOR_STORY_SCRIPT","concept_id":"c1",
          "concept":{"working_title":"Why Brakes Work Backwards","audience_promise":"Understand the system","viewer_problem":"Confusing behavior","viewer_moment":"Watching a race","desired_outcome":"Understand why","packaging":{"title":"Why Racing Brakes Work Backwards","one_sentence_promise":"Explain the counterintuitive behavior","expected_payoff":"A clear explanation","thumbnail":{"message":"Backwards?"}}},
          "claims":[{"claim_id":"clm001","statement":"Heat changes braking behavior.","role":"core","question_ids":["rq001"],"coverage":{"state":"MULTI_SOURCE"}}]
        }
    def test_request_preserves_package_and_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"pkg.json"; p.write_text(json.dumps(self.package()),encoding="utf-8")
            req=build_script_request(self.package(),p)
        self.assertEqual(req["accepted_claim_ids"],["clm001"])
        self.assertEqual(req["package"]["title"],"Why Racing Brakes Work Backwards")
    def test_unapproved_claim_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"pkg.json"; p.write_text(json.dumps(self.package()),encoding="utf-8")
            req=build_script_request(self.package(),p)
        response={"concept_id":"c1","title":"T","opening_hook":"Hook","sections":[{"section_id":"s1","purpose":"Explain","narration":"Text","claim_ids":["bad"]}],"closing":"Close"}
        result=validate_script_response(response,req)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unapproved claim_id" in e for e in result["errors"]))
    def test_valid_claim_mapping_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"pkg.json"; p.write_text(json.dumps(self.package()),encoding="utf-8")
            req=build_script_request(self.package(),p)
        response={"concept_id":"c1","title":"T","opening_hook":"Hook","sections":[{"section_id":"s1","purpose":"Explain","narration":"Text","claim_ids":["clm001"]},{"section_id":"s2","purpose":"Payoff","narration":"Text","claim_ids":[]}],"closing":"Close"}
        result=validate_script_response(response,req)
        self.assertTrue(result["valid"])
        self.assertEqual(result["claim_usage"],["clm001"])
if __name__=="__main__": unittest.main()
