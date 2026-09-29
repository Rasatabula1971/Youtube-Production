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
