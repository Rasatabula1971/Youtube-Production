import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import server


class ExperimentUiTests(unittest.TestCase):
    def test_send_json_ignores_client_disconnect(self):
        class DisconnectingWriter:
            def write(self, _body):
                raise ConnectionAbortedError("browser disconnected")

        class FakeHandler:
            wfile = DisconnectingWriter()

            def send_response(self, _status):
                pass

            def send_header(self, _name, _value):
                pass

            def end_headers(self):
                pass

        server.Handler._send_json(FakeHandler(), {"status": "ok"})

    def test_human_gate_mutations_are_locked_while_job_runs(self):
        with patch.object(server.JOB_MANAGER, "running", return_value=True):
            for route in server.HUMAN_GATE_MUTATION_ROUTES:
                self.assertIsNotNone(
                    server.human_gate_mutation_block_reason(route)
                )
            self.assertIsNone(
                server.human_gate_mutation_block_reason("/api/stop")
            )

    def test_ui_v3_routes_are_registered(self):
        self.assertEqual(
            server.APP_ROUTES,
            {
                "/",
                "/opportunity",
                "/opportunity/review",
                "/radar",
                "/production",
                "/review",
                "/packaging",
                "/analysis",
                "/productions",
                "/tools",
            },
        )


    def test_script_gate_route_starts_automatic_downstream_work(self):
        source = (server.HERE / "server.py").read_text(encoding="utf-8")
        post_start = source.index("def do_POST")
        start = source.index(
            'if route == "/api/script-gate":',
            post_start,
        )
        end = source.index(
            'if route == "/api/script-section-review":',
            start,
        )
        block = source[start:end]

        self.assertIn("maybe_start_automatic_workflow()", block)
        self.assertIn('"automation_job": auto_job', block)

    def test_script_section_review_route_is_human_gate_guarded(self):
        self.assertIn(
            "/api/script-section-review",
            server.HUMAN_GATE_MUTATION_ROUTES,
        )
        source = (server.HERE / "server.py").read_text(encoding="utf-8")
        self.assertIn('route == "/api/script-section-review"', source)
        self.assertIn("apply_script_section_review_action", source)

    def test_script_section_review_route_forwards_restore_version_id(self):
        source = (server.HERE / "server.py").read_text(encoding="utf-8")
        post_start = source.index("def do_POST")
        start = source.index('if route == "/api/script-section-review":', post_start)
        end = source.index('if route == "/api/format-gate":', start)
        block = source[start:end]
        self.assertIn('version_id=(', block)
        self.assertIn('body["version_id"]', block)


    def test_research_gate_route_dispatches_question_waivers(self):
        source = (server.HERE / "server.py").read_text(encoding="utf-8")
        post_start = source.index("def do_POST")
        start = source.index('if route == "/api/research-gate" and body.get("action")', post_start)
        end = source.index('if route == "/api/research-gate":', start)
        block = source[start:end]
        self.assertIn('"WAIVE_QUESTION"', block)
        self.assertIn("apply_research_question_waiver(", block)
        self.assertIn('question_id=str(body.get("question_id", ""))', block)
        self.assertIn("maybe_start_automatic_workflow()", block)
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="researchCoverage"', html)
        self.assertIn("renderResearchCoverage", script)
        self.assertIn("Not needed for script", script)

    def test_script_gate_supports_direct_edit_and_wholesale_accept(self):
        source = (server.HERE / "server.py").read_text(encoding="utf-8")
        post_start = source.index("def do_POST")
        start = source.index('if route == "/api/script-gate":', post_start)
        block = source[start:start + 900]
        self.assertIn('accept_open_sections=body.get("accept_open_sections") is True', block)
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-edit-target", script)
        self.assertIn("editScriptTarget", script)
        self.assertIn("accept_open_sections: acceptOpenSections", script)
        self.assertIn('id="scriptSectionManualEditor"', html)

    def test_ui_v3_static_shell_has_four_views_and_job_drawer(self):
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")

        for view in ("home", "opportunity", "analysis", "tools"):
            self.assertIn(f'data-view="{view}"', html)

        self.assertIn('id="jobDrawer"', html)
        self.assertIn('id="visionReviewPanel"', html)
        self.assertIn('id="visionFrameImage"', html)
        self.assertIn('id="visionObservation"', html)
        self.assertIn('id="conceptReviewPanel"', html)
        self.assertIn('id="conceptCriteria"', html)
        self.assertIn('id="conceptNote"', html)
        self.assertIn('id="packagingReviewPanel"', html)
        self.assertIn('id="packagingCriteria"', html)
        self.assertIn('id="packagingNote"', html)
        self.assertIn('id="titleDirectionReviewPanel"', html)
        self.assertIn('id="titleDirectionDetail"', html)
        self.assertIn('id="titleDirectionAccept"', html)
        self.assertIn('id="researchReviewPanel"', html)
        self.assertIn('id="researchCriteria"', html)
        self.assertIn('id="researchNote"', html)
        self.assertIn('id="scriptSectionReviewPane"', html)
        self.assertIn('id="scriptSectionTarget"', html)
        self.assertIn('id="scriptSectionManualText"', html)
        self.assertIn('id="scriptSectionSaveManual"', html)
        self.assertIn('id="scriptSectionReason"', html)
        self.assertIn('id="scriptSectionGenerate"', html)
        self.assertIn('id="scriptSectionAlternativeCards"', html)
        self.assertIn('id="finalSoundImportPanel"', html)
        self.assertIn('id="finalSoundLicenceReference"', html)
        self.assertIn('id="finalSoundCommercialUse"', html)
        self.assertIn('id="finalExportReviewPanel"', html)
        self.assertIn('id="finalExportVideo"', html)
        self.assertIn('id="finalExportApprove"', html)
        self.assertIn('data-route="/opportunity"', html)
        self.assertIn('data-route="/analysis"', html)
        self.assertIn('data-route="/tools"', html)

        self.assertIn('"/opportunity"', script)
        self.assertIn('"/analysis"', script)
        self.assertIn('"/tools"', script)
        self.assertIn("openJobDrawer", script)
        self.assertIn("renderVisionReview", script)
        self.assertIn("/api/vision-review", script)
        self.assertIn("renderConceptReview", script)
        self.assertIn("/api/concept-gate", script)
        self.assertIn("renderPackagingReview", script)
        self.assertIn("/api/packaging-gate", script)
        self.assertIn("renderTitleDirectionReview", script)
        self.assertIn("/api/title-direction-gate", script)
        self.assertIn('id="packagingBriefPanel"', html)
        self.assertIn("renderPackagingBrief", script)
        self.assertIn("THUMBNAIL_CONCEPTS_READY", script)
        self.assertIn("PACKAGE_VALIDATION_READY", script)
        self.assertIn("psychological_angles", script)
        self.assertIn("thumbnail_concepts", script)
        self.assertIn("package_validation", script)
        self.assertIn("renderResearchReview", script)
        self.assertIn("/api/research-gate", script)
        self.assertIn("renderScriptSectionReview", script)
        self.assertIn("submitScriptSectionAction", script)
        self.assertIn('"MANUAL_EDIT"', script)
        self.assertIn("replacement_text", script)
        self.assertIn("/api/script-section-review", script)
        self.assertIn("data-script-section-selection", script)
        self.assertIn("renderFinalSoundImport", script)
        self.assertIn("/api/final-sound-asset", script)
        self.assertIn("renderFinalExportReview", script)
        self.assertIn("/api/final-export-review", script)
        self.assertIn("/api/final-render-video", script)

    def test_title_direction_route_is_human_gate_guarded(self):
        self.assertIn(
            "/api/title-direction-gate",
            server.HUMAN_GATE_MUTATION_ROUTES,
        )
        for action_id in (
            "title_direction_prepare",
            "title_direction_generate",
            "title_direction_gate_prepare",
            "packaging_brief_prepare",
            "psychological_angle_prepare",
            "psychological_angle_generate",
            "thumbnail_concept_prepare",
            "thumbnail_concept_generate",
            "package_pairing_prepare",
            "package_pairing_generate",
        ):
            self.assertIn(action_id, server.ACTION_DEFS)

        script_index = server.AUTO_MACHINE_ACTION_ORDER.index(
            "script_gate_prepare"
        )
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[
                script_index + 1 : script_index + 11
            ],
            [
                "title_direction_prepare",
                "title_direction_generate",
                "title_direction_gate_prepare",
                "packaging_brief_prepare",
                "psychological_angle_prepare",
                "psychological_angle_generate",
                "thumbnail_concept_prepare",
                "thumbnail_concept_generate",
                "package_pairing_prepare",
                "package_pairing_generate",
            ],
        )

    def test_final_sound_route_is_human_gate_guarded(self):
        self.assertIn(
            "/api/final-sound-asset",
            server.HUMAN_GATE_MUTATION_ROUTES,
        )
        self.assertIn("final_sound_plan_prepare", server.ACTION_DEFS)
        self.assertIn(
            "production_engine/final_sound_plan.py",
            server.ACTION_DEFS["final_sound_plan_prepare"]["command"][1],
        )

    def test_final_export_route_is_human_gate_guarded(self):
        self.assertIn(
            "/api/final-export-review",
            server.HUMAN_GATE_MUTATION_ROUTES,
        )
        self.assertIn("final_render_manifest_prepare", server.ACTION_DEFS)
        self.assertIn("final_render_local", server.ACTION_DEFS)
        self.assertIn(
            "production_engine/final_render_manifest.py",
            server.ACTION_DEFS[
                "final_render_manifest_prepare"
            ]["command"][1],
        )
        self.assertIn(
            "production_engine/final_render.py",
            server.ACTION_DEFS["final_render_local"]["command"][1],
        )

    def test_action_allowlist_contains_no_shell_strings(self):
        self.assertIn("exp13_discover", server.ACTION_DEFS)
        self.assertIn("exp13_restart", server.ACTION_DEFS)
        self.assertIn("exp13_auto_refresh_install", server.ACTION_DEFS)
        self.assertIn("exp13_auto_refresh_remove", server.ACTION_DEFS)
        self.assertIn(
            "--restart-discovery",
            server.ACTION_DEFS["exp13_restart"]["command"],
        )
        self.assertIn(
            "scripts/install_experiment_01_3_auto_refresh.ps1",
            server.ACTION_DEFS["exp13_auto_refresh_install"]["command"],
        )
        self.assertIn(
            "scripts/remove_experiment_01_3_auto_refresh.ps1",
            server.ACTION_DEFS["exp13_auto_refresh_remove"]["command"],
        )
        for action in server.ACTION_DEFS.values():
            self.assertIsInstance(action["command"], list)
            self.assertTrue(action["command"])
            self.assertFalse(
                any(part in {"cmd", "powershell"} for part in action["command"])
            )

    def test_guided_opportunity_action_is_present(self):
        self.assertIn("opportunity_research", server.ACTION_DEFS)
        self.assertIn(
            "opportunity_research.py",
            server.ACTION_DEFS["opportunity_research"]["command"][1],
        )
        self.assertIn(
            "opportunity_research",
            server.WORKFLOW_ACTION_ORDER,
        )

    def test_main_workflow_uses_one_automatic_downstream_action(self):
        self.assertEqual(
            server.WORKFLOW_ACTION_ORDER,
            ["opportunity_research", "auto_continue"],
        )
        self.assertIn("auto_continue", server.ACTION_DEFS)
        self.assertIn(
            "workflow_automation.py",
            server.ACTION_DEFS["auto_continue"]["command"][1],
        )


    def test_completed_human_gate_starts_auto_continue_when_machine_work_is_ready(self):
        with (
            patch.object(server.JOB_MANAGER, "running", return_value=False),
            patch.object(
                server,
                "action_readiness",
                return_value={
                    "auto_continue": {
                        "enabled": True,
                        "reason": "Automatic machine work is ready: Prepare Format Requests",
                    }
                },
            ),
            patch.object(
                server.JOB_MANAGER,
                "start",
                return_value={
                    "action_id": "auto_continue",
                    "status": "RUNNING",
                },
            ) as start,
        ):
            job = server.maybe_start_automatic_workflow()

        start.assert_called_once_with("auto_continue")
        self.assertEqual(job["action_id"], "auto_continue")
        self.assertEqual(job["status"], "RUNNING")

    def test_completed_human_gate_does_not_start_job_without_ready_machine_step(self):
        with (
            patch.object(server.JOB_MANAGER, "running", return_value=False),
            patch.object(
                server,
                "action_readiness",
                return_value={
                    "auto_continue": {
                        "enabled": False,
                        "reason": "Waiting at a human gate.",
                    }
                },
            ),
            patch.object(server.JOB_MANAGER, "start") as start,
        ):
            job = server.maybe_start_automatic_workflow()

        start.assert_not_called()
        self.assertIsNone(job)

    def test_experiment_02_evidence_acquisition_is_guided_step(self):
        self.assertIn("exp2_acquire", server.ACTION_DEFS)
        self.assertIn(
            "source_acquisition/experiment_02_evidence.py",
            server.ACTION_DEFS["exp2_acquire"]["command"][1],
        )
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[
                server.AUTO_MACHINE_ACTION_ORDER.index("exp2_prepare") + 1
            ],
            "exp2_acquire",
        )

    def test_transformation_concept_actions_follow_synthesis(self):
        for action_id in (
            "transform_prepare",
            "concept_generate",
            "concept_gate_prepare",
        ):
            self.assertIn(action_id, server.ACTION_DEFS)

        synthesis_index = server.AUTO_MACHINE_ACTION_ORDER.index("synthesis_build")
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[synthesis_index + 1 : synthesis_index + 5],
            [
                "transform_prepare",
                "concept_generate",
                "concept_triage",
                "concept_gate_prepare",
            ],
        )
        self.assertIn(
            "transformation_engine/transformation_engine.py",
            server.ACTION_DEFS["transform_prepare"]["command"][1],
        )
        self.assertIn(
            "transformation_engine/concept_model_runner.py",
            server.ACTION_DEFS["concept_generate"]["command"][1],
        )
        self.assertIn(
            "transformation_engine/concept_review.py",
            server.ACTION_DEFS["concept_gate_prepare"]["command"][1],
        )

    def test_legacy_packaging_actions_are_retained_but_not_in_active_order(self):
        for action_id in (
            "package_prepare",
            "package_generate",
            "package_gate_prepare",
        ):
            self.assertIn(action_id, server.ACTION_DEFS)
            self.assertNotIn(action_id, server.AUTO_MACHINE_ACTION_ORDER)

        self.assertIn(
            "packaging_engine/packaging_engine.py",
            server.ACTION_DEFS["package_prepare"]["command"][1],
        )
        self.assertIn(
            "packaging_engine/package_model_runner.py",
            server.ACTION_DEFS["package_generate"]["command"][1],
        )
        self.assertIn(
            "packaging_engine/package_review.py",
            server.ACTION_DEFS["package_gate_prepare"]["command"][1],
        )

    def test_research_actions_follow_concept_gate_directly(self):
        for action_id in (
            "research_prepare",
            "research_acquire",
            "research_generate",
            "research_gate_prepare",
        ):
            self.assertIn(action_id, server.ACTION_DEFS)

        concept_index = server.AUTO_MACHINE_ACTION_ORDER.index("concept_gate_prepare")
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[concept_index + 1 : concept_index + 5],
            [
                "research_prepare",
                "research_acquire",
                "research_generate",
                "research_gate_prepare",
            ],
        )
        self.assertIn(
            "research_engine/research_engine.py",
            server.ACTION_DEFS["research_prepare"]["command"][1],
        )
        self.assertIn(
            "research_engine/research_acquisition.py",
            server.ACTION_DEFS["research_acquire"]["command"][1],
        )
        self.assertIn(
            "research_engine/research_model_runner.py",
            server.ACTION_DEFS["research_generate"]["command"][1],
        )
        self.assertIn(
            "research_engine/research_review.py",
            server.ACTION_DEFS["research_gate_prepare"]["command"][1],
        )

    def test_pending_research_gate_becomes_human_workflow_gate(self):
        with (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={
                    "ready_for_experiment_02": True,
                    "opportunities": [],
                },
            ),
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
                "opportunity_research_state",
                return_value={},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "research_ready": True,
                    "concept_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "research_ready": True,
                    "packaging_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "research_gate": {
                        "status": "AWAITING_HUMAN_DECISION",
                    },
                },
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "HUMAN_RESEARCH_GATE")
        self.assertEqual(
            workflow["current_title"],
            "Review Research Claims",
        )

    def test_legacy_pending_packaging_gate_does_not_block_research(self):
        with (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={
                    "ready_for_experiment_02": True,
                    "opportunities": [],
                },
            ),
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
                "opportunity_research_state",
                return_value={},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "research_ready": True,
                    "concept_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "packaging_gate": {
                        "status": "AWAITING_HUMAN_DECISION",
                    },
                },
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "research_gate": {
                        "status": "AWAITING_HUMAN_DECISION",
                    },
                },
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "HUMAN_RESEARCH_GATE")

    def test_pending_concept_gate_becomes_human_workflow_gate(self):
        with (
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={
                    "ready_for_experiment_02": True,
                    "opportunities": [],
                },
            ),
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
                "opportunity_research_state",
                return_value={},
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={
                    "candidates_ready": True,
                    "concept_gate": {
                        "status": "AWAITING_HUMAN_DECISION",
                    },
                },
            ),
        ):
            workflow = server.workflow_guidance({})

        self.assertEqual(workflow["state"], "HUMAN_CONCEPT_GATE")
        self.assertEqual(
            workflow["current_title"],
            "Review Concept Candidates",
        )

    def test_exp2_acquisition_requires_prepared_profiles_and_transcript_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                review_requests,
                reviewed,
            ):
                path.mkdir()

            profile = prepared / "v1.json"
            profile.write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(
                    server,
                    "EXP2_REVIEW_REQUESTS_DIR",
                    review_requests,
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                patch.object(
                    server,
                    "EXP2_SYNTHESIS_FILE",
                    root / "missing_synthesis.json",
                ),
                patch.object(
                    server,
                    "EXP2_ACQUISITION_SUMMARY",
                    root / "missing_acquisition.json",
                ),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": True,
                        "opportunities": [],
                    },
                ),
                patch.object(
                    server.shutil,
                    "which",
                    side_effect=lambda name: (
                        "C:/fake/yt-dlp.exe" if name == "yt-dlp" else None
                    ),
                ),
            ):
                readiness = server.action_readiness()

                self.assertFalse(readiness["exp2_prepare"]["enabled"])
                self.assertTrue(readiness["exp2_acquire"]["enabled"])
                self.assertFalse(readiness["analysis_batch_prepare"]["enabled"])

                enriched_profile = enriched / "v1.json"
                enriched_profile.write_text(
                    json.dumps(
                        {
                            "source_inputs": {"transcript": {"status": "PROVIDED"}},
                            "evidence": [
                                {
                                    "evidence_id": "transcript.p0001",
                                    "type": "transcript",
                                    "observation": "Ready.",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

                readiness = server.action_readiness()
                self.assertFalse(readiness["exp2_acquire"]["enabled"])
                self.assertTrue(readiness["analysis_batch_prepare"]["enabled"])

    def test_experiment_02_visual_structure_is_guided_after_source_evidence(self):
        self.assertIn("exp2_visual", server.ACTION_DEFS)
        self.assertIn(
            "source_acquisition/experiment_02_visual.py",
            server.ACTION_DEFS["exp2_visual"]["command"][1],
        )
        acquire_index = server.AUTO_MACHINE_ACTION_ORDER.index("exp2_acquire")
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[acquire_index + 1],
            "exp2_visual",
        )

    def test_visual_review_is_guided_after_visual_structure(self):
        self.assertIn("exp2_vision_prepare", server.ACTION_DEFS)
        self.assertIn(
            "experiment_02_analysis/vision_review.py",
            server.ACTION_DEFS["exp2_vision_prepare"]["command"][1],
        )
        visual_index = server.AUTO_MACHINE_ACTION_ORDER.index("exp2_visual")
        self.assertEqual(
            server.AUTO_MACHINE_ACTION_ORDER[visual_index + 1],
            "exp2_vision_prepare",
        )

    def test_visual_structure_blocks_analysis_when_dependencies_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            model_runs = root / "model_runs"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            source_output = root / "source_output"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                model_runs,
                review_requests,
                reviewed,
                source_output,
            ):
                path.mkdir()

            prepared_profile = prepared / "v1.json"
            prepared_profile.write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )
            (enriched / "v1.json").write_text(
                json.dumps(
                    {
                        "source_inputs": {"transcript": {"status": "PROVIDED"}},
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Evidence.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with ExitStack() as stack:
                for context in (
                    patch.object(server, "EXP2_PREPARED_DIR", prepared),
                    patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                    patch.object(server, "EXP2_REQUESTS_DIR", requests),
                    patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                    patch.object(server, "EXP2_MODEL_RUNS_DIR", model_runs),
                    patch.object(
                        server,
                        "EXP2_REVIEW_REQUESTS_DIR",
                        review_requests,
                    ),
                    patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                    patch.object(server, "SOURCE_ACQ_OUTPUT", source_output),
                    patch.object(
                        server,
                        "EXP2_SYNTHESIS_FILE",
                        root / "missing_synthesis.json",
                    ),
                    patch.object(
                        server,
                        "EXP2_ACQUISITION_SUMMARY",
                        root / "missing_acquisition.json",
                    ),
                    patch.object(
                        server,
                        "EXP2_VISUAL_SUMMARY",
                        root / "missing_visual.json",
                    ),
                    patch.object(
                        server,
                        "opportunity_gate_snapshot",
                        return_value={
                            "ready_for_experiment_02": True,
                            "opportunities": [],
                        },
                    ),
                    patch.object(
                        server.shutil,
                        "which",
                        side_effect=lambda name: (
                            f"C:/fake/{name}.exe"
                            if name in {"yt-dlp", "ffmpeg"}
                            else None
                        ),
                    ),
                ):
                    stack.enter_context(context)

                readiness = server.action_readiness()
                self.assertTrue(readiness["exp2_visual"]["enabled"])
                self.assertFalse(readiness["analysis_batch_prepare"]["enabled"])

                report_dir = source_output / "experiment_02" / "v1"
                report_dir.mkdir(parents=True)
                (report_dir / "visual_analysis.json").write_text(
                    json.dumps(
                        {
                            "status": "READY",
                            "profile_sha256": server.sha256_file(prepared_profile),
                        }
                    ),
                    encoding="utf-8",
                )
                (enriched / "v1.json").write_text(
                    json.dumps(
                        {
                            "source_inputs": {"transcript": {"status": "PROVIDED"}},
                            "evidence": [
                                {
                                    "evidence_id": "transcript.p0001",
                                    "type": "transcript",
                                    "observation": "Evidence.",
                                },
                                {
                                    "evidence_id": "timing.scene_change_summary",
                                    "type": "timing_note",
                                    "observation": "Detector summary.",
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

                readiness = server.action_readiness()
                self.assertFalse(readiness["exp2_visual"]["enabled"])
                self.assertTrue(readiness["exp2_vision_prepare"]["enabled"])
                self.assertFalse(readiness["analysis_batch_prepare"]["enabled"])

    def test_pending_visual_review_becomes_human_workflow_gate(self):
        with (
            patch.object(
                server,
                "vision_review_snapshot",
                return_value={
                    "status": "AWAITING_HUMAN_REVIEW",
                    "awaiting_human_review": True,
                    "complete": False,
                    "packets": [],
                },
            ),
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={
                    "ready_for_experiment_02": True,
                    "opportunities": [],
                },
            ),
        ):
            workflow = server.workflow_guidance(server.action_readiness())

        self.assertEqual(workflow["state"], "HUMAN_VISION_GATE")
        self.assertEqual(
            workflow["current_title"],
            "Review Visual Evidence",
        )
        self.assertEqual(
            workflow["next_action_id"],
            "auto_continue",
        )

    def test_completed_visual_review_can_unlock_analysis_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            model_runs = root / "model_runs"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            source_output = root / "source_output"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                model_runs,
                review_requests,
                reviewed,
                source_output,
            ):
                path.mkdir()

            prepared_profile = prepared / "v1.json"
            prepared_profile.write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )
            (enriched / "v1.json").write_text(
                json.dumps(
                    {
                        "source_inputs": {"transcript": {"status": "PROVIDED"}},
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Evidence.",
                            },
                            {
                                "evidence_id": "timing.scene_change_summary",
                                "type": "timing_note",
                                "observation": "Detector summary.",
                            },
                            {
                                "evidence_id": "visual.scene_0001",
                                "type": "visual_note",
                                "observation": "A tyre fills the frame.",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report_dir = source_output / "experiment_02" / "v1"
            report_dir.mkdir(parents=True)
            (report_dir / "visual_analysis.json").write_text(
                json.dumps(
                    {
                        "status": "READY",
                        "profile_sha256": server.sha256_file(prepared_profile),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(server, "EXP2_MODEL_RUNS_DIR", model_runs),
                patch.object(
                    server,
                    "EXP2_REVIEW_REQUESTS_DIR",
                    review_requests,
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                patch.object(server, "SOURCE_ACQ_OUTPUT", source_output),
                patch.object(
                    server,
                    "EXP2_SYNTHESIS_FILE",
                    root / "missing_synthesis.json",
                ),
                patch.object(
                    server,
                    "EXP2_ACQUISITION_SUMMARY",
                    root / "missing_acquisition.json",
                ),
                patch.object(
                    server,
                    "EXP2_VISUAL_SUMMARY",
                    root / "missing_visual.json",
                ),
                patch.object(
                    server,
                    "vision_review_snapshot",
                    return_value={
                        "status": "COMPLETE",
                        "complete": True,
                        "awaiting_human_review": False,
                        "packets": [],
                    },
                ),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": True,
                        "opportunities": [],
                    },
                ),
                patch.object(
                    server.shutil,
                    "which",
                    side_effect=lambda name: (
                        f"C:/fake/{name}.exe" if name in {"yt-dlp", "ffmpeg"} else None
                    ),
                ),
            ):
                readiness = server.action_readiness()

        self.assertFalse(readiness["exp2_vision_prepare"]["enabled"])
        self.assertTrue(readiness["analysis_batch_prepare"]["enabled"])

    def test_failed_visual_attempt_allows_analysis_and_exposes_force_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            model_runs = root / "model_runs"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            source_output = root / "source_output"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                model_runs,
                review_requests,
                reviewed,
                source_output,
            ):
                path.mkdir()

            prepared_profile = prepared / "v1.json"
            prepared_profile.write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )
            (enriched / "v1.json").write_text(
                json.dumps(
                    {
                        "source_inputs": {"transcript": {"status": "PROVIDED"}},
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Evidence.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report_dir = source_output / "experiment_02" / "v1"
            report_dir.mkdir(parents=True)
            (report_dir / "visual_analysis.json").write_text(
                json.dumps(
                    {
                        "status": "SCENE_DETECTION_FAILED",
                        "profile_sha256": server.sha256_file(prepared_profile),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(server, "EXP2_MODEL_RUNS_DIR", model_runs),
                patch.object(
                    server,
                    "EXP2_REVIEW_REQUESTS_DIR",
                    review_requests,
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                patch.object(server, "SOURCE_ACQ_OUTPUT", source_output),
                patch.object(
                    server,
                    "EXP2_SYNTHESIS_FILE",
                    root / "missing_synthesis.json",
                ),
                patch.object(
                    server,
                    "EXP2_ACQUISITION_SUMMARY",
                    root / "missing_acquisition.json",
                ),
                patch.object(
                    server,
                    "EXP2_VISUAL_SUMMARY",
                    root / "missing_visual.json",
                ),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": True,
                        "opportunities": [],
                    },
                ),
                patch.object(
                    server.shutil,
                    "which",
                    side_effect=lambda name: (
                        f"C:/fake/{name}.exe" if name in {"yt-dlp", "ffmpeg"} else None
                    ),
                ),
            ):
                readiness = server.action_readiness()

        self.assertFalse(readiness["exp2_visual"]["enabled"])
        self.assertTrue(readiness["exp2_visual_retry"]["enabled"])
        self.assertTrue(readiness["analysis_batch_prepare"]["enabled"])

    def test_missing_ffmpeg_allows_transcript_only_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            model_runs = root / "model_runs"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            source_output = root / "source_output"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                model_runs,
                review_requests,
                reviewed,
                source_output,
            ):
                path.mkdir()

            (prepared / "v1.json").write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )
            (enriched / "v1.json").write_text(
                json.dumps(
                    {
                        "source_inputs": {"transcript": {"status": "PROVIDED"}},
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Evidence.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(server, "EXP2_MODEL_RUNS_DIR", model_runs),
                patch.object(
                    server,
                    "EXP2_REVIEW_REQUESTS_DIR",
                    review_requests,
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                patch.object(server, "SOURCE_ACQ_OUTPUT", source_output),
                patch.object(
                    server,
                    "EXP2_SYNTHESIS_FILE",
                    root / "missing_synthesis.json",
                ),
                patch.object(
                    server,
                    "EXP2_ACQUISITION_SUMMARY",
                    root / "missing_acquisition.json",
                ),
                patch.object(
                    server,
                    "EXP2_VISUAL_SUMMARY",
                    root / "missing_visual.json",
                ),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": True,
                        "opportunities": [],
                    },
                ),
                patch.object(
                    server.shutil,
                    "which",
                    side_effect=lambda name: (
                        "C:/fake/yt-dlp.exe" if name == "yt-dlp" else None
                    ),
                ),
            ):
                readiness = server.action_readiness()

        self.assertFalse(readiness["exp2_visual"]["enabled"])
        self.assertTrue(readiness["analysis_batch_prepare"]["enabled"])

    def test_analysis_request_must_match_current_enriched_profile_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            review_requests = root / "review_requests"
            reviewed = root / "reviewed"
            for path in (
                prepared,
                enriched,
                requests,
                analyzed,
                review_requests,
                reviewed,
            ):
                path.mkdir()

            (prepared / "v1.json").write_text(
                json.dumps({"video_id": "v1"}),
                encoding="utf-8",
            )
            enriched_path = enriched / "v1.json"
            enriched_path.write_text(
                json.dumps(
                    {
                        "source_inputs": {"transcript": {"status": "PROVIDED"}},
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Evidence.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            request_path = requests / "v1.analysis_request.json"
            request_path.write_text(
                json.dumps({"request_provenance": {"profile_sha256": "stale"}}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(
                    server,
                    "EXP2_REVIEW_REQUESTS_DIR",
                    review_requests,
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", reviewed),
                patch.object(
                    server,
                    "EXP2_SYNTHESIS_FILE",
                    root / "missing_synthesis.json",
                ),
                patch.object(
                    server,
                    "EXP2_ACQUISITION_SUMMARY",
                    root / "missing_acquisition.json",
                ),
            ):
                state = server.exp2_artifact_state()
                self.assertFalse(state["requests_complete"])

                request_path.write_text(
                    json.dumps(
                        {
                            "request_provenance": {
                                "profile_sha256": server.sha256_file(enriched_path)
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                state = server.exp2_artifact_state()
                self.assertTrue(state["requests_complete"])

    def test_waiting_automatic_velocity_blocks_duplicate_research_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "opportunity_research_state.json"
            state.write_text(
                json.dumps(
                    {
                        "status": "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH",
                        "next_refresh_due_at": "2026-09-27T16:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(server, "OPPORTUNITY_RESEARCH_STATE", state),
                patch.object(server, "EXP15_DIR", root / "missing_15"),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": False,
                        "opportunities": [],
                    },
                ),
            ):
                readiness = server.action_readiness()
                workflow = server.workflow_guidance(readiness)

        self.assertFalse(readiness["opportunity_research"]["enabled"])
        self.assertEqual(workflow["state"], "WAITING_AUTOMATIC")
        self.assertIn("Automatic", workflow["current_title"])

    def test_pending_human_gate_is_current_guided_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp15 = root / "experiment_01_5"
            exp15.mkdir()
            (exp15 / "study_set.json").write_text("[]", encoding="utf-8")
            with (
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "ready_for_experiment_02": False,
                        "gate_complete": False,
                        "opportunities": [{"opportunity_id": "x"}],
                    },
                ),
            ):
                readiness = server.action_readiness()
                workflow = server.workflow_guidance(readiness)

        self.assertEqual(workflow["state"], "HUMAN_GATE")
        self.assertEqual(workflow["current_title"], "Review Opportunity")
        self.assertEqual(workflow["next_action_id"], "auto_continue")

    def test_auto_refresh_actions_are_windows_gated(self):
        with patch.object(server, "IS_WINDOWS", False):
            readiness = server.action_readiness()
        self.assertFalse(readiness["exp13_auto_refresh_install"]["enabled"])
        self.assertFalse(readiness["exp13_auto_refresh_remove"]["enabled"])

        with patch.object(server, "IS_WINDOWS", True):
            readiness = server.action_readiness()
        self.assertTrue(readiness["exp13_auto_refresh_install"]["enabled"])
        self.assertTrue(readiness["exp13_auto_refresh_remove"]["enabled"])

    def test_job_manager_sets_unbuffered_python_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs"
            state = root / "job_state.json"
            actions = {
                "test_action": {
                    "label": "Test",
                    "stage": "test",
                    "command": [
                        sys.executable,
                        "-c",
                        (
                            "import os; "
                            "print(os.environ.get('PYTHONUNBUFFERED', 'missing'))"
                        ),
                    ],
                    "description": "test",
                }
            }

            manager = server.JobManager()
            with (
                patch.object(server, "ACTION_DEFS", actions),
                patch.object(
                    server,
                    "action_readiness",
                    return_value={
                        "test_action": {
                            "enabled": True,
                            "reason": "test",
                        }
                    },
                ),
                patch.object(server, "PROJECT_ROOT", root),
                patch.object(server, "JOB_LOG_DIR", jobs),
                patch.object(server, "UI_OUTPUT_DIR", root),
                patch.object(server, "JOB_STATE_FILE", state),
            ):
                manager.start("test_action")
                deadline = time.time() + 5
                while manager.running() and time.time() < deadline:
                    time.sleep(0.05)

                self.assertIn("1", manager.log_text())

    def test_velocity_samples_default_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = Path(tmp)
            with patch.object(server, "EXP13_DIR", fake_dir):
                self.assertEqual(server.exp13_valid_velocity_samples(), 0)

    def test_velocity_samples_read_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = Path(tmp)
            (fake_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 7,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(server, "EXP13_DIR", fake_dir):
                self.assertEqual(server.exp13_valid_velocity_samples(), 7)

    def test_job_manager_forces_utf8_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs"
            state = root / "job_state.json"
            actions = {
                "test_utf8": {
                    "label": "UTF8",
                    "stage": "test",
                    "command": [
                        sys.executable,
                        "-c",
                        (
                            "import os; "
                            "print(os.environ.get('PYTHONUTF8')); "
                            "print(os.environ.get('PYTHONIOENCODING')); "
                            "print('STAGE 2 — UTF8')"
                        ),
                    ],
                    "description": "test",
                }
            }

            manager = server.JobManager()
            with (
                patch.object(server, "ACTION_DEFS", actions),
                patch.object(
                    server,
                    "action_readiness",
                    return_value={
                        "test_utf8": {
                            "enabled": True,
                            "reason": "test",
                        }
                    },
                ),
                patch.object(server, "PROJECT_ROOT", root),
                patch.object(server, "JOB_LOG_DIR", jobs),
                patch.object(server, "UI_OUTPUT_DIR", root),
                patch.object(server, "JOB_STATE_FILE", state),
            ):
                manager.start("test_utf8")
                deadline = time.time() + 5
                while manager.running() and time.time() < deadline:
                    time.sleep(0.05)

                log = manager.log_text()
                self.assertIn("1", log)
                self.assertIn("utf-8", log.lower())
                self.assertIn("STAGE 2 — UTF8", log)

    def test_job_manager_runs_allowlisted_command_without_deadlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs"
            state = root / "job_state.json"
            actions = {
                "test_action": {
                    "label": "Test",
                    "stage": "test",
                    "command": [
                        sys.executable,
                        "-c",
                        "print('hello-ui')",
                    ],
                    "description": "test",
                }
            }

            manager = server.JobManager()
            with (
                patch.object(server, "ACTION_DEFS", actions),
                patch.object(
                    server,
                    "action_readiness",
                    return_value={
                        "test_action": {
                            "enabled": True,
                            "reason": "test",
                        }
                    },
                ),
                patch.object(server, "PROJECT_ROOT", root),
                patch.object(server, "JOB_LOG_DIR", jobs),
                patch.object(server, "UI_OUTPUT_DIR", root),
                patch.object(server, "JOB_STATE_FILE", state),
            ):
                job = manager.start("test_action")
                self.assertEqual(job["status"], "RUNNING")

                deadline = time.time() + 5
                while manager.running() and time.time() < deadline:
                    time.sleep(0.05)

                final = manager.current()
                self.assertEqual(final["status"], "SUCCEEDED")
                self.assertIn("hello-ui", manager.log_text())

    def test_current_job_state_is_json_serializable_while_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs"
            state = root / "job_state.json"
            actions = {
                "test_action": {
                    "label": "Test",
                    "stage": "test",
                    "command": [
                        sys.executable,
                        "-c",
                        "import time; print('running'); time.sleep(1)",
                    ],
                    "description": "test",
                }
            }

            manager = server.JobManager()
            with (
                patch.object(server, "ACTION_DEFS", actions),
                patch.object(
                    server,
                    "action_readiness",
                    return_value={
                        "test_action": {
                            "enabled": True,
                            "reason": "test",
                        }
                    },
                ),
                patch.object(server, "PROJECT_ROOT", root),
                patch.object(server, "JOB_LOG_DIR", jobs),
                patch.object(server, "UI_OUTPUT_DIR", root),
                patch.object(server, "JOB_STATE_FILE", state),
            ):
                manager.start("test_action")
                current = manager.current()

                self.assertIsNotNone(current)
                self.assertNotIn("_log_handle", current)
                json.dumps(current)

                manager.stop()

    def test_checkpoint_complete_is_not_stage_complete_without_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"status": "COMPLETE"}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "DISCOVERY NEEDS RESUME",
            )
            self.assertEqual(stage["state"], "COMPLETE")

    def test_running_discovery_has_human_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"status": "COMPLETE"}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(
                    server,
                    "current_action_id",
                    return_value="exp13_discover",
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "DISCOVERY RUNNING",
            )
            self.assertEqual(stage["tone"], "running")

    def test_velocity_ready_is_human_stage_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            exp13.mkdir()
            (exp13 / "cohort_manifest.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "topic_velocity.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 4,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
                patch.object(
                    server,
                    "exp13_cohort_readiness",
                    return_value={
                        "frozen_size": 6,
                        "required_unique_channels": 3,
                        "ready_cell_count": 1,
                        "max_unique_channels_in_cell": 3,
                        "sufficient": True,
                    },
                ),
                patch.object(
                    server,
                    "exp13_depth_ready_cell_count",
                    return_value=1,
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertTrue(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "STAGE COMPLETE",
            )
            self.assertTrue(all(item["done"] for item in stage["criteria"]))

    def test_insufficient_cohort_tells_user_to_rerun_not_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            exp13.mkdir()

            (exp13 / "cohort_manifest.json").write_text(
                json.dumps(
                    {
                        "video_ids": ["only-video"],
                        "candidates": [
                            {
                                "video_id": "only-video",
                                "channel_id": "channel-1",
                                "format_candidate": "long_form_candidate",
                                "validated_topics": ["brakes"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (exp13 / "topic_velocity.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
                patch.object(
                    server,
                    "exp13_cohort_readiness",
                    return_value={
                        "frozen_size": 1,
                        "required_unique_channels": 3,
                        "ready_cell_count": 0,
                        "max_unique_channels_in_cell": 1,
                        "sufficient": False,
                    },
                ),
                patch.object(
                    server,
                    "exp13_depth_ready_cell_count",
                    return_value=0,
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "INSUFFICIENT COHORT — RERUN DISCOVERY",
            )
            self.assertIn(
                "Do not wait",
                stage["next_action"],
            )

    def test_refresh_is_disabled_for_insufficient_cohort(self):
        with (
            patch.object(
                server,
                "exp13_cohort_readiness",
                return_value={
                    "frozen_size": 1,
                    "required_unique_channels": 3,
                    "ready_cell_count": 0,
                    "max_unique_channels_in_cell": 1,
                    "sufficient": False,
                },
            ),
            patch.object(
                server,
                "exp13_depth_ready_cell_count",
                return_value=0,
            ),
        ):
            readiness = server.action_readiness()

        self.assertFalse(readiness["exp13_refresh"]["enabled"])
        self.assertIn(
            "do not wait",
            readiness["exp13_refresh"]["reason"].lower(),
        )

    def test_unknown_action_is_rejected(self):
        manager = server.JobManager()
        with self.assertRaises(ValueError):
            manager.start("not_real")

    def test_experiment_02_prepare_requires_human_opportunity_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp15 = root / "experiment_01_5"
            exp2 = root / "experiment_02"
            exp15.mkdir()
            (exp15 / "study_set.json").write_text("[]", encoding="utf-8")

            with (
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "status": "AWAITING_HUMAN_DECISION",
                        "ready_for_experiment_02": False,
                        "gate_complete": False,
                        "opportunities": [],
                    },
                ),
            ):
                readiness = server.action_readiness()

            self.assertFalse(readiness["exp2_prepare"]["enabled"])
            self.assertIn(
                "approve",
                readiness["exp2_prepare"]["reason"].lower(),
            )

            with (
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "status": "APPROVED",
                        "ready_for_experiment_02": True,
                        "gate_complete": True,
                        "opportunities": [],
                    },
                ),
            ):
                readiness = server.action_readiness()

            self.assertTrue(readiness["exp2_prepare"]["enabled"])

    def test_remaining_analysis_action_is_in_guided_workflow(self):
        self.assertIn("analysis_model_remaining", server.AUTO_MACHINE_ACTION_ORDER)
        one_index = server.AUTO_MACHINE_ACTION_ORDER.index("analysis_model_one")
        remaining_index = server.AUTO_MACHINE_ACTION_ORDER.index("analysis_model_remaining")
        review_index = server.AUTO_MACHINE_ACTION_ORDER.index("human_review_prepare")
        self.assertLess(one_index, remaining_index)
        self.assertLess(remaining_index, review_index)

        command = server.ACTION_DEFS["analysis_model_remaining"]["command"]
        self.assertIn(
            "analysis_model_runner.py", " ".join(str(part) for part in command)
        )
        self.assertIn("--mode", command)
        self.assertIn("batch", command)
        self.assertNotIn("--max-requests", command)

    def test_exp2_artifact_state_counts_partial_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared"
            enriched = root / "enriched"
            requests = root / "requests"
            analyzed = root / "analyzed"
            runs = root / "runs"
            for path in (prepared, enriched, requests, analyzed, runs):
                path.mkdir()

            for video_id in ("v1", "v2"):
                prepared_path = prepared / f"{video_id}.json"
                prepared_path.write_text(
                    json.dumps({"video_id": video_id}), encoding="utf-8"
                )
                enriched_path = enriched / f"{video_id}.json"
                enriched_path.write_text(
                    json.dumps(
                        {
                            "video_id": video_id,
                            "source_inputs": {"transcript": {"status": "PROVIDED"}},
                            "evidence": [{"type": "transcript"}],
                        }
                    ),
                    encoding="utf-8",
                )
                request_path = requests / f"{video_id}.analysis_request.json"
                request_path.write_text(
                    json.dumps(
                        {
                            "video_id": video_id,
                            "request_provenance": {
                                "profile_sha256": server.sha256_file(enriched_path)
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            first_request = requests / "v1.analysis_request.json"
            (analyzed / "v1.json").write_text(
                json.dumps({"video_id": "v1"}), encoding="utf-8"
            )
            (runs / "v1.model_run.json").write_text(
                json.dumps(
                    {
                        "status": "APPLIED",
                        "request_sha256": server.sha256_file(first_request),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP2_PREPARED_DIR", prepared),
                patch.object(server, "EXP2_ENRICHED_DIR", enriched),
                patch.object(server, "EXP2_REQUESTS_DIR", requests),
                patch.object(server, "EXP2_ANALYZED_DIR", analyzed),
                patch.object(server, "EXP2_MODEL_RUNS_DIR", runs),
                patch.object(
                    server, "EXP2_REVIEW_REQUESTS_DIR", root / "review_requests"
                ),
                patch.object(server, "EXP2_REVIEWED_DIR", root / "reviewed"),
                patch.object(server, "EXP2_SYNTHESIS_FILE", root / "synthesis.json"),
                patch.object(server, "EXP2_ACQUISITION_SUMMARY", root / "acq.json"),
                patch.object(server, "EXP2_VISUAL_SUMMARY", root / "visual.json"),
                patch.object(server, "SOURCE_ACQ_OUTPUT", root / "source"),
            ):
                state = server.exp2_artifact_state()

        self.assertEqual(state["analysis_request_ids"], ["v1", "v2"])
        self.assertEqual(state["analyzed_ids"], ["v1"])
        self.assertEqual(state["analyzed_current_count"], 1)

    def test_concept_triage_precedes_human_concept_gate(self):
        self.assertIn("concept_triage", server.AUTO_MACHINE_ACTION_ORDER)
        generate_index = server.AUTO_MACHINE_ACTION_ORDER.index("concept_generate")
        triage_index = server.AUTO_MACHINE_ACTION_ORDER.index("concept_triage")
        gate_index = server.AUTO_MACHINE_ACTION_ORDER.index("concept_gate_prepare")
        self.assertLess(generate_index, triage_index)
        self.assertLess(triage_index, gate_index)

        command = server.ACTION_DEFS["concept_triage"]["command"]
        self.assertIn(
            "transformation_engine/concept_triage.py",
            " ".join(str(part) for part in command),
        )
        self.assertIn("--mode", command)
        self.assertIn("run", command)

    def test_state_changing_posts_require_same_origin_json_and_csrf(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            bad = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/stop",
                data=b"{}",
                method="POST",
                headers={
                    "Content-Type": "text/plain",
                    "Origin": "https://evil.example",
                },
            )
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(bad, timeout=5)
            self.assertEqual(denied.exception.code, 403)

            good = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/stop",
                data=b"{}",
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{port}",
                    "X-CSRF-Token": server.CSRF_TOKEN,
                },
            )
            try:
                with urllib.request.urlopen(good, timeout=5) as response:
                    self.assertNotEqual(response.status, 403)
            except urllib.error.HTTPError as allowed:
                self.assertNotEqual(
                    allowed.code,
                    403,
                    "same-origin JSON request with CSRF token must pass security checks",
                )
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
