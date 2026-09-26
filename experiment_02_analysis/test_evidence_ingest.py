import json
import tempfile
import unittest
from pathlib import Path

from evidence_ingest import (
    ingest_bundle,
    merge_evidence,
    parse_notes_file,
    parse_subtitle_file,
    parse_text_transcript,
    register_image,
)


class EvidenceIngestTests(unittest.TestCase):
    def test_parse_srt_creates_timestamped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.srt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:02,500\nThis is the hook.\n\n"
                "2\n00:00:02,500 --> 00:00:05,000\nSecond line.\n",
                encoding="utf-8",
            )
            evidence = parse_subtitle_file(path)

        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0]["type"], "transcript")
        self.assertEqual(evidence[0]["locator"], "00:00:00.000-00:00:02.500")
        self.assertEqual(evidence[0]["observation"], "This is the hook.")


    def test_parse_vtt_supports_minute_second_timecodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.vtt"
            path.write_text(
                "WEBVTT\n\n00:00.000 --> 00:02.000\nOpening line.\n",
                encoding="utf-8",
            )
            evidence = parse_subtitle_file(path)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["locator"], "00:00:00.000-00:00:02.000")

    def test_plain_text_uses_paragraph_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
            evidence = parse_text_transcript(path)

        self.assertEqual(
            [item["evidence_id"] for item in evidence],
            ["transcript.p0001", "transcript.p0002"],
        )

    def test_notes_require_supported_type_and_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(
                json.dumps(
                    {
                        "notes": [
                            {
                                "type": "visual_note",
                                "start_seconds": 1,
                                "end_seconds": 3,
                                "observation": "Cut from car to gearbox animation.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            evidence = parse_notes_file(path)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["type"], "visual_note")
        self.assertEqual(evidence[0]["locator"], "00:00:01.000-00:00:03.000")

    def test_registered_image_without_observation_is_not_claim_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thumb.jpg"
            path.write_bytes(b"fake-image-bytes")
            source_input, evidence = register_image(
                kind="thumbnail",
                path=path,
                observation=None,
            )

        self.assertEqual(source_input["status"], "REGISTERED_UNOBSERVED")
        self.assertIsNone(evidence)

    def test_merge_rejects_conflicting_duplicate_id(self):
        profile = {
            "evidence": [
                {
                    "evidence_id": "transcript.p0001",
                    "type": "transcript",
                    "observation": "A",
                }
            ]
        }
        with self.assertRaises(ValueError):
            merge_evidence(
                profile,
                [
                    {
                        "evidence_id": "transcript.p0001",
                        "type": "transcript",
                        "observation": "B",
                    }
                ],
            )

    def test_bundle_video_id_must_match_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "video_id": "actual",
                        "source_inputs": {},
                        "evidence": [],
                        "analysis": {},
                        "working_hypotheses": [],
                        "transfer": {},
                    }
                ),
                encoding="utf-8",
            )
            bundle = root / "bundle.json"
            bundle.write_text(
                json.dumps(
                    {
                        "video_id": "different",
                        "profile": "profile.json",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                ingest_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
