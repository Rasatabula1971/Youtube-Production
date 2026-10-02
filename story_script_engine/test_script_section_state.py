import json
import tempfile
import unittest
from pathlib import Path

import script_section_state as section_state


class ScriptSectionStateTests(unittest.TestCase):
    def draft(self):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "opening_hook": "This machine looks broken, but that movement is deliberate.",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "setup_01",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Establish the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "NONE",
                    "narration": "First, notice what the machine is doing.",
                    "claim_ids": [],
                },
                {
                    "section_id": "explanation_02",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain the mechanism.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": "PROGRESS",
                    "narration": "The flexible joint is carrying the load differently.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "Once you see the load path, the strange movement makes sense.",
        }

    def write_draft(self, root):
        path = root / "c1.long_form.script_draft.json"
        payload = self.draft()
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, payload

    def prepare(self, root):
        draft_path, payload = self.write_draft(root)
        state_dir = root / "states"
        state = section_state.prepare_state(
            draft_path,
            state_dir=state_dir,
        )
        path = section_state.state_path_for("c1", "long_form", state_dir)
        return draft_path, payload, path, state

    def target(self, state, target_id):
        return next(
            item
            for item in state["targets"]
            if item["target_id"] == target_id
        )

    def test_state_creates_stable_hook_sections_and_closing_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, _, state = self.prepare(root)

        self.assertEqual(
            [item["target_id"] for item in state["targets"]],
            [
                "hook:opening",
                "section:setup_01",
                "section:explanation_02",
                "closing:closing",
            ],
        )
        self.assertEqual(
            self.target(state, "section:explanation_02")["section_id"],
            "explanation_02",
        )
        self.assertEqual(
            self.target(state, "hook:opening")["target_type"],
            "OPENING_HOOK",
        )
        self.assertEqual(
            self.target(state, "closing:closing")["target_type"],
            "CLOSING",
        )

    def test_prepare_is_idempotent_for_same_exact_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, _, first = self.prepare(root)
            second = section_state.prepare_state(
                draft_path,
                state_dir=root / "states",
            )

        self.assertEqual(first, second)

    def test_accept_locks_target_and_records_audit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)
            updated = section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:setup_01",
                action="ACCEPT",
                reviewer="ricky",
            )

        target = self.target(updated, "section:setup_01")
        self.assertEqual(target["decision"], "ACCEPTED")
        self.assertTrue(target["locked"])
        self.assertEqual(updated["state_version"], 2)
        self.assertEqual(updated["history"][-1]["action"], "ACCEPT")
        self.assertEqual(updated["history"][-1]["reviewer"], "ricky")

    def test_locked_target_cannot_be_reworked_until_unlocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)
            section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:setup_01",
                action="ACCEPT",
                reviewer="r",
            )

            with self.assertRaisesRegex(
                ValueError,
                "Locked target cannot be reworked",
            ):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="section:setup_01",
                    action="REWORK",
                    reviewer="r",
                    reason="TOO_LONG",
                )

    def test_unlock_then_rework_marks_only_selected_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)
            section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:setup_01",
                action="ACCEPT",
                reviewer="r",
            )
            unlocked = section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:setup_01",
                action="UNLOCK",
                reviewer="r",
            )
            self.assertEqual(
                self.target(unlocked, "section:setup_01")["decision"],
                "PENDING",
            )

            updated = section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:setup_01",
                action="REWORK",
                reviewer="r",
                reason="TOO_BORING",
                custom_instruction="Make the transition more concrete.",
            )

        selected = self.target(updated, "section:setup_01")
        untouched = self.target(updated, "section:explanation_02")
        self.assertEqual(selected["decision"], "REWORK_REQUESTED")
        self.assertEqual(selected["rework_reason"], "TOO_BORING")
        self.assertEqual(
            selected["custom_instruction"],
            "Make the transition more concrete.",
        )
        self.assertEqual(untouched["decision"], "PENDING")
        self.assertFalse(untouched["locked"])

    def test_rework_requires_reason_or_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)

            with self.assertRaisesRegex(
                ValueError,
                "requires a reason or custom instruction",
            ):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="section:explanation_02",
                    action="REWORK",
                    reviewer="r",
                )

    def test_unknown_target_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)

            with self.assertRaisesRegex(
                ValueError,
                "Unknown script rework target",
            ):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="section:missing",
                    action="LOCK",
                    reviewer="r",
                )

    def test_duplicate_section_ids_are_rejected(self):
        draft = self.draft()
        draft["sections"][1]["section_id"] = "setup_01"

        with self.assertRaisesRegex(ValueError, "Duplicate script section_id"):
            section_state.build_targets(draft)

    def test_stale_state_rejects_changed_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)
            changed = self.draft()
            changed["sections"][0]["narration"] = "Changed after review state was created."
            draft_path.write_text(json.dumps(changed), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "STALE_SECTION_STATE: script draft changed",
            ):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="section:setup_01",
                    action="LOCK",
                    reviewer="r",
                )

    def test_section_actions_never_mutate_script_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, original, state_path, _ = self.prepare(root)
            before = draft_path.read_bytes()
            section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:explanation_02",
                action="REWORK",
                reviewer="r",
                reason="TOO_TECHNICAL",
            )
            after = draft_path.read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(json.loads(after.decode("utf-8")), original)

    def test_custom_reason_requires_custom_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, _, state_path, _ = self.prepare(root)

            with self.assertRaisesRegex(
                ValueError,
                "CUSTOM rework reason requires custom_instruction",
            ):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="hook:opening",
                    action="REWORK",
                    reviewer="r",
                    reason="CUSTOM",
                )


if __name__ == "__main__":
    unittest.main()
