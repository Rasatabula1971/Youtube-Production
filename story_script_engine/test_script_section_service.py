import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_section_service as service


class ScriptSectionServiceTests(unittest.TestCase):
    def draft(self):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "opening_hook": "The movement looks wrong, but it is deliberate.",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "setup_01",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Establish the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "NONE",
                    "narration": "Watch the part move before the load settles.",
                    "claim_ids": [],
                },
                {
                    "section_id": "explanation_02",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain the mechanism.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": "PROGRESS",
                    "narration": "The joint changes how the force travels.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "The motion is part of the design.",
        }

    def dirs(self, root):
        values = {
            "drafts_dir": root / "drafts",
            "state_dir": root / "states",
            "rework_requests_dir": root / "rework_requests",
            "alternatives_dir": root / "alternatives",
            "versions_dir": root / "versions",
            "transactions_dir": root / "transactions",
            "review_requests_dir": root / "review_requests",
            "review_responses_dir": root / "review_responses",
            "approved_dir": root / "approved",
        }
        for path in values.values():
            path.mkdir()
        return values

    def write_draft(self, dirs):
        path = dirs["drafts_dir"] / "c1.long_form.script_draft.json"
        path.write_text(json.dumps(self.draft()), encoding="utf-8")
        return path

    def test_prepare_exposes_stable_targets_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            self.write_draft(dirs)

            before = service.branch_snapshot(
                "c1",
                "long_form",
                drafts_dir=dirs["drafts_dir"],
                state_dir=dirs["state_dir"],
                alternatives_dir=dirs["alternatives_dir"],
            )
            self.assertEqual(before["status"], "SECTION_STATE_NOT_PREPARED")

            after = service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="PREPARE",
                **dirs,
            )

        self.assertEqual(after["status"], "READY_FOR_SECTION_REVIEW")
        self.assertEqual(
            [item["target_id"] for item in after["targets"]],
            [
                "hook:opening",
                "section:setup_01",
                "section:explanation_02",
                "closing:closing",
            ],
        )
        self.assertEqual(
            after["targets"][2]["text"],
            "The joint changes how the force travels.",
        )

    def test_rework_invalidates_branch_response_and_approved_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            self.write_draft(dirs)
            service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="PREPARE",
                **dirs,
            )

            response = (
                dirs["review_responses_dir"]
                / "c1.long_form.script_review_response.json"
            )
            approved = dirs["approved_dir"] / "c1.approved_script.json"
            response.write_text("{}", encoding="utf-8")
            approved.write_text("{}", encoding="utf-8")

            snapshot = service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="REWORK",
                target_id="section:explanation_02",
                reason="TOO_TECHNICAL",
                custom_instruction="Make it easier to picture.",
                reviewer="r",
                **dirs,
            )

        target = next(
            item
            for item in snapshot["targets"]
            if item["target_id"] == "section:explanation_02"
        )
        self.assertEqual(target["decision"], "REWORK_REQUESTED")
        self.assertFalse(response.exists())
        self.assertFalse(approved.exists())

    def test_lock_and_unlock_are_target_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            self.write_draft(dirs)
            service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="PREPARE",
                **dirs,
            )
            locked = service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="ACCEPT",
                target_id="section:setup_01",
                reviewer="r",
                **dirs,
            )
            target = next(
                item
                for item in locked["targets"]
                if item["target_id"] == "section:setup_01"
            )
            self.assertTrue(target["locked"])

            unlocked = service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="UNLOCK",
                target_id="section:setup_01",
                reviewer="r",
                **dirs,
            )

        target = next(
            item
            for item in unlocked["targets"]
            if item["target_id"] == "section:setup_01"
        )
        self.assertFalse(target["locked"])
        self.assertEqual(target["decision"], "PENDING")

    def test_select_uses_deterministic_artifact_path_not_user_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            self.write_draft(dirs)
            expected = (
                dirs["alternatives_dir"]
                / "c1.long_form.section_explanation_02.alternatives.json"
            )
            expected.write_text("{}", encoding="utf-8")

            with patch.object(
                service,
                "apply_selection",
                return_value={"status": "ALTERNATIVE_SELECTED"},
            ) as mocked:
                service.apply_action(
                    concept_id="c1",
                    fmt="long_form",
                    action="SELECT_ALTERNATIVE",
                    target_id="section:explanation_02",
                    selection_id="B",
                    reviewer="r",
                    **dirs,
                )

            selected_path = mocked.call_args.args[0]

        self.assertEqual(selected_path, expected)

    def test_path_like_identity_cannot_escape_drafts_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            path = service._draft_path(
                "../outside",
                "../../long_form",
                drafts_dir=dirs["drafts_dir"],
            )

        self.assertEqual(path.parent, dirs["drafts_dir"])
        self.assertNotIn("..", path.name)

    def test_snapshot_reports_stale_state_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            draft_path = self.write_draft(dirs)
            service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="PREPARE",
                **dirs,
            )
            changed = self.draft()
            changed["closing"] = "Changed outside section review."
            draft_path.write_text(json.dumps(changed), encoding="utf-8")

            snapshot = service.branch_snapshot(
                "c1",
                "long_form",
                drafts_dir=dirs["drafts_dir"],
                state_dir=dirs["state_dir"],
                alternatives_dir=dirs["alternatives_dir"],
            )

        self.assertEqual(snapshot["status"], "STALE_SECTION_STATE")
        self.assertIn("STALE_SECTION_STATE", snapshot["error"])


    def test_sanitized_identity_collision_does_not_open_other_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            path = dirs["drafts_dir"] / "a_b.long_form.script_draft.json"
            payload = self.draft()
            payload["concept_id"] = "a/b"
            path.write_text(json.dumps(payload), encoding="utf-8")

            snapshot = service.branch_snapshot(
                "a b",
                "long_form",
                drafts_dir=dirs["drafts_dir"],
                state_dir=dirs["state_dir"],
                alternatives_dir=dirs["alternatives_dir"],
            )

            self.assertEqual(
                snapshot["status"],
                "SCRIPT_DRAFT_IDENTITY_MISMATCH",
            )
            with self.assertRaisesRegex(
                ValueError,
                "Script draft identity mismatch",
            ):
                service.apply_action(
                    concept_id="a b",
                    fmt="long_form",
                    action="PREPARE",
                    **dirs,
                )



    def test_manual_edit_uses_resolved_paths_and_clears_stale_rework_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = self.dirs(root)
            draft_path = self.write_draft(dirs)
            service.apply_action(
                concept_id="c1",
                fmt="long_form",
                action="PREPARE",
                **dirs,
            )
            state_path = (
                dirs["state_dir"]
                / "c1.long_form.section_state.json"
            )
            alternatives = (
                dirs["alternatives_dir"]
                / "c1.long_form.section_explanation_02.alternatives.json"
            )
            rework_request = (
                dirs["rework_requests_dir"]
                / "c1.long_form.section_explanation_02.section_rework_request.json"
            )
            alternatives.write_text("{}", encoding="utf-8")
            rework_request.write_text("{}", encoding="utf-8")

            with patch.object(
                service,
                "apply_manual_edit",
                return_value={"status": "MANUAL_EDIT_APPLIED"},
            ) as mocked:
                snapshot = service.apply_action(
                    concept_id="c1",
                    fmt="long_form",
                    action="MANUAL_EDIT",
                    target_id="section:explanation_02",
                    replacement_text="Human-written replacement.",
                    reviewer="r",
                    **dirs,
                )

            self.assertEqual(mocked.call_args.args[0], draft_path)
            self.assertEqual(mocked.call_args.args[1], state_path)
            self.assertEqual(
                mocked.call_args.kwargs["target_id"],
                "section:explanation_02",
            )
            self.assertEqual(
                mocked.call_args.kwargs["replacement_text"],
                "Human-written replacement.",
            )
            self.assertFalse(alternatives.exists())
            self.assertFalse(rework_request.exists())
            self.assertEqual(
                snapshot["status"],
                "READY_FOR_SECTION_REVIEW",
            )



if __name__ == "__main__":
    unittest.main()
