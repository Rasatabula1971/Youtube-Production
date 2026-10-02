import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
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
                "request_source": str(script_request_path.resolve()),
                "request_sha256": script_review.sha256_file(script_request_path),
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


    def test_review_request_contains_slice1_section_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = self.draft("short", "Short proof, reveal, payoff.")
            path = Path(tmp) / "c1.short.script_draft.json"
            path.write_text(json.dumps(draft), encoding="utf-8")

            request = script_review.build_review_request(draft, path)

        state = request["section_review"]
        self.assertEqual(state["artifact"], "script_section_review_state")
        self.assertEqual(
            state["source_draft_sha256"],
            request["request_provenance"]["script_draft_sha256"],
        )
        self.assertEqual(
            [item["target_id"] for item in state["targets"]],
            ["opening_hook", "section:s1", "closing"],
        )
        for item in state["targets"]:
            self.assertEqual(item["review_state"], "PENDING")
            self.assertFalse(item["locked"])
            self.assertTrue(item["editable"])
            self.assertEqual(item["revision"], 0)

    def test_snapshot_preserves_section_review_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
            ):
                snapshot = script_review.snapshot()

        short = next(
            item for item in snapshot["scripts"]
            if item["format"] == "short"
        )
        self.assertEqual(
            [item["target_id"] for item in short["section_review"]["targets"]],
            ["opening_hook", "section:s1", "closing"],
        )
        self.assertEqual(
            short["section_review"]["source_draft_sha256"],
            short["request_provenance"]["script_draft_sha256"],
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


    def test_section_action_persists_without_changing_script_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()
            draft_path = drafts / "c1.short.script_draft.json"
            before_hash = script_review.sha256_file(draft_path)

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
            ):
                result = script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="LOCK",
                    reviewer="r",
                )
                snapshot = script_review.snapshot()

            after_hash = script_review.sha256_file(draft_path)
            self.assertEqual(before_hash, after_hash)
            self.assertEqual(result["status"], "SECTION_REVIEW_UPDATED")
            self.assertEqual(result["script_revision"], 0)
            state_file = (
                states / "c1.short.script_section_review_state.json"
            )
            self.assertTrue(state_file.exists())
            short = next(
                item for item in snapshot["scripts"]
                if item["format"] == "short"
            )
            target = next(
                item for item in short["section_review"]["targets"]
                if item["target_id"] == "section:s1"
            )
            self.assertTrue(target["locked"])
            self.assertEqual(target["review_state"], "PENDING")

    def test_prepare_preserves_section_state_for_same_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / "drafts"
            requests = root / "review_requests"
            states = root / "section_states"
            responses = root / "responses"
            approved = root / "approved"
            for path in (drafts, requests, states, responses, approved):
                path.mkdir()

            draft = self.draft(
                "short",
                "Short proof, reveal, payoff.",
            )
            draft_path = drafts / "c1.short.script_draft.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")

            with (
                patch.object(script_review, "DRAFTS_DIR", drafts),
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
            ):
                script_review.prepare()
                first = script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="LOCK",
                    reviewer="r",
                )
                self.assertEqual(first["state_revision"], 1)

                script_review.prepare()
                state = json.loads(
                    (
                        states
                        / "c1.short.script_section_review_state.json"
                    ).read_text(encoding="utf-8")
                )
                request = json.loads(
                    (
                        requests
                        / "c1.short.script_review_request.json"
                    ).read_text(encoding="utf-8")
                )

            target = next(
                item for item in state["targets"]
                if item["target_id"] == "section:s1"
            )
            request_target = next(
                item for item in request["section_review"]["targets"]
                if item["target_id"] == "section:s1"
            )
            self.assertTrue(target["locked"])
            self.assertEqual(state["state_revision"], 1)
            self.assertTrue(request_target["locked"])
            self.assertEqual(
                request["section_review"]["state_revision"],
                1,
            )

    def test_section_rework_invalidates_branch_acceptance_and_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()
            summary = root / "summary.json"

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(script_review, "SUMMARY_FILE", summary),
            ):
                for fmt in ("long_form", "short"):
                    script_review.apply_payload(
                        requests / f"c1.{fmt}.script_review_request.json",
                        self.accept_payload(fmt),
                    )

                bundle = approved / "c1.approved_script.json"
                short_response = script_review.response_path("c1", "short")
                long_response = script_review.response_path("c1", "long_form")
                self.assertTrue(bundle.exists())
                self.assertTrue(short_response.exists())
                self.assertTrue(long_response.exists())

                result = script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="WEAK_CURIOSITY",
                    note="Make the question sharper.",
                    reviewer="r",
                )

            self.assertTrue(result["branch_approval_invalidated"])
            self.assertFalse(bundle.exists())
            self.assertFalse(short_response.exists())
            self.assertTrue(long_response.exists())

    def test_branch_accept_is_blocked_while_section_rework_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="TOO_LONG",
                    reviewer="r",
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "ACCEPT blocked",
                ):
                    script_review.apply_payload(
                        requests / "c1.short.script_review_request.json",
                        self.accept_payload("short"),
                    )

    def test_unlocking_accepted_target_invalidates_existing_branch_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()
            summary = root / "summary.json"

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(script_review, "SUMMARY_FILE", summary),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="ACCEPT",
                    reviewer="r",
                )
                script_review.apply_payload(
                    requests / "c1.short.script_review_request.json",
                    self.accept_payload("short"),
                )
                short_response = script_review.response_path("c1", "short")
                self.assertTrue(short_response.exists())

                result = script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="UNLOCK",
                    reviewer="r",
                )

            self.assertTrue(result["branch_approval_invalidated"])
            self.assertFalse(short_response.exists())
            self.assertEqual(result["target"]["review_state"], "PENDING")


    def test_concurrent_section_actions_do_not_lose_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(
                            script_review.apply_section_review_action,
                            concept_id="c1",
                            format="short",
                            target_id="opening_hook",
                            action="LOCK",
                            reviewer="r1",
                        ),
                        pool.submit(
                            script_review.apply_section_review_action,
                            concept_id="c1",
                            format="short",
                            target_id="section:s1",
                            action="LOCK",
                            reviewer="r2",
                        ),
                    ]
                    for future in futures:
                        future.result()

                state = json.loads(
                    (
                        states
                        / "c1.short.script_section_review_state.json"
                    ).read_text(encoding="utf-8")
                )

            by_id = {
                item["target_id"]: item
                for item in state["targets"]
            }
            self.assertTrue(by_id["opening_hook"]["locked"])
            self.assertTrue(by_id["section:s1"]["locked"])
            self.assertEqual(state["state_revision"], 2)


    def test_concurrent_branch_accept_and_section_rework_cannot_leave_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            states.mkdir()
            summary = root / "summary.json"
            short_request = requests / "c1.short.script_review_request.json"

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(script_review, "SUMMARY_FILE", summary),
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(
                            script_review.apply_payload,
                            short_request,
                            self.accept_payload("short"),
                        ),
                        pool.submit(
                            script_review.apply_section_review_action,
                            concept_id="c1",
                            format="short",
                            target_id="section:s1",
                            action="REWORK",
                            reason="WEAK_CURIOSITY",
                            note="Sharpen the question.",
                            reviewer="r",
                        ),
                    ]
                    for future in futures:
                        try:
                            future.result()
                        except ValueError as exc:
                            self.assertIn("ACCEPT blocked", str(exc))

                state = json.loads(
                    (
                        states
                        / "c1.short.script_section_review_state.json"
                    ).read_text(encoding="utf-8")
                )
                short_response = script_review.response_path("c1", "short")

            target = next(
                item for item in state["targets"]
                if item["target_id"] == "section:s1"
            )
            self.assertEqual(target["review_state"], "REWORK_REQUESTED")
            self.assertFalse(short_response.exists())


    def test_prepare_section_rework_request_is_bounded_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "section_rework_requests"
            states.mkdir()
            rework_requests.mkdir()
            draft_path = drafts / "c1.short.script_draft.json"
            before_hash = script_review.sha256_file(draft_path)

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(
                    script_review,
                    "SECTION_REWORK_REQUESTS_DIR",
                    rework_requests,
                ),
                patch.object(
                    script_review,
                    "REQUESTS_DIR",
                    root / "script_requests",
                ),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="TOO_TECHNICAL",
                    note="Use plain language.",
                    reviewer="r",
                )
                prepared = script_review.prepare_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )
                packet = json.loads(
                    Path(prepared["request"]).read_text(encoding="utf-8")
                )
                current = script_review.validate_prepared_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )

            self.assertEqual(
                script_review.sha256_file(draft_path),
                before_hash,
            )
            self.assertFalse(prepared["model_called"])
            self.assertFalse(prepared["script_changed"])
            self.assertEqual(
                packet["target"]["target_id"],
                "section:s1",
            )
            self.assertEqual(
                [item["target_id"] for item in packet["adjacent_context"]],
                ["opening_hook", "closing"],
            )
            self.assertTrue(
                all(
                    item["read_only"]
                    for item in packet["adjacent_context"]
                )
            )
            self.assertEqual(
                packet["channel_voice"]["binding"]["profile_sha256"],
                "voice-v1",
            )
            self.assertEqual(
                [item["claim_id"] for item in packet["allowed_claims"]],
                ["clm001"],
            )
            self.assertTrue(current["current"])

    def test_repeated_section_rework_prepare_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "section_rework_requests"
            states.mkdir()
            rework_requests.mkdir()

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(
                    script_review,
                    "SECTION_REWORK_REQUESTS_DIR",
                    rework_requests,
                ),
                patch.object(
                    script_review,
                    "REQUESTS_DIR",
                    root / "script_requests",
                ),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="WEAK_CURIOSITY",
                    note="Sharpen the question.",
                    reviewer="r",
                )
                first = script_review.prepare_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )
                second = script_review.prepare_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )

            self.assertEqual(
                first["status"],
                "SECTION_REWORK_REQUEST_PREPARED",
            )
            self.assertEqual(
                second["status"],
                "SECTION_REWORK_REQUEST_CURRENT",
            )
            self.assertEqual(
                first["request_sha256"],
                second["request_sha256"],
            )

    def test_prepared_rework_request_becomes_stale_after_state_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "section_rework_requests"
            states.mkdir()
            rework_requests.mkdir()

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(
                    script_review,
                    "SECTION_REWORK_REQUESTS_DIR",
                    rework_requests,
                ),
                patch.object(
                    script_review,
                    "REQUESTS_DIR",
                    root / "script_requests",
                ),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="WEAK_TRANSITION",
                    note="Make the transition smoother.",
                    reviewer="r",
                )
                script_review.prepare_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="CANCEL_REWORK",
                    reviewer="r",
                )
                stale = script_review.validate_prepared_section_rework_request(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                )

            self.assertFalse(stale["current"])
            self.assertEqual(
                stale["reason"],
                "STALE_SECTION_REWORK_REQUEST",
            )

    def test_prepare_rework_request_fails_if_original_script_request_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "section_rework_requests"
            states.mkdir()
            rework_requests.mkdir()
            original_request = (
                root
                / "script_requests"
                / "c1.short.script_request.json"
            )

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(
                    script_review,
                    "SECTION_REWORK_REQUESTS_DIR",
                    rework_requests,
                ),
                patch.object(
                    script_review,
                    "REQUESTS_DIR",
                    root / "script_requests",
                ),
            ):
                script_review.apply_section_review_action(
                    concept_id="c1",
                    format="short",
                    target_id="section:s1",
                    action="REWORK",
                    reason="TOO_LONG",
                    reviewer="r",
                )
                changed = json.loads(
                    original_request.read_text(encoding="utf-8")
                )
                changed["tampered"] = True
                original_request.write_text(
                    json.dumps(changed),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_SCRIPT_REQUEST",
                ):
                    script_review.prepare_section_rework_request(
                        concept_id="c1",
                        format="short",
                        target_id="section:s1",
                    )

    def test_prepare_rework_request_requires_rework_requested_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requests, responses, approved = self.setup_gate(root)
            states = root / "section_states"
            rework_requests = root / "section_rework_requests"
            states.mkdir()
            rework_requests.mkdir()

            with (
                patch.object(script_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(script_review, "RESPONSES_DIR", responses),
                patch.object(script_review, "APPROVED_DIR", approved),
                patch.object(script_review, "SECTION_REVIEW_STATES_DIR", states),
                patch.object(
                    script_review,
                    "SECTION_REWORK_REQUESTS_DIR",
                    rework_requests,
                ),
                patch.object(
                    script_review,
                    "REQUESTS_DIR",
                    root / "script_requests",
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "REWORK_REQUESTED",
                ):
                    script_review.prepare_section_rework_request(
                        concept_id="c1",
                        format="short",
                        target_id="section:s1",
                    )

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
