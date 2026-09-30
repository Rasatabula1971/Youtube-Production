from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_preview
import narration_preview_review


class NarrationPreviewTests(unittest.TestCase):
    def test_manifest_is_zero_cost_and_contains_sound_design(self) -> None:
        spec = {
            "concept_id": "c1",
            "format": "shorts",
            "title": "Test",
            "performance_gate": {"status": "PERFORMANCE_SPEC_APPROVED"},
            "beats": [
                {"beat_id": "b1", "purpose": "opening hook tension", "immutable_narration": "Listen."},
                {"beat_id": "b2", "purpose": "solution reveal payoff", "immutable_narration": "Here is why."},
            ],
            "directions": [
                {"emotion": "curious", "intensity": .5, "speed": 1.1, "pause_before_ms": 0, "pause_after_ms": 100, "emphasis_terms": []},
                {"emotion": "satisfied", "intensity": .6, "speed": .95, "pause_before_ms": 100, "pause_after_ms": 250, "emphasis_terms": []},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "approved.json"
            source.write_text("{}", encoding="utf-8")
            manifest = narration_preview.build_manifest(spec, source)
        self.assertFalse(manifest["cost_policy"]["paid_calls_allowed"])
        self.assertTrue(manifest["segments"][0]["sound_design"]["editorial_only"])
        self.assertIn("kokoro_local", manifest["renderer_preference"])

    def test_paid_quote_approval_requires_preview_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            manifest.write_text('{"concept_id":"c1","format":"shorts"}', encoding="utf-8")
            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
            ):
                with self.assertRaisesRegex(ValueError, "before listening artifact exists"):
                    narration_preview_review.apply_action(
                        concept_id="c1",
                        format="shorts",
                        decision="APPROVE_FINAL",
                    )


if __name__ == "__main__":
    unittest.main()
