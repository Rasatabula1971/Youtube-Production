from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_audio_qc


class NarrationAudioQcTests(unittest.TestCase):
    def test_qc_uses_request_duration_not_provider_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            request_path = root / "request.json"
            spend_path = root / "spend.json"
            audio_path = root / "audio.wav"
            audio_path.write_bytes(b"fake-audio")

            request = {
                "concept_id": "concept-1",
                "format": "long_form",
                "max_regenerations_per_segment": 2,
                "max_attempts_per_segment": 3,
                "segments": [
                    {
                        "segment_id": "b1",
                        "expected_duration_seconds": 2.0,
                        "delivery": {
                            "pause_before_ms": 100,
                            "pause_after_ms": 200,
                        },
                    }
                ],
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")
            spend_path.write_text("{}", encoding="utf-8")
            result = {
                "artifact": "narration_render_result",
                "concept_id": "concept-1",
                "format": "long_form",
                "segments": [
                    {
                        "segment_id": "b1",
                        "attempt": 1,
                        "audio_file": str(audio_path),
                        "expected_duration_seconds": 99.0,
                    }
                ],
            }
            result_path.write_text(json.dumps(result), encoding="utf-8")
            config = {
                "audio_qc": {
                    "duration_tolerance_ratio": 0.3,
                    "clipping_peak_dbfs": -0.1,
                    "unexpected_silence_seconds": 0.8,
                    "silence_noise_db": -50.0,
                    "ffprobe_binary": "ffprobe",
                    "ffmpeg_binary": "ffmpeg",
                }
            }

            with (
                patch.object(
                    narration_audio_qc,
                    "current_registered_result",
                    return_value=(result_path, result),
                ),
                patch.object(
                    narration_audio_qc,
                    "validate_render_result",
                    return_value=(request_path, request, spend_path, {}),
                ),
                patch.object(
                    narration_audio_qc,
                    "probe_duration_seconds",
                    return_value=2.0,
                ),
                patch.object(
                    narration_audio_qc,
                    "detect_unexpected_silence",
                    return_value=[],
                ),
                patch.object(
                    narration_audio_qc,
                    "max_volume_dbfs",
                    return_value=-3.0,
                ),
            ):
                qc, timing = narration_audio_qc.qc_render_result(
                    result,
                    result_path,
                    config,
                )

            self.assertEqual(qc["status"], "PASS")
            self.assertEqual(
                qc["checks"][0]["expected_duration_seconds"],
                2.0,
            )
            self.assertEqual(
                timing["status"],
                "READY_FOR_ROUGH_CUT",
            )
            self.assertAlmostEqual(
                timing["segments"][0]["timeline_end_seconds"],
                2.3,
            )

    def test_unregistered_result_is_rejected_before_qc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            result = {
                "artifact": "narration_render_result",
                "concept_id": "concept-1",
                "format": "shorts",
                "segments": [],
            }
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with patch.object(
                narration_audio_qc,
                "current_registered_result",
                return_value=None,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "current registered provider return",
                ):
                    narration_audio_qc.qc_render_result(
                        result,
                        result_path,
                        {
                            "audio_qc": {
                                "duration_tolerance_ratio": 0.3,
                                "clipping_peak_dbfs": -0.1,
                                "unexpected_silence_seconds": 0.8,
                                "silence_noise_db": -50.0,
                                "ffprobe_binary": "ffprobe",
                                "ffmpeg_binary": "ffmpeg",
                            }
                        },
                    )


if __name__ == "__main__":
    unittest.main()
