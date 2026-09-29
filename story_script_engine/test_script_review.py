import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_review


class ScriptReviewTests(unittest.TestCase):
    def draft(self, fmt, narration):
        return {
            "concept_id": "c1",
            "format": fmt,
            "required_branches": ["long_form", "short"],
            "title": "T",
            "opening_hook": f"{fmt} hook",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "s1",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Explain",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "PROGRESS",
                    "narration": narration,
                    "claim_ids": ["clm001"],
                }
            ],
            "closing": f"{fmt} close",
            "package": {
                "title": "T",
                "one_sentence_promise": "Promise",
                "format_intent": "either",
            },
            "story_plan": {"title": "T", "beats": []},
            "psychology_contract": {"opening_line": {"required": True}},
            "psychology_profile": {"reward_density": "HIGH" if fmt == "short" else "MODERATE"},
            "accepted_claims": [{"claim_id": "clm001", "statement": "Fact"}],
            "validation": {"source_overlap": {"blocking": False}},
        }

    def setup_gate(self, root):
        drafts = root / "drafts"
        requests = root / "requests"
        responses = root / "responses"
        approved = root / "approved"
        for path in (drafts, requests, responses, approved):
            path.mkdir()
        for fmt, narration in (
            ("long_form", "Long form explanation with context and a full payoff."),
            ("short", "Short proof, reveal, payoff."),
        ):
            draft_path = drafts / f"c1.{fmt}.script_draft.json"
            draft_path.write_text(
                json.dumps(self.draft(fmt, narration)),
                encoding="utf-8",
            )
            req = script_review.build_review_request(
                self.draft(fmt, narration),
                draft_path,
            )
            request_path = requests / f"c1.{fmt}.script_review_request.json"
            request_path.write_text(json.dumps(req), encoding="utf-8")
        return drafts, requests, responses, approved

    def accept_payload(self, fmt):
        return {
            "concept_id": "c1",
            "format": fmt,
            "reviewer": "r",
            "decision": "ACCEPT",
            "criteria": {key: True for key in script_review.CRITERIA},
            "note": "",
        }

    def test_snapshot_tracks_branches_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
            ):
                snap = script_review.snapshot()
            self.assertEqual(snap["pending"], 2)
            self.assertEqual(
                sorted(item["format"] for item in snap["scripts"]),
                ["long_form", "short"],
            )

    def test_accept_requires_all_criteria(self):
        req = {
            "concept_id": "c1",
            "format": "short",
        }
        payload = self.accept_payload("short")
        payload["criteria"]["audience_psychology_coherent"] = False
        with self.assertRaisesRegex(ValueError, "all criteria"):
            script_review.validate_response(req, payload)

    def test_bundle_is_created_only_after_all_required_branches_accept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            summary = root / "summary.json"
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SUMMARY_FILE", summary),
            ):
                long_req = requests / "c1.long_form.script_review_request.json"
                first = script_review.apply_payload(
                    long_req,
                    self.accept_payload("long_form"),
                )
                self.assertIsNone(first["approved_script"])
                short_req = requests / "c1.short.script_review_request.json"
                second = script_review.apply_payload(
                    short_req,
                    self.accept_payload("short"),
                )

            bundle_path = Path(second["approved_script"])
            self.assertTrue(bundle_path.exists())
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle["status"], "READY_FOR_PRODUCTION")
            self.assertEqual(
                sorted(bundle["branch_scripts"]),
                ["long_form", "short"],
            )
            self.assertEqual(
                bundle["branch_scripts"]["short"]["psychology_profile"]["reward_density"],
                "HIGH",
            )

    def test_rework_revokes_existing_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                for fmt in ("long_form", "short"):
                    script_review.apply_payload(
                        requests / f"c1.{fmt}.script_review_request.json",
                        self.accept_payload(fmt),
                    )
                bundle = approved / "c1.approved_script.json"
                self.assertTrue(bundle.exists())
                payload = {
                    "concept_id": "c1",
                    "format": "short",
                    "reviewer": "r",
                    "decision": "REWORK",
                    "criteria": {},
                    "note": "Short needs a faster payoff.",
                }
                script_review.apply_payload(
                    requests / "c1.short.script_review_request.json",
                    payload,
                )
                self.assertFalse(bundle.exists())

    def test_identical_or_truncated_branch_scripts_do_not_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            same = self.draft("short", "Long form explanation with context and a full payoff.")
            short_path = drafts / "c1.short.script_draft.json"
            short_path.write_text(json.dumps(same), encoding="utf-8")
            short_req = script_review.build_review_request(same, short_path)
            (requests / "c1.short.script_review_request.json").write_text(
                json.dumps(short_req),
                encoding="utf-8",
            )
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                script_review.apply_payload(
                    requests / "c1.long_form.script_review_request.json",
                    self.accept_payload("long_form"),
                )
                with self.assertRaisesRegex(ValueError, "identical|truncation"):
                    script_review.apply_payload(
                        requests / "c1.short.script_review_request.json",
                        self.accept_payload("short"),
                    )

    def test_stale_draft_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            path = drafts / "c1.short.script_draft.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["closing"] = "Changed after review preparation"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                self.assertRaisesRegex(ValueError, "STALE_REVIEW_REQUEST"),
            ):
                script_review.apply_payload(
                    requests / "c1.short.script_review_request.json",
                    self.accept_payload("short"),
                )

    def test_reviewer_identity_can_be_configured(self):
        with patch.dict(
            "os.environ",
            {"YOUTUBE_REVIEWER_ID": "ricky"},
            clear=False,
        ):
            self.assertEqual(script_review.reviewer_id(), "ricky")


if __name__ == "__main__":
    unittest.main()
