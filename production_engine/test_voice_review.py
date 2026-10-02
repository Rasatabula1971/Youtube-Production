from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import voice_review


def spec() -> dict:
    return {
        "artifact": "voice_performance_spec",
        "concept_id": "concept-1",
        "format": "long_form",
        "title": "Locked",
        "duration_intent_seconds": 120,
        "promise_delivery": "Promise",
        "payoff": "Payoff",
        "beats": [
            {
                "beat_id": "b1",
                "immutable_narration": "Exact words.",
                "immutable_narration_sha256": "abc",
            }
        ],
        "directions": [
            {
                "beat_id": "b1",
                "emotion": "neutral",
                "intensity": 0.2,
                "speed": 1.0,
                "pause_before_ms": 0,
                "pause_after_ms": 200,
                "emphasis_terms": [],
            }
        ],
        "voice_identity": {
            "provider": "higgsfield",
            "voice_id": None,
            "license_reference": None,
            "calibration_artifact": None,
        },
        "render_prerequisites_configured": False,
        "validation": {"valid": True, "errors": []},
    }


def gate_config() -> dict:
    return {
        "required_accept_criteria": [
            "narration_text_unchanged",
            "delivery_matches_branch_intent",
            "emotion_curve_is_restrained",
            "pace_and_pauses_support_comprehension",
            "emphasis_is_grounded_in_spoken_words",
        ],
        "require_reviewer_name": True,
    }


