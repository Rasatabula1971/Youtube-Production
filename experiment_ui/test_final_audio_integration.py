"""The Final Audio Gate holds visual work until the paid audio is approved (D-137)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import server
import workflow_automation
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()


class FinalAudioIntegrationTests(unittest.TestCase):
    def narration_state(self, final):
        patches = [
            patch.object(server, "voice_performance_artifact_state", return_value={"visual_ready": True}),
            patch.object(server, "narration_render_snapshot", return_value={}),
            patch.object(server, "narration_spend_gate_snapshot", return_value={}),
            patch.object(server, "narration_render_return_snapshot", return_value={"expected": 1, "current": 1}),
            patch.object(server, "narration_audio_qc_snapshot", return_value={"status": "PASS", "processed": 1, "passed": 1}),
            patch.object(server.narration_final_review, "snapshot", return_value=final),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return server.narration_artifact_state()

    def test_qc_pass_alone_no_longer_makes_audio_ready(self):
        state = self.narration_state({"status": "AWAITING_HUMAN_FINAL_AUDIO", "complete": False, "items": []})
        self.assertTrue(state["audio_qc_passed"])
        self.assertFalse(state["audio_ready"])

    def test_human_approval_makes_audio_ready(self):
        state = self.narration_state({"status": "FINAL_AUDIO_APPROVED", "complete": True, "items": []})
        self.assertTrue(state["audio_ready"])

    def test_gate_is_a_locked_route_and_a_workflow_stop(self):
        self.assertIn("/api/final-audio-gate", server.HUMAN_GATE_MUTATION_ROUTES)
        with patch.object(server.JOB_MANAGER, "running", return_value=True):
            self.assertIsNotNone(server.human_gate_mutation_block_reason("/api/final-audio-gate"))
        source = (server.PROJECT_ROOT / "experiment_ui" / "workflow_automation.py").read_text(encoding="utf-8")
        for state in ("HUMAN_FINAL_AUDIO_GATE", "FINAL_AUDIO_REWORK_REQUIRED"):
            self.assertIn(f'"{state}"', source)
        self.assertTrue(callable(workflow_automation.run_until_human_gate))


if __name__ == "__main__":
    unittest.main()
