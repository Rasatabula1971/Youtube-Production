"""Publishing is a locked human route and a workflow stop (D-142, D-143)."""

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


class PublishIntegrationTests(unittest.TestCase):
    def test_route_is_locked_during_jobs(self):
        self.assertIn("/api/publish-gate", server.HUMAN_GATE_MUTATION_ROUTES)
        with patch.object(server.JOB_MANAGER, "running", return_value=True):
            self.assertIsNotNone(server.human_gate_mutation_block_reason("/api/publish-gate"))

    def test_states_stop_the_workflow(self):
        source = (server.PROJECT_ROOT / "experiment_ui" / "workflow_automation.py").read_text(encoding="utf-8")
        for state in ("HUMAN_PUBLISH_GATE", "WAITING_FOR_UPLOAD", "PUBLISHED"):
            self.assertIn(f'"{state}"', source)

    def test_publish_state_degrades_instead_of_raising(self):
        with patch.object(server.publish_review, "snapshot", side_effect=ValueError("boom")):
            state = server.publish_gate_state()
        self.assertEqual(state["status"], "ERROR")
        self.assertFalse(state["uploader"]["ready"])


if __name__ == "__main__":
    unittest.main()
