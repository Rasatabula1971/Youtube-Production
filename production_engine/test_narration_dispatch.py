"""Paid narration dispatch (D-139)."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_dispatch as dispatch
import test_narration_render_import as base

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "
BASE_REQUEST = base.request_payload
TEXTS = {"b1": "Brakes glow orange at racing speed.", "b2": "That heat is the design target."}


def request_with_text() -> dict:
    payload = BASE_REQUEST()
    for segment in payload["segments"]:
        segment["immutable_narration"] = TEXTS[segment["segment_id"]]
        segment["delivery"] = {"speed": 1.0}
    payload["voice_identity"] = {"voice_id": "v-1"}
    return payload


def config(**adapter):
    return {
        "provider": "higgsfield",
        "provider_contract": {
            "schema_verified": True, "endpoint": "https://tts.example/v1/speak",
            "documentation_url": "https://tts.example/docs", "verified_at": "2026-10-04",
        },
        "max_regenerations_per_segment": 2, "quote_currency": "USD",
        "require_provider_quote": True, "audio_qc": {},
        "provider_adapter": {
            "kind": "HTTP_TTS_JSON", "model": "m1", "api_key_env": "NARRATION_PROVIDER_API_KEY",
            "price_per_1000_characters_usd": 30.0, **adapter,
        },
    }


class NarrationDispatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        with patch.object(base, "request_payload", request_with_text):
            self.case = base.NarrationRenderImportTests().setup_case(self.root)
        stack = base.NarrationRenderImportTests().patched_case(self.case)
        self.addCleanup(stack.close)
        stack.__enter__()
        self.config = config()
        for item in (
            patch.object(dispatch, "load_config", side_effect=lambda *_: copy.deepcopy(self.config)),
            patch.object(dispatch, "OUTPUT_DIR", self.root),
            patch.object(dispatch, "STAGING_DIR", self.root / "staging"),
            patch.object(dispatch, "HISTORY_FILE", self.root / "dispatch.jsonl"),
            patch.dict("os.environ", {"NARRATION_PROVIDER_API_KEY": "secret"}),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.calls = []

    def fake(self, segment, *, settings, endpoint, voice):
        self.calls.append((segment["segment_id"], endpoint, voice.get("voice_id")))
        return {"bytes": WAV + segment["segment_id"].encode(), "suffix": ".wav"}

    def run_dispatch(self, **kwargs):
        return dispatch.dispatch(
            concept_id="concept-1", format="long_form", reviewer="me",
            adapters={"HTTP_TTS_JSON": self.fake}, **kwargs,
        )

    def test_nothing_is_called_until_contract_price_and_key_are_set(self):
        self.config["provider_contract"]["schema_verified"] = False
        self.config["provider_adapter"]["price_per_1000_characters_usd"] = None
        problems = " ".join(dispatch.provider_status(self.config)["problems"])
        self.assertIn("not verified", problems)
        self.assertIn("never guessed", problems)
        with self.assertRaisesRegex(ValueError, "not available"):
            self.run_dispatch()
        self.assertEqual(self.calls, [])

    def test_first_dispatch_renders_every_segment_and_registers_the_return(self):
        result = self.run_dispatch()
        self.assertEqual([c[0] for c in self.calls], ["b1", "b2"])
        self.assertEqual(self.calls[0][1:], ("https://tts.example/v1/speak", "v-1"))
        chars = sum(len(t) for t in TEXTS.values())
        self.assertAlmostEqual(result["actual_cost_usd"], round(chars / 1000 * 30, 2), places=2)
        self.assertEqual([s["attempt"] for s in result["segments"]], [1, 1])
        history = dispatch.read_jsonl(dispatch.HISTORY_FILE)
        self.assertEqual(history[-1]["event"], "RENDERED")
        self.assertFalse(any((self.root / "staging").rglob("*.wav")))

    def test_rerecording_touches_only_named_segments_within_the_attempt_policy(self):
        first = self.run_dispatch()
        with self.assertRaisesRegex(ValueError, "name the segments"):
            self.run_dispatch()
        second = self.run_dispatch(segment_ids=["b2"])
        self.assertEqual([c[0] for c in self.calls], ["b1", "b2", "b2"])
        self.assertEqual([s["attempt"] for s in second["segments"]], [1, 2])
        self.assertGreater(second["actual_cost_usd"], first["actual_cost_usd"])
        self.run_dispatch(segment_ids=["b2"])
        with self.assertRaisesRegex(ValueError, "all 3 approved attempts"):
            self.run_dispatch(segment_ids=["b2"])

    def test_estimate_above_the_approved_worst_case_is_refused(self):
        self.config["provider_adapter"]["price_per_1000_characters_usd"] = 500.0
        with self.assertRaisesRegex(ValueError, "approved worst case"):
            self.run_dispatch()
        self.assertEqual(self.calls, [])

    def test_provider_failure_part_way_records_what_was_spent(self):
        def flaky(segment, **kwargs):
            if segment["segment_id"] == "b2":
                raise ValueError("Narration provider call failed: TimeoutError")
            return self.fake(segment, **kwargs)

        with self.assertRaisesRegex(ValueError, "TimeoutError"):
            dispatch.dispatch(concept_id="concept-1", format="long_form", adapters={"HTTP_TTS_JSON": flaky})
        event = dispatch.read_jsonl(dispatch.HISTORY_FILE)[-1]
        self.assertEqual((event["event"], event["rendered"]), ("FAILED", ["b1"]))
        self.assertGreater(event["cost_usd"], 0)
        ledger = dispatch.read_jsonl(self.root / "video_budget_ledger.jsonl")
        self.assertEqual(ledger[-1]["event"], "ACTUAL")

    def test_provider_cost_above_the_worst_case_stops_before_the_next_segment(self):
        ceiling = self.case["worst_case"] if "worst_case" in self.case else None
        def pricey(segment, **kwargs):
            audio = self.fake(segment, **kwargs)
            audio["cost_usd"] = 10_000.0  # the provider bills far more than estimated
            return audio

        with self.assertRaisesRegex(ValueError, "approved worst case"):
            dispatch.dispatch(concept_id="concept-1", format="long_form", adapters={"HTTP_TTS_JSON": pricey})
        self.assertEqual(len(self.calls), 1, "only the first segment was paid for")
        event = dispatch.read_jsonl(dispatch.HISTORY_FILE)[-1]
        self.assertEqual(event["event"], "FAILED")
        self.assertEqual(event["cost_usd"], 10_000.0)
        ledger = dispatch.read_jsonl(self.root / "video_budget_ledger.jsonl")
        self.assertEqual((ledger[-1]["event"], ledger[-1]["amount_usd"]), ("ACTUAL", 10_000.0))
        del ceiling

    def test_unusable_reported_costs_fall_back_to_the_estimate(self):
        for bad in (True, float("nan"), -1, "free", None):
            with self.subTest(bad=bad):
                self.assertGreater(dispatch._reported_cost(bad, fallback=0.25), 0)
                self.assertEqual(dispatch._reported_cost(bad, fallback=0.25), 0.25)
        self.assertEqual(dispatch._reported_cost(0.1, fallback=0.25), 0.1)

    def test_failed_dispatches_count_toward_spend_and_attempts(self):
        def flaky(segment, **kwargs):
            if segment["segment_id"] == "b2":
                raise ValueError("synthetic provider failure")
            return self.fake(segment, **kwargs)

        for _ in range(4):
            try:
                dispatch.dispatch(concept_id="concept-1", format="long_form", adapters={"HTTP_TTS_JSON": flaky})
            except ValueError:
                pass
        # b1 was paid for three times (the approved 1 + 2 regenerations); a
        # fourth call is refused instead of paying again.
        self.assertEqual(sum(c[0] == "b1" for c in self.calls), 3)
        paid = sum(e["cost_usd"] for e in dispatch.read_jsonl(dispatch.HISTORY_FILE))
        ledger = dispatch.read_jsonl(self.root / "video_budget_ledger.jsonl")
        self.assertAlmostEqual(ledger[-1]["amount_usd"], round(paid, 4), places=4)
        with self.assertRaisesRegex(ValueError, "all 3 approved attempts"):
            self.run_dispatch()

    def test_concurrent_dispatches_cannot_both_pass_the_worst_case_check(self):
        import threading

        self.config["provider_adapter"]["price_per_1000_characters_usd"] = 80.0  # one full render fits, two do not
        gate = threading.Event()

        def slow(segment, **kwargs):
            gate.wait(timeout=0.2)
            return self.fake(segment, **kwargs)

        outcomes = []

        def call():
            try:
                dispatch.dispatch(concept_id="concept-1", format="long_form", adapters={"HTTP_TTS_JSON": slow})
                outcomes.append("ok")
            except ValueError as exc:
                outcomes.append(str(exc))

        threads = [threading.Thread(target=call) for _ in range(2)]
        for thread in threads:
            thread.start()
        gate.set()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main()
