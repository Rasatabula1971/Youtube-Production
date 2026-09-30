from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import voice_model_runner as runner


class VoiceModelRunnerFallbackTests(unittest.TestCase):
    def config(self) -> dict:
        return {
            "adapter": "fair_subprocess",
            "fair": {
                "quality_level": "standard",
                "task_type": "youtube_structured_pipeline",
                "max_attempts": 3,
                "max_unanswered_attempts": 6,
                "max_verification_attempts": 1,
                "timeout_seconds": 45,
                "cross_check_required": False,
                "max_output_tokens": 4096,
                "cache_mode": "bypass",
                "priority": "P2",
                "client_id": "test",
                "application_id": "youtube-production",
                "confirmed_free_providers": [],
            },
            "runner": {
                "max_prompt_chars": 95000,
                "subprocess_timeout_seconds": 30,
                "max_requests_per_batch": 4,
            },
        }

    def request(self) -> dict:
        return {
            "concept_id": "c1",
            "format": "long_form",
            "title": "Title",
            "beats": [
                {
                    "beat_id": "b1",
                    "immutable_narration": "Narration.",
                    "reveal_beat": False,
                }
            ],
            "performance_controls": {
                "allowed_emotions": ["neutral"],
                "max_intensity": 0.7,
                "speed_min": 0.9,
                "speed_max": 1.1,
                "pause_ms_max": 1200,
                "emphasis_terms_max": 4,
            },
        }

    def test_authorized_free_tier_direct_gemini_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "c1.long_form.voice_request.json"
            request_path.write_text(json.dumps(self.request()), encoding="utf-8")

            result = {
                "status": "ACCEPTED",
                "reason_code": "DIRECT_GEMINI_BACKUP",
                "request_id": "direct-gemini-test",
                "output": '{"concept_id":"c1","format":"long_form","directions":[]}',
                "provider_id": "direct_gemini_backup",
                "model_id": "gemini-3.5-flash",
                "paid_inference_executed": None,
                "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
                "direct_backup_used": True,
                "direct_backup_free_tier_only": True,
                "direct_backup_may_bill": False,
                "attempts": [],
            }

            with (
                patch.object(
                    runner,
                    "resolve_fair_paths",
                    return_value={
                        "repo": root,
                        "env_file": root / ".env",
                        "python": root / "python.exe",
                    },
                ),
                patch.object(runner, "call_fair_bridge", return_value=result),
                patch.object(
                    runner,
                    "parse_model_json",
                    return_value={
                        "concept_id": "c1",
                        "format": "long_form",
                        "directions": [],
                    },
                ),
                patch.object(
                    runner,
                    "validate_response",
                    return_value={"valid": True, "errors": [], "directions": []},
                ),
                patch.object(
                    runner,
                    "validation_contract_sha256",
                    return_value="contract-hash",
                ),
                patch.object(runner, "MODEL_RUNS_DIR", root / "runs"),
                patch.object(runner, "RAW_OUTPUTS_DIR", root / "raw"),
                patch.object(runner, "RESPONSES_DIR", root / "responses"),
                patch.object(runner, "SPECS_DIR", root / "specs"),
            ):
                run = runner.run_one(
                    request_path,
                    force=True,
                    config=self.config(),
                )

        self.assertEqual(run["status"], "VALIDATED")
        self.assertTrue(run["direct_backup_used"])
        self.assertTrue(run["direct_backup_free_tier_only"])
        self.assertFalse(run["direct_backup_may_bill"])


if __name__ == "__main__":
    unittest.main()
