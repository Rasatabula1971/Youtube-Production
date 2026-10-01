from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import package_review as review


class PackageReviewTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        output = root / "output"
        output.mkdir()
        stack.enter_context(patch.object(review, "OUTPUT_DIR", output))
        stack.enter_context(
            patch.object(
                review, "DEFAULT_CANDIDATES", output / "package_candidates.json"
            )
        )
        stack.enter_context(
            patch.object(review, "STATE_FILE", output / "packaging_gate_ui_state.json")
        )
        stack.enter_context(
            patch.object(
                review, "REVIEW_REQUEST_FILE", output / "packaging_gate_request.json"
            )
        )
        stack.enter_context(
            patch.object(
                review, "REVIEWED_FILE", output / "packaging_gate_reviewed.json"
            )
        )
        stack.enter_context(
            patch.object(review, "APPROVED_FILE", output / "approved_packages.json")
        )
        stack.enter_context(
            patch.object(
                review, "RESEARCH_HANDOFF_FILE", output / "research_handoff.json"
            )
        )
        stack.enter_context(
            patch.object(review, "SUMMARY_FILE", output / "packaging_gate_summary.json")
        )

    def candidates(self):
        base = {
            "concept_id": "c1",
            "expected_viewer": "Curious automotive viewer",
            "awareness_level": "Problem aware",
            "viewer_problem": "Why does this happen?",
            "viewer_moment": "After noticing the effect.",
            "desired_outcome": "Understand the mechanism.",
            "one_sentence_promise": "This video helps curious drivers understand the effect so they can explain what is happening.",
            "gap_positioning": "Explains the accepted hypothesis without claiming demand proof.",
            "channel_fit_alignment": "Automotive engineering explainer.",
            "core_promise": "Explain the mechanism.",
            "curiosity_gap": "The visible effect looks wrong but may be expected.",
            "expected_payoff": "A clear mechanical explanation.",
            "format_intent": "short",
            "title_thumbnail_relationship": "Title asks why; image shows the visual mystery.",
            "research_dependencies": ["Verify the physical mechanism."],
            "concept_context": {
                "working_title": "Accepted concept",
                "premise": "Explain a counterintuitive effect.",
                "research_questions": ["What causes it?"],
            },
        }
        first = {
            **base,
            "package_id": "p1",
            "title": "Why It Looks Broken",
            "thumbnail": {
                "message": "This looks damaged.",
                "visual_concept": "Close-up of the effect.",
                "text_overlay": "BROKEN?",
            },
            "opening_frame": {
                "purpose": "Show the visual mystery immediately.",
                "visual_concept": "Macro shot of the effect.",
            },
        }
        second = {
            **base,
            "package_id": "p2",
            "title": "The Damage That Is Not Damage",
            "thumbnail": {
                "message": "Looks ruined, but is it?",
                "visual_concept": "Before/after comparison.",
                "text_overlay": "",
            },
            "opening_frame": {
                "purpose": "Challenge the viewer assumption.",
                "visual_concept": "Side-by-side comparison.",
            },
        }
        return {
            "artifact": "package_candidates",
            "count": 2,
            "packages": [first, second],
        }

    def criteria(self):
        return {
            "promise_clear": True,
            "viewer_problem_aligned": True,
            "viewer_moment_fit": True,
            "one_sentence_promise_clear": True,
            "content_gap_honest": True,
            "channel_fit_preserved": True,
            "concept_aligned": True,
            "title_thumbnail_complementary": True,
            "not_misleading": True,
            "viewer_awareness_fit": True,
            "payoff_defined": True,
            "research_dependencies_explicit": True,
        }

    def test_prepare_creates_pending_packages(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()), encoding="utf-8"
            )
            snapshot = review.prepare_state()

        self.assertEqual(snapshot["status"], "AWAITING_HUMAN_DECISION")
        self.assertEqual(snapshot["pending"], 2)
        self.assertTrue(
            all(item["decision"] == "PENDING" for item in snapshot["packages"])
        )

    def test_accept_requires_every_criterion(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()), encoding="utf-8"
            )
            review.prepare_state()
            criteria = self.criteria()
            criteria["not_misleading"] = False
            with self.assertRaises(ValueError):
                review.apply_action(
                    package_id="p1",
                    decision="ACCEPT",
                    criteria=criteria,
                    note="",
                )

    def test_only_one_package_can_be_accepted_per_concept(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()), encoding="utf-8"
            )
            review.prepare_state()
            review.apply_action(
                package_id="p1",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )
            with self.assertRaises(ValueError):
                review.apply_action(
                    package_id="p2",
                    decision="ACCEPT",
                    criteria=self.criteria(),
                    note="",
                )

    def test_rework_note_is_written_into_model_request_and_invalidates_response(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            output = root / "output"
            requests = output / "package_requests"
            responses = output / "package_responses"
            requests.mkdir()
            responses.mkdir()

            request_path = requests / "c1.package_request.json"
            response_path = responses / "c1.json"
            request_path.write_text(
                json.dumps({
                    "concept_id": "c1",
                    "package_count_requested": 2,
                }),
                encoding="utf-8",
            )

            candidates = self.candidates()
            for package in candidates["packages"]:
                package["response_source"] = str(response_path)
            response_path.write_text(
                json.dumps({
                    "concept_id": "c1",
                    "packages": [
                        {
                            key: value
                            for key, value in package.items()
                            if key != "response_source"
                        }
                        for package in candidates["packages"]
                    ],
                    "response_provenance": {
                        "request_source": str(request_path),
                        "request_sha256": "old",
                    },
                }),
                encoding="utf-8",
            )
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(candidates), encoding="utf-8"
            )
            review.prepare_state()

            criteria = self.criteria()
            criteria["viewer_awareness_fit"] = False
            result = review.apply_action(
                package_id="p1",
                decision="REWORK",
                criteria=criteria,
                note="Audience must be anyone who flies, not a specialist group.",
            )
            updated = json.loads(request_path.read_text(encoding="utf-8"))

        self.assertEqual(
            updated["human_rework_note"],
            "Audience must be anyone who flies, not a specialist group.",
        )
        self.assertEqual(updated["human_rework_package_id"], "p1")
        self.assertEqual(updated["human_rework_iteration"], 1)
        self.assertIn(
            "viewer_awareness_fit",
            updated["human_rework_change_criteria"],
        )
        self.assertEqual(len(updated["human_rework_original_packages"]), 2)
        self.assertFalse(response_path.exists())
        self.assertEqual(result["status"], "AWAITING_HUMAN_DECISION")

    def test_prepare_preserves_unchanged_non_rework_decisions(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            original = self.candidates()
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(original), encoding="utf-8"
            )
            review.prepare_state()
            review.apply_action(
                package_id="p2",
                decision="REJECT",
                criteria={key: False for key in self.criteria()},
                note="",
            )

            changed = self.candidates()
            changed["packages"][0]["expected_viewer"] = "Anyone who flies"
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(changed), encoding="utf-8"
            )
            snapshot = review.prepare_state()
            p2 = next(item for item in snapshot["packages"] if item["package_id"] == "p2")
            p1 = next(item for item in snapshot["packages"] if item["package_id"] == "p1")

        self.assertEqual(p2["decision"], "REJECT")
        self.assertEqual(p1["decision"], "PENDING")

    def test_complete_gate_writes_research_handoff(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            review.DEFAULT_CANDIDATES.write_text(
                json.dumps(self.candidates()), encoding="utf-8"
            )
            review.prepare_state()
            review.apply_action(
                package_id="p1",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )
            final = review.apply_action(
                package_id="p2",
                decision="REJECT",
                criteria={key: False for key in self.criteria()},
                note="",
            )
            handoff = json.loads(
                review.RESEARCH_HANDOFF_FILE.read_text(encoding="utf-8")
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["accepted"], 1)
        self.assertEqual(handoff["status"], "READY_FOR_RESEARCH")
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(
            handoff["concepts"][0]["packaging"]["package_id"],
            "p1",
        )


if __name__ == "__main__":
    unittest.main()
