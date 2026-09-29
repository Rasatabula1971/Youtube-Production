from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_cost_review


def estimate() -> dict:
    return {
        "artifact": "narration_cost_estimate",
        "concept_id": "concept-1",
        "format": "long_form",
        "provider": "higgsfield",
        "currency": "USD",
        "segment_count": 2,
        "max_attempts_per_segment": 3,
        "render_request_sha256": "render-sha",
        "render_blockers": [],
        "status": "READY_FOR_SPEND_GATE",
        "initial_estimate_usd": 2.0,
        "worst_case_estimate_usd": 6.0,
        "provider_quote": {
            "quote_reference": "quote-1",
            "quoted_at": "2026-09-29T12:00:00Z",
            "quote_source": "provider_dry_run",
        },
    }


class NarrationCostReviewTests(unittest.TestCase):
    def test_accept_requires_every_spend_criterion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estimate.json"
            path.write_text(json.dumps(estimate()), encoding="utf-8")
            request = narration_cost_review.build_review_request(
                estimate(),
                path,
            )
            criteria = {
                name: True
                for name in narration_cost_review.REQUIRED_ACCEPT_CRITERIA
            }
            criteria["worst_case_cost_is_accepted"] = False
            with self.assertRaisesRegex(ValueError, "all spend criteria"):
                narration_cost_review.validate_response(
                    request,
                    {
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "reviewer": "tester",
                        "decision": "ACCEPT",
                        "criteria": criteria,
                        "note": "",
                    },
                )

    def test_accept_writes_sha_bound_spend_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            estimates = root / "estimates"
            requests = root / "requests"
            responses = root / "responses"
            approved = root / "approved"
            estimates.mkdir()
            source = estimates / "concept-1.long_form.narration_cost_estimate.json"
            source.write_text(json.dumps(estimate()), encoding="utf-8")

            with (
                patch.object(narration_cost_review, "ESTIMATES_DIR", estimates),
                patch.object(
                    narration_cost_review,
                    "REVIEW_REQUESTS_DIR",
                    requests,
                ),
                patch.object(narration_cost_review, "RESPONSES_DIR", responses),
                patch.object(narration_cost_review, "APPROVED_DIR", approved),
                patch.object(
                    narration_cost_review,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
            ):
                prepared = narration_cost_review.prepare()
                self.assertEqual(prepared["prepared"], 1)
                criteria = {
                    name: True
                    for name in narration_cost_review.REQUIRED_ACCEPT_CRITERIA
                }
                snapshot = narration_cost_review.apply_action(
                    concept_id="concept-1",
                    format="long_form",
                    decision="ACCEPT",
                    criteria=criteria,
                )

            self.assertTrue(snapshot["complete"])
            self.assertEqual(snapshot["accepted"], 1)
            files = list(approved.glob("*.approved_narration_spend.json"))
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(
                payload["spend_gate"]["status"],
                "NARRATION_SPEND_APPROVED",
            )
            self.assertEqual(payload["worst_case_estimate_usd"], 6.0)


if __name__ == "__main__":
    unittest.main()
