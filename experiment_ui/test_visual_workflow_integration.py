from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

import server
import workflow_automation


class VisualWorkflowIntegrationTests(unittest.TestCase):
    def workflow(self, visual_post, spend_gate=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        patches = (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={"ready_for_experiment_02": True},
            ),
            patch.object(server, "opportunity_research_state", return_value={}),
            patch.object(
                server,
                "vision_review_snapshot",
                return_value={
                    "awaiting_human_review": False,
                    "complete": True,
                },
            ),
            patch.object(
                server,
                "human_analysis_review_snapshot",
                return_value={"status": "COMPLETE"},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={"candidates_ready": False, "concept_gate": {}},
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={"candidates_ready": False, "packaging_gate": {}},
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={"drafts_ready": False, "research_gate": {}},
            ),
            patch.object(
                server,
                "story_script_artifact_state",
                return_value={"drafts_ready": False, "script_gate": {}},
            ),
            patch.object(
                server,
                "format_artifact_state",
                return_value={"plans_ready": False, "format_gate": {}},
            ),
            patch.object(
                server,
                "voice_performance_artifact_state",
                return_value={
                    "specs_ready": False,
                    "performance_gate": {},
                    "visual_ready": True,
                },
            ),
            patch.object(
                server,
                "narration_preview_gate_snapshot",
                return_value={"items": [], "complete": True},
            ),
            patch.object(
                server,
                "production_visual_artifact_state",
                return_value={"manifests_ready": True},
            ),
            patch.object(
                server,
                "visual_post_search_artifact_state",
                return_value=visual_post,
            ),
            patch.object(
                server,
                "visual_spend_review_snapshot",
                return_value=(
                    spend_gate
                    if spend_gate is not None
                    else {
                        "status": "NO_PREMIUM_GENERATION_REQUIRED",
                        "complete": True,
                        "hero_candidates": 0,
                        "authorized": 0,
                    }
                ),
            ),
        )
        for context in patches:
            stack.enter_context(context)
        return server.workflow_guidance({})

    def test_candidate_gate_precedes_rights_and_rough_cut(self):
        workflow = self.workflow(
            {
                "candidate_gate": {
                    "packets": [{"shots": [{"shot_id": "s1"}]}],
                    "stale_shots": 0,
                },
                "candidate_complete": False,
                "rights_gate": {"required": 0},
                "rights_complete": True,
                "rough_cuts_ready": False,
                "rough_gate": {},
                "rough_gate_complete": False,
                "gap_plans_ready": False,
            }
        )
        self.assertEqual(
            workflow["state"],
            "HUMAN_VISUAL_CANDIDATE_GATE",
        )

    def test_rights_gate_follows_complete_candidate_review(self):
        workflow = self.workflow(
            {
                "candidate_gate": {
                    "packets": [{"shots": [{"shot_id": "s1"}]}],
                    "stale_shots": 0,
                },
                "candidate_complete": True,
                "rights_gate": {"required": 1, "complete": False},
                "rights_complete": False,
                "rough_cuts_ready": False,
                "rough_gate": {},
                "rough_gate_complete": False,
                "gap_plans_ready": False,
            }
        )
        self.assertEqual(
            workflow["state"],
            "HUMAN_VISUAL_RIGHTS_GATE",
        )

    def test_rough_cut_gate_follows_rights_completion(self):
        workflow = self.workflow(
            {
                "candidate_gate": {"packets": [], "stale_shots": 0},
                "candidate_complete": True,
                "rights_gate": {"required": 1, "complete": True},
                "rights_complete": True,
                "rough_cuts_ready": True,
                "rough_gate": {
                    "items": [{"rough_cut_file": "x"}],
                    "complete": False,
                },
                "rough_gate_complete": False,
                "gap_plans_ready": False,
            }
        )
        self.assertEqual(workflow["state"], "HUMAN_ROUGH_CUT_GATE")

    def test_gap_plan_with_premium_candidate_stops_at_spend_gate(self):
        workflow = self.workflow(
            {
                "candidate_gate": {"packets": [], "stale_shots": 0},
                "candidate_complete": True,
                "rights_gate": {"required": 0, "complete": True},
                "rights_complete": True,
                "rough_cuts_ready": True,
                "rough_gate": {"items": [], "complete": True},
                "rough_gate_complete": True,
                "gap_plans_ready": True,
            },
            spend_gate={
                "status": "READY_FOR_VISUAL_SPEND_GATE",
                "complete": False,
                "hero_candidates": 1,
                "authorized": 0,
            },
        )
        self.assertEqual(workflow["state"], "HUMAN_VISUAL_SPEND_GATE")
        self.assertIn("maximum spend", workflow["current_detail"])

    def test_gap_plan_without_premium_candidate_needs_no_spend(self):
        workflow = self.workflow(
            {
                "candidate_gate": {"packets": [], "stale_shots": 0},
                "candidate_complete": True,
                "rights_gate": {"required": 0, "complete": True},
                "rights_complete": True,
                "rough_cuts_ready": True,
                "rough_gate": {"items": [], "complete": True},
                "rough_gate_complete": True,
                "gap_plans_ready": True,
            }
        )
        self.assertEqual(workflow["state"], "VISUAL_ASSEMBLY_READY")
        self.assertIn("No unresolved shot met", workflow["current_detail"])

    def test_completed_spend_gate_exposes_authorized_generation_state(self):
        workflow = self.workflow(
            {
                "candidate_gate": {"packets": [], "stale_shots": 0},
                "candidate_complete": True,
                "rights_gate": {"required": 0, "complete": True},
                "rights_complete": True,
                "rough_cuts_ready": True,
                "rough_gate": {"items": [], "complete": True},
                "rough_gate_complete": True,
                "gap_plans_ready": True,
            },
            spend_gate={
                "status": "COMPLETE",
                "complete": True,
                "hero_candidates": 1,
                "authorized": 1,
            },
        )
        self.assertEqual(workflow["state"], "VISUAL_GENERATION_AUTHORIZED")
        self.assertIn("cost ceilings", workflow["current_detail"])


    def test_visual_machine_order_stops_at_human_boundaries(self):
        search_index = workflow_automation.AUTO_MACHINE_ACTION_ORDER.index(
            "visual_search_acquire"
        )
        self.assertEqual(
            workflow_automation.AUTO_MACHINE_ACTION_ORDER[
                search_index : search_index + 3
            ],
            [
                "visual_search_acquire",
                "visual_rough_cut_prepare",
                "visual_gap_prepare",
            ],
        )
        self.assertIn("visual_rough_cut_prepare", server.ACTION_DEFS)
        self.assertIn("visual_gap_prepare", server.ACTION_DEFS)


if __name__ == "__main__":
    unittest.main()
