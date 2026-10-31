"""One corrected attempt when a packaging answer fails validation (D-186)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from packaging_engine import psychological_angle_model_runner as runner
from packaging_engine import validation_repair as repair


def accepted(output: dict) -> dict:
    return {
        "status": "ACCEPTED",
        "output": json.dumps(output),
        "provider_id": "groq",
        "model_id": "openai/gpt-oss-120b",
        "paid_inference_executed": False,
        "attempts": [],
    }


def check(answer: dict) -> None:
    if answer.get("bad"):
        raise ValueError("angle-mystery.viewer_question invents unsupported number '300'")


class AttemptRepairTests(unittest.TestCase):
    def test_the_error_and_previous_answer_go_back_to_the_model(self):
        sent: list[dict] = []

        def call(payload):
            sent.append(payload)
            return accepted({"angles": "fixed"})

        result = repair.attempt_repair(
            payload={"prompt": "PROMPT", "settings": {}},
            raw='{"bad": true}',
            error="invents unsupported number '300'",
            call=call,
            check=check,
        )
        self.assertEqual(result["status"], "REPAIRED")
        self.assertEqual(result["parsed"], {"angles": "fixed"})
        prompt = sent[0]["prompt"]
        self.assertTrue(prompt.startswith("PROMPT"))
        self.assertIn("invents unsupported number '300'", prompt)
        self.assertIn('{"bad": true}', prompt)

    def test_a_second_slip_is_reported_not_accepted(self):
        result = repair.attempt_repair(
            payload={"prompt": "PROMPT"},
            raw="{}",
            error="first",
            call=lambda payload: accepted({"bad": True}),
            check=check,
        )
        self.assertEqual(result["status"], "REPAIR_VALIDATION_ERROR")
        self.assertEqual(repair.failure_status(result), "MODEL_OUTPUT_VALIDATION_ERROR")

    def test_the_corrected_attempt_obeys_the_cost_policy(self):
        paid = {**accepted({}), "paid_inference_executed": True}
        result = repair.attempt_repair(
            payload={"prompt": "PROMPT"}, raw="{}", error="first", call=lambda payload: paid, check=check
        )
        self.assertEqual(repair.failure_status(result), "COST_POLICY_VIOLATION")


class AngleRunnerRepairTests(unittest.TestCase):
    def run_with(self, answers: list[dict]) -> tuple[dict, list[dict]]:
        calls: list[dict] = []

        def call(payload, **kwargs):
            calls.append(payload)
            return answers[len(calls) - 1]

        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            request_path = root / "c1_short.psychological_angle_request.json"
            request_path.write_text(json.dumps({"video_id": "c1:short"}), encoding="utf-8")
            for name, value in (
                ("MODEL_RUNS_DIR", root / "runs"),
                ("RAW_OUTPUTS_DIR", root / "raw"),
                ("RESPONSES_DIR", root / "responses"),
            ):
                stack.enter_context(patch.object(runner, name, value))
            stack.enter_context(patch.object(runner, "request_is_current", return_value={"video_id": "c1:short"}))
            stack.enter_context(patch.object(runner, "response_schema", return_value={}))
            stack.enter_context(patch.object(runner, "build_prompt", return_value="PROMPT"))
            stack.enter_context(patch.object(runner, "resolve_fair_paths", return_value={"python": "python"}))
            stack.enter_context(
                patch.object(runner, "bridge_payload", side_effect=lambda **kw: {"prompt": kw["prompt"], "settings": {}})
            )
            stack.enter_context(patch.object(runner, "call_fair_bridge", side_effect=call))
            stack.enter_context(patch.object(runner, "validate_response", side_effect=lambda answer, request: check(answer)))
            report = runner.run_one(request_path, force=True, runner_config={"runner": {}})
        return report, calls

    def test_a_slip_is_corrected_in_the_same_run(self):
        """The "300" slip stopped the run; now the model gets one corrected attempt."""
        report, calls = self.run_with([accepted({"bad": True}), accepted({"angles": []})])
        self.assertEqual(report["status"], "VALIDATED")
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["validation_repair_status"], "REPAIRED")
        self.assertIn("'300'", report["first_validation_error"])

    def test_two_slips_still_stop_with_both_errors(self):
        report, calls = self.run_with([accepted({"bad": True}), accepted({"bad": True})])
        self.assertEqual(report["status"], "MODEL_OUTPUT_VALIDATION_ERROR")
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["validation_repair_status"], "REPAIR_VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
