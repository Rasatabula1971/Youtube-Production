from __future__ import annotations

import unittest
from unittest.mock import patch

import server


class FormatUiIntegrationTests(unittest.TestCase):
    def test_format_actions_are_in_automatic_machine_order(self):
        for action_id in ("format_prepare", "format_generate", "format_gate_prepare"):
            self.assertIn(action_id, server.ACTION_DEFS)
            self.assertIn(action_id, server.AUTO_MACHINE_ACTION_ORDER)

        script_index = server.AUTO_MACHINE_ACTION_ORDER.index("script_gate_prepare")
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[script_index + 1 : script_index + 11],
            [
                "format_prepare",
                "format_generate",
                "format_gate_prepare",
                "voice_prepare",
                "voice_generate",
                "voice_gate_prepare",
                "narration_prepare",
                "narration_spend_gate_prepare",
                "narration_audio_qc",
                "production_visual_prepare",
            ],
        )
        self.assertIn("format_output", server.OPEN_TARGETS)
        self.assertIn("production_output", server.OPEN_TARGETS)
        self.assertIn("production_visual_prepare", server.ACTION_DEFS)
        self.assertIn(
            "production_engine/visual_acquisition.py",
            server.ACTION_DEFS["production_visual_prepare"]["command"][1],
        )

    def test_static_ui_contains_format_gate(self):
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="formatReviewPanel"', html)
        self.assertIn('id="formatCriteria"', html)
        self.assertIn('id="formatNote"', html)
        self.assertIn(">Format</span>", html)
        self.assertIn("renderFormatReview", script)
        self.assertIn("/api/format-gate", script)

    def test_pending_format_gate_is_a_human_boundary(self):
        with (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={"ready_for_experiment_02": True, "opportunities": []},
            ),
            patch.object(
                server,
                "opportunity_research_state",
                return_value={},
            ),
            patch.object(
                server,
                "vision_review_snapshot",
                return_value={"awaiting_human_review": False, "complete": True},
            ),
            patch.object(
                server,
                "human_analysis_review_snapshot",
                return_value={"status": "COMPLETE"},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "concept_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "packaging_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "research_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "story_script_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "script_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "format_artifact_state",
                return_value={
                    "plans_ready": True,
                    "format_gate": {"status": "AWAITING_HUMAN_DECISION"},
                },
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "HUMAN_FORMAT_GATE")
        self.assertEqual(workflow["current_title"], "Review Format Plan")


    def test_visual_manifest_ready_is_next_production_boundary(self):
        with (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={"ready_for_experiment_02": True, "opportunities": []},
            ),
            patch.object(server, "opportunity_research_state", return_value={}),
            patch.object(
                server,
                "vision_review_snapshot",
                return_value={"awaiting_human_review": False, "complete": True},
            ),
            patch.object(
                server,
                "human_analysis_review_snapshot",
                return_value={"status": "COMPLETE"},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "concept_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "packaging_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "research_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "story_script_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "script_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "format_artifact_state",
                return_value={
                    "plans_ready": True,
                    "production_engine_ready": True,
                    "format_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "voice_performance_artifact_state",
                return_value={
                    "visual_ready": True,
                    "specs_ready": True,
                    "performance_gate": {"status": "COMPLETE", "complete": True},
                },
            ),
            patch.object(
                server,
                "production_visual_artifact_state",
                return_value={"manifests_ready": True},
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "VISUAL_ACQUISITION_REQUIRED")
        self.assertEqual(
            workflow["current_title"],
            "Visual acquisition manifest ready",
        )

if __name__ == "__main__":
    unittest.main()
