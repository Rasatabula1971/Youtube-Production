from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import narration_render_import as render_import


def request_payload() -> dict:
    return {
        "artifact": "narration_render_request",
        "concept_id": "concept-1",
        "format": "long_form",
        "provider": "higgsfield",
        "max_attempts_per_segment": 3,
        "segments": [
            {
                "segment_id": "b1",
                "purpose": "hook",
                "expected_duration_seconds": 1.5,
            },
            {
                "segment_id": "b2",
                "purpose": "payoff",
                "expected_duration_seconds": 2.0,
            },
        ],
    }


class NarrationRenderImportTests(unittest.TestCase):
    def setup_case(self, root: Path):
        requests = root / "requests"
        estimates = root / "estimates"
        approved = root / "approved"
        results = root / "results"
        managed = root / "managed"
        qc = root / "qc"
        timing = root / "timing"
        for directory in (
            requests,
            estimates,
            approved,
            results,
            managed,
            qc,
            timing,
        ):
            directory.mkdir()

        key = "concept-1.long_form"
        request_path = requests / f"{key}.narration_render_request.json"
        request_path.write_text(
            json.dumps(request_payload()),
            encoding="utf-8",
        )
        request_hash = render_import.sha256_file(request_path)

        estimate = {
            "artifact": "narration_cost_estimate",
            "concept_id": "concept-1",
            "format": "long_form",
            "provider": "higgsfield",
            "currency": "USD",
            "status": "READY_FOR_SPEND_GATE",
            "render_request_sha256": request_hash,
            "worst_case_estimate_usd": 6.0,
        }
        estimate_path = estimates / f"{key}.narration_cost_estimate.json"
        estimate_path.write_text(json.dumps(estimate), encoding="utf-8")
        estimate_hash = render_import.sha256_file(estimate_path)

        spend = {
            **estimate,
            "spend_gate": {
                "status": "NARRATION_SPEND_APPROVED",
                "worst_case_estimate_usd": 6.0,
                "currency": "USD",
            },
            "approved_provenance": {
                "narration_cost_estimate_sha256": estimate_hash,
            },
        }
        spend_path = approved / f"{key}.approved_narration_spend.json"
        spend_path.write_text(json.dumps(spend), encoding="utf-8")

        return {
            "requests": requests,
            "estimates": estimates,
            "approved": approved,
            "results": results,
            "managed": managed,
            "qc": qc,
            "timing": timing,
            "request_path": request_path,
            "estimate_path": estimate_path,
            "spend_path": spend_path,
        }

    def patched_case(self, case):
        stack = ExitStack()
        for item in (
            patch.object(render_import, "REQUESTS_DIR", case["requests"]),
            patch.object(render_import, "ESTIMATES_DIR", case["estimates"]),
            patch.object(render_import, "APPROVED_SPEND_DIR", case["approved"]),
            patch.object(render_import, "RENDER_RESULTS_DIR", case["results"]),
            patch.object(render_import, "MANAGED_AUDIO_DIR", case["managed"]),
            patch.object(render_import, "QC_DIR", case["qc"]),
            patch.object(render_import, "TIMING_DIR", case["timing"]),
            patch.object(
                render_import,
                "QC_SUMMARY_FILE",
                case["qc"].parent / "qc_summary.json",
            ),
            patch.object(
                render_import,
                "SUMMARY_FILE",
                case["results"].parent / "return_summary.json",
            ),
            patch.object(
                render_import,
                "narration_render_snapshot",
                return_value={
                    "status": "READY_FOR_SPEND_GATE",
                    "items": [
                        {
                            "concept_id": "concept-1",
                            "format": "long_form",
                            "status": "READY_FOR_SPEND_GATE",
                        }
                    ],
                },
            ),
        ):
            stack.enter_context(item)
        return stack

    def test_register_copies_audio_and_binds_current_spend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = self.setup_case(root)
            a = root / "a.wav"
            b = root / "b.wav"
            a.write_bytes(b"audio-a")
            b.write_bytes(b"audio-b")
            stale_qc = case["qc"] / "concept-1.long_form.narration_audio_qc.json"
            stale_timing = (
                case["timing"]
                / "concept-1.long_form.narration_timing_map.json"
            )
            stale_qc.write_text("{}", encoding="utf-8")
            stale_timing.write_text("{}", encoding="utf-8")

            with self.patched_case(case):
                registered = render_import.register(
                    concept_id="concept-1",
                    format="long_form",
                    provider_job_id="job-123",
                    actual_cost_usd=4.25,
                    segments=[
                        {
                            "segment_id": "b1",
                            "attempt": 1,
                            "audio_file": str(a),
                        },
                        {
                            "segment_id": "b2",
                            "attempt": 2,
                            "audio_file": str(b),
                        },
                    ],
                )
                current = render_import.current_result(
                    "concept-1",
                    "long_form",
                )

            self.assertIsNotNone(current)
            self.assertEqual(
                registered["result"]["actual_cost_usd"],
                4.25,
            )
            self.assertEqual(
                registered["result"]["approved_cost_ceiling_usd"],
                6.0,
            )
            self.assertFalse(stale_qc.exists())
            self.assertFalse(stale_timing.exists())
            for segment in registered["result"]["segments"]:
                path = Path(segment["audio_file"])
                self.assertTrue(path.exists())
                self.assertEqual(
                    segment["audio_sha256"],
                    render_import.sha256_file(path),
                )

    def test_cost_above_approved_ceiling_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = self.setup_case(root)
            a = root / "a.wav"
            b = root / "b.wav"
            a.write_bytes(b"a")
            b.write_bytes(b"b")

            with self.patched_case(case):
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    render_import.register(
                        concept_id="concept-1",
                        format="long_form",
                        provider_job_id="job-123",
                        actual_cost_usd=6.01,
                        segments=[
                            {
                                "segment_id": "b1",
                                "attempt": 1,
                                "audio_file": str(a),
                            },
                            {
                                "segment_id": "b2",
                                "attempt": 1,
                                "audio_file": str(b),
                            },
                        ],
                    )

    def test_failed_multi_segment_copy_preserves_previous_managed_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = self.setup_case(root)
            a = root / "a.wav"
            b = root / "b.wav"
            a.write_bytes(b"new-a")
            b.write_bytes(b"new-b")
            branch_dir = case["managed"] / "concept-1.long_form"
            branch_dir.mkdir()
            marker = branch_dir / "old.wav"
            marker.write_bytes(b"previous-current-audio")

            real_copy = render_import._copy_audio
            calls = {"count": 0}

            def fail_second(source, destination):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated copy failure")
                real_copy(source, destination)

            with self.patched_case(case):
                with patch.object(
                    render_import,
                    "_copy_audio",
                    side_effect=fail_second,
                ):
                    with self.assertRaisesRegex(OSError, "simulated"):
                        render_import.register(
                            concept_id="concept-1",
                            format="long_form",
                            provider_job_id="job-123",
                            actual_cost_usd=2.0,
                            segments=[
                                {
                                    "segment_id": "b1",
                                    "attempt": 1,
                                    "audio_file": str(a),
                                },
                                {
                                    "segment_id": "b2",
                                    "attempt": 1,
                                    "audio_file": str(b),
                                },
                            ],
                        )

            self.assertTrue(marker.exists())
            self.assertEqual(
                marker.read_bytes(),
                b"previous-current-audio",
            )
            self.assertFalse(
                (case["managed"] / ".concept-1.long_form.staging").exists()
            )

    def test_missing_or_reordered_segment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = self.setup_case(root)
            a = root / "a.wav"
            b = root / "b.wav"
            a.write_bytes(b"a")
            b.write_bytes(b"b")

            with self.patched_case(case):
                with self.assertRaisesRegex(ValueError, "exact order"):
                    render_import.register(
                        concept_id="concept-1",
                        format="long_form",
                        provider_job_id="job-123",
                        actual_cost_usd=2.0,
                        segments=[
                            {
                                "segment_id": "b2",
                                "attempt": 1,
                                "audio_file": str(b),
                            },
                            {
                                "segment_id": "b1",
                                "attempt": 1,
                                "audio_file": str(a),
                            },
                        ],
                    )


if __name__ == "__main__":
    unittest.main()
