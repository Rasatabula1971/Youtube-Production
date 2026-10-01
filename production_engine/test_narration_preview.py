from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_preview
import narration_preview_render
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

    def _write_current_render(self, manifest: Path, audio: Path) -> None:
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"current preview audio")
        metadata = {
            "artifact": "narration_preview_render_metadata",
            "manifest_sha256": narration_preview_review.sha256_file(manifest),
            "audio_sha256": narration_preview_review.sha256_file(audio),
        }
        metadata_path = audio.with_suffix(".meta.json")
        metadata_path.write_text(
            __import__("json").dumps(metadata),
            encoding="utf-8",
        )

    def test_current_audio_is_bound_to_manifest_and_audio_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio_dir = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            manifest.write_text(
                '{"concept_id":"c1","format":"shorts","segments":[]}',
                encoding="utf-8",
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "SUMMARY_FILE", root / "summary.json"),
            ):
                result = narration_preview_review.apply_action(
                    concept_id="c1",
                    format="shorts",
                    decision="APPROVE_FINAL",
                )
                current = narration_preview_review.snapshot()

            self.assertTrue(result["complete"])
            self.assertTrue(current["items"][0]["audio_ready"])
            self.assertTrue(current["items"][0]["approved_for_paid_quote"])
            self.assertIsNotNone(current["items"][0]["audio_sha256"])

    def test_manifest_change_makes_existing_preview_audio_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio_dir = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            manifest.write_text(
                '{"concept_id":"c1","format":"shorts","segments":[{"segment_id":"a"}]}',
                encoding="utf-8",
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)
            manifest.write_text(
                '{"concept_id":"c1","format":"shorts","segments":[{"segment_id":"b"}]}',
                encoding="utf-8",
            )

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
            ):
                snapshot = narration_preview_review.snapshot()
                with self.assertRaisesRegex(
                    ValueError,
                    "current preview manifest",
                ):
                    narration_preview_review.apply_action(
                        concept_id="c1",
                        format="shorts",
                        decision="APPROVE_FINAL",
                    )

            self.assertFalse(snapshot["items"][0]["audio_ready"])
            self.assertIsNone(snapshot["items"][0]["audio"])

    def test_audio_change_makes_render_metadata_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio_dir = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            manifest.write_text(
                '{"concept_id":"c1","format":"shorts"}',
                encoding="utf-8",
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)
            audio.write_bytes(b"changed after metadata")

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
            ):
                snapshot = narration_preview_review.snapshot()

            self.assertFalse(snapshot["items"][0]["audio_ready"])

    def test_batch_writes_manifest_bound_render_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifests = root / "manifests"
            audio_dir = root / "audio"
            manifests.mkdir()
            manifest = manifests / "c1.short.narration_preview.json"
            manifest.write_text(
                '{"concept_id":"c1","format":"short","segments":[]}',
                encoding="utf-8",
            )

            def fake_render(_manifest, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"fake wav")
                return {
                    "status": "FREE_PREVIEW_RENDERED",
                    "renderer": "test_local",
                    "voice": "test",
                    "sample_rate": 24000,
                    "audio": str(destination),
                    "paid_call": False,
                }

            with (
                patch.object(narration_preview_render, "MANIFEST_DIR", manifests),
                patch.object(narration_preview_render, "AUDIO_DIR", audio_dir),
                patch.object(narration_preview_render, "SUMMARY_FILE", root / "render_summary.json"),
                patch.object(narration_preview_render, "render_manifest", side_effect=fake_render),
            ):
                result = narration_preview_render.batch()

            metadata_path = audio_dir / "c1.short.preview.meta.json"
            metadata = __import__("json").loads(
                metadata_path.read_text(encoding="utf-8")
            )
            self.assertEqual(result["status"], "READY_FOR_LISTEN_GATE")
            self.assertEqual(
                metadata["manifest_sha256"],
                narration_preview_render.sha256_file(manifest),
            )
            self.assertEqual(
                metadata["audio_sha256"],
                narration_preview_render.sha256_file(
                    audio_dir / "c1.short.preview.wav"
                ),
            )

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
