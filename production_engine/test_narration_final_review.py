"""Human Final Audio Gate (D-137)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_final_review as gate
from narration_render import artifact_key


class FinalAudioGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.qc_dir, self.timing_dir = self.root / "qc", self.root / "timing"
        audio = self.root / "narration_audio" / "c1.short"
        for path in (self.qc_dir, self.timing_dir, audio):
            path.mkdir(parents=True)
        self.audio = audio / "b1.wav"
        self.audio.write_bytes(b"RIFF....WAVE")
        self.qc_status = "PASS"
        for item in (
            patch.object(gate, "QC_DIR", self.qc_dir),
            patch.object(gate, "TIMING_DIR", self.timing_dir),
            patch.object(gate, "OUTPUT_DIR", self.root),
            patch.object(gate, "APPROVED_DIR", self.root / "approved"),
            patch.object(gate, "HISTORY_FILE", self.root / "history.jsonl"),
            patch.object(gate, "audio_qc_snapshot", side_effect=self.qc_snapshot),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.write_qc()

    def qc_snapshot(self):
        return {
            "status": self.qc_status,
            "passed": 1 if self.qc_status == "PASS" else 0,
            "items": [{"concept_id": "c1", "format": "short", "status": self.qc_status}],
        }

    def write_qc(self, duration=4.0):
        key = artifact_key("c1", "short")
        (self.qc_dir / f"{key}.narration_audio_qc.json").write_text(json.dumps({
            "status": "PASS",
            "checks": [{"segment_id": "b1", "attempt": 1, "audio_file": str(self.audio),
                        "expected_duration_seconds": 4.2, "actual_duration_seconds": duration}],
        }))
        (self.timing_dir / f"{key}.narration_timing_map.json").write_text(json.dumps({
            "status": "READY_FOR_ROUGH_CUT",
            "segments": [{"segment_id": "b1", "audio_start_seconds": 0.2, "audio_end_seconds": 0.2 + duration}],
        }))

    def test_qc_passed_audio_waits_for_a_human(self):
        snap = gate.snapshot()
        self.assertEqual(snap["status"], "AWAITING_HUMAN_FINAL_AUDIO")
        self.assertFalse(snap["complete"])
        self.assertEqual(snap["items"][0]["segments"][0]["actual_duration_seconds"], 4.0)
        self.assertFalse(gate.is_approved("c1", "short"))

    def test_approval_is_bound_to_the_current_audio(self):
        snap = gate.apply_action(concept_id="c1", format="short", decision="APPROVE_FINAL_AUDIO")
        self.assertTrue(snap["complete"])
        self.assertEqual(snap["status"], "FINAL_AUDIO_APPROVED")
        self.write_qc(duration=4.1)  # a new provider return re-ran QC
        self.assertFalse(gate.is_approved("c1", "short"))
        self.assertEqual(gate.snapshot()["items"][0]["decision"], "PENDING")

    def test_rework_names_segments_and_needs_a_note_and_is_logged(self):
        with self.assertRaisesRegex(ValueError, "note"):
            gate.apply_action(concept_id="c1", format="short", decision="REWORK_SEGMENTS", segment_ids=["b1"])
        with self.assertRaisesRegex(ValueError, "at least one segment"):
            gate.apply_action(concept_id="c1", format="short", decision="REWORK_SEGMENTS", note="flat")
        with self.assertRaisesRegex(ValueError, "Unknown segment"):
            gate.apply_action(concept_id="c1", format="short", decision="REWORK_SEGMENTS", note="flat", segment_ids=["zz"])
        gate.apply_action(concept_id="c1", format="short", decision="APPROVE_FINAL_AUDIO")
        snap = gate.apply_action(
            concept_id="c1", format="short", decision="REWORK_SEGMENTS", note="Too flat.", segment_ids=["b1"]
        )
        item = snap["items"][0]
        self.assertEqual((item["decision"], item["rework_segment_ids"]), ("REWORK_SEGMENTS", ["b1"]))
        self.assertFalse(gate.is_approved("c1", "short"))
        self.assertEqual([e["decision"] for e in item["history"]], ["APPROVE_FINAL_AUDIO", "REWORK_SEGMENTS"])

    def test_nothing_to_review_until_qc_passes(self):
        self.qc_status = "FAIL"
        self.assertEqual(gate.snapshot()["status"], "WAITING_FOR_AUDIO_QC")
        with self.assertRaisesRegex(ValueError, "No QC-passed narration"):
            gate.apply_action(concept_id="c1", format="short", decision="APPROVE_FINAL_AUDIO")

    def test_audio_files_are_served_only_from_managed_narration(self):
        self.assertEqual(gate.audio_file_path("c1", "short", "b1"), self.audio.resolve())
        with self.assertRaisesRegex(ValueError, "Unknown segment"):
            gate.audio_file_path("c1", "short", "nope")
        outside = self.root / "elsewhere.wav"
        outside.write_bytes(b"x")
        self.audio = outside
        self.write_qc()
        with self.assertRaisesRegex(ValueError, "managed narration"):
            gate.audio_file_path("c1", "short", "b1")


if __name__ == "__main__":
    unittest.main()
