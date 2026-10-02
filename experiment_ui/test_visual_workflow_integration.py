from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

import server
import workflow_automation


class VisualWorkflowIntegrationTests(unittest.TestCase):
    def workflow(
        self,
        visual_post,
        spend_gate=None,
        handoff_state=None,
        assembly_state=None,
        edit_manifest_state=None,
        edit_preview_state=None,
        ffmpeg_ready=True,
        edit_gate=None,
        final_handoff_state=None,
        readiness=None,
    ):
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
                "visual_asset_acquisition_artifact_state",
                return_value={
                    "status": "CURRENT",
                    "current": True,
                    "acquired": 0,
                    "manual_required": 0,
                    "failures": 0,
                    "items": [],
                    "manual_items": [],
                    "failure_items": [],
                },
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
            patch.object(
                server,
                "visual_generation_handoff_artifact_state",
                return_value=(
                    handoff_state
                    if handoff_state is not None
                    else {
                        "status": "NO_PAID_VISUAL_GENERATION_AUTHORIZED",
                        "ready": False,
                        "expected": 0,
                        "current": 0,
                    }
                ),
            ),
            patch.object(
                server,
                "visual_assembly_artifact_state",
                return_value=(
                    assembly_state
                    if assembly_state is not None
                    else {
                        "status": "STALE_OR_INCOMPLETE",
                        "ready": False,
                        "waiting_for_premium_assets": 0,
                        "waiting_for_local_assets": 0,
                        "waiting_for_existing_retry": 0,
                    }
                ),
            ),
            patch.object(
                server,
                "edit_manifest_artifact_state",
                return_value=(
                    edit_manifest_state
                    if edit_manifest_state is not None
                    else {
                        "status": "STALE_OR_INCOMPLETE",
                        "ready": False,
                    }
                ),
            ),
            patch.object(
                server,
                "edit_preview_artifact_state",
                return_value=(
                    edit_preview_state
                    if edit_preview_state is not None
                    else {
                        "status": "STALE_OR_INCOMPLETE",
                        "ready": False,
                    }
                ),
            ),
            patch.object(
                server,
                "structural_ffmpeg_available",
                return_value=ffmpeg_ready,
            ),
            patch.object(
                server,
                "edit_preview_review_snapshot",
                return_value=(
                    edit_gate
                    if edit_gate is not None
                    else {
                        "status": "AWAITING_HUMAN_DECISION",
                        "complete": False,
                        "rework": 0,
                    }
                ),
            ),
            patch.object(
                server,
                "final_production_handoff_artifact_state",
                return_value=(
                    final_handoff_state
                    if final_handoff_state is not None
                    else {
                        "status": "STALE_OR_INCOMPLETE",
                        "ready": False,
                        "expected": 1,
                        "current": 0,
                        "stale": 0,
                        "blocked": 0,
                        "ready_for_final_sound": 0,
                    }
                ),
            ),
        )
        for context in patches:
            stack.enter_context(context)
        return server.workflow_guidance(readiness or {})

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
        self.assertEqual(workflow["state"], "ACTION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Build Visual Edit Assembly Plan",
        )
        self.assertEqual(
            workflow["current_action_id"],
            "auto_continue",
        )

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
        self.assertEqual(workflow["state"], "ACTION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Prepare Premium Visual Generation Briefs",
        )
        self.assertEqual(
            workflow["current_action_id"],
            "auto_continue",
        )


    def test_current_no_spend_assembly_starts_slice19_manifest(self):
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
                "expected_branches": [("c1", "short")],
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
        )
        self.assertEqual(workflow["state"], "ACTION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Build Edit Preview Manifest",
        )
        self.assertEqual(
            workflow["current_action_id"],
            "auto_continue",
        )

    def test_current_manifest_without_ffmpeg_stops_fail_closed(self):
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
                "expected_branches": [("c1", "short")],
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            ffmpeg_ready=False,
        )
        self.assertEqual(
            workflow["state"],
            "LOCAL_FFMPEG_REQUIRED",
        )
        self.assertIn(
            "will not use a paid/cloud fallback",
            workflow["current_detail"],
        )

    def test_current_manifest_runs_local_preview_next(self):
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
                "expected_branches": [("c1", "short")],
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            edit_preview_state={
                "status": "STALE_OR_INCOMPLETE",
                "ready": False,
            },
            ffmpeg_ready=True,
        )
        self.assertEqual(workflow["state"], "ACTION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Render Free Structural Edit Preview",
        )

    def test_current_preview_stops_at_human_edit_preview_gate(self):
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
                "expected_branches": [("c1", "short")],
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            edit_preview_state={"status": "CURRENT", "ready": True},
            ffmpeg_ready=True,
            edit_gate={
                "status": "AWAITING_HUMAN_DECISION",
                "complete": False,
                "rework": 0,
            },
        )
        self.assertEqual(
            workflow["state"],
            "HUMAN_EDIT_PREVIEW_GATE",
        )
        self.assertIn(
            "structural only",
            workflow["current_detail"],
        )

    def test_approved_edit_direction_unlocks_final_handoff_prepare(self):
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
                "expected_branches": [["c1", "short"]],
            },
            assembly_state={
                "status": "CURRENT",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            edit_preview_state={"status": "CURRENT", "ready": True},
            edit_gate={
                "status": "COMPLETE",
                "complete": True,
                "rework": 0,
                "approved": 1,
            },
            final_handoff_state={
                "status": "STALE_OR_INCOMPLETE",
                "ready": False,
                "expected": 1,
                "current": 0,
                "stale": 0,
                "blocked": 0,
                "ready_for_final_sound": 0,
            },
            readiness={
                "final_production_handoff_prepare": {
                    "enabled": True,
                    "reason": "ready",
                }
            },
        )
        self.assertEqual(workflow["state"], "ACTION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Prepare Final Production Handoff",
        )

    def test_current_final_handoff_stops_at_slice20_boundary(self):
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
                "expected_branches": [["c1", "short"]],
            },
            assembly_state={
                "status": "CURRENT",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            edit_preview_state={"status": "CURRENT", "ready": True},
            edit_gate={
                "status": "COMPLETE",
                "complete": True,
                "rework": 0,
                "approved": 1,
            },
            final_handoff_state={
                "status": "CURRENT",
                "ready": True,
                "expected": 1,
                "current": 1,
                "stale": 0,
                "blocked": 0,
                "ready_for_final_sound": 1,
            },
        )
        self.assertEqual(
            workflow["state"],
            "FINAL_PRODUCTION_HANDOFF_READY",
        )
        self.assertIn("Slice 20 stops here", workflow["current_detail"])

    def test_blocked_final_handoff_stops_without_paid_action(self):
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
                "expected_branches": [["c1", "short"]],
            },
            assembly_state={
                "status": "CURRENT",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
                "ready_for_edit_assembly": 1,
                "expected": 1,
            },
            edit_manifest_state={"status": "CURRENT", "ready": True},
            edit_preview_state={"status": "CURRENT", "ready": True},
            edit_gate={
                "status": "COMPLETE",
                "complete": True,
                "rework": 0,
                "approved": 1,
            },
            final_handoff_state={
                "status": "CURRENT",
                "ready": True,
                "expected": 1,
                "current": 1,
                "stale": 0,
                "blocked": 1,
                "ready_for_final_sound": 0,
            },
        )
        self.assertEqual(
            workflow["state"],
            "FINAL_PRODUCTION_HANDOFF_BLOCKED",
        )
        self.assertIn(
            "no paid provider",
            workflow["current_detail"].lower(),
        )

    def test_current_premium_assembly_waits_for_external_asset(self):
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
                "expected_branches": [("c1", "short")],
            },
            spend_gate={
                "status": "COMPLETE",
                "complete": True,
                "global_cap_valid": True,
                "hero_candidates": 1,
                "authorized": 1,
            },
            handoff_state={
                "status": "READY_FOR_PROVIDER_HANDOFF",
                "ready": True,
                "expected": 1,
                "current": 1,
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 1,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 0,
            },
        )
        self.assertEqual(
            workflow["state"],
            "WAITING_FOR_PREMIUM_VISUAL_ASSETS",
        )
        self.assertIn(
            "no paid provider call",
            workflow["current_detail"].lower(),
        )

    def test_retry_existing_decision_stops_before_edit_preview(self):
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
                "expected_branches": [("c1", "short")],
            },
            spend_gate={
                "status": "COMPLETE",
                "complete": True,
                "global_cap_valid": True,
                "hero_candidates": 1,
                "authorized": 0,
            },
            assembly_state={
                "status": "ASSEMBLY_PLANS_READY",
                "ready": True,
                "waiting_for_premium_assets": 0,
                "waiting_for_local_assets": 0,
                "waiting_for_existing_retry": 1,
            },
        )
        self.assertEqual(
            workflow["state"],
            "VISUAL_EXISTING_RETRY_REQUIRED",
        )

    def test_visual_machine_order_stops_at_human_boundaries(self):
        search_index = workflow_automation.AUTO_MACHINE_ACTION_ORDER.index(
            "visual_search_acquire"
        )
        self.assertEqual(
            workflow_automation.AUTO_MACHINE_ACTION_ORDER[
                search_index : search_index + 9
            ],
            [
                "visual_search_acquire",
                "visual_asset_acquire",
                "visual_rough_cut_prepare",
                "visual_gap_prepare",
                "visual_generation_handoff_prepare",
                "visual_assembly_prepare",
                "edit_manifest_prepare",
                "edit_preview_render",
                "final_production_handoff_prepare",
            ],
        )
        self.assertIn("visual_rough_cut_prepare", server.ACTION_DEFS)
        self.assertIn("visual_gap_prepare", server.ACTION_DEFS)


if __name__ == "__main__":
    unittest.main()
