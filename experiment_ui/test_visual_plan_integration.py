"""The Visual Plan Gate holds narration spend (D-138)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import server
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()


class VisualPlanIntegrationTests(unittest.TestCase):
    def test_narration_spend_accept_needs_an_approved_plan(self):
        body = {"concept_id": "c1", "format": "short", "decision": "ACCEPT"}
        with patch.object(server.visual_plan_review, "is_approved", return_value=False):
            with self.assertRaisesRegex(ValueError, "Approve the visual plan"):
                server.require_visual_plan_for_spend(body)
            server.require_visual_plan_for_spend({**body, "decision": "REJECT"})
        with patch.object(server.visual_plan_review, "is_approved", return_value=True):
            server.require_visual_plan_for_spend(body)

    def test_videos_already_spent_are_not_pulled_back(self):
        spend = {"items": [{"concept_id": "c1", "format": "short", "decision": "ACCEPT"}]}
        plans = {"items": [
            {"concept_id": "c1", "format": "short", "decision": "PENDING"},
            {"concept_id": "c2", "format": "short", "decision": "PENDING"},
        ]}
        blocking = server.visual_plan_blocking_items(spend, plans)
        self.assertEqual([item["concept_id"] for item in blocking], ["c2"])

    def test_gate_route_is_locked_and_a_workflow_stop(self):
        self.assertIn("/api/visual-plan-gate", server.HUMAN_GATE_MUTATION_ROUTES)
        source = (server.PROJECT_ROOT / "experiment_ui" / "workflow_automation.py").read_text(encoding="utf-8")
        for state in ("HUMAN_VISUAL_PLAN_GATE", "VISUAL_PLAN_REWORK_REQUIRED"):
            self.assertIn(f'"{state}"', source)


if __name__ == "__main__":
    unittest.main()
