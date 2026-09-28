from __future__ import annotations

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fair_bridge


class FakeFair:
    last_kwargs = None
    last_solve_kwargs = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self.skipped = {"provider-x": "not configured"}
        model = SimpleNamespace(
            model_id="schema-model",
            capabilities={"structured_output", "text"},
            max_output_tokens=4096,
            active=True,
        )
        provider = SimpleNamespace(
            provider_id="schema-provider",
            models=[model],
        )
        self._registry = SimpleNamespace(
            providers={"schema-provider": provider}
        )

    def providers(self):
        return ["kilo_free"]

    async def solve(self, prompt, **kwargs):
        type(self).last_solve_kwargs = kwargs
        return SimpleNamespace(
            status="ACCEPTED",
            reason_code="QUALITY_ACCEPTED",
            request_id="req-1",
            output='{"ok": true}',
            provider_id="kilo_free",
            model_id="free-model",
            best_quality_score=91.0,
            verification_state="SCHEMA_VERIFIED",
            paid_inference_executed=False,
            attempts=[],
        )

    async def close(self):
        return None


class BrokenFair:
    def __init__(self, **kwargs):
        raise TypeError("constructor contract changed")


class CloseFailingFair(FakeFair):
    async def close(self):
        raise RuntimeError("close failed")


class SolveFailingFair(FakeFair):
    async def solve(self, prompt, **kwargs):
        raise RuntimeError("provider connection dropped after dispatch")


def fake_module(fair_class):
    module = types.ModuleType("fair")
    module.FAIR = fair_class
    return module


class FairBridgeTests(unittest.TestCase):
    def payload(self, repo: Path, action="analyze"):
        return {
            "fair_repo_path": str(repo),
            "env_file": "",
            "confirmed_free_providers": ["kilo_free"],
            "action": action,
            "prompt": "Analyze this.",
            "expected_schema": {"type": "object"},
            "settings": {
                "quality_level": "standard",
                "max_attempts": 3,
                "max_unanswered_attempts": 6,
                "max_verification_attempts": 1,
                "timeout_seconds": 45,
                "cross_check_required": False,
                "max_output_tokens": 2048,
                "client_id": "test-client",
                "application_id": "youtube-production",
                "expected_schema_present": True,
                "priority": "P2",
                "cache_mode": "bypass",
            },
        }

    def test_doctor_uses_current_fair_constructor_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(sys.modules, {"fair": fake_module(FakeFair)}):
                result = asyncio.run(
                    fair_bridge.execute(self.payload(repo, action="doctor"))
                )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["providers"], ["kilo_free"])
        self.assertFalse(result["paid_inference_executed"])
        self.assertEqual(FakeFair.last_kwargs["max_attempts"], 3)
        self.assertEqual(
            FakeFair.last_kwargs["application_id"],
            "youtube-production",
        )
        self.assertTrue(
            result["compatibility"]["compatible_route_available"]
        )
        self.assertEqual(
            FakeFair.last_kwargs["confirmed_free_providers"],
            {"kilo_free"},
        )

    def test_doctor_reports_close_failure_instead_of_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(
                sys.modules,
                {"fair": fake_module(CloseFailingFair)},
            ):
                result = asyncio.run(
                    fair_bridge.execute(
                        self.payload(repo, action="doctor")
                    )
                )

        self.assertEqual(
            result["status"],
            "DOCTOR_CLOSE_FAILED",
        )
        self.assertEqual(
            result["error_type"],
            "RuntimeError",
        )
        self.assertFalse(
            result["paid_inference_executed"]
        )

    def test_analysis_uses_current_fair_solve_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(sys.modules, {"fair": fake_module(FakeFair)}):
                result = asyncio.run(
                    fair_bridge.execute(self.payload(repo))
                )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["provider_id"], "kilo_free")
        self.assertFalse(result["paid_inference_executed"])
        self.assertEqual(
            FakeFair.last_solve_kwargs["cache_mode"],
            "bypass",
        )
        self.assertEqual(
            FakeFair.last_solve_kwargs["client_id"],
            "test-client",
        )
        self.assertEqual(
            FakeFair.last_solve_kwargs["task_type"],
            "youtube_structured_pipeline",
        )

    def test_constructor_contract_failure_is_reported_without_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(sys.modules, {"fair": fake_module(BrokenFair)}):
                result = asyncio.run(
                    fair_bridge.execute(self.payload(repo))
                )

        self.assertEqual(result["status"], "BRIDGE_ERROR")
        self.assertEqual(result["error_type"], "TypeError")
        self.assertFalse(result["paid_inference_executed"])


    def test_solve_exception_after_dispatch_has_unknown_cost_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with patch.dict(sys.modules, {"fair": fake_module(SolveFailingFair)}):
                result = asyncio.run(fair_bridge.execute(self.payload(repo)))
        self.assertEqual(result["status"], "BRIDGE_ERROR")
        self.assertIsNone(result["paid_inference_executed"])
        self.assertEqual(result["cost_state"], "UNKNOWN_AFTER_DISPATCH")


if __name__ == "__main__":
    unittest.main()
