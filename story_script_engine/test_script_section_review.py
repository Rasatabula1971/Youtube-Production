import unittest

from script_section_review import (
    REWORK_REASONS,
    apply_target_action,
    build_section_review_state,
    validate_section_review_state,
)


class ScriptSectionReviewContractTests(unittest.TestCase):
    def draft(self):
        return {
            "opening_hook": "This brake works worse before it works better.",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "s1",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Set up the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "PROGRESS",
                    "narration": "At low temperature, the behavior feels wrong.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "s2",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain the mechanism.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": "PROOF",
                    "narration": "Heat changes how the braking system behaves.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "The design makes sense once temperature is part of the picture.",
        }

    def test_builds_stable_targets_with_initial_review_state(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["source_draft_sha256"], "draft-sha")
        self.assertEqual(state["script_revision"], 0)
        self.assertEqual(state["state_revision"], 0)
        self.assertEqual(
            [target["target_id"] for target in state["targets"]],
            ["opening_hook", "section:s1", "section:s2", "closing"],
        )
        for target in state["targets"]:
            self.assertEqual(target["review_state"], "PENDING")
            self.assertFalse(target["locked"])
            self.assertTrue(target["editable"])
            self.assertEqual(target["revision"], 0)
            self.assertIsNone(target["rework_reason"])
            self.assertIsNone(target["rework_note"])
            self.assertTrue(target["content_sha256"])

        self.assertIn("TOO_TECHNICAL", REWORK_REASONS)
        self.assertIn("CUSTOM_INSTRUCTION", REWORK_REASONS)
        self.assertTrue(validate_section_review_state(state)["valid"])

    def test_same_draft_produces_same_target_hashes(self):
        first = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        second = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        self.assertEqual(
            [item["content_sha256"] for item in first["targets"]],
            [item["content_sha256"] for item in second["targets"]],
        )

    def test_target_hash_changes_only_for_changed_target(self):
        original = build_section_review_state(
            self.draft(),
            source_draft_sha256="old-draft",
        )
        changed_draft = self.draft()
        changed_draft["sections"][1]["narration"] = (
            "Heat changes the coefficient and therefore the braking behavior."
        )
        changed = build_section_review_state(
            changed_draft,
            source_draft_sha256="new-draft",
        )

        original_hashes = {
            item["target_id"]: item["content_sha256"]
            for item in original["targets"]
        }
        changed_hashes = {
            item["target_id"]: item["content_sha256"]
            for item in changed["targets"]
        }

        self.assertEqual(
            original_hashes["opening_hook"],
            changed_hashes["opening_hook"],
        )
        self.assertEqual(
            original_hashes["section:s1"],
            changed_hashes["section:s1"],
        )
        self.assertNotEqual(
            original_hashes["section:s2"],
            changed_hashes["section:s2"],
        )
        self.assertEqual(
            original_hashes["closing"],
            changed_hashes["closing"],
        )

    def test_duplicate_section_ids_fail_closed(self):
        draft = self.draft()
        draft["sections"][1]["section_id"] = "s1"

        with self.assertRaisesRegex(ValueError, "Duplicate script section_id"):
            build_section_review_state(
                draft,
                source_draft_sha256="draft-sha",
            )

    def test_missing_section_id_fails_closed(self):
        draft = self.draft()
        draft["sections"][0]["section_id"] = ""

        with self.assertRaisesRegex(ValueError, "requires section_id"):
            build_section_review_state(
                draft,
                source_draft_sha256="draft-sha",
            )


    def action(self, state, *, target_id="section:s1", action, reason=None, note=None):
        return apply_target_action(
            state,
            source_draft_sha256="draft-sha",
            target_id=target_id,
            action=action,
            reviewer="tester",
            updated_at="2026-10-01T21:02:00-04:00",
            reason=reason,
            note=note,
        )

    def test_accept_locks_target_and_increments_only_state_revision(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        before_hash = next(
            item["content_sha256"]
            for item in state["targets"]
            if item["target_id"] == "section:s1"
        )

        result = self.action(state, action="ACCEPT")

        target = result["target"]
        self.assertTrue(result["changed"])
        self.assertEqual(target["review_state"], "ACCEPTED")
        self.assertTrue(target["locked"])
        self.assertFalse(target["editable"])
        self.assertEqual(target["revision"], 1)
        self.assertEqual(target["content_sha256"], before_hash)
        self.assertEqual(target["last_action"], "ACCEPT")
        self.assertEqual(target["last_reviewer"], "tester")
        self.assertEqual(result["state"]["state_revision"], 1)
        self.assertEqual(result["state"]["script_revision"], 0)

    def test_lock_is_not_the_same_as_accept(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        result = self.action(state, action="LOCK")

        self.assertEqual(result["target"]["review_state"], "PENDING")
        self.assertTrue(result["target"]["locked"])
        self.assertFalse(result["target"]["editable"])
        self.assertFalse(result["invalidates_branch_approval"])

    def test_repeated_actions_are_no_ops_without_revision_inflation(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        first = self.action(state, action="LOCK")
        second = self.action(first["state"], action="LOCK")

        self.assertFalse(second["changed"])
        self.assertEqual(second["state"]["state_revision"], 1)
        self.assertEqual(second["target"]["revision"], 1)

        unlocked = self.action(second["state"], action="UNLOCK")
        unlock_retry = self.action(unlocked["state"], action="UNLOCK")
        self.assertFalse(unlock_retry["changed"])
        self.assertEqual(unlock_retry["state"]["state_revision"], 2)

    def test_unlocking_accepted_target_reopens_it_and_invalidates_branch(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        accepted = self.action(state, action="ACCEPT")

        reopened = self.action(accepted["state"], action="UNLOCK")

        self.assertEqual(reopened["target"]["review_state"], "PENDING")
        self.assertFalse(reopened["target"]["locked"])
        self.assertTrue(reopened["target"]["editable"])
        self.assertTrue(reopened["invalidates_branch_approval"])

    def test_locked_target_cannot_be_marked_for_rework(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        locked = self.action(state, action="LOCK")

        with self.assertRaisesRegex(ValueError, "unlock it first"):
            self.action(
                locked["state"],
                action="REWORK",
                reason="TOO_TECHNICAL",
            )

    def test_rework_records_bounded_reason_and_cancel_clears_it(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        rework = self.action(
            state,
            action="REWORK",
            reason="TOO_TECHNICAL",
            note="Translate the mechanism into normal language.",
        )

        self.assertEqual(rework["target"]["review_state"], "REWORK_REQUESTED")
        self.assertEqual(rework["target"]["rework_reason"], "TOO_TECHNICAL")
        self.assertEqual(
            rework["target"]["rework_note"],
            "Translate the mechanism into normal language.",
        )
        self.assertTrue(rework["invalidates_branch_approval"])

        cancelled = self.action(rework["state"], action="CANCEL_REWORK")
        self.assertEqual(cancelled["target"]["review_state"], "PENDING")
        self.assertIsNone(cancelled["target"]["rework_reason"])
        self.assertIsNone(cancelled["target"]["rework_note"])

        retry = self.action(cancelled["state"], action="CANCEL_REWORK")
        self.assertFalse(retry["changed"])
        self.assertEqual(
            retry["state"]["state_revision"],
            cancelled["state"]["state_revision"],
        )

    def test_custom_rework_requires_human_instruction(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        with self.assertRaisesRegex(ValueError, "non-empty rework_note"):
            self.action(
                state,
                action="REWORK",
                reason="CUSTOM_INSTRUCTION",
                note="",
            )

    def test_unknown_reason_and_target_fail_closed(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        with self.assertRaisesRegex(ValueError, "valid rework_reason"):
            self.action(
                state,
                action="REWORK",
                reason="MAKE_IT_VIRAL",
            )

        with self.assertRaisesRegex(ValueError, "Unknown section review target"):
            self.action(
                state,
                target_id="section:missing",
                action="LOCK",
            )

    def test_stale_draft_hash_fails_closed(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        with self.assertRaisesRegex(ValueError, "STALE_SECTION_REVIEW_STATE"):
            apply_target_action(
                state,
                source_draft_sha256="different-draft",
                target_id="section:s1",
                action="LOCK",
                reviewer="tester",
                updated_at="2026-10-01T21:02:00-04:00",
            )

    def test_rework_retry_preserves_metadata_and_is_no_op(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        first = self.action(
            state,
            action="REWORK",
            reason="WEAK_TRANSITION",
            note="Bridge this more smoothly.",
        )

        retry = self.action(
            first["state"],
            action="REWORK",
            reason="WEAK_TRANSITION",
            note="Bridge this more smoothly.",
        )
        unlocked_retry = self.action(retry["state"], action="UNLOCK")

        self.assertFalse(retry["changed"])
        self.assertFalse(unlocked_retry["changed"])
        self.assertEqual(
            unlocked_retry["target"]["rework_reason"],
            "WEAK_TRANSITION",
        )
        self.assertEqual(
            unlocked_retry["target"]["rework_note"],
            "Bridge this more smoothly.",
        )

    def test_invalid_state_is_rejected(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        state["targets"][0]["review_state"] = "MAGIC"

        validation = validate_section_review_state(state)

        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("invalid review_state" in item for item in validation["errors"])
        )


if __name__ == "__main__":
    unittest.main()
