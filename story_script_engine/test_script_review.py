import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import script_review
import script_section_service as section_service
import script_section_state as section_state


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
            "channel_voice": {
                "profile": {
                    "profile_id": "engineering_nonengineers",
                    "version": 1,
                    "status": "APPROVED",
                },
                "binding": {"profile_sha256": "voice-v1"},
                "apply_to_generation": True,
            },
            "accepted_claims": [{"claim_id": "clm001", "statement": "Fact"}],
            "validation": {"source_overlap": {"blocking": False}},
        }

    def setup_gate(self, root):
        drafts = root / "drafts"
        requests = root / "requests"
        responses = root / "responses"
        approved = root / "approved"
        script_requests = root / "script_requests"
        for path in (drafts, requests, responses, approved, script_requests):
            path.mkdir()
        for fmt, narration in (
            ("long_form", "Long form explanation with context and a full payoff."),
            ("short", "Short proof, reveal, payoff."),
        ):
            script_request_path = (
                script_requests / f"c1.{fmt}.script_request.json"
            )
            script_request_path.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "format": fmt,
                        "package": {"title": "T"},
                        "accepted_claims": [
                            {"claim_id": "clm001", "statement": "Fact"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            draft_payload = self.draft(fmt, narration)
            draft_payload["draft_provenance"] = {
                "request_source": str(script_request_path.resolve())
            }
            draft_path = drafts / f"c1.{fmt}.script_draft.json"
            draft_path.write_text(
                json.dumps(draft_payload),
                encoding="utf-8",
            )
            req = script_review.build_review_request(
                draft_payload,
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

    def test_accept_is_one_click_and_records_audit_criteria(self):
        req = {
            "concept_id": "c1",
            "format": "short",
        }
        payload = self.accept_payload("short")
        payload["criteria"] = {}
        normalized = script_review.validate_response(req, payload)

        self.assertEqual(normalized["decision"], "ACCEPT")
        self.assertTrue(all(normalized["criteria"].values()))

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
            self.assertEqual(
                bundle["channel_voice"]["binding"]["profile_sha256"],
                "voice-v1",
            )

    def test_rework_revokes_existing_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "REQUESTS_DIR", root / "script_requests"),
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
                script_request_path = (
                    root / "script_requests" / "c1.short.script_request.json"
                )
                before_hash = script_review.sha256_file(script_request_path)
                script_review.apply_payload(
                    requests / "c1.short.script_review_request.json",
                    payload,
                )
                updated = json.loads(
                    script_request_path.read_text(encoding="utf-8")
                )
                after_hash = script_review.sha256_file(script_request_path)
                self.assertFalse(bundle.exists())
                self.assertNotEqual(before_hash, after_hash)
                self.assertEqual(
                    updated["human_rework_note"],
                    "Short needs a faster payoff.",
                )
                self.assertEqual(
                    updated["human_rework_mode"],
                    "HUMAN_INSTRUCTION_ONLY",
                )
                self.assertEqual(updated["human_rework_format"], "short")

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


    def test_branch_accept_is_blocked_by_canonical_section_rework_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()
            draft_path = drafts / "c1.short.script_draft.json"
            state = section_state.prepare_state(
                draft_path,
                state_dir=states,
            )
            state_path = section_state.state_path_for(
                "c1",
                "short",
                states,
            )
            section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:s1",
                action="REWORK",
                reviewer="r",
                reason="TOO_TECHNICAL",
            )

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_STATE_DIR", states),
                self.assertRaisesRegex(
                    ValueError,
                    "ACCEPT blocked while section rework is pending",
                ),
            ):
                script_review.apply_payload(
                    requests / "c1.short.script_review_request.json",
                    self.accept_payload("short"),
                )


    def test_concurrent_branch_accept_and_section_rework_cannot_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "rework_requests"
            alternatives = root / "alternatives"
            versions = root / "versions"
            transactions = root / "transactions"
            for path in (
                states,
                rework_requests,
                alternatives,
                versions,
                transactions,
            ):
                path.mkdir()

            draft_path = drafts / "c1.short.script_draft.json"
            section_state.prepare_state(
                draft_path,
                state_dir=states,
            )
            short_request = (
                requests / "c1.short.script_review_request.json"
            )

            service_dirs = {
                "drafts_dir": drafts,
                "state_dir": states,
                "rework_requests_dir": rework_requests,
                "alternatives_dir": alternatives,
                "versions_dir": versions,
                "transactions_dir": transactions,
                "review_requests_dir": requests,
                "review_responses_dir": responses,
                "approved_dir": approved,
            }

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_STATE_DIR", states),
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(
                            script_review.apply_payload,
                            short_request,
                            self.accept_payload("short"),
                        ),
                        pool.submit(
                            section_service.apply_action,
                            concept_id="c1",
                            fmt="short",
                            action="REWORK",
                            target_id="section:s1",
                            reason="TOO_TECHNICAL",
                            custom_instruction="Use plain language.",
                            reviewer="r",
                            **service_dirs,
                        ),
                    ]
                    for future in futures:
                        try:
                            future.result()
                        except ValueError as exc:
                            self.assertIn(
                                "ACCEPT blocked while section rework is pending",
                                str(exc),
                            )

            state_path = section_state.state_path_for(
                "c1",
                "short",
                states,
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            target = next(
                item
                for item in state["targets"]
                if item["target_id"] == "section:s1"
            )
            branch_response = (
                responses / "c1.short.script_review_response.json"
            )

        self.assertEqual(target["decision"], "REWORK_REQUESTED")
        self.assertFalse(branch_response.exists())

    def test_reviewer_identity_can_be_configured(self):
        with patch.dict(
            "os.environ",
            {"YOUTUBE_REVIEWER_ID": "ricky"},
            clear=False,
        ):
            self.assertEqual(script_review.reviewer_id(), "ricky")


    def test_bundle_rejects_mixed_channel_voice_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            short_path = drafts / "c1.short.script_draft.json"
            short = json.loads(short_path.read_text(encoding="utf-8"))
            short["channel_voice"]["profile"]["version"] = 2
            short["channel_voice"]["binding"]["profile_sha256"] = "voice-v2"
            short_path.write_text(json.dumps(short), encoding="utf-8")
            short_req = script_review.build_review_request(short, short_path)
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
                with self.assertRaisesRegex(
                    ValueError,
                    "different Channel Voice bindings",
                ):
                    script_review.apply_payload(
                        requests / "c1.short.script_review_request.json",
                        self.accept_payload("short"),
                    )



if __name__ == "__main__":
    unittest.main()
