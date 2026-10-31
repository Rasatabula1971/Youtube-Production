"""Gemini first, FAIR as the fallback (D-187)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import model_bridge


class Completed:
    returncode = 0


def gemini_answer() -> dict:
    return {
        "status": "ACCEPTED",
        "reason_code": "DIRECT_GEMINI_BACKUP",
        "output": "{}",
        "provider_id": "direct_gemini_backup",
        "paid_inference_executed": False,
        "direct_backup_used": True,
        "direct_backup_free_tier_only": True,
        "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
        "attempts": [],
    }


class GeminiFirstTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.python = Path(tmp.name) / "python.exe"
        self.python.write_text("", encoding="utf-8")
        self.sent_to_fair: list[dict] = []
        self.fair_answer = {"status": "ACCEPTED", "output": "{}", "provider_id": "groq", "paid_inference_executed": False, "attempts": []}

    def fake_run(self, args, **_kwargs):
        self.sent_to_fair.append(json.loads(Path(args[args.index("--input") + 1]).read_text(encoding="utf-8")))
        Path(args[args.index("--output") + 1]).write_text(json.dumps(self.fair_answer), encoding="utf-8")
        return Completed()

    def call(self, *, gemini_first=True, available=True, gemini=None):
        payload = {"action": "solve", "prompt": "test", "expected_schema": {"type": "object"}, "direct_gemini_first": gemini_first}
        with (
            patch.object(model_bridge, "direct_gemini_available", return_value=available),
            patch.object(model_bridge, "call_direct_gemini_backup", side_effect=gemini or (lambda *a, **k: gemini_answer())) as direct,
            patch.object(model_bridge.subprocess, "run", side_effect=self.fake_run),
        ):
            result = model_bridge.call_fair_bridge(payload, python_executable=self.python, timeout_seconds=30)
        return result, direct

    def test_gemini_answers_first_and_fair_is_not_run(self):
        result, direct = self.call()
        self.assertEqual(result["provider_id"], "direct_gemini_backup")
        self.assertEqual(result["reason_code"], "DIRECT_GEMINI_FIRST")
        self.assertTrue(model_bridge.inference_cost_authorized(result))
        self.assertEqual(self.sent_to_fair, [])
        direct.assert_called_once()

    def test_fair_answers_when_gemini_cannot_and_gemini_is_not_asked_twice(self):
        refused = {**model_bridge._GEMINI_FIRST_NOT_RUN, "reason_code": "FAIR_AND_DIRECT_GEMINI_FAILED", "attempts": [{"error_detail": "429"}]}
        self.fair_answer = {"status": "ESCALATION_REQUIRED", "reason_code": "ALL_FREE_MODELS_UNAVAILABLE", "paid_inference_executed": False, "attempts": []}
        result, direct = self.call(gemini=lambda *a, **k: refused)
        direct.assert_called_once()
        self.assertEqual(result["status"], "ESCALATION_REQUIRED")
        self.assertTrue(result["direct_gemini_first"]["tried"])
        self.assertEqual(len(self.sent_to_fair), 1)

    def test_the_flag_is_never_sent_to_fair(self):
        self.call(gemini=lambda *a, **k: dict(model_bridge._GEMINI_FIRST_NOT_RUN))
        self.assertNotIn("direct_gemini_first", self.sent_to_fair[0])

    def test_without_the_billing_attestation_gemini_is_not_called(self):
        result, direct = self.call(available=False)
        direct.assert_not_called()
        self.assertEqual(result["provider_id"], "groq")

    def test_switched_off_fair_comes_first_as_before(self):
        result, direct = self.call(gemini_first=False)
        direct.assert_not_called()
        self.assertEqual(result["provider_id"], "groq")

    def test_the_runner_config_sets_the_flag_on_every_solve_request(self):
        config = {"fair": {}, "runner": {"direct_gemini_first": True}}
        paths = {"repo": Path("r"), "env_file": Path("e")}
        with patch.object(model_bridge, "confirmed_free_providers", return_value=[]):
            payload = model_bridge.bridge_payload(action="solve", prompt="p", schema={}, config=config, paths=paths)
            off = model_bridge.bridge_payload(action="solve", prompt="p", schema={}, config={"fair": {}, "runner": {}}, paths=paths)
        self.assertTrue(payload["direct_gemini_first"])
        self.assertFalse(off["direct_gemini_first"])

    def test_the_shipped_config_puts_gemini_first(self):
        self.assertTrue(model_bridge.load_runner_config()["runner"]["direct_gemini_first"])


if __name__ == "__main__":
    unittest.main()