class VoiceReviewTests(unittest.TestCase):
    def test_accept_is_one_click_and_records_audit_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "spec.json"
            source.write_text(json.dumps(spec()), encoding="utf-8")
            request = voice_review.build_review_request(
                spec(), source, gate_config()
            )
            response = {
                "concept_id": "concept-1",
                "format": "long_form",
                "reviewer": "tester",
                "decision": "ACCEPT",
                "criteria": {},
                "note": "",
            }
            normalized = voice_review.validate_response(
                request, response, gate_config()
            )

        self.assertEqual(normalized["decision"], "ACCEPT")
        self.assertTrue(all(normalized["criteria"].values()))


    def test_rework_note_invalidates_spec_and_updates_planner_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "specs"
            requests = root / "requests"
            responses = root / "responses"
            approved = root / "approved"
            model_runs = root / "model_runs"
            specs.mkdir()
            model_runs.mkdir()
            planner_request = root / "concept-1.long_form.voice_request.json"
            planner_request.write_text(
                json.dumps(
                    {
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "human_rework_iteration": 0,
                    }
                ),
                encoding="utf-8",
            )
            payload = spec()
            payload["spec_provenance"] = {
                "request_source": str(planner_request.resolve()),
                "request_sha256": voice_review.sha256_file(planner_request),
            }
            source = specs / "concept-1.long_form.voice_performance_spec.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            (model_runs / "concept-1.long_form.model_run.json").write_text(
                json.dumps(
                    {
                        "status": "VALIDATED",
                        "request_sha256": voice_review.sha256_file(planner_request),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(voice_review, "SPECS_DIR", specs),
                patch.object(voice_review, "REQUESTS_DIR", root),
                patch.object(voice_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(voice_review, "RESPONSES_DIR", responses),
                patch.object(voice_review, "APPROVED_DIR", approved),
                patch.object(voice_review, "MODEL_RUNS_DIR", model_runs),
                patch.object(voice_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                voice_review.prepare(gate_config())
                voice_review.apply_action(
                    concept_id="concept-1",
                    format="long_form",
                    decision="REWORK",
                    criteria={},
                    note="Slow the reveal and reduce the emotional jump.",
                )

            self.assertFalse(source.exists())
            revised_request = json.loads(
                planner_request.read_text(encoding="utf-8")
            )
            self.assertEqual(revised_request["human_rework_iteration"], 1)
            self.assertEqual(
                revised_request["human_rework_note"],
                "Slow the reveal and reduce the emotional jump.",
            )

    def test_prepare_skips_stale_spec_and_removes_old_gate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "specs"
            planner_requests = root / "planner_requests"
            review_requests = root / "review_requests"
            responses = root / "responses"
            approved = root / "approved"
            for directory in (
                specs,
                planner_requests,
                review_requests,
                responses,
                approved,
            ):
                directory.mkdir()

            planner_request = (
                planner_requests / "concept-1.long_form.voice_request.json"
            )
            planner_request.write_text(
                json.dumps({"concept_id": "concept-1", "format": "long_form"}),
                encoding="utf-8",
            )
            payload = spec()
            payload["spec_provenance"] = {
                "request_source": str(planner_request.resolve()),
                "request_sha256": "stale-hash",
            }
            source = specs / "concept-1.long_form.voice_performance_spec.json"
            source.write_text(json.dumps(payload), encoding="utf-8")

            stale_paths = [
                review_requests / "concept-1.long_form.voice_review_request.json",
                responses / "concept-1.long_form.voice_review_response.json",
                approved / "concept-1.long_form.approved_voice_spec.json",
            ]
            for path in stale_paths:
                path.write_text("{}", encoding="utf-8")
            summary = root / "voice_performance_gate_summary.json"
            summary.write_text("{}", encoding="utf-8")

            with (
                patch.object(voice_review, "SPECS_DIR", specs),
                patch.object(voice_review, "REQUESTS_DIR", planner_requests),
                patch.object(voice_review, "REVIEW_REQUESTS_DIR", review_requests),
                patch.object(voice_review, "RESPONSES_DIR", responses),
                patch.object(voice_review, "APPROVED_DIR", approved),
                patch.object(voice_review, "SUMMARY_FILE", summary),
            ):
                result = voice_review.prepare(gate_config())

            self.assertEqual(result["prepared"], 0)
            self.assertEqual(result["skipped_stale_specs"], [str(source.resolve())])
            self.assertTrue(all(not path.exists() for path in stale_paths))
            self.assertFalse(summary.exists())

    def test_prepare_rejects_spec_without_validated_model_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "specs"
            planner_requests = root / "planner_requests"
            model_runs = root / "model_runs"
            review_requests = root / "review_requests"
            responses = root / "responses"
            approved = root / "approved"
            for directory in (
                specs,
                planner_requests,
                model_runs,
                review_requests,
                responses,
                approved,
            ):
                directory.mkdir()

            planner_request = (
                planner_requests / "concept-1.long_form.voice_request.json"
            )
            planner_request.write_text(
                json.dumps({"concept_id": "concept-1", "format": "long_form"}),
                encoding="utf-8",
            )
            request_hash = voice_review.sha256_file(planner_request)
            payload = spec()
            payload["spec_provenance"] = {
                "request_source": str(planner_request.resolve()),
                "request_sha256": request_hash,
            }
            source = specs / "concept-1.long_form.voice_performance_spec.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            (model_runs / "concept-1.long_form.model_run.json").write_text(
                json.dumps(
                    {"status": "RUNNER_ERROR", "request_sha256": request_hash}
                ),
                encoding="utf-8",
            )

            with (
                patch.object(voice_review, "SPECS_DIR", specs),
                patch.object(voice_review, "REQUESTS_DIR", planner_requests),
                patch.object(voice_review, "MODEL_RUNS_DIR", model_runs),
                patch.object(voice_review, "REVIEW_REQUESTS_DIR", review_requests),
                patch.object(voice_review, "RESPONSES_DIR", responses),
                patch.object(voice_review, "APPROVED_DIR", approved),
                patch.object(voice_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                result = voice_review.prepare(gate_config())

            self.assertEqual(result["prepared"], 0)
            self.assertEqual(result["skipped_stale_specs"], [str(source.resolve())])

    def test_accept_creates_approved_spec_without_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "specs"
            requests = root / "requests"
            responses = root / "responses"
            approved = root / "approved"
            specs.mkdir()
            planner_request = root / "concept-1.long_form.voice_request.json"
            planner_request.write_text(
                json.dumps({"concept_id": "concept-1", "format": "long_form"}),
                encoding="utf-8",
            )
            payload = spec()
            payload["spec_provenance"] = {
                "request_source": str(planner_request.resolve()),
                "request_sha256": voice_review.sha256_file(planner_request),
            }
            source = specs / "concept-1.long_form.voice_performance_spec.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            (model_runs / "concept-1.long_form.model_run.json").write_text(
                json.dumps(
                    {
                        "status": "VALIDATED",
                        "request_sha256": voice_review.sha256_file(planner_request),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(voice_review, "SPECS_DIR", specs),
                patch.object(voice_review, "REQUESTS_DIR", root),
                patch.object(voice_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(voice_review, "RESPONSES_DIR", responses),
                patch.object(voice_review, "APPROVED_DIR", approved),
                patch.object(voice_review, "MODEL_RUNS_DIR", model_runs),
                patch.object(voice_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                prepared = voice_review.prepare(gate_config())
                self.assertEqual(prepared["prepared"], 1)
                snapshot = voice_review.apply_action(
                    concept_id="concept-1",
                    format="long_form",
                    decision="ACCEPT",
                    criteria={},
                )

            self.assertTrue(snapshot["complete"])
            self.assertEqual(snapshot["accepted"], 1)
            approved_files = list(approved.glob("*.approved_voice_spec.json"))
            self.assertEqual(len(approved_files), 1)
            payload = json.loads(approved_files[0].read_text(encoding="utf-8"))
            self.assertEqual(
                payload["performance_gate"]["status"],
                "PERFORMANCE_SPEC_APPROVED",
            )
            self.assertFalse(payload["render_prerequisites_configured"])


if __name__ == "__main__":
    unittest.main()
