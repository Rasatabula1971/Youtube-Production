import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_model_runner import (
    build_model_prompt,
    call_direct_gemini_backup,
    call_fair_bridge,
    confirmed_free_providers,
    gemini_compatible_schema,
    inference_cost_authorized,
    parse_model_json,
    response_schema,
    restrict_response_to_request,
    run_one,
)


class AnalysisModelRunnerTests(unittest.TestCase):
    def request(self):
        return {
            "video_id": "v1",
            "study_id": "h1",
            "source": {"title": "F1 Gearbox"},
            "mechanism_taxonomy": {
                "curiosity_gap": "Curiosity",
                "hidden_mechanism": "Hidden mechanism",
            },
            "evidence_library": {
                "metadata.title": {
                    "evidence_id": "metadata.title",
                    "type": "metadata",
                    "observation": "Why F1 Gearboxes Are Strange",
                },
                "transcript.open": {
                    "evidence_id": "transcript.open",
                    "type": "transcript",
                    "observation": "Why does it need eight gears?",
                },
            },
            "dimensions": {
                "packaging": {
                    "evidence_refs": ["metadata.title"],
                },
                "opening_hook": {
                    "evidence_refs": ["transcript.open"],
                },
            },
            "instructions": [],
            "request_provenance": {},
        }

    def profile(self):
        return {
            "schema_version": "2.0",
            "experiment_id": "02",
            "study_id": "h1",
            "video_id": "v1",
            "source": {"channel_id": "c1"},
            "source_inputs": {},
            "evidence": [
                {
                    "evidence_id": "metadata.title",
                    "type": "metadata",
                    "locator": "video title",
                    "observation": "Why F1 Gearboxes Are Strange",
                },
                {
                    "evidence_id": "transcript.open",
                    "type": "transcript",
                    "locator": "00:00:00.000-00:00:05.000",
                    "observation": "Why does it need eight gears?",
                },
                {
                    "evidence_id": "transcript.hidden",
                    "type": "transcript",
                    "locator": "00:01:00.000-00:01:05.000",
                    "observation": "Evidence the model was not shown.",
                },
            ],
            "analysis": {
                "packaging": {"findings": [], "notes": ""},
                "opening_hook": {"findings": [], "notes": ""},
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [],
                "source_specific_elements": [],
                "transformation_opportunities": [],
            },
        }

    def valid_response(self):
        return {
            "video_id": "v1",
            "analysis": {
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "The opening poses a direct question.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": ["transcript.open"],
                            "confidence": "MODERATE",
                        }
                    ],
                    "notes": "",
                },
                "packaging": {
                    "findings": [],
                    "notes": "",
                },
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [],
                "source_specific_elements": [],
                "transformation_opportunities": [],
            },
        }

    def experiment_config(self):
        return {
            "required_dimensions": ["packaging", "opening_hook"],
            "allowed_confidence": ["LOW", "MODERATE", "HIGH"],
            "evidence_types": [
                "metadata",
                "transcript",
                "thumbnail",
                "opening_frame",
                "visual_note",
                "timing_note",
                "audio_note",
                "opportunity_evidence",
            ],
            "dimension_evidence_types": {
                "packaging": ["metadata", "thumbnail", "opening_frame"],
                "opening_hook": [
                    "transcript",
                    "opening_frame",
                    "visual_note",
                    "audio_note",
                ],
            },
            "mechanism_taxonomy": {
                "curiosity_gap": "Curiosity",
                "hidden_mechanism": "Hidden mechanism",
            },
            "causal_warning_phrases": [
                "made it viral",
                "caused the views",
            ],
        }

    def runner_config(self):
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

    def test_schema_locks_video_id_and_mechanisms(self):
        schema = response_schema(self.request())

        self.assertEqual(
            schema["properties"]["video_id"]["const"],
            "v1",
        )
        mechanism_enum = schema["properties"]["analysis"]["properties"]["opening_hook"][
            "properties"
        ]["findings"]["items"]["properties"]["mechanism_ids"]["items"]["enum"]
        self.assertEqual(
            mechanism_enum,
            ["curiosity_gap", "hidden_mechanism"],
        )

    def test_prompt_is_bounded(self):
        prompt = build_model_prompt(
            self.request(),
            maximum_chars=95000,
        )
        self.assertIn("ANALYSIS REQUEST", prompt)

        with self.assertRaises(ValueError):
            build_model_prompt(
                self.request(),
                maximum_chars=20,
            )

    def test_code_fenced_json_is_parsed(self):
        payload = self.valid_response()
        fence = chr(96) * 3
        output = fence + "json\n" + json.dumps(payload) + "\n" + fence

        parsed = parse_model_json(output)

        self.assertEqual(parsed["video_id"], "v1")

    def test_response_scope_removes_unseen_evidence_refs(self):
        response = self.valid_response()
        response["analysis"]["opening_hook"]["findings"][0]["evidence_refs"] = [
            "transcript.open",
            "transcript.hidden",
        ]

        restricted, removals = restrict_response_to_request(
            response,
            self.request(),
        )

        self.assertEqual(
            restricted["analysis"]["opening_hook"]["findings"][0]["evidence_refs"],
            ["transcript.open"],
        )
        self.assertEqual(len(removals), 1)

    def test_confirmations_merge_config_and_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "FAIR_CONFIRMED_FREE_PROVIDERS=groq,mistral\n",
                encoding="utf-8",
            )
            config = self.runner_config()
            config["fair"]["confirmed_free_providers"] = ["google_gemini_api"]
            with patch.dict("os.environ", {}, clear=True):
                providers = confirmed_free_providers(
                    config,
                    env_file,
                )

        self.assertEqual(
            providers,
            ["google_gemini_api", "groq", "mistral"],
        )

    @patch("analysis_model_runner.load_experiment_config")
    @patch("analysis_model_runner.resolve_fair_paths")
    @patch("analysis_model_runner.call_fair_bridge")
    def test_run_one_applies_accepted_response(
        self,
        call_bridge,
        resolve_paths,
        load_config,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "v1.analysis_request.json"
            profile_path = root / "v1.profile.json"

            request = self.request()
            request["request_provenance"] = {
                "profile_source": str(profile_path),
            }
            request_path.write_text(
                json.dumps(request),
                encoding="utf-8",
            )
            profile_path.write_text(
                json.dumps(self.profile()),
                encoding="utf-8",
            )

            load_config.return_value = self.experiment_config()
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "reason_code": "QUALITY_ACCEPTED",
                "request_id": "req-1",
                "output": json.dumps(self.valid_response()),
                "provider_id": "kilo_free",
                "model_id": "model-free",
                "best_quality_score": 85.0,
                "verification_state": "SCHEMA_VERIFIED",
                "paid_inference_executed": False,
                "attempts": [],
            }

            import analysis_model_runner as module

            old_runs = module.MODEL_RUNS_DIR
            old_responses = module.MODEL_RESPONSES_DIR
            old_raw = module.RAW_OUTPUTS_DIR
            old_analyzed = module.ANALYZED_DIR
            try:
                module.MODEL_RUNS_DIR = root / "runs"
                module.MODEL_RESPONSES_DIR = root / "responses"
                module.RAW_OUTPUTS_DIR = root / "raw"
                module.ANALYZED_DIR = root / "analyzed"

                result = run_one(
                    request_path,
                    profile_path=profile_path,
                    force=False,
                    runner_config=self.runner_config(),
                )
            finally:
                module.MODEL_RUNS_DIR = old_runs
                module.MODEL_RESPONSES_DIR = old_responses
                module.RAW_OUTPUTS_DIR = old_raw
                module.ANALYZED_DIR = old_analyzed

        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual(result["provider_id"], "kilo_free")
        self.assertEqual(result["apply"]["accepted_findings"], 1)

    @patch("analysis_model_runner.load_experiment_config")
    @patch("analysis_model_runner.resolve_fair_paths")
    @patch("analysis_model_runner.call_fair_bridge")
    def test_invalid_final_profile_is_not_applied(
        self,
        call_bridge,
        resolve_paths,
        load_config,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "v1.analysis_request.json"
            profile_path = root / "v1.profile.json"

            request = self.request()
            request["request_provenance"] = {
                "profile_source": str(profile_path),
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")

            broken_profile = self.profile()
            broken_profile["schema_version"] = "1.0"
            profile_path.write_text(
                json.dumps(broken_profile),
                encoding="utf-8",
            )

            load_config.return_value = self.experiment_config()
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "reason_code": "QUALITY_ACCEPTED",
                "request_id": "req-2",
                "output": json.dumps(self.valid_response()),
                "provider_id": "kilo_free",
                "model_id": "model-free",
                "best_quality_score": 85.0,
                "verification_state": "SCHEMA_VERIFIED",
                "paid_inference_executed": False,
                "attempts": [],
            }

            import analysis_model_runner as module

            old_runs = module.MODEL_RUNS_DIR
            old_responses = module.MODEL_RESPONSES_DIR
            old_raw = module.RAW_OUTPUTS_DIR
            old_analyzed = module.ANALYZED_DIR
            try:
                module.MODEL_RUNS_DIR = root / "runs"
                module.MODEL_RESPONSES_DIR = root / "responses"
                module.RAW_OUTPUTS_DIR = root / "raw"
                module.ANALYZED_DIR = root / "analyzed"

                result = run_one(
                    request_path,
                    profile_path=profile_path,
                    force=True,
                    runner_config=self.runner_config(),
                )
            finally:
                module.MODEL_RUNS_DIR = old_runs
                module.MODEL_RESPONSES_DIR = old_responses
                module.RAW_OUTPUTS_DIR = old_raw
                module.ANALYZED_DIR = old_analyzed

        self.assertEqual(result["status"], "APPLY_VALIDATION_FAILED")

    def test_gemini_schema_sanitizer_converts_unsupported_keywords(self):
        schema = {
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "const": "c1",
                    "minLength": 1,
                },
                "tags": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "maxLength": 20},
                },
            },
            "required": ["concept_id", "tags"],
            "additionalProperties": False,
        }
        normalized = gemini_compatible_schema(schema)
        concept = normalized["properties"]["concept_id"]
        tags = normalized["properties"]["tags"]
        self.assertEqual(concept["enum"], ["c1"])
        self.assertNotIn("const", concept)
        self.assertNotIn("minLength", concept)
        self.assertNotIn("uniqueItems", tags)
        self.assertNotIn("maxLength", tags["items"])

    def test_direct_gemini_backup_is_explicitly_authorized_not_marked_free(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {"text": '{"scores":[],"summary":"ok"}'}
                                    ]
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        fair_result = {
            "status": "ESCALATION_REQUIRED",
            "reason_code": "ALL_FREE_MODELS_UNAVAILABLE",
            "paid_inference_executed": False,
            "attempts": [],
        }
        payload = {
            "prompt": "score concepts",
            "expected_schema": {
                "type": "object",
                "properties": {
                    "scores": {"type": "array", "items": {"type": "object"}},
                    "summary": {"type": "string"},
                },
                "required": ["scores", "summary"],
            },
        }
        with (
            patch.dict(
                "os.environ",
                {
                    "DIRECT_GEMINI_API_KEY": "test-key",
                    "DIRECT_GEMINI_MODEL": "gemini-test",
                },
                clear=False,
            ),
            patch("analysis_model_runner.urllib.request.urlopen", return_value=FakeResponse()),
        ):
            result = call_direct_gemini_backup(
                payload,
                timeout_seconds=30,
                fair_result=fair_result,
            )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["provider_id"], "direct_gemini_backup")
        self.assertEqual(result["model_id"], "gemini-test")
        self.assertTrue(result["direct_backup_used"])
        self.assertTrue(result["direct_backup_may_bill"])
        self.assertIsNone(result["paid_inference_executed"])
        self.assertTrue(inference_cost_authorized(result))

    def test_shared_bridge_uses_direct_backup_after_clean_fair_escalation(self):
        class Completed:
            returncode = 0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / "python.exe"
            python.write_text("", encoding="utf-8")

            def fake_run(args, **_kwargs):
                output = Path(args[args.index("--output") + 1])
                output.write_text(
                    json.dumps(
                        {
                            "status": "ESCALATION_REQUIRED",
                            "reason_code": "ALL_FREE_MODELS_UNAVAILABLE",
                            "paid_inference_executed": False,
                            "attempts": [],
                        }
                    ),
                    encoding="utf-8",
                )
                return Completed()

            backup = {
                "status": "ACCEPTED",
                "provider_id": "direct_gemini_backup",
                "paid_inference_executed": None,
                "direct_backup_used": True,
                "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
            }
            with (
                patch.dict(
                    "os.environ",
                    {"DIRECT_GEMINI_API_KEY": "test-key"},
                    clear=False,
                ),
                patch("analysis_model_runner.subprocess.run", side_effect=fake_run),
                patch(
                    "analysis_model_runner.call_direct_gemini_backup",
                    return_value=backup,
                ) as direct_backup,
            ):
                result = call_fair_bridge(
                    {
                        "prompt": "test",
                        "expected_schema": {"type": "object"},
                    },
                    python_executable=python,
                    timeout_seconds=30,
                )

        self.assertEqual(result["provider_id"], "direct_gemini_backup")
        direct_backup.assert_called_once()

    def test_shared_bridge_does_not_backup_unknown_fair_cost(self):
        class Completed:
            returncode = 0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / "python.exe"
            python.write_text("", encoding="utf-8")

            def fake_run(args, **_kwargs):
                output = Path(args[args.index("--output") + 1])
                output.write_text(
                    json.dumps(
                        {
                            "status": "BRIDGE_ERROR",
                            "paid_inference_executed": None,
                            "cost_state": "UNKNOWN_AFTER_DISPATCH",
                            "attempts": [],
                        }
                    ),
                    encoding="utf-8",
                )
                return Completed()

            with (
                patch.dict(
                    "os.environ",
                    {"DIRECT_GEMINI_API_KEY": "test-key"},
                    clear=False,
                ),
                patch("analysis_model_runner.subprocess.run", side_effect=fake_run),
                patch(
                    "analysis_model_runner.call_direct_gemini_backup"
                ) as direct_backup,
            ):
                result = call_fair_bridge(
                    {
                        "prompt": "test",
                        "expected_schema": {"type": "object"},
                    },
                    python_executable=python,
                    timeout_seconds=30,
                )

        self.assertEqual(result["status"], "BRIDGE_ERROR")
        direct_backup.assert_not_called()

    def test_unknown_fair_cost_is_never_authorized_implicitly(self):
        result = {
            "status": "BRIDGE_ERROR",
            "paid_inference_executed": None,
            "cost_state": "UNKNOWN_AFTER_DISPATCH",
        }
        self.assertFalse(inference_cost_authorized(result))

    @patch("analysis_model_runner.resolve_fair_paths")
    @patch("analysis_model_runner.call_fair_bridge")
    def test_paid_inference_fails_closed(
        self,
        call_bridge,
        resolve_paths,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "v1.analysis_request.json"
            profile_path = root / "v1.profile.json"
            request = self.request()
            request["request_provenance"] = {
                "profile_source": str(profile_path),
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")
            profile_path.write_text(
                json.dumps(self.profile()),
                encoding="utf-8",
            )
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "paid_inference_executed": True,
            }

            import analysis_model_runner as module

            old_runs = module.MODEL_RUNS_DIR
            try:
                module.MODEL_RUNS_DIR = root / "runs"
                result = run_one(
                    request_path,
                    profile_path=profile_path,
                    force=True,
                    runner_config=self.runner_config(),
                )
            finally:
                module.MODEL_RUNS_DIR = old_runs

        self.assertEqual(result["status"], "COST_POLICY_VIOLATION")


if __name__ == "__main__":
    unittest.main()
