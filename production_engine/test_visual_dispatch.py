"""Paid premium-visual dispatch for authorized shots (D-140)."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_budget
import visual_dispatch as dispatch
import visual_generated_asset_import as importer
import test_visual_generated_asset_import as base
from test_visual_generated_asset_import import write_json

PNG = b"\x89PNG\r\n\x1a\n"


class VisualDispatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = self.root = Path(tmp.name)
        gap = write_json(root / "gap.json", {"version": 1})
        spend = write_json(root / "spend.json", {"version": 1})
        request = base.VisualGeneratedAssetImportTests.request(None, gap, spend)
        request["generation_brief"] = {
            "subject_and_action": "A brake disc glowing orange on a test rig",
            "lighting": "low key",
            "negative_constraints": ["No logos."],
        }
        self.request_path = write_json(root / "requests" / "c1.short.shot-001.visual_generation_request.json", request)
        budget_config = write_json(root / "budget.json", {"target_usd": 5, "ceiling_usd": 10})
        self.config = {
            "active_provider": "openai_compatible",
            "variants_per_shot": 2,
            "providers": {"openai_compatible": {
                "kind": "OPENAI_COMPATIBLE_IMAGES", "endpoint": "https://img.example/v1", "model": "m1",
                "api_key_env": "VISUAL_PROVIDER_API_KEY", "price_per_image_usd": 0.5,
                "license": "Commercial use per terms", "contract_verified": True,
            }},
        }
        for item in (
            patch.object(dispatch, "REQUEST_DIR", root / "requests"),
            patch.object(importer, "REQUEST_DIR", root / "requests"),
            patch.object(importer, "ASSET_DIR", root / "assets"),
            patch.object(importer, "REGISTRY_DIR", root / "registry"),
            patch.object(dispatch, "OUTPUT", root),
            patch.object(dispatch, "CANDIDATES_DIR", root / "candidates"),
            patch.object(dispatch, "HISTORY_FILE", root / "history.jsonl"),
            patch.object(dispatch, "load_config", side_effect=lambda: copy.deepcopy(self.config)),
            patch.object(video_budget, "CONFIG_FILE", budget_config),
            patch.dict("os.environ", {"VISUAL_PROVIDER_API_KEY": "secret"}),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.calls = []

    def fake(self, prompt, *, count, settings):
        self.calls.append((prompt, count))
        return [{"bytes": PNG + bytes([len(self.calls), i]), "provider_job_id": f"j{i}"} for i in range(count)]

    def generate(self):
        return dispatch.generate(request_file=self.request_path, reviewer="me", adapters={"OPENAI_COMPATIBLE_IMAGES": self.fake})

    def test_nothing_is_called_until_a_provider_is_configured(self):
        self.config["active_provider"] = ""
        with self.assertRaisesRegex(ValueError, "not available"):
            self.generate()
        self.config["active_provider"] = "openai_compatible"
        self.config["providers"]["openai_compatible"]["price_per_image_usd"] = None
        self.assertIn("never guessed", " ".join(dispatch.provider_status(self.config)["problems"]))
        self.assertEqual(self.calls, [])

    def test_variants_are_generated_from_the_brief_and_spend_is_recorded(self):
        view = self.generate()
        prompt, count = self.calls[0]
        self.assertEqual(count, 2)
        self.assertIn("brake disc glowing orange", prompt)
        self.assertIn("No logos.", prompt)
        self.assertEqual(len(view["candidates"]), 2)
        self.assertEqual(view["spent_usd"], 1.0)
        ledger = video_budget.read_jsonl(self.root / "video_budget_ledger.jsonl")
        self.assertEqual((ledger[-1]["event"], ledger[-1]["amount_usd"]), ("ACTUAL", 1.0))

    def test_generation_stops_at_the_shots_authorized_maximum(self):
        self.generate()
        self.generate()  # 2.0 of 2.5 spent
        with self.assertRaisesRegex(ValueError, "authorized \\$2.50"):
            self.generate()
        self.assertEqual(len(self.calls), 2)

    def test_the_human_chooses_one_variant_and_it_is_registered(self):
        view = self.generate()
        chosen = view["candidates"][1]["candidate_id"]
        result = dispatch.choose(request_file=self.request_path, candidate_id=chosen)
        self.assertEqual(result["status"], "REGISTERED_CURRENT")
        self.assertEqual(result["actual_cost_usd"], 1.0)
        self.assertEqual(result["execution_origin"], "APP_PROVIDER_DISPATCH")
        self.assertTrue(result["app_provider_call_executed"])
        self.assertTrue(dispatch.candidate_file_path(self.request_path, chosen).is_file())
        with self.assertRaisesRegex(ValueError, "Unknown generated variant"):
            dispatch.choose(request_file=self.request_path, candidate_id="nope")

    def test_only_current_requests_in_the_request_folder_are_accepted(self):
        outside = write_json(self.root / "elsewhere" / "x.visual_generation_request.json", json.loads(self.request_path.read_text()))
        with self.assertRaisesRegex(ValueError, "Invalid visual generation request"):
            dispatch.generate(request_file=outside, adapters={"OPENAI_COMPATIBLE_IMAGES": self.fake})
        write_json(self.root / "gap.json", {"version": 2})  # the gap plan changed
        with self.assertRaisesRegex(ValueError, "STALE"):
            self.generate()

    def test_concurrent_generations_cannot_both_pass_the_authorization(self):
        import concurrent.futures

        payload = json.loads(self.request_path.read_text())
        payload["spend_authorization"]["max_cost_usd"] = 1.5
        self.request_path.write_text(json.dumps(payload))
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.generate) for _ in range(2)]
            outcomes = []
            for future in futures:
                try:
                    future.result(10)
                    outcomes.append("ok")
                except ValueError:
                    outcomes.append("refused")
        self.assertEqual(sorted(outcomes), ["ok", "refused"])
        self.assertEqual(dispatch.spent_on_shot("c1.short.shot-001"), 1.0)

    def test_variants_from_an_earlier_request_cannot_be_chosen(self):
        old = self.generate()["candidates"][0]["candidate_id"]
        request = json.loads(self.request_path.read_text())
        request["generation_brief"]["subject_and_action"] = "A turbine blade cross section"
        self.request_path.write_text(json.dumps(request))
        self.assertEqual(dispatch.shot_view(self.request_path)["candidates"], [])
        with self.assertRaisesRegex(ValueError, "Unknown generated variant"):
            dispatch.choose(request_file=self.request_path, candidate_id=old)

    def test_non_https_endpoint_is_not_ready(self):
        self.config["providers"]["openai_compatible"]["endpoint"] = "file:///etc/passwd"
        self.assertIn("https", " ".join(dispatch.provider_status(self.config)["problems"]))


if __name__ == "__main__":
    unittest.main()
