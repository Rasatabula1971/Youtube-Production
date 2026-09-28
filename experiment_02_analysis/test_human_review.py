import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import human_review

from human_review import (
    apply_review,
    apply_review_action,
    build_review_request,
    decision_map,
    review_snapshot,
)


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.experiment_config = {
            "required_dimensions": ["opening_hook"],
            "allowed_confidence": ["LOW", "MODERATE", "HIGH"],
            "evidence_types": [
                "metadata",
                "transcript",
                "thumbnail",
                "opening_frame",
                "visual_note",
                "timing_note",
                "audio_note",
                "opportunity_evidence",
            ],
            "dimension_evidence_types": {
                "opening_hook": [
                    "transcript",
                    "opening_frame",
                    "visual_note",
                    "audio_note",
                ]
            },
            "mechanism_taxonomy": {
                "curiosity_gap": "Curiosity",
            },
            "minimum_replication_videos": 2,
            "minimum_replication_channels": 2,
            "causal_warning_phrases": ["made it viral"],
        }
        self.review_config = {
            "max_evidence_chars": 600,
            "require_reviewer_name": True,
        }

    def profile(self):
        return {
            "schema_version": "2.0",
            "experiment_id": "02",
            "video_id": "v1",
            "source": {"channel_id": "c1"},
            "evidence": [
                {
                    "evidence_id": "transcript.open",
                    "type": "transcript",
                    "locator": "00:00:00.000-00:00:05.000",
                    "observation": "Why does it need eight gears?",
                }
            ],
            "analysis": {
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "The opening asks a direct question.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": ["transcript.open"],
                            "confidence": "MODERATE",
                        }
                    ],
                    "notes": "",
                }
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [
                    {
                        "description": "Use a direct unanswered question.",
                        "mechanism_ids": ["curiosity_gap"],
                        "evidence_refs": ["transcript.open"],
                        "confidence": "MODERATE",
                    }
                ],
                "source_specific_elements": [],
                "transformation_opportunities": [],
            },
            "review": {"completed": False},
        }

    def response_for(self, request, decision="ACCEPT"):
        return {
            "video_id": "v1",
            "reviewer": "reviewer-1",
            "decisions": [
                {
                    "item_id": item["item_id"],
                    "decision": decision,
                    "note": "",
                }
                for item in request["items"]
            ],
            "overall_note": "",
        }

    def test_prepare_includes_stable_items_and_evidence(self):
        request = build_review_request(
            self.profile(),
            self.experiment_config,
            self.review_config,
        )

        self.assertEqual(request["reviewable_item_count"], 2)
        self.assertTrue(request["items"][0]["item_id"].startswith("review."))
        self.assertEqual(len(request["items"][0]["item_id"]), 31)
        self.assertEqual(
            request["items"][0]["supporting_evidence"][0][
                "evidence_id"
            ],
            "transcript.open",
        )

    def test_incomplete_review_is_rejected(self):
        request = build_review_request(
            self.profile(),
            self.experiment_config,
            self.review_config,
        )
        response = {
            "video_id": "v1",
            "reviewer": "reviewer-1",
            "decisions": [],
        }

        with self.assertRaises(ValueError):
            decision_map(
                request,
                response,
                self.review_config,
            )

    def test_duplicate_decision_is_rejected(self):
        request = build_review_request(
            self.profile(),
            self.experiment_config,
            self.review_config,
        )
        first = request["items"][0]["item_id"]
        response = self.response_for(request)
        response["decisions"].append(
            {
                "item_id": first,
                "decision": "ACCEPT",
                "note": "",
            }
        )

        with self.assertRaises(ValueError):
            decision_map(
                request,
                response,
                self.review_config,
            )

    def test_accept_all_completes_review(self):
        profile = self.profile()
        request = build_review_request(
            profile,
            self.experiment_config,
            self.review_config,
        )
        reviewed, report = apply_review(
            profile,
            request,
            self.response_for(request),
            self.experiment_config,
            self.review_config,
        )

        self.assertTrue(reviewed["review"]["completed"])
        self.assertEqual(report["status"], "REVIEW_COMPLETED")
        self.assertEqual(report["accepted_count"], 2)

    def test_reject_finding_removes_it_before_completion(self):
        profile = self.profile()
        request = build_review_request(
            profile,
            self.experiment_config,
            self.review_config,
        )
        response = self.response_for(request)
        response["decisions"][0]["decision"] = "REJECT"

        reviewed, report = apply_review(
            profile,
            request,
            response,
            self.experiment_config,
            self.review_config,
        )

        self.assertEqual(
            reviewed["analysis"]["opening_hook"]["findings"],
            [],
        )
        self.assertTrue(reviewed["review"]["completed"])
        self.assertEqual(report["rejected_count"], 1)

    def test_reject_transfer_item_removes_it(self):
        profile = self.profile()
        request = build_review_request(
            profile,
            self.experiment_config,
            self.review_config,
        )
        response = self.response_for(request)
        transfer_id = next(
            item["item_id"]
            for item in request["items"]
            if item["kind"] == "transferable_mechanism"
        )
        for decision in response["decisions"]:
            if decision["item_id"] == transfer_id:
                decision["decision"] = "REJECT"

        reviewed, _ = apply_review(
            profile,
            request,
            response,
            self.experiment_config,
            self.review_config,
        )

        self.assertEqual(
            reviewed["transfer"]["transferable_mechanisms"],
            [],
        )

    def test_invalid_base_profile_cannot_prepare(self):
        profile = self.profile()
        profile["schema_version"] = "1.0"

        with self.assertRaises(ValueError):
            build_review_request(
                profile,
                self.experiment_config,
                self.review_config,
            )


    def test_ui_review_action_persists_and_finalizes_only_when_complete(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            analyzed_dir = root / "analyzed"
            requests_dir = root / "requests"
            responses_dir = root / "responses"
            reviewed_dir = root / "reviewed"
            reports_dir = root / "reports"
            for path in (analyzed_dir, requests_dir, responses_dir, reviewed_dir, reports_dir):
                path.mkdir()

            profile_path = analyzed_dir / "v1.json"
            profile_path.write_text(json.dumps(self.profile()), encoding="utf-8")
            request = build_review_request(
                self.profile(),
                self.experiment_config,
                self.review_config,
            )
            request_path = requests_dir / "v1.review_request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            stack.enter_context(patch.object(human_review, "DEFAULT_ANALYZED_DIR", analyzed_dir))
            stack.enter_context(patch.object(human_review, "REVIEW_REQUESTS_DIR", requests_dir))
            stack.enter_context(patch.object(human_review, "REVIEW_RESPONSES_DIR", responses_dir))
            stack.enter_context(patch.object(human_review, "REVIEWED_PROFILES_DIR", reviewed_dir))
            stack.enter_context(patch.object(human_review, "REVIEW_REPORTS_DIR", reports_dir))

            first = request["items"][0]["item_id"]
            second = request["items"][1]["item_id"]

            with patch.object(human_review, "run_apply") as run_apply:
                snapshot = apply_review_action(
                    video_id="v1",
                    item_id=first,
                    decision="ACCEPT",
                    note="looks supported",
                )
                run_apply.assert_not_called()
                self.assertEqual(snapshot["pending"], 1)
                self.assertEqual(snapshot["accepted"], 1)

                def finalize(profile_path, request_path, response_path, output_path):
                    reviewed_dir.joinpath("v1.json").write_text(
                        json.dumps({"video_id": "v1", "review": {"completed": True}}),
                        encoding="utf-8",
                    )
                    return {"status": "REVIEW_COMPLETED"}

                run_apply.side_effect = finalize
                snapshot = apply_review_action(
                    video_id="v1",
                    item_id=second,
                    decision="REJECT",
                    note="too broad",
                )

            self.assertTrue(snapshot["complete"])
            self.assertEqual(snapshot["accepted"], 1)
            self.assertEqual(snapshot["rejected"], 1)
            saved = json.loads(
                (responses_dir / "v1.review_response.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(saved["decisions"]), 2)


if __name__ == "__main__":
    unittest.main()
