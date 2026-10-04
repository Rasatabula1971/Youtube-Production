import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import server
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    # Never read the real pipeline outputs of the machine running the tests.
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()
import workflow_automation


def ready(**extra):
    return {"ready": True, **extra}


class FinalPackagingIntegrationTests(unittest.TestCase):
    def test_route_is_human_gate_guarded_and_runner_stops_at_gate(self):
        self.assertIn("/api/final-packaging-gate", server.HUMAN_GATE_MUTATION_ROUTES)
        source = Path(workflow_automation.__file__).read_text(encoding="utf-8")
        self.assertIn('"HUMAN_FINAL_PACKAGING_GATE"', source)
        self.assertIn('"FINAL_PACKAGING_REJECTED"', source)
        self.assertNotIn('"PACKAGE_VALIDATION_READY"', source)

    def test_static_ui_contains_final_packaging_gate(self):
        static = Path(server.__file__).resolve().parent / "static"
        html = (static / "index.html").read_text(encoding="utf-8")
        script = (static / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="finalPackagingReviewPanel"', html)
        self.assertIn('value="SCRIPT"', html)
        self.assertIn("renderFinalPackagingReview", script)
        self.assertIn("/api/final-packaging-gate", script)
        self.assertIn("HUMAN_FINAL_PACKAGING_GATE", script)

    def guidance(self, final_state, format_state=None):
        patches = [
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
                server, "human_analysis_review_snapshot", return_value={"status": "COMPLETE"}
            ),
            patch.object(
                server,
                "transformation_artifact_state",
                return_value={"candidates_ready": True, "concept_gate": {"status": "COMPLETE"}},
            ),
            patch.object(
                server,
                "packaging_artifact_state",
                return_value={"candidates_ready": True, "packaging_gate": {"status": "COMPLETE"}},
            ),
            patch.object(
                server,
                "research_artifact_state",
                return_value={"drafts_ready": True, "research_gate": {"status": "COMPLETE"}},
            ),
            patch.object(
                server,
                "story_script_artifact_state",
                return_value={
                    "drafts_ready": True,
                    "production_ready": True,
                    "script_gate": {"status": "COMPLETE"},
                },
            ),
            patch.object(
                server,
                "title_direction_artifact_state",
                return_value={
                    "requests_ready": True,
                    "candidates_ready": True,
                    "gate": {"status": "TITLE_DIRECTION_SELECTED"},
                },
            ),
            patch.object(server, "packaging_brief_snapshot", return_value=ready()),
            patch.object(server, "psychological_angle_request_snapshot", return_value=ready()),
            patch.object(server, "psychological_angle_snapshot", return_value=ready()),
            patch.object(server, "thumbnail_concept_request_snapshot", return_value=ready()),
            patch.object(server, "thumbnail_concept_snapshot", return_value=ready()),
            patch.object(server, "package_pairing_request_snapshot", return_value=ready()),
            patch.object(
                server,
                "package_validation_snapshot",
                return_value=ready(current_pairs=50, **{"pass": 12}),
            ),
            patch.object(server, "final_packaging_gate_state", return_value=final_state),
            patch.object(
                server,
                "format_artifact_state",
                return_value=format_state
                or {"plans_ready": False, "format_gate": {"status": "WAITING_FOR_FORMAT_PLANS"}},
            ),
        ]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return server.workflow_guidance({})

    def test_validated_matrix_stops_at_final_packaging_gate(self):
        workflow = self.guidance(
            {"status": "AWAITING_HUMAN_FINAL_PACKAGING", "ready": False}
        )
        self.assertEqual(workflow["state"], "HUMAN_FINAL_PACKAGING_GATE")
        self.assertIn("12 of 50", workflow["current_detail"])

    def test_rejected_final_package_holds_format(self):
        workflow = self.guidance({"status": "FINAL_PACKAGING_REJECTED", "ready": False})
        self.assertEqual(workflow["state"], "FINAL_PACKAGING_REJECTED")

    def test_approved_final_package_continues_to_format(self):
        workflow = self.guidance(
            {"status": "FINAL_PACKAGING_APPROVED", "ready": True},
            {"plans_ready": True, "format_gate": {"status": "AWAITING_HUMAN_DECISION"}},
        )
        self.assertEqual(workflow["state"], "HUMAN_FORMAT_GATE")

    def test_format_request_is_current_only_with_current_final_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved = root / "approved"
            requests = root / "requests"
            approved.mkdir()
            requests.mkdir()
            script = approved / "c1.approved_script.json"
            script.write_text(
                json.dumps(
                    {"concept_id": "c1", "script_gate": {"status": "READY_FOR_PRODUCTION"}}
                ),
                encoding="utf-8",
            )
            (requests / "c1.format_request.json").write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "request_provenance": {
                            "approved_script_sha256": server.sha256_file(script),
                            "final_package_sha256": "bundle-1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(server, "SCRIPT_APPROVED_DIR", approved),
                patch.object(server, "FORMAT_REQUESTS_DIR", requests),
                patch.object(server, "FORMAT_PLANS_DIR", root / "plans"),
                patch.object(
                    server, "story_script_artifact_state", return_value={"production_ready": True}
                ),
                patch.object(
                    server, "current_final_package_hashes", return_value={"c1": "bundle-1"}
                ),
            ):
                current = server.format_artifact_state()
            with (
                patch.object(server, "SCRIPT_APPROVED_DIR", approved),
                patch.object(server, "FORMAT_REQUESTS_DIR", requests),
                patch.object(server, "FORMAT_PLANS_DIR", root / "plans"),
                patch.object(
                    server, "story_script_artifact_state", return_value={"production_ready": True}
                ),
                patch.object(
                    server, "current_final_package_hashes", return_value={"c1": "bundle-2"}
                ),
            ):
                stale = server.format_artifact_state()
        self.assertTrue(current["requests_ready"])
        self.assertFalse(stale["requests_ready"])

    def test_package_image_urls_only_for_approved_images(self):
        payload = server.with_final_package_image_urls(
            {
                "items": [
                    {
                        "packages": [
                            {"render_id": "c1:short--t1", "image_approved": True},
                            {"render_id": "c1:short--t2", "image_approved": False},
                        ]
                    }
                ]
            }
        )
        packages = payload["items"][0]["packages"]
        self.assertEqual(
            packages[0]["image_url"],
            "/api/thumbnail-file?render_id=c1%3Ashort--t1&name=thumbnail.jpg",
        )
        self.assertIsNone(packages[1]["image_url"])


if __name__ == "__main__":
    unittest.main()
