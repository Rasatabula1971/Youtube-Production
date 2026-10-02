from __future__ import annotations

import unittest
from unittest.mock import patch

import server


class VoicePerformanceUiIntegrationTests(unittest.TestCase):
    def test_voice_actions_run_before_visual_manifest(self) -> None:
        for action_id in ("voice_prepare", "voice_generate", "voice_gate_prepare"):
            self.assertIn(action_id, server.ACTION_DEFS)
            self.assertIn(action_id, server.AUTO_MACHINE_ACTION_ORDER)

        format_gate_index = server.AUTO_MACHINE_ACTION_ORDER.index(
            "format_gate_prepare"
        )
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[
                format_gate_index + 1 : format_gate_index + 13
            ],
            [
                "voice_prepare",
                "voice_generate",
                "voice_gate_prepare",
                "pre_render_engagement",
                "narration_preview_prepare",
                "prototype_sound_prepare",
                "narration_preview_render",
                "sound_design_brief_prepare",
                "narration_prepare",
                "narration_spend_gate_prepare",
                "narration_audio_qc",
                "production_visual_prepare",
            ],
        )

    def test_static_ui_contains_performance_gate(self) -> None:
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="performanceReviewPanel"', html)
        self.assertIn('id="performanceCriteria"', html)
        self.assertIn("HUMAN PERFORMANCE GATE", html)
        self.assertIn("renderPerformanceReview", script)
        self.assertIn("/api/performance-gate", script)

    def test_performance_accept_ui_announces_automatic_free_preview(self) -> None:
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            'payload.automation_job.action_id === "auto_continue"',
            script,
        )
        self.assertIn(
            "Performance Gate complete. Free narration preview started automatically.",
            script,
        )

    def test_pending_performance_gate_is_human_boundary(self) -> None:
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
                    "specs_ready": True,
                    "performance_gate": {
                        "status": "AWAITING_HUMAN_DECISION",
                        "complete": False,
                    },
                },
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "HUMAN_PERFORMANCE_GATE")
        self.assertEqual(workflow["current_title"], "Review Voice Performance")
        self.assertIn("spends no provider credits", workflow["current_detail"])


if __name__ == "__main__":
    unittest.main()
