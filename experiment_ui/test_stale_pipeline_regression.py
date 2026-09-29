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
            request = write_json(
                requests / "m1.concept_request.json",
                {
                    "mechanism_id": "m1",
                    "request_provenance": {
                        "handoff_sha256": sha(synthesis),
                    },
                },
            )
            response = write_json(
                responses / "m1.json",
                {
                    "mechanism_id": "m1",
                    "response_provenance": {
                        "request_sha256": sha(request),
                    },
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
            response = write_json(
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


if __name__ == "__main__":
    unittest.main()
