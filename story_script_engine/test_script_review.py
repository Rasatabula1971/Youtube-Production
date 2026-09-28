import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_review


class ScriptReviewTests(unittest.TestCase):
    def request(self):
        return {
            "concept_id": "c1",
            "title": "T",
            "opening_hook": "Hook",
            "sections": [
                {
                    "section_id": "s1",
                    "purpose": "Explain",
                    "narration": "Text",
                    "claim_ids": ["clm001"],
                }
            ],
            "closing": "Close",
            "package": {"title": "T", "one_sentence_promise": "Promise"},
            "accepted_claims": [{"claim_id": "clm001", "statement": "Fact"}],
            "required_accept_criteria": list(script_review.CRITERIA),
            "criteria": {key: key for key in script_review.CRITERIA},
            "request_provenance": {"script_draft": "DUMMY", "script_draft_sha256": "x"},
        }

    def test_snapshot_pending_after_prepare_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            req = root / "requests"
            resp = root / "responses"
            req.mkdir()
            resp.mkdir()
            (req / "c1.script_review_request.json").write_text(
                json.dumps(self.request()), encoding="utf-8"
            )
            with patch.object(script_review, "REVIEW_REQUESTS_DIR", req), patch.object(
                script_review, "RESPONSES_DIR", resp
            ):
                snap = script_review.snapshot()
            self.assertEqual(snap["status"], "AWAITING_HUMAN_DECISION")
            self.assertEqual(snap["pending"], 1)

    def test_accept_requires_all_criteria(self):
        req = self.request()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.json"
            request = root / "request.json"
            response = root / "response.json"
            approved = root / "approved"
            approved.mkdir()
            draft.write_text(json.dumps({"concept_id": "c1"}), encoding="utf-8")
            req["request_provenance"]["script_draft"] = str(draft)
            req["request_provenance"]["script_draft_sha256"] = (
                script_review.sha256_file(draft)
            )
            request.write_text(json.dumps(req), encoding="utf-8")
            response.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "reviewer": "r",
                        "decision": "ACCEPT",
                        "criteria": {key: True for key in script_review.CRITERIA},
                        "note": "",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(script_review, "APPROVED_DIR", approved), patch.object(
                script_review, "SUMMARY_FILE", root / "summary.json"
            ):
                result = script_review.apply(request, response)
            self.assertEqual(result["status"], "READY_FOR_PRODUCTION")
            self.assertTrue(Path(result["approved_script"]).exists())

    def test_stale_draft_is_rejected_and_reject_revokes_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.json"
            request = root / "request.json"
            response = root / "response.json"
            approved = root / "approved"
            approved.mkdir()
            draft.write_text(
                json.dumps({"concept_id": "c1", "title": "A"}), encoding="utf-8"
            )
            req = script_review.build_review_request(
                {"concept_id": "c1", "title": "A"}, draft
            )
            request.write_text(json.dumps(req), encoding="utf-8")
            draft.write_text(
                json.dumps({"concept_id": "c1", "title": "B"}), encoding="utf-8"
            )
            response.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "reviewer": "r",
                        "decision": "ACCEPT",
                        "criteria": {key: True for key in script_review.CRITERIA},
                        "note": "",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(script_review, "APPROVED_DIR", approved), patch.object(
                script_review, "SUMMARY_FILE", root / "summary.json"
            ):
                with self.assertRaisesRegex(ValueError, "STALE_REVIEW_REQUEST"):
                    script_review.apply(request, response)

            draft.write_text(
                json.dumps({"concept_id": "c1", "title": "A"}), encoding="utf-8"
            )
            req = script_review.build_review_request(
                {"concept_id": "c1", "title": "A"}, draft
            )
            request.write_text(json.dumps(req), encoding="utf-8")
            with patch.object(script_review, "APPROVED_DIR", approved), patch.object(
                script_review, "SUMMARY_FILE", root / "summary.json"
            ):
                response.write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "reviewer": "r",
                            "decision": "ACCEPT",
                            "criteria": {key: True for key in script_review.CRITERIA},
                            "note": "",
                        }
                    ),
                    encoding="utf-8",
                )
                result = script_review.apply(request, response)
                self.assertTrue(Path(result["approved_script"]).exists())
                response.write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "reviewer": "r",
                            "decision": "REJECT",
                            "criteria": {},
                            "note": "",
                        }
                    ),
                    encoding="utf-8",
                )
                script_review.apply(request, response)
                self.assertFalse((approved / "c1.approved_script.json").exists())


if __name__ == "__main__":
    unittest.main()
