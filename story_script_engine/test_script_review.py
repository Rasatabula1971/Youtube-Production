import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import script_review

class ScriptReviewTests(unittest.TestCase):
    def request(self):
        return {
          "concept_id":"c1","title":"T","opening_hook":"Hook",
          "sections":[{"section_id":"s1","purpose":"Explain","narration":"Text","claim_ids":["clm001"]}],
          "closing":"Close","package":{"title":"T","one_sentence_promise":"Promise"},
          "accepted_claims":[{"claim_id":"clm001","statement":"Fact"}],
          "required_accept_criteria":list(script_review.CRITERIA),
          "criteria":{key:key for key in script_review.CRITERIA},
          "request_provenance":{"script_draft":"DUMMY","script_draft_sha256":"x"}
        }
    def test_snapshot_pending_after_prepare_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); req=root/"requests"; resp=root/"responses"; req.mkdir(); resp.mkdir()
            (req/"c1.script_review_request.json").write_text(json.dumps(self.request()),encoding="utf-8")
            with patch.object(script_review,"REVIEW_REQUESTS_DIR",req), patch.object(script_review,"RESPONSES_DIR",resp):
                snap=script_review.snapshot()
            self.assertEqual(snap["status"],"AWAITING_HUMAN_DECISION")
            self.assertEqual(snap["pending"],1)
    def test_accept_requires_all_criteria(self):
        req=self.request()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); draft=root/"draft.json"; request=root/"request.json"; response=root/"response.json"; approved=root/"approved"; approved.mkdir()
            draft.write_text(json.dumps({"concept_id":"c1"}),encoding="utf-8")
            req["request_provenance"]["script_draft"]=str(draft)
            request.write_text(json.dumps(req),encoding="utf-8")
            response.write_text(json.dumps({"concept_id":"c1","reviewer":"r","decision":"ACCEPT","criteria":{key:True for key in script_review.CRITERIA},"note":""}),encoding="utf-8")
            with patch.object(script_review,"APPROVED_DIR",approved), patch.object(script_review,"SUMMARY_FILE",root/"summary.json"):
                result=script_review.apply(request,response)
            self.assertEqual(result["status"],"READY_FOR_PRODUCTION")
            self.assertTrue(Path(result["approved_script"]).exists())
if __name__=="__main__": unittest.main()
