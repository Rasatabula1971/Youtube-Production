from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import concept_review as review


class ConceptReviewTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        output = root / "output"
        output.mkdir()
        candidates = output / "concept_candidates.json"
        state = output / "concept_gate_ui_state.json"
        request = output / "concept_gate_request.json"
        reviewed = output / "concept_gate_reviewed.json"
        handoff = output / "research_handoff.json"
        summary = output / "concept_gate_summary.json"
        saved_ideas = root / ".idea_bank" / "saved_ideas.json"

        stack.enter_context(patch.object(review, "OUTPUT_DIR", output))
        stack.enter_context(patch.object(review, "DEFAULT_CANDIDATES", candidates))
        stack.enter_context(patch.object(review, "STATE_FILE", state))
        stack.enter_context(patch.object(review, "REVIEW_REQUEST_FILE", request))
        stack.enter_context(patch.object(review, "REVIEWED_FILE", reviewed))
        stack.enter_context(patch.object(review, "RESEARCH_HANDOFF_FILE", handoff))
        stack.enter_context(patch.object(review, "SUMMARY_FILE", summary))
        stack.enter_context(patch.object(review, "SAVED_IDEAS_FILE", saved_ideas))

    def candidates(self):
        return {
            "artifact": "concept_candidates",
            "count": 2,
            "concepts": [
                {
                    "concept_id": "c1",
                    "mechanism_id": "curiosity_gap",
                    "mechanism_label": "Curiosity",
                    "working_title": "Why Racing Tyres Look Destroyed",
                    "premise": "Explain a counterintuitive tyre surface change.",
                    "audience_promise": "Reveal what the visible damage actually means.",
                    "viewer_problem": "Why do racing tyres look ruined so quickly?",
                    "viewer_moment": "Watching a race and noticing torn tyre surfaces.",
                    "desired_outcome": "Understand the physical process.",
                    "content_gap": {
                        "hypothesis": "Many clips show the effect without explaining it.",
                        "evidence_status": "HYPOTHESIS",
                        "evidence_basis": [],
                    },
                    "channel_fit": {
                        "status": "FIT",
                        "rationale": "Automotive engineering explainer.",
                    },
                    "title_clarity_test": {
                        "options": ["A", "B", "C"],
                        "result": "PASS",
                        "rationale": "Three clear framings.",
                    },
                    "format_intent": "short",
                    "mechanism_application": "Open with the visible mystery.",
                    "transformation_method": "Independent research and explanation.",
                    "research_questions": ["What causes it?", "When does it happen?"],
                    "source_dependency_test": {
                        "passes": True,
                        "source_assets_required": False,
                        "rationale": "Independent.",
                    },
                },
                {
                    "concept_id": "c2",
                    "mechanism_id": "hidden_mechanism",
                    "mechanism_label": "Hidden mechanism",
                    "working_title": "What F1 Tyre Blankets Really Do",
                    "premise": "Explain the thermal preparation mechanism.",
                    "audience_promise": "Show why tyre temperature matters before movement.",
                    "viewer_problem": "Why heat tyres before the car moves?",
                    "viewer_moment": "Seeing tyre blankets in the garage.",
                    "desired_outcome": "Understand the thermal reason.",
                    "content_gap": {
                        "hypothesis": "The equipment is visible but its role may be underexplained.",
                        "evidence_status": "HYPOTHESIS",
                        "evidence_basis": [],
                    },
                    "channel_fit": {
                        "status": "FIT",
                        "rationale": "Automotive engineering explainer.",
                    },
                    "title_clarity_test": {
                        "options": ["D", "E", "F"],
                        "result": "PASS",
                        "rationale": "Three clear framings.",
                    },
                    "format_intent": "short",
                    "mechanism_application": "Reveal the hidden thermal purpose.",
                    "transformation_method": "Independent topic and research.",
                    "research_questions": [
                        "What temperature target?",
                        "What happens if cold?",
                    ],
                    "source_dependency_test": {
                        "passes": True,
                        "source_assets_required": False,
                        "rationale": "Independent.",
                    },
                },
            ],
        }

    def triaged_candidates(self):
        payload = self.candidates()
        shortlisted, override = payload["concepts"]
        return {
            "artifact": "triaged_concept_candidates",
            "source_candidates_sha256": "test-source",
            "concept_count": 1,
            "concepts": [shortlisted],
            "override_concepts": [override],
        }

    def criteria(self):
        return {
            "originality_clear": True,
            "audience_promise_clear": True,
            "viewer_problem_specific": True,
            "viewer_moment_clear": True,
            "viewer_need_evidence_honest": True,
            "desired_outcome_specific": True,
            "content_gap_honest": True,
            "channel_fit_confirmed": True,
            "title_clarity_passes": True,
            "source_independent": True,
            "feasible": True,
            "researchable": True,
        }

    def test_prepare_creates_pending_concepts(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )

            snapshot = review.prepare_state()

        self.assertEqual(snapshot["status"], "AWAITING_HUMAN_DECISION")
        self.assertEqual(snapshot["pending"], 2)
        self.assertTrue(
            all(item["decision"] == "PENDING" for item in snapshot["concepts"])
        )

    def test_accept_needs_no_checkbox_clicks(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            snapshot = review.apply_action(
                concept_id="c1",
                decision="ACCEPT",
                criteria={},
                note="",
            )

        self.assertFalse(snapshot["complete"])
        accepted = snapshot["concepts"][0]
        self.assertEqual(accepted["decision"], "ACCEPT")
        self.assertTrue(all(accepted["criteria_decisions"].values()))

    def test_rework_checkboxes_mean_keep_and_note_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            snapshot = review.apply_action(
                concept_id="c1",
                decision="REWORK",
                criteria={
                    "originality_clear": True,
                    "source_independent": True,
                },
                note="",
            )

        item = snapshot["concepts"][0]
        self.assertEqual(item["decision"], "REWORK")
        self.assertTrue(item["criteria_decisions"]["originality_clear"])
        self.assertTrue(item["criteria_decisions"]["source_independent"])
        self.assertFalse(item["criteria_decisions"]["researchable"])

    def test_handoff_waits_until_every_concept_decided(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            first = review.apply_action(
                concept_id="c1",
                decision="ACCEPT",
                criteria={},
                note="",
            )
            self.assertFalse(first["complete"])
            self.assertFalse(review.RESEARCH_HANDOFF_FILE.exists())

            final = review.apply_action(
                concept_id="c2",
                decision="REJECT",
                criteria={key: False for key in self.criteria()},
                note="",
            )
            handoff_exists = review.RESEARCH_HANDOFF_FILE.exists()
            handoff = json.loads(
                review.RESEARCH_HANDOFF_FILE.read_text(encoding="utf-8")
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["accepted"], 1)
        self.assertEqual(final["rejected"], 1)
        self.assertTrue(handoff_exists)
        self.assertEqual(handoff["status"], "READY_FOR_RESEARCH")
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(handoff["concepts"][0]["concept_id"], "c1")

    def test_triaged_gate_finalizes_after_shortlist_only(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.triaged_candidates()),
                encoding="utf-8",
            )

            prepared = review.prepare_state()
            self.assertEqual(prepared["pending"], 1)
            self.assertEqual(
                [item["concept_id"] for item in prepared["concepts"]],
                ["c1"],
            )
            self.assertEqual(
                [item["concept_id"] for item in prepared["override_concepts"]],
                ["c2"],
            )

            final = review.apply_action(
                concept_id="c1",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )
            handoff = json.loads(
                review.RESEARCH_HANDOFF_FILE.read_text(encoding="utf-8")
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["accepted"], 1)
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(handoff["concepts"][0]["concept_id"], "c1")

    def test_override_becomes_required_only_after_activation(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.triaged_candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            overridden = review.apply_action(
                concept_id="c2",
                decision="OVERRIDE",
                criteria={},
                note="",
            )
            self.assertEqual(overridden["pending"], 2)
            self.assertEqual(
                {item["concept_id"] for item in overridden["concepts"]},
                {"c1", "c2"},
            )

            first = review.apply_action(
                concept_id="c1",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )
            self.assertFalse(first["complete"])

            final = review.apply_action(
                concept_id="c2",
                decision="REJECT",
                criteria={key: False for key in self.criteria()},
                note="",
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["accepted"], 1)
        self.assertEqual(final["rejected"], 1)

    def test_save_idea_is_terminal_for_active_concept(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            saved = review.apply_action(
                concept_id="c1",
                decision="SAVE_IDEA",
                criteria={},
                note="Strong title; revisit later.",
            )
            bank = json.loads(
                review.SAVED_IDEAS_FILE.read_text(encoding="utf-8")
            )

        self.assertFalse(saved["complete"])
        self.assertEqual(saved["pending"], 1)
        self.assertEqual(saved["saved_idea_count"], 1)
        self.assertEqual(saved["concepts"][0]["decision"], "SAVE_IDEA")
        self.assertTrue(saved["concepts"][0]["idea_saved"])
        self.assertEqual(bank["ideas"][0]["working_title"], "Why Racing Tyres Look Destroyed")
        self.assertEqual(bank["ideas"][0]["note"], "Strong title; revisit later.")

    def test_save_idea_allowed_after_gate_complete_and_deduped(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()),
                encoding="utf-8",
            )
            review.prepare_state()

            review.apply_action(
                concept_id="c1",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )
            complete = review.apply_action(
                concept_id="c2",
                decision="REJECT",
                criteria={key: False for key in self.criteria()},
                note="",
            )
            self.assertTrue(complete["complete"])

            first_save = review.apply_action(
                concept_id="c2",
                decision="SAVE_IDEA",
                criteria={},
                note="Keep the title, rebuild the premise.",
            )
            second_save = review.apply_action(
                concept_id="c2",
                decision="SAVE_IDEA",
                criteria={},
                note="Keep for a future tyre-temperature series.",
            )
            bank = json.loads(
                review.SAVED_IDEAS_FILE.read_text(encoding="utf-8")
            )

        self.assertTrue(first_save["complete"])
        self.assertTrue(second_save["complete"])
        self.assertEqual(second_save["saved_idea_count"], 1)
        self.assertEqual(len(bank["ideas"]), 1)
        self.assertEqual(
            bank["ideas"][0]["note"],
            "Keep for a future tyre-temperature series.",
        )

    def test_candidate_change_invalidates_old_ui_state(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            payload = self.candidates()
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            review.prepare_state()

            payload["concepts"][0]["working_title"] = "Changed"
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            snapshot = review.snapshot()

        self.assertEqual(snapshot["status"], "READY_TO_PREPARE")
        self.assertFalse(snapshot["complete"])


if __name__ == "__main__":
    unittest.main()
