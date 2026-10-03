from __future__ import annotations

import json
import tempfile
import unittest
import wave
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

    def _bind_current_manifest(
        self,
        root: Path,
        manifest: Path,
        payload: dict,
    ) -> Path:
        voice_dir = root / "voice"
        voice_dir.mkdir(exist_ok=True)
        concept_id = str(payload.get("concept_id") or "")
        fmt = str(payload.get("format") or "")
        spec_path = voice_dir / f"{concept_id}.{fmt}.approved_voice_spec.json"
        spec_path.write_text(
            json.dumps(
                {
                    "concept_id": concept_id,
                    "format": fmt,
                    "performance_gate": {
                        "status": "PERFORMANCE_SPEC_APPROVED",
                    },
                }
            ),
            encoding="utf-8",
        )
        current = dict(payload)
        current["provenance"] = {
            "approved_voice_spec": str(spec_path.resolve()),
            "approved_voice_spec_sha256": narration_preview_review.sha256_file(
                spec_path
            ),
        }
        manifest.write_text(json.dumps(current), encoding="utf-8")
        return voice_dir

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
            voice_dir = self._bind_current_manifest(
                root,
                manifest,
                {"concept_id": "c1", "format": "shorts", "segments": []},
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "APPROVED_VOICE_DIR", voice_dir),
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
            voice_dir = self._bind_current_manifest(
                root,
                manifest,
                {
                    "concept_id": "c1",
                    "format": "shorts",
                    "segments": [{"segment_id": "a"}],
                },
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)
            changed = json.loads(manifest.read_text(encoding="utf-8"))
            changed["segments"] = [{"segment_id": "b"}]
            manifest.write_text(json.dumps(changed), encoding="utf-8")

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "APPROVED_VOICE_DIR", voice_dir),
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
            voice_dir = self._bind_current_manifest(
                root,
                manifest,
                {"concept_id": "c1", "format": "shorts"},
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)
            audio.write_bytes(b"changed after metadata")

            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "APPROVED_VOICE_DIR", voice_dir),
            ):
                snapshot = narration_preview_review.snapshot()

            self.assertFalse(snapshot["items"][0]["audio_ready"])

    def test_changed_approved_voice_spec_makes_old_preview_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio_dir = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            voice_dir = self._bind_current_manifest(
                root,
                manifest,
                {"concept_id": "c1", "format": "shorts", "segments": []},
            )
            audio = audio_dir / "c1.shorts.preview.wav"
            self._write_current_render(manifest, audio)

            spec_path = voice_dir / "c1.shorts.approved_voice_spec.json"
            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio_dir),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "APPROVED_VOICE_DIR", voice_dir),
            ):
                current = narration_preview_review.snapshot()
                changed = json.loads(spec_path.read_text(encoding="utf-8"))
                changed["title"] = "Changed performance"
                spec_path.write_text(json.dumps(changed), encoding="utf-8")
                stale = narration_preview_review.snapshot()
                with self.assertRaisesRegex(ValueError, "stale"):
                    narration_preview_review.apply_action(
                        concept_id="c1",
                        format="shorts",
                        decision="APPROVE_FINAL",
                    )

            self.assertTrue(current["items"][0]["audio_ready"])
            self.assertFalse(stale["items"][0]["audio_ready"])
            self.assertFalse(stale["complete"])

    def test_preview_snapshot_requires_current_engagement_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_voice = root / "approved_voice"
            engagement = root / "engagement"
            manifests = root / "manifests"
            approved_voice.mkdir()
            engagement.mkdir()
            manifests.mkdir()

            spec_path = approved_voice / "c1.shorts.approved_voice_spec.json"
            voice_spec = {
                "concept_id": "c1",
                "format": "shorts",
                "title": "Test",
                "performance_gate": {"status": "PERFORMANCE_SPEC_APPROVED"},
                "beats": [
                    {
                        "beat_id": "b1",
                        "purpose": "opening hook",
                        "immutable_narration": "Listen.",
                    }
                ],
                "directions": [
                    {
                        "emotion": "curious",
                        "intensity": 0.5,
                        "speed": 1.0,
                        "pause_before_ms": 0,
                        "pause_after_ms": 100,
                        "emphasis_terms": [],
                    }
                ],
            }
            spec_path.write_text(json.dumps(voice_spec), encoding="utf-8")
            engagement_path = engagement / f"{spec_path.stem}.engagement.json"
            engagement_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "provenance": {
                            "approved_voice_spec": str(spec_path.resolve()),
                            "approved_voice_spec_sha256": narration_preview.sha256_file(
                                spec_path
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest = narration_preview.build_manifest(voice_spec, spec_path)
            manifest_path = manifests / "c1.shorts.narration_preview.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with (
                patch.object(narration_preview, "APPROVED_DIR", approved_voice),
                patch.object(narration_preview, "ENGAGEMENT_DIR", engagement),
                patch.object(narration_preview, "MANIFEST_DIR", manifests),
            ):
                current = narration_preview.snapshot()
                voice_spec["title"] = "Changed"
                spec_path.write_text(json.dumps(voice_spec), encoding="utf-8")
                stale = narration_preview.snapshot()

            self.assertEqual(current["status"], "READY_FOR_FREE_PREVIEW_RENDER")
            self.assertEqual(current["prepared"], 1)
            self.assertNotEqual(stale["status"], "READY_FOR_FREE_PREVIEW_RENDER")
            self.assertEqual(stale["prepared"], 0)

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

    def test_segment_cache_rerenders_only_changed_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            segment_dir = root / "segments"
            destination = root / "audio" / "c1.short.preview.wav"
            manifest = {
                "concept_id": "c1",
                "format": "short",
                "segments": [
                    {
                        "segment_id": "s1",
                        "immutable_narration": "First line.",
                        "delivery": {
                            "speed": 1.0,
                            "pause_before_ms": 0,
                            "pause_after_ms": 50,
                        },
                    },
                    {
                        "segment_id": "s2",
                        "immutable_narration": "Second line.",
                        "delivery": {
                            "speed": 1.0,
                            "pause_before_ms": 0,
                            "pause_after_ms": 50,
                        },
                    },
                ],
            }

            def fake_segment_render(_segment, path, _pipeline):
                path.parent.mkdir(parents=True, exist_ok=True)
                with wave.open(str(path), "wb") as handle:
                    handle.setnchannels(1)
                    handle.setsampwidth(2)
                    handle.setframerate(narration_preview_render.SAMPLE_RATE)
                    handle.writeframes(b"\x00\x00" * 24)

            with (
                patch.object(
                    narration_preview_render,
                    "SEGMENT_AUDIO_DIR",
                    segment_dir,
                ),
                patch.object(
                    narration_preview_render,
                    "_load_local_pipeline",
                    return_value=object(),
                ) as load_pipeline,
                patch.object(
                    narration_preview_render,
                    "_render_segment",
                    side_effect=fake_segment_render,
                ) as render_segment,
            ):
                first = narration_preview_render.render_manifest(
                    manifest,
                    destination,
                )
                changed = {
                    **manifest,
                    "segments": [
                        {
                            **manifest["segments"][0],
                            "delivery": {
                                **manifest["segments"][0]["delivery"],
                                "speed": 0.9,
                            },
                        },
                        manifest["segments"][1],
                    ],
                }
                second = narration_preview_render.render_manifest(
                    changed,
                    destination,
                )
                third = narration_preview_render.render_manifest(
                    changed,
                    destination,
                )

            self.assertEqual(first["segments_rendered"], 2)
            self.assertEqual(first["segments_reused"], 0)
            self.assertEqual(second["segments_rendered"], 1)
            self.assertEqual(second["segments_reused"], 1)
            self.assertEqual(third["segments_rendered"], 0)
            self.assertEqual(third["segments_reused"], 2)
            self.assertEqual(render_segment.call_count, 3)
            self.assertEqual(load_pipeline.call_count, 2)
            self.assertTrue(destination.exists())

    def test_paid_quote_approval_requires_preview_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = root / "preview"
            audio = root / "audio"
            responses = root / "responses"
            approved = root / "approved"
            preview.mkdir()
            manifest = preview / "c1.shorts.narration_preview.json"
            voice_dir = self._bind_current_manifest(
                root,
                manifest,
                {"concept_id": "c1", "format": "shorts"},
            )
            with (
                patch.object(narration_preview_review, "PREVIEW_DIR", preview),
                patch.object(narration_preview_review, "RENDER_DIR", audio),
                patch.object(narration_preview_review, "RESPONSES_DIR", responses),
                patch.object(narration_preview_review, "APPROVED_DIR", approved),
                patch.object(narration_preview_review, "APPROVED_VOICE_DIR", voice_dir),
            ):
                with self.assertRaisesRegex(ValueError, "before listening artifact exists"):
                    narration_preview_review.apply_action(
                        concept_id="c1",
                        format="shorts",
                        decision="APPROVE_FINAL",
                    )


if __name__ == "__main__":
    unittest.main()
