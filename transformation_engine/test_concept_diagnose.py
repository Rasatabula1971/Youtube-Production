"""The concept diagnostic captures what Groq refused and why (diagnostic only)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import concept_diagnose as diag
import test_concept_model_runner as runner_tests


# The runner tests' fixtures, without running those tests again here.
FIXTURES = runner_tests.ConceptModelRunnerTests("request")


class ConceptDiagnoseTests(unittest.TestCase):
    def request(self):
        return FIXTURES.request()

    def valid_concept(self):
        return FIXTURES.valid_concept()

    def runner_config(self):
        return FIXTURES.runner_config()

    def run_diagnose(self, status, payload, strict=False, count=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "curiosity_gap.concept_request.json").write_text(json.dumps(self.request()), encoding="utf-8")
            with (
                patch.object(diag, "REQUESTS_DIR", root),
                patch.object(diag, "DIAGNOSTICS_DIR", root / "diag"),
                patch.object(diag.runner, "load_runner_config", return_value=self.runner_config()),
                patch.object(diag, "groq_key", return_value="k"),
                patch.object(diag, "post", return_value=(status, payload)) as post,
            ):
                report = diag.diagnose("curiosity_gap", "openai/gpt-oss-120b", 32768, 30, strict=strict, count=count)
                saved = json.loads(Path(report["text_file"]).with_suffix(".json").read_text())
            body = post.call_args.args[0]
        self.assertEqual(saved["http_status"], status)
        self.assertNotIn('"maxItems"', json.dumps(body["response_format"]))
        self.assertEqual(body["response_format"]["json_schema"].get("strict", False), strict)
        return report

    def test_refusal_keeps_the_failed_generation_and_reason(self):
        cut = json.dumps({"mechanism_id": "curiosity_gap", "concepts": [self.valid_concept()]})[:400]
        report = self.run_diagnose(400, {"error": {
            "code": "json_validate_failed", "type": "invalid_request_error",
            "message": "Failed to validate JSON", "failed_generation": cut}})
        self.assertEqual(report["error_code"], "json_validate_failed")
        self.assertFalse(report["failed_generation_check"]["parses"])
        self.assertEqual(report["failed_generation_check"]["chars"], 400)

    def test_answer_is_validated_by_the_app(self):
        bad = dict(self.valid_concept(), concept_id="bad", source_specific_elements_used=["a source clip"])
        extra = dict(self.valid_concept(), notes="an extra field the provider schema forbids")
        content = json.dumps({"mechanism_id": "curiosity_gap", "concepts": [extra, bad]})
        report = self.run_diagnose(200, {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                                         "usage": {"completion_tokens": 900}})
        check = report["answer_check"]
        self.assertEqual(report["finish_reason"], "stop")
        self.assertTrue(check["parses"])
        self.assertEqual(check["concepts_returned"], 2)
        self.assertEqual(check["accepted"], 1)
        self.assertEqual(len(check["rejected"]), 1)
        self.assertEqual(check["unexpected_fields"], ["notes"])

    def test_a_gateway_refusal_is_reported_with_its_body(self):
        report = self.run_diagnose(403, {"raw": "error code: 1010"})
        self.assertIn("1010", report["unexpected_response"])
        self.assertNotIn("answer_check", report)

    def test_requests_send_a_named_user_agent(self):
        with patch.object(diag.urllib.request, "urlopen", side_effect=OSError("offline")) as urlopen:
            with self.assertRaises(OSError):
                diag.post({"model": "m"}, "k", 5)
        self.assertTrue(urlopen.call_args.args[0].get_header("User-agent").startswith("youtube-production"))

    def test_strict_mode_is_requested_and_reported(self):
        content = json.dumps({"mechanism_id": "curiosity_gap", "concepts": [self.valid_concept()]})
        report = self.run_diagnose(200, {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}, strict=True)
        self.assertTrue(report["strict"])
        self.assertTrue(report["text_file"].endswith(".strict.txt"))
        self.assertEqual(report["answer_check"]["accepted"], 1)

    def test_count_overrides_the_request_and_inspect_compares_requests(self):
        content = json.dumps({"mechanism_id": "curiosity_gap", "concepts": [self.valid_concept()]})
        report = self.run_diagnose(200, {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}, count=2)
        self.assertEqual(report["concept_count_requested"], 2)
        self.assertIn(".n2.", report["text_file"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "curiosity_gap.concept_request.json").write_text(json.dumps(self.request()), encoding="utf-8")
            with patch.object(diag, "REQUESTS_DIR", root), patch.object(diag, "OUTPUT_DIR", root):
                rows = diag.inspect_requests()
        self.assertEqual(rows[0]["mechanism_id"], "curiosity_gap")
        self.assertIn("template_has_human_framing", rows[0])
        self.assertIsNone(rows[0]["last_run_status"])
