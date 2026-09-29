from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import server


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StalePipelineRegressionTests(unittest.TestCase):
    def test_stale_packaging_request_cannot_bypass_incomplete_concept_gate(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            handoff = write_json(
                root / "research_handoff.json",
                {
                    "status": "READY_FOR_RESEARCH",
                    "concepts": [{"concept_id": "old_c1"}],
                },
            )
            requests = root / "package_requests"
            write_json(
                requests / "old_c1.package_request.json",
                {
                    "concept_id": "old_c1",
                    "request_provenance": {
                        "concept_handoff_sha256": sha(handoff),
                    },
                },
            )

            stack.enter_context(
                patch.object(
                    server,
                    "transformation_artifact_state",
                    return_value={"research_ready": False},
                )
            )
            stack.enter_context(patch.object(server, "TRANSFORM_RESEARCH_HANDOFF", handoff))
            stack.enter_context(patch.object(server, "PACKAGING_REQUESTS_DIR", requests))
            stack.enter_context(
                patch.object(server, "PACKAGING_RESPONSES_DIR", root / "package_responses")
            )
            stack.enter_context(
                patch.object(server, "PACKAGING_CANDIDATES_FILE", root / "candidates.json")
            )
            stack.enter_context(
                patch.object(server, "PACKAGING_RESEARCH_HANDOFF", root / "packaging_handoff.json")
            )

            state = server.packaging_artifact_state()

        self.assertFalse(state["requests_ready"])
        self.assertFalse(state["candidates_ready"])
        self.assertFalse(state["research_ready"])

    def test_stale_script_artifacts_cannot_bypass_incomplete_research_gate(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            verified_dir = root / "verified"
            requests_dir = root / "script_requests"
            drafts_dir = root / "script_drafts"
            verified = write_json(
                verified_dir / "old_c1.verified_research_package.json",
                {
                    "concept_id": "old_c1",
                    "status": "READY_FOR_STORY_SCRIPT",
                    "claims": [{"claim_id": "c1", "statement": "x"}],
                },
            )
            request = write_json(
                requests_dir / "old_c1.script_request.json",
                {
                    "concept_id": "old_c1",
                    "request_provenance": {
                        "verified_research_sha256": sha(verified),
                    },
                },
            )
            write_json(
                drafts_dir / "old_c1.script_draft.json",
                {
                    "concept_id": "old_c1",
                    "draft_provenance": {"request_sha256": sha(request)},
                },
            )

            stack.enter_context(
                patch.object(
                    server,
                    "research_artifact_state",
                    return_value={"story_ready": False},
                )
            )
            stack.enter_context(patch.object(server, "RESEARCH_VERIFIED_DIR", verified_dir))
            stack.enter_context(patch.object(server, "SCRIPT_REQUESTS_DIR", requests_dir))
            stack.enter_context(patch.object(server, "SCRIPT_DRAFTS_DIR", drafts_dir))

            state = server.story_script_artifact_state()

        self.assertFalse(state["requests_ready"])
        self.assertFalse(state["drafts_ready"])
        self.assertFalse(state["production_ready"])
        self.assertEqual(state["script_gate"]["status"], "WAITING_FOR_SCRIPT_DRAFTS")

    def test_transform_candidates_must_match_current_response_hashes(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            synthesis = write_json(root / "synthesis.json", {"v": 2})
            requests = root / "concept_requests"
            responses = root / "concept_responses"
            runs = root / "concept_model_runs"
            request = write_json(
                requests / "m1.concept_request.json",
                {
                    "mechanism_id": "m1",
                    "request_provenance": {
                        "handoff_sha256": sha(synthesis),
                    },
                },
            )
            validation_contract = server.transformation_validation_contract_sha256()
            write_json(
                responses / "m1.json",
                {
                    "mechanism_id": "m1",
                    "response_provenance": {
                        "request_sha256": sha(request),
                        "validation_contract_sha256": validation_contract,
                    },
                },
            )
            write_json(
                runs / "m1.model_run.json",
                {
                    "status": "VALIDATED",
                    "request_sha256": sha(request),
                    "validation_contract_sha256": validation_contract,
                },
            )
            candidates = write_json(
                root / "concept_candidates.json",
                {
                    "count": 1,
                    "source_response_sha256": {"m1": "old-response-hash"},
                    "concepts": [{"concept_id": "c1"}],
                },
            )

            stack.enter_context(patch.object(server, "EXP2_SYNTHESIS_FILE", synthesis))
            stack.enter_context(patch.object(server, "TRANSFORM_REQUESTS_DIR", requests))
            stack.enter_context(patch.object(server, "TRANSFORM_RESPONSES_DIR", responses))
            stack.enter_context(patch.object(server, "TRANSFORM_MODEL_RUNS_DIR", runs))
            stack.enter_context(patch.object(server, "TRANSFORM_CANDIDATES_FILE", candidates))
            stack.enter_context(patch.object(server, "TRANSFORM_TRIAGE_FILE", root / "triage.json"))
            stack.enter_context(
                patch.object(server, "TRANSFORM_TRIAGED_CANDIDATES_FILE", root / "triaged.json")
            )
            stack.enter_context(
                patch.object(server, "TRANSFORM_RESEARCH_HANDOFF", root / "handoff.json")
            )

            state = server.transformation_artifact_state()

        self.assertTrue(state["responses_complete"])
        self.assertFalse(state["candidate_provenance_current"])
        self.assertFalse(state["candidates_ready"])

    def test_package_candidates_must_match_current_response_hashes(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            handoff = write_json(root / "handoff.json", {"status": "READY_FOR_RESEARCH"})
            requests = root / "package_requests"
            responses = root / "package_responses"
            request = write_json(
                requests / "c1.package_request.json",
                {
                    "concept_id": "c1",
                    "request_provenance": {
                        "concept_handoff_sha256": sha(handoff),
                    },
                },
            )
            write_json(
                responses / "c1.json",
                {
                    "concept_id": "c1",
                    "response_provenance": {
                        "request_sha256": sha(request),
                    },
                },
            )
            candidates = write_json(
                root / "package_candidates.json",
                {
                    "count": 1,
                    "source_response_sha256": {"c1": "old-response-hash"},
                    "packages": [{"package_id": "p1", "concept_id": "c1"}],
                },
            )

            stack.enter_context(
                patch.object(
                    server,
                    "transformation_artifact_state",
                    return_value={"research_ready": True},
                )
            )
            stack.enter_context(patch.object(server, "TRANSFORM_RESEARCH_HANDOFF", handoff))
            stack.enter_context(patch.object(server, "PACKAGING_REQUESTS_DIR", requests))
            stack.enter_context(patch.object(server, "PACKAGING_RESPONSES_DIR", responses))
            stack.enter_context(patch.object(server, "PACKAGING_CANDIDATES_FILE", candidates))
            stack.enter_context(
                patch.object(server, "PACKAGING_RESEARCH_HANDOFF", root / "research_handoff.json")
            )

            state = server.packaging_artifact_state()

        self.assertTrue(state["responses_complete"])
        self.assertFalse(state["candidate_provenance_current"])
        self.assertFalse(state["candidates_ready"])


    def test_changed_human_reviews_make_existing_synthesis_rebuildable(self):
        stale_state = {
            "prepared_count": 1,
            "evidence_complete": True,
            "visual_attempted": True,
            "visual_complete": False,
            "requests_complete": True,
            "analyzed_current_count": 1,
            "analysis_request_ids": ["v1"],
            "review_requests_current_count": 1,
            "reviewed_current_count": 1,
            "synthesis_ready": False,
        }
        transform = {
            "requests_ready": False,
            "candidates_ready": False,
            "triage_ready": False,
            "concept_gate": {"status": "WAITING_FOR_CONCEPT_CANDIDATES"},
            "concept_gate_complete": False,
            "research_ready": False,
            "shortlist_count": 0,
        }
        packaging = {
            "requests_ready": False,
            "candidates_ready": False,
            "packaging_gate": {"status": "WAITING_FOR_PACKAGE_CANDIDATES"},
            "packaging_gate_complete": False,
            "research_ready": False,
        }
        research = {
            "plans_ready": False,
            "evidence_complete": False,
            "drafts_ready": False,
            "research_gate": {"status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES"},
            "research_gate_complete": False,
            "story_ready": False,
        }
        story = {
            "requests_ready": False,
            "drafts_ready": False,
            "script_gate": {"status": "WAITING_FOR_SCRIPT_DRAFTS"},
            "script_gate_complete": False,
            "production_ready": False,
        }
        fmt = {
            "requests_ready": False,
            "plans_ready": False,
            "format_gate": {"status": "WAITING_FOR_FORMAT_PLANS"},
            "format_gate_complete": False,
            "production_engine_ready": False,
        }

        with (
            patch.object(server, "exp13_cohort_readiness", return_value={"sufficient": False}),
            patch.object(server, "exp13_depth_ready_cell_count", return_value=0),
            patch.object(server, "exp14_plan_status", return_value="WAITING"),
            patch.object(server, "exp14_execution_status", return_value="WAITING"),
            patch.object(server, "opportunity_research_state", return_value={}),
            patch.object(
                server,
                "opportunity_gate_snapshot",
                return_value={"ready_for_experiment_02": True},
            ),
            patch.object(server, "exp2_artifact_state", return_value=stale_state),
            patch.object(
                server,
                "vision_review_snapshot",
                return_value={"complete": True, "awaiting_human_review": False},
            ),
            patch.object(server, "transformation_artifact_state", return_value=transform),
            patch.object(server, "packaging_artifact_state", return_value=packaging),
            patch.object(server, "research_artifact_state", return_value=research),
            patch.object(server, "story_script_artifact_state", return_value=story),
            patch.object(server, "format_artifact_state", return_value=fmt),
            patch.object(server.shutil, "which", return_value=None),
        ):
            readiness = server.action_readiness()

        self.assertTrue(readiness["synthesis_build"]["enabled"])


if __name__ == "__main__":
    unittest.main()
