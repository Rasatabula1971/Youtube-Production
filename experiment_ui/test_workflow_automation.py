from __future__ import annotations

import unittest
from unittest.mock import patch

import workflow_automation as automation


class WorkflowAutomationTests(unittest.TestCase):
    def test_next_enabled_action_uses_pipeline_order(self):
        readiness = {
            "package_generate": {"enabled": True},
            "exp2_acquire": {"enabled": True},
        }
        self.assertEqual(
            automation.next_enabled_action(readiness),
            "exp2_acquire",
        )

    def test_runs_machine_steps_until_human_boundary(self):
        state = {"completed": 0}

        def readiness():
            if state["completed"] == 0:
                return {"exp2_prepare": {"enabled": True, "reason": "ready"}}
            if state["completed"] == 1:
                return {"exp2_acquire": {"enabled": True, "reason": "ready"}}
            return {}

        def fake_run(action_id):
            state["completed"] += 1
            return 0

        with (
            patch.object(automation.control, "action_readiness", side_effect=readiness),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_VISION_GATE",
                    "current_title": "Review Visual Evidence",
                },
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["completed_actions"],
            ["exp2_prepare", "exp2_acquire"],
        )
        self.assertEqual(result["workflow_state"], "HUMAN_VISION_GATE")

    def test_repeats_same_batched_action_when_progress_changes(self):
        state = {"completed": 0}

        def readiness():
            if state["completed"] == 0:
                return {
                    "concept_generate": {
                        "enabled": True,
                        "reason": "Concept generation progress: 0/5 current responses.",
                    }
                }
            if state["completed"] == 1:
                return {
                    "concept_generate": {
                        "enabled": True,
                        "reason": "Concept generation progress: 4/5 current responses.",
                    }
                }
            return {}

        def fake_run(_action_id):
            state["completed"] += 1
            return 0

        with (
            patch.object(automation.control, "action_readiness", side_effect=readiness),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_CONCEPT_GATE",
                    "current_title": "Review Concept Candidates",
                },
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["completed_actions"],
            ["concept_generate", "concept_generate"],
        )

    def test_partial_batched_action_continues_when_progress_changes(self):
        state = {"calls": 0}

        def readiness():
            if state["calls"] == 0:
                return {
                    "concept_generate": {
                        "enabled": True,
                        "reason": "Concept generation progress: 0/5 current responses.",
                    }
                }
            if state["calls"] == 1:
                return {
                    "concept_generate": {
                        "enabled": True,
                        "reason": "Concept generation progress: 2/5 current responses.",
                    }
                }
            return {}

        def fake_run(_action_id):
            state["calls"] += 1
            return 2 if state["calls"] == 1 else 0

        with (
            patch.object(automation.control, "action_readiness", side_effect=readiness),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_CONCEPT_GATE",
                    "current_title": "Review Concept Candidates",
                },
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["completed_actions"],
            ["concept_generate", "concept_generate"],
        )


    def test_script_gate_completion_runs_format_chain_to_human_format_gate(self):
        state = {"completed": 0}
        sequence = [
            "format_prepare",
            "format_generate",
            "format_gate_prepare",
        ]

        def readiness():
            if state["completed"] < len(sequence):
                action_id = sequence[state["completed"]]
                return {
                    action_id: {
                        "enabled": True,
                        "reason": f"{action_id} ready",
                    }
                }
            return {}

        def fake_run(action_id):
            self.assertEqual(action_id, sequence[state["completed"]])
            state["completed"] += 1
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_FORMAT_GATE",
                    "current_title": "Review Format Plan",
                },
            ),
            patch.object(
                automation,
                "run_action",
                side_effect=fake_run,
            ),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(result["completed_actions"], sequence)
        self.assertEqual(result["workflow_state"], "HUMAN_FORMAT_GATE")
        self.assertEqual(result["message"], "Review Format Plan")

    def test_format_gate_completion_runs_voice_chain_to_human_performance_gate(self):
        state = {"completed": 0}
        sequence = [
            "voice_prepare",
            "voice_generate",
            "voice_gate_prepare",
        ]

        def readiness():
            if state["completed"] < len(sequence):
                action_id = sequence[state["completed"]]
                return {
                    action_id: {
                        "enabled": True,
                        "reason": f"{action_id} ready",
                    }
                }
            return {}

        def fake_run(action_id):
            self.assertEqual(action_id, sequence[state["completed"]])
            state["completed"] += 1
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_PERFORMANCE_GATE",
                    "current_title": "Review Voice Performance",
                },
            ),
            patch.object(
                automation,
                "run_action",
                side_effect=fake_run,
            ),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(result["completed_actions"], sequence)
        self.assertEqual(result["workflow_state"], "HUMAN_PERFORMANCE_GATE")
        self.assertEqual(result["message"], "Review Voice Performance")

    def test_performance_gate_completion_runs_free_preview_chain_to_listen_gate(self):
        state = {"completed": 0}
        sequence = [
            "pre_render_engagement",
            "narration_preview_prepare",
            "prototype_sound_prepare",
            "narration_preview_render",
        ]

        def readiness():
            if state["completed"] < len(sequence):
                action_id = sequence[state["completed"]]
                return {
                    action_id: {
                        "enabled": True,
                        "reason": f"{action_id} ready",
                    }
                }
            return {}

        def guidance(_readiness):
            if state["completed"] == len(sequence):
                return {
                    "state": "HUMAN_NARRATION_PREVIEW_GATE",
                    "current_title": "Listen to Free Audio Prototype",
                }
            return {
                "state": "ACTION_REQUIRED",
                "current_title": "Continue automatic preview preparation",
            }

        def fake_run(action_id):
            self.assertEqual(action_id, sequence[state["completed"]])
            state["completed"] += 1
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                side_effect=guidance,
            ),
            patch.object(
                automation,
                "run_action",
                side_effect=fake_run,
            ),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(result["completed_actions"], sequence)
        self.assertEqual(
            result["workflow_state"],
            "HUMAN_NARRATION_PREVIEW_GATE",
        )
        self.assertEqual(result["message"], "Listen to Free Audio Prototype")

    def test_preview_gate_blocks_stale_downstream_machine_action(self):
        readiness = {
            "narration_spend_gate_prepare": {
                "enabled": True,
                "reason": "stale prior quote still exists",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "HUMAN_NARRATION_PREVIEW_GATE",
                    "current_title": "Listen to Free Audio Prototype",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "HUMAN_NARRATION_PREVIEW_GATE",
        )

    def test_local_preview_partial_has_specific_fail_closed_message(self):
        readiness = {
            "narration_preview_render": {
                "enabled": True,
                "reason": "Render the free local Kokoro prototype for listening.",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "ACTION_REQUIRED",
                    "current_title": "Render preview",
                },
            ),
            patch.object(automation, "run_action", return_value=2),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("local Kokoro", result["message"])
        self.assertIn("paid fallback is forbidden", result["message"])

    def test_preview_approval_runs_cost_chain_to_human_spend_gate(self):
        state = {"completed": 0}
        sequence = [
            "sound_design_brief_prepare",
            "narration_prepare",
            "narration_spend_gate_prepare",
        ]

        def readiness():
            if state["completed"] < len(sequence):
                action_id = sequence[state["completed"]]
                return {
                    action_id: {
                        "enabled": True,
                        "reason": f"{action_id} ready",
                    }
                }
            return {}

        def guidance(_readiness):
            if state["completed"] == len(sequence):
                return {
                    "state": "HUMAN_NARRATION_SPEND_GATE",
                    "current_title": "Review Narration Spend",
                }
            return {
                "state": "ACTION_REQUIRED",
                "current_title": "Prepare narration cost boundary",
            }

        def fake_run(action_id):
            self.assertEqual(action_id, sequence[state["completed"]])
            state["completed"] += 1
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                side_effect=guidance,
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(result["completed_actions"], sequence)
        self.assertEqual(
            result["workflow_state"],
            "HUMAN_NARRATION_SPEND_GATE",
        )
        self.assertEqual(result["message"], "Review Narration Spend")

    def test_waiting_for_quote_blocks_downstream_visual_work(self):
        readiness = {
            "production_visual_prepare": {
                "enabled": True,
                "reason": "visual work would otherwise be ready",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "WAITING_NARRATION_PROVIDER_QUOTE",
                    "current_title": "Current Narration Quote Required",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "WAITING_NARRATION_PROVIDER_QUOTE",
        )

    def test_provider_setup_blocker_stops_before_visual_work(self):
        readiness = {
            "visual_search_prepare": {
                "enabled": True,
                "reason": "stale visual path is ready",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "NARRATION_PROVIDER_SETUP_REQUIRED",
                    "current_title": "Complete Narration Provider Setup",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "NARRATION_PROVIDER_SETUP_REQUIRED",
        )

    def test_spend_approval_waits_for_provider_audio_return(self):
        readiness = {
            "production_visual_prepare": {
                "enabled": True,
                "reason": "stale downstream visual work",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "WAITING_NARRATION_RENDER_RETURN",
                    "current_title": "Register Final Narration Audio",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "WAITING_NARRATION_RENDER_RETURN",
        )

    def test_registered_narration_runs_qc_then_stops_before_visuals(self):
        state = {"qc_done": False}

        def readiness():
            if not state["qc_done"]:
                return {
                    "narration_audio_qc": {
                        "enabled": True,
                        "reason": "current provider audio ready for QC",
                    },
                    "production_visual_prepare": {
                        "enabled": False,
                        "reason": "QC first",
                    },
                }
            return {
                "production_visual_prepare": {
                    "enabled": True,
                    "reason": "would be next after Slice 12",
                }
            }

        def guidance(_readiness):
            if state["qc_done"]:
                return {
                    "state": "NARRATION_AUDIO_READY",
                    "current_title": "Final Narration Audio Ready",
                }
            return {
                "state": "ACTION_REQUIRED",
                "current_title": "Run Narration Audio QC",
            }

        def fake_run(action_id):
            self.assertEqual(action_id, "narration_audio_qc")
            state["qc_done"] = True
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                side_effect=guidance,
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["completed_actions"],
            ["narration_audio_qc"],
        )
        self.assertEqual(
            result["workflow_state"],
            "NARRATION_AUDIO_READY",
        )

    def test_failed_narration_qc_blocks_visual_work(self):
        readiness = {
            "production_visual_prepare": {
                "enabled": True,
                "reason": "stale visual work",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "NARRATION_AUDIO_QC_FAILED",
                    "current_title": "Narration Audio QC Failed",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "NARRATION_AUDIO_QC_FAILED",
        )

    def test_audio_ready_runs_visual_plan_chain_then_stops_before_search(self):
        state = {"completed": 0}
        sequence = [
            "production_visual_prepare",
            "storyboard_prepare",
            "visual_search_prepare",
        ]

        def readiness():
            if state["completed"] < len(sequence):
                action_id = sequence[state["completed"]]
                return {
                    action_id: {
                        "enabled": True,
                        "reason": f"{action_id} ready",
                    }
                }
            return {
                "visual_search_acquire": {
                    "enabled": True,
                    "reason": "free search would be next",
                }
            }

        def guidance(_readiness):
            if state["completed"] == len(sequence):
                return {
                    "state": "VISUAL_SEARCH_READY",
                    "current_title": "Visual Search Plan Ready",
                }
            return {
                "state": "ACTION_REQUIRED",
                "current_title": "Build narration-bound visual plan",
            }

        def fake_run(action_id):
            self.assertEqual(
                action_id,
                sequence[state["completed"]],
            )
            state["completed"] += 1
            return 0

        with (
            patch.object(
                automation.control,
                "action_readiness",
                side_effect=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                side_effect=guidance,
            ),
            patch.object(automation, "run_action", side_effect=fake_run),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(result["completed_actions"], sequence)
        self.assertNotIn("visual_search_acquire", result["completed_actions"])
        self.assertEqual(
            result["workflow_state"],
            "VISUAL_SEARCH_READY",
        )

    def test_visual_search_ready_blocks_stale_search_adapter_action(self):
        readiness = {
            "visual_search_acquire": {
                "enabled": True,
                "reason": "search adapter is ready",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(
                automation.control,
                "workflow_guidance",
                return_value={
                    "state": "VISUAL_SEARCH_READY",
                    "current_title": "Visual Search Plan Ready",
                },
            ),
            patch.object(automation, "run_action") as run_action,
        ):
            result = automation.run_until_human_gate()

        run_action.assert_not_called()
        self.assertEqual(result["status"], "STOPPED_AT_BOUNDARY")
        self.assertEqual(
            result["workflow_state"],
            "VISUAL_SEARCH_READY",
        )

    def test_partial_command_without_progress_stops_as_partial(self):
        readiness = {
            "concept_generate": {
                "enabled": True,
                "reason": "Concept generation progress: 2/5 current responses.",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(automation, "run_action", return_value=2),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["return_code"], 2)
        self.assertEqual(result["failed_action"], "concept_generate")
        self.assertIn("Retry Continue Automatically later", result["message"])

    def test_stops_if_successful_command_makes_no_progress(self):
        readiness = {
            "exp2_prepare": {
                "enabled": True,
                "reason": "still ready",
            }
        }
        with (
            patch.object(
                automation.control,
                "action_readiness",
                return_value=readiness,
            ),
            patch.object(automation, "run_action", return_value=0),
        ):
            result = automation.run_until_human_gate()

        self.assertEqual(result["status"], "NO_PROGRESS")
        self.assertEqual(result["failed_action"], "exp2_prepare")


if __name__ == "__main__":
    unittest.main()
