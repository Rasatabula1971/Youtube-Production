"""A stress word the script doesn't say no longer throws the voice plan away (D-192)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from production_engine import test_voice_model_runner as base
from production_engine import voice_model_runner as runner

NARRATION = "The jet touches down in a rainstorm, splashing water, its wheels looking like smooth rubber."


def request() -> dict:
    return {
        "concept_id": "c_tyre",
        "format": "short",
        "title": "Why Aviation Tires Lack Deep Treads",
        "beats": [{"beat_id": "beat_01", "immutable_narration": NARRATION, "reveal_beat": False}],
        "performance_controls": {
            "allowed_emotions": ["curious", "neutral"],
            "max_intensity": 0.7,
            "speed_min": 0.9,
            "speed_max": 1.1,
            "pause_ms_max": 1200,
            "emphasis_terms_max": 4,
        },
    }


def answer(terms, intensity=0.5) -> dict:
    return {
        "status": "ACCEPTED",
        "output": json.dumps({"concept_id": "c_tyre", "format": "short", "directions": [{
            "beat_id": "beat_01", "emotion": "curious", "intensity": intensity, "speed": 1.0,
            "pause_before_ms": 200, "pause_after_ms": 400, "emphasis_terms": terms,
        }]}),
        "provider_id": "direct_gemini_backup",
        "model_id": "gemini-3.5-flash-lite",
        "paid_inference_executed": False,
        "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
        "direct_backup_used": True,
        "direct_backup_free_tier_only": True,
        "direct_backup_may_bill": False,
        "attempts": [],
    }


class DropUnspokenEmphasisTests(unittest.TestCase):
    def test_a_term_not_in_the_narration_is_dropped_and_recorded(self):
        response = json.loads(answer(["touch down", "Smooth Rubber", ""])["output"])
        dropped = runner.drop_unspoken_emphasis(response, request())
        self.assertEqual(dropped, [{"beat_id": "beat_01", "term": "touch down"}])
        # Case does not matter; an empty term is left for the validator to refuse.
        self.assertEqual(response["directions"][0]["emphasis_terms"], ["Smooth Rubber", ""])


class VoiceRunTests(unittest.TestCase):
    def run_with(self, answers: list[dict]) -> tuple[dict, list[dict], Path]:
        calls: list[dict] = []

        def call(payload, **_kwargs):
            calls.append(payload)
            return answers[len(calls) - 1]

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        path = root / "c_tyre.short.voice_request.json"
        path.write_text(json.dumps(request()), encoding="utf-8")
        with (
            patch.object(runner, "resolve_fair_paths", return_value={"repo": root, "env_file": root / ".env", "python": root / "python.exe"}),
            patch.object(runner, "call_fair_bridge", side_effect=call),
            patch.object(runner, "validation_contract_sha256", return_value="contract-hash"),
            patch.object(runner, "MODEL_RUNS_DIR", root / "runs"),
            patch.object(runner, "RAW_OUTPUTS_DIR", root / "raw"),
            patch.object(runner, "RESPONSES_DIR", root / "responses"),
            patch.object(runner, "SPECS_DIR", root / "specs"),
        ):
            report = runner.run_one(path, force=True, config=base.VoiceModelRunnerFallbackTests.config(self))
        return report, calls, root

    def test_the_touch_down_slip_keeps_the_plan(self):
        """31 Oct 2026: "touch down" vs "touches down" stopped the Aviation Tires run."""
        report, calls, root = self.run_with([answer(["touch down", "smooth rubber"])])
        self.assertEqual(report["status"], "VALIDATED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["emphasis_terms_dropped"], [{"beat_id": "beat_01", "term": "touch down"}])
        spec = json.loads((root / "specs" / "c_tyre.short.voice_performance_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["directions"][0]["emphasis_terms"], ["smooth rubber"])

    def test_another_slip_gets_one_corrected_attempt(self):
        report, calls, _root = self.run_with([answer(["smooth rubber"], intensity=0.95), answer(["smooth rubber"])])
        self.assertEqual(report["status"], "VALIDATED")
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["validation_repair_status"], "REPAIRED")
        self.assertIn("intensity", report["first_validation_error"])
        self.assertIn("intensity", calls[1]["prompt"])

    def test_two_slips_still_stop(self):
        report, calls, _root = self.run_with([answer([], intensity=0.95), answer([], intensity=0.99)])
        self.assertEqual(report["status"], "MODEL_OUTPUT_VALIDATION_ERROR")
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["validation_repair_status"], "REPAIR_VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
