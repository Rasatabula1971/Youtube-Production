"""Candidate subject images: provider gating, spend caps, import and choice (D-135)."""

from __future__ import annotations

import base64
import copy
import json
from unittest.mock import patch

from production_engine import thumbnail_image_provider as images
from production_engine import thumbnail_review as review
from production_engine.test_thumbnail_render import RID, PipelineTestCase

PNG = b"\x89PNG\r\n\x1a\n" + b"candidate"


def configured(**overrides):
    config = copy.deepcopy(images.render.load_json(images.CONFIG_FILE))
    config["active_provider"] = "openai_compatible"
    config["providers"]["openai_compatible"].update(
        {
            "endpoint": "https://images.example/v1/images/generations",
            "model": "image-model-1",
            "price_per_image_usd": 0.04,
            "license": "Commercial use per provider terms",
            "contract_verified": True,
        }
    )
    config.update(overrides)
    return config


class ProviderTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.set_units()
        self.config = configured()
        for item in (
            patch.object(images, "load_config", side_effect=lambda: self.config),
            patch.dict("os.environ", {"THUMBNAIL_IMAGE_API_KEY": "secret"}),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.calls = []

    def fake(self, prompt, *, count, settings):
        self.calls.append((prompt, count, settings["model"]))
        return [{"bytes": PNG + bytes([index]), "provider_job_id": f"job-{index}"} for index in range(count)]

    def generate(self, max_cost="0.12"):
        return images.generate(
            render_id=RID, max_cost_usd=max_cost, reviewer="me",
            adapters={"OPENAI_COMPATIBLE_IMAGES": self.fake},
        )

    def test_nothing_is_called_until_a_provider_is_fully_configured(self):
        self.config = images.render.load_json(images.CONFIG_FILE)
        status = images.provider_status(self.config)
        self.assertFalse(status["ready"])
        self.assertIn("No image provider has been chosen", status["problems"][0])
        self.config = configured(active_provider="openai_compatible")
        self.config["providers"]["openai_compatible"]["price_per_image_usd"] = None
        self.config["providers"]["openai_compatible"]["contract_verified"] = False
        problems = " ".join(images.provider_status(self.config)["problems"])
        self.assertIn("never guessed", problems)
        self.assertIn("not verified", problems)
        with self.assertRaisesRegex(ValueError, "not available"):
            self.generate()
        self.assertEqual(self.calls, [])

    def test_prompt_is_built_from_the_concept_without_text(self):
        unit = images._current_unit(RID)
        prompt = images.build_prompt(unit)
        self.assertIn(str(unit["hero_subject"]), prompt)
        self.assertIn("No text, letters, numbers, logos", prompt)

    def test_generation_needs_an_explicit_cost_within_the_caps_and_is_ledgered(self):
        with self.assertRaisesRegex(ValueError, "below the estimate"):
            self.generate("0.05")
        with self.assertRaisesRegex(ValueError, "per-thumbnail cap"):
            self.generate("5")
        with self.assertRaisesRegex(ValueError, "maximum cost in US dollars"):
            self.generate(None)
        view = self.generate()
        self.assertEqual(len(view["candidates"]), 3)
        self.assertEqual(self.calls[0][1:], (3, "image-model-1"))
        self.assertTrue(all(c["current"] and c["origin"] == "GENERATED" for c in view["candidates"]))
        self.assertEqual(view["video_spend_usd"], 0.12)
        ledger = images.read_jsonl(images.ledger_path())
        self.assertEqual(ledger[-1]["event"], "GENERATED")
        self.assertEqual(ledger[-1]["actual_cost_usd"], 0.12)
        self.config["per_video_cap_usd"] = 0.2
        with self.assertRaisesRegex(ValueError, "per-video cap"):
            self.generate()

    def test_choosing_a_candidate_sets_the_subject_image(self):
        view = self.generate()
        chosen = view["candidates"][1]["candidate_id"]
        snapshot = images.choose(render_id=RID, candidate_id=chosen)
        subject = snapshot["items"][0]["subject_image"]
        self.assertEqual(subject["path"], view["candidates"][1]["file"])
        self.assertEqual(subject["source_tier"], "CHEAP_AI")
        self.assertEqual(subject["license"], "Commercial use per provider terms")
        item = review.snapshot()["items"][0]
        marked = {c["candidate_id"]: c["chosen"] for c in item["image_candidates"]["candidates"]}
        self.assertTrue(marked[chosen])
        name = view["candidates"][1]["file"]
        self.assertTrue(review.thumbnail_file_path(RID, name).is_file())
        with self.assertRaisesRegex(ValueError, "Unknown thumbnail file"):
            review.thumbnail_file_path(RID, "candidates/../render_spec.json")
        with self.assertRaisesRegex(ValueError, "Unknown image candidate"):
            images.choose(render_id=RID, candidate_id="nope")

    def test_import_records_provenance_and_rejects_non_images(self):
        made = self.root / "made.png"
        made.write_bytes(PNG)
        with self.assertRaisesRegex(ValueError, "licence is required"):
            images.import_candidate(
                render_id=RID, path=str(made), provider="Tool", source_tier="CHEAP_AI", license="", reviewer="me"
            )
        view = images.import_candidate(
            render_id=RID, path=str(made), provider="Tool", source_tier="CHEAP_AI",
            license="Tool terms", cost_usd="0.02", reviewer="me",
        )
        row = view["candidates"][0]
        self.assertEqual((row["origin"], row["provider"], row["cost_usd"]), ("IMPORTED", "Tool", 0.02))
        fake = self.root / "fake.png"
        fake.write_bytes(b"not an image")
        with self.assertRaisesRegex(ValueError, "not a PNG, JPEG or WebP"):
            images.import_candidate(
                render_id=RID, path=str(fake), provider="Tool", source_tier="OWN_LIBRARY", license="", reviewer="me"
            )

    def test_openai_compatible_adapter_reads_base64_images(self):
        body = {"created": 7, "data": [{"b64_json": base64.b64encode(PNG).decode()}]}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(body).encode()

        settings = self.config["providers"]["openai_compatible"]
        with patch.object(images.urllib.request, "urlopen", return_value=Response()) as urlopen:
            result = images.openai_compatible_images("a prompt", count=1, settings=settings)
        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data)["n"], 1)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(result[0]["bytes"], PNG)

    def test_provider_image_urls_must_be_https(self):
        body = {"data": [{"url": "file:///etc/hostname"}]}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(body).encode()

        settings = self.config["providers"]["openai_compatible"]
        with patch.object(images.urllib.request, "urlopen", return_value=Response()) as urlopen:
            with self.assertRaisesRegex(ValueError, "non-https"):
                images.openai_compatible_images("a prompt", count=1, settings=settings)
        self.assertEqual(urlopen.call_count, 1)

    def test_nan_maximum_cost_is_refused(self):
        with self.assertRaisesRegex(ValueError, "maximum cost"):
            self.generate("nan")
        self.assertEqual(self.calls, [])
