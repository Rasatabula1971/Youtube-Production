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
    def test_accept_requires_all_criteria(self) -> None:
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
                "criteria": {
                    name: True
                    for name in gate_config()["required_accept_criteria"]
                },
                "note": "",
            }
            response["criteria"]["emotion_curve_is_restrained"] = False
            with self.assertRaisesRegex(ValueError, "all criteria"):
                voice_review.validate_response(
                    request, response, gate_config()
                )

    def test_accept_creates_approved_spec_without_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "specs"
            requests = root / "requests"
            responses = root / "responses"
            approved = root / "approved"
            specs.mkdir()
            source = specs / "concept-1.long_form.voice_performance_spec.json"
            source.write_text(json.dumps(spec()), encoding="utf-8")

            with (
                patch.object(voice_review, "SPECS_DIR", specs),
                patch.object(voice_review, "REVIEW_REQUESTS_DIR", requests),
                patch.object(voice_review, "RESPONSES_DIR", responses),
                patch.object(voice_review, "APPROVED_DIR", approved),
                patch.object(voice_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                prepared = voice_review.prepare(gate_config())
                self.assertEqual(prepared["prepared"], 1)
                criteria = {
                    name: True
                    for name in gate_config()["required_accept_criteria"]
                }
                snapshot = voice_review.apply_action(
                    concept_id="concept-1",
                    format="long_form",
                    decision="ACCEPT",
                    criteria=criteria,
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
