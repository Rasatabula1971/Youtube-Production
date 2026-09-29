import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import format_review

CRITERIA = format_review.criteria_names()


def accept_response(**overrides):
    payload = {
        "concept_id": "c1",
        "reviewer": "r",
        "decision": "ACCEPT",
        "criteria": {key: True for key in CRITERIA},
        "note": "",
    }
    payload.update(overrides)
    return payload


def plan(concept_id="c1", title="A"):
    return {
        "concept_id": concept_id,
        "title": title,
        "format_intent": "either",
        "required_branches": ["long_form", "short"],
        "branches": [
            {"format": "long_form", "beats": []},
            {"format": "short", "beats": []},
        ],
        "validation": {
            "branch_separation": {"identical": False, "truncation": False},
            "claim_usage_by_branch": {"long_form": ["clm001"], "short": ["clm001"]},
            "unused_accepted_claim_ids": [],
            "source_overlap": {},
        },
    }


class FormatReviewTests(unittest.TestCase):
    def test_review_request_carries_separation_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan()), encoding="utf-8")
            request = format_review.build_review_request(plan(), path)
        self.assertEqual(request["request_type"], "human_format_gate")
        self.assertIn("branches_are_separate_productions", request["criteria"])
        self.assertEqual(request["branch_separation"]["identical"], False)
        self.assertEqual(request["required_branches"], ["long_form", "short"])

    def test_plan_without_concept_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            payload = plan(concept_id="")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                format_review.build_review_request(payload, path)

    def test_snapshot_pending_after_prepare_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            responses = root / "responses"
            requests.mkdir()
            responses.mkdir()
            source = root / "plan.json"
            source.write_text(json.dumps(plan()), encoding="utf-8")
            request = format_review.build_review_request(plan(), source)
            (requests / "c1.format_review_request.json").write_text(
                json.dumps(request), encoding="utf-8"
            )
            with (
                patch.object(format_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(format_review, "RESPONSES_DIR", responses),
            ):
                snapshot = format_review.snapshot()
        self.assertEqual(snapshot["status"], "AWAITING_HUMAN_DECISION")
        self.assertEqual(snapshot["pending"], 1)

    def test_accept_requires_all_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "plan.json"
            request_path = root / "request.json"
            response_path = root / "response.json"
            approved = root / "approved"
            approved.mkdir()
            source.write_text(json.dumps(plan()), encoding="utf-8")
            request_path.write_text(
                json.dumps(format_review.build_review_request(plan(), source)),
                encoding="utf-8",
            )
            partial = accept_response()
            partial["criteria"][CRITERIA[0]] = False
            response_path.write_text(json.dumps(partial), encoding="utf-8")
            with (
                patch.object(format_review, "APPROVED_DIR", approved),
                patch.object(format_review, "SUMMARY_FILE", root / "summary.json"),
                self.assertRaisesRegex(ValueError, "ACCEPT requires all criteria"),
            ):
                format_review.apply(request_path, response_path)

    def test_accept_produces_approved_format_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "plan.json"
            request_path = root / "request.json"
            response_path = root / "response.json"
            approved = root / "approved"
            approved.mkdir()
            source.write_text(json.dumps(plan()), encoding="utf-8")
            request_path.write_text(
                json.dumps(format_review.build_review_request(plan(), source)),
                encoding="utf-8",
            )
            response_path.write_text(json.dumps(accept_response()), encoding="utf-8")
            with (
                patch.object(format_review, "APPROVED_DIR", approved),
                patch.object(format_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                result = format_review.apply(request_path, response_path)
            self.assertEqual(result["status"], "READY_FOR_PRODUCTION_ENGINE")
            approved_path = Path(result["approved_format_plan"])
            self.assertTrue(approved_path.exists())
            stored = json.loads(approved_path.read_text(encoding="utf-8"))
            self.assertIn("approved_provenance", stored)

    def test_rework_requires_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "plan.json"
            request_path = root / "request.json"
            response_path = root / "response.json"
            source.write_text(json.dumps(plan()), encoding="utf-8")
            request_path.write_text(
                json.dumps(format_review.build_review_request(plan(), source)),
                encoding="utf-8",
            )
            response_path.write_text(
                json.dumps(accept_response(decision="REWORK", criteria={}, note="")),
                encoding="utf-8",
            )
            with (
                patch.object(format_review, "SUMMARY_FILE", root / "summary.json"),
                self.assertRaisesRegex(ValueError, "REWORK requires note"),
            ):
                format_review.apply(request_path, response_path)

    def test_stale_plan_is_rejected_and_reject_revokes_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "plan.json"
            request_path = root / "request.json"
            response_path = root / "response.json"
            approved = root / "approved"
            approved.mkdir()

            source.write_text(json.dumps(plan(title="A")), encoding="utf-8")
            request_path.write_text(
                json.dumps(format_review.build_review_request(plan("c1", "A"), source)),
                encoding="utf-8",
            )
            source.write_text(json.dumps(plan(title="B")), encoding="utf-8")
            response_path.write_text(json.dumps(accept_response()), encoding="utf-8")
            with (
                patch.object(format_review, "APPROVED_DIR", approved),
                patch.object(format_review, "SUMMARY_FILE", root / "summary.json"),
                self.assertRaisesRegex(ValueError, "STALE_REVIEW_REQUEST"),
            ):
                format_review.apply(request_path, response_path)

            request_path.write_text(
                json.dumps(format_review.build_review_request(plan("c1", "B"), source)),
                encoding="utf-8",
            )
            with (
                patch.object(format_review, "APPROVED_DIR", approved),
                patch.object(format_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                result = format_review.apply(request_path, response_path)
                self.assertTrue(Path(result["approved_format_plan"]).exists())

                response_path.write_text(
                    json.dumps(
                        accept_response(decision="REJECT", criteria={}, note="")
                    ),
                    encoding="utf-8",
                )
                format_review.apply(request_path, response_path)
                self.assertFalse((approved / "c1.approved_format_plan.json").exists())


if __name__ == "__main__":
    unittest.main()
