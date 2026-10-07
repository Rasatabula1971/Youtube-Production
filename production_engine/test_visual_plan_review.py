"""Human Visual Plan Gate before narration spend (D-138)."""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import video_budget
import visual_plan_review as gate
from test_visual_acquisition import approved_plan, write_plan

KEY = "concept-1.long_form"


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * int(24000 * seconds))


class VisualPlanGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        formats, previews, approved_previews, segments = (
            self.root / name for name in ("formats", "previews", "approved_previews", "segments")
        )
        for path in (formats, previews, approved_previews):
            path.mkdir()
        self.plan_path = write_plan(formats, approved_plan())
        (previews / f"{KEY}.narration_preview.json").write_text(json.dumps(
            {"segments": [{"segment_id": "lf001"}, {"segment_id": "lf002"}]}
        ))
        write_wav(segments / f"{KEY}.000.lf001.segment.wav", 2.5)
        write_wav(segments / f"{KEY}.001.lf002.segment.wav", 4.0)
        self.approved_preview = approved_previews / f"{KEY}.approved_preview.json"
        self.approved_preview.write_text(json.dumps({"decision": "APPROVE_FINAL", "preview_audio_sha256": "a1"}))
        budget_config = self.root / "budget.json"
        budget_config.write_text(json.dumps({"target_usd": 5, "ceiling_usd": 10}))
        for item in (
            patch.object(gate, "APPROVED_FORMAT_DIR", formats),
            patch.object(gate, "PREVIEW_DIR", previews),
            patch.object(gate, "APPROVED_PREVIEW_DIR", approved_previews),
            patch.object(gate, "SEGMENT_AUDIO_DIR", segments),
            patch.object(gate, "OUTPUT_DIR", self.root),
            patch.object(gate, "APPROVED_DIR", self.root / "approved_plans"),
            patch.object(gate, "HISTORY_FILE", self.root / "history.jsonl"),
            patch.object(video_budget, "CONFIG_FILE", budget_config),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_plan_is_built_from_the_format_plan_and_timed_from_the_preview(self):
        snap = gate.snapshot()
        self.assertEqual(snap["status"], "AWAITING_HUMAN_VISUAL_PLAN")
        item = snap["items"][0]
        self.assertEqual([s["beat_id"] for s in item["shots"]], ["lf001", "lf002"])
        second = item["shots"][1]
        self.assertEqual((second["preview_start_seconds"], second["preview_end_seconds"]), (2.5, 6.5))
        self.assertEqual(item["preview_total_seconds"], 6.5)
        self.assertEqual(item["untimed_shots"], 0)
        self.assertEqual(item["budget"]["ceiling_usd"], 10.0)
        self.assertFalse(gate.is_approved("concept-1", "long_form"))

    def test_no_plan_until_the_free_preview_is_approved(self):
        self.approved_preview.unlink()
        self.assertEqual(gate.snapshot()["status"], "WAITING_FOR_APPROVED_PREVIEW")
        with self.assertRaisesRegex(ValueError, "approve its free narration preview"):
            gate.apply_action(concept_id="concept-1", format="long_form", decision="APPROVE_VISUAL_PLAN")

    def test_approval_is_bound_to_the_format_plan_and_preview(self):
        gate.apply_action(concept_id="concept-1", format="long_form", decision="APPROVE_VISUAL_PLAN")
        self.assertTrue(gate.is_approved("concept-1", "long_form"))
        self.assertTrue(gate.snapshot()["complete"])
        changed = approved_plan()
        changed["branches"][0]["beats"][1]["treatment"] = "A slow-motion splash."
        write_plan(self.plan_path.parent, changed)
        self.assertFalse(gate.is_approved("concept-1", "long_form"))
        gate.apply_action(concept_id="concept-1", format="long_form", decision="APPROVE_VISUAL_PLAN")
        self.approved_preview.write_text(json.dumps({"decision": "APPROVE_FINAL", "preview_audio_sha256": "a2"}))
        self.assertFalse(gate.is_approved("concept-1", "long_form"))

    def test_rework_needs_a_note_and_is_logged(self):
        with self.assertRaisesRegex(ValueError, "note"):
            gate.apply_action(concept_id="concept-1", format="long_form", decision="REWORK_VISUAL_PLAN")
        gate.apply_action(concept_id="concept-1", format="long_form", decision="APPROVE_VISUAL_PLAN")
        snap = gate.apply_action(
            concept_id="concept-1", format="long_form", decision="REWORK_VISUAL_PLAN", note="Too many talking heads."
        )
        item = snap["items"][0]
        self.assertEqual(item["decision"], "REWORK_VISUAL_PLAN")
        self.assertEqual(snap["rework"], 1)
        self.assertFalse(gate.is_approved("concept-1", "long_form"))
        self.assertEqual([e["decision"] for e in item["history"]], ["APPROVE_VISUAL_PLAN", "REWORK_VISUAL_PLAN"])

    def test_missing_preview_segments_are_reported_as_untimed(self):
        (gate.SEGMENT_AUDIO_DIR / f"{KEY}.001.lf002.segment.wav").unlink()
        item = gate.snapshot()["items"][0]
        self.assertEqual(item["untimed_shots"], 1)
        self.assertIsNone(item["shots"][1]["preview_start_seconds"])


if __name__ == "__main__":
    unittest.main()
