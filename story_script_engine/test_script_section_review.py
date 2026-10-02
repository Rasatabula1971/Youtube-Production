import unittest

from script_section_review import (
    REWORK_REASONS,
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
