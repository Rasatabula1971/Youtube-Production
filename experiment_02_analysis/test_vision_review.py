from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from experiment_02_analysis import vision_review as vision


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class VisionReviewTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        prepared = root / "prepared"
        enriched = root / "enriched"
        review = root / "review"
        notes = root / "notes"
        visual = root / "visual"
        for path in (prepared, enriched, review, notes, visual):
            path.mkdir()

        stack.enter_context(patch.object(vision, "PREPARED_DIR", prepared))
        stack.enter_context(patch.object(vision, "ENRICHED_DIR", enriched))
        stack.enter_context(patch.object(vision, "VISION_REVIEW_DIR", review))
        stack.enter_context(patch.object(vision, "VISION_NOTES_DIR", notes))
        stack.enter_context(patch.object(vision, "SOURCE_VISUAL_ROOT", visual))

    def write_visual_source(
        self,
        root: Path,
        *,
        video_id: str = "v1",
        with_opening: bool = True,
        scene_count: int = 3,
    ) -> tuple[Path, Path]:
        prepared = vision.PREPARED_DIR / f"{video_id}.json"
        prepared.write_text(
            json.dumps({"video_id": video_id}),
            encoding="utf-8",
        )

        source_dir = vision.SOURCE_VISUAL_ROOT / video_id
        source_dir.mkdir()
        opening = source_dir / "opening_frame.jpg"
        if with_opening:
            opening.write_bytes(b"opening")

        retained = []
        for index in range(1, scene_count + 1):
            frame = source_dir / f"scene_{index:04d}.jpg"
            frame.write_bytes(f"scene-{index}".encode())
            retained.append(
                {
                    "path": str(frame),
                    "timestamp_seconds": float(index * 2),
                }
            )

        report = {
            "video_id": video_id,
            "status": "READY",
            "profile_sha256": vision.sha256_file(prepared),
            "opening_frame": (
                {
                    "path": str(opening),
                    "timestamp_seconds": 0.25,
                }
                if with_opening
                else None
            ),
            "retained_scene_frames": retained,
        }
        report_path = source_dir / "visual_analysis.json"
        report_path.write_text(
            json.dumps(report),
            encoding="utf-8",
        )

        (source_dir / "visual_timing_notes.json").write_text(
            json.dumps(
                {
                    "notes": [
                        {
                            "evidence_id": "timing.scene_change_summary",
                            "type": "timing_note",
                            "locator": "whole video",
                            "observation": "Three detector events.",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (source_dir / "evidence_bundle_visual.json").write_text(
            json.dumps(
                {
                    "video_id": video_id,
                    "profile": str(prepared),
                    "transcript": str(source_dir / "captions.vtt"),
                    "notes": str(source_dir / "visual_timing_notes.json"),
                    "opening_frame": (
                        {
                            "path": str(opening),
                            "observation": None,
                        }
                        if with_opening
                        else None
                    ),
                }
            ),
            encoding="utf-8",
        )
        (source_dir / "captions.vtt").write_text(
            "WEBVTT\n\n00:00.000 --> 00:01.000\nHello.\n",
            encoding="utf-8",
        )
        return prepared, report_path

    def test_human_provider_creates_pending_review_items(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root)

            packet = vision.build_packet("v1", provider="human")

        self.assertEqual(packet["provider"], "human")
        self.assertEqual(packet["status"], "AWAITING_HUMAN_REVIEW")
        self.assertGreaterEqual(len(packet["frames"]), 1)
        self.assertTrue(all(item["decision"] == "PENDING" for item in packet["frames"]))
        self.assertTrue(all(item["proposal"] is None for item in packet["frames"]))

    def test_ollama_proposal_is_only_a_structured_draft(self):
        response = _FakeResponse(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "observation": "A racing tyre fills the center of the frame.",
                            "visible_text": "P ZERO",
                            "confidence": "HIGH",
                            "uncertainty": "",
                        }
                    )
                }
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            frame = Path(tmp) / "frame.jpg"
            frame.write_bytes(b"image")
            with patch.object(
                vision.urllib.request,
                "urlopen",
                return_value=response,
            ):
                proposal = vision.ollama_frame_proposal(
                    frame,
                    model="vision-test",
                    host="http://127.0.0.1:11434",
                )

        self.assertEqual(proposal["confidence"], "HIGH")
        self.assertIn("P ZERO", proposal["observation"])
        self.assertNotIn("decision", proposal)

    def gemini_ready(self, stack: ExitStack, root: Path) -> None:
        billing = root / "billing.json"
        billing.write_text(json.dumps({"billing_disabled_confirmed": True, "confirmed_on": "2026-10-29"}), encoding="utf-8")
        stack.enter_context(patch.object(vision.model_bridge, "DIRECT_GEMINI_BILLING_FILE", billing))
        stack.enter_context(patch.dict("os.environ", {"DIRECT_GEMINI_API_KEY": "test-key", "DIRECT_GEMINI_MODELS": "gemini-lite,gemini-flash"}))
        stack.enter_context(patch.object(vision.time, "sleep"))

    def test_gemini_drafts_every_frame_when_it_is_set_up(self):
        """D-179: the free Gemini API comes before a slow local model."""
        answer = {"candidates": [{"content": {"parts": [{"text": json.dumps(
            {"observation": "A worn racing tyre fills the frame.", "visible_text": "", "confidence": "HIGH", "uncertainty": ""}
        )}]}}]}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root)
            self.gemini_ready(stack, root)
            ollama = stack.enter_context(patch.object(vision, "ollama_frame_proposal"))
            urlopen = stack.enter_context(patch.object(
                vision.model_bridge.urllib.request, "urlopen", return_value=_FakeResponse(answer)))
            packet = vision.build_packet("v1")

        self.assertEqual((packet["provider"], packet["model"]), ("gemini", "gemini-lite"))
        self.assertTrue(all(item["proposal"]["observation"].startswith("A worn racing tyre") for item in packet["frames"]))
        self.assertTrue(all(item["decision"] == "PENDING" for item in packet["frames"]))  # still a draft
        ollama.assert_not_called()
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-lite:generateContent")
        self.assertEqual(body["contents"][0]["parts"][1]["inlineData"]["mimeType"], "image/jpeg")
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")

    def test_without_the_billing_attestation_no_frame_leaves_the_pc(self):
        """D-161 holds for images too: until it is confirmed, Ollama or human review is used."""
        billing = {"billing_disabled_confirmed": False, "confirmed_on": None}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root)
            (root / "billing.json").write_text(json.dumps(billing), encoding="utf-8")
            stack.enter_context(patch.object(vision.model_bridge, "DIRECT_GEMINI_BILLING_FILE", root / "billing.json"))
            stack.enter_context(patch.dict("os.environ", {"DIRECT_GEMINI_API_KEY": "test-key"}))
            urlopen = stack.enter_context(patch.object(vision.model_bridge.urllib.request, "urlopen"))
            packet = vision.build_packet("v1", provider="auto", model="")
            with self.assertRaisesRegex(ValueError, "billing"):
                vision.build_packet("v1", provider="gemini")

        urlopen.assert_not_called()
        self.assertEqual(packet["provider"], "human")
        self.assertEqual(packet["provider_status"]["gemini_status"]["status"], "DIRECT_GEMINI_BILLING_UNCONFIRMED")

    def test_a_frame_gemini_cannot_draft_is_left_for_the_reviewer(self):
        import urllib.error

        def quota(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, None)

        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root)
            self.gemini_ready(stack, root)
            urlopen = stack.enter_context(patch.object(vision.model_bridge.urllib.request, "urlopen", side_effect=quota))
            packet = vision.build_packet("v1")

        self.assertEqual(packet["provider"], "gemini")
        self.assertTrue(all(item["proposal"] is None for item in packet["frames"]))
        self.assertTrue(all("HTTP_429" in item["proposal_error"] for item in packet["frames"]))
        # Each frame tried the lite model, then the next free model.
        self.assertEqual(urlopen.call_count, 2 * len(packet["frames"]))

    def test_review_action_never_accepts_blank_observation(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root, scene_count=1)
            packet = vision.build_packet("v1", provider="human")
            frame_id = packet["frames"][0]["frame_id"]

            with self.assertRaises(ValueError):
                vision.apply_review_action(
                    action="ACCEPT_FRAME",
                    video_id="v1",
                    frame_id=frame_id,
                    observation="",
                )

    def test_review_action_records_reviewer_and_decider(self):
        # The gate policy sets both variables while it decides (D-156, D-160).
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root, scene_count=1)
            packet = vision.build_packet("v1", provider="human")
            frame_id = packet["frames"][0]["frame_id"]
            with patch.dict("os.environ", {"YOUTUBE_REVIEWER_ID": "gate-policy-auto", "YOUTUBE_DECIDED_BY": "GATE_POLICY"}):
                vision.apply_review_action(action="ACCEPT_FRAME", video_id="v1", frame_id=frame_id, observation="A tyre.")
            lines = vision.history_file().read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[-1])
        self.assertEqual((event["reviewer"], event["decided_by"]), ("gate-policy-auto", "GATE_POLICY"))

    def test_combined_notes_bind_scene_observation_to_image(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root, scene_count=1)
            frame = vision.SOURCE_VISUAL_ROOT / "v1" / "scene_0001.jpg"

            notes_path = vision.combined_notes(
                "v1",
                [
                    {
                        "frame_id": "scene_0001",
                        "path": str(frame),
                        "timestamp_seconds": 2.0,
                        "final_observation": "A tyre fills most of the frame.",
                    }
                ],
            )
            payload = json.loads(notes_path.read_text(encoding="utf-8"))

        visual_notes = [
            item for item in payload["notes"] if item.get("type") == "visual_note"
        ]
        self.assertEqual(len(visual_notes), 1)
        self.assertEqual(visual_notes[0]["source_image"], str(frame))

    def test_finalize_rebuilds_bundle_only_from_human_accepted_frames(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root, scene_count=2)

            packet = vision.build_packet("v1", provider="human")
            for item in packet["frames"]:
                if item["kind"] == "opening_frame":
                    item["decision"] = "ACCEPT"
                    item["final_observation"] = (
                        "A tyre is centered against a dark background."
                    )
                elif item["frame_id"] == "scene_0001":
                    item["decision"] = "ACCEPT"
                    item["final_observation"] = "A close-up shows the tyre surface."
                else:
                    item["decision"] = "REJECT"
                    item["final_observation"] = None

            ingest = stack.enter_context(patch.object(vision, "run_ingest"))
            finalized = vision.finalize_packet(packet)

            final_bundle = Path(finalized["final_bundle"])
            bundle = json.loads(final_bundle.read_text(encoding="utf-8"))
            notes = json.loads(Path(bundle["notes"]).read_text(encoding="utf-8"))

        self.assertEqual(finalized["status"], "COMPLETE")
        self.assertEqual(
            bundle["opening_frame"]["observation"],
            "A tyre is centered against a dark background.",
        )
        visual_notes = [
            item for item in notes["notes"] if item.get("type") == "visual_note"
        ]
        self.assertEqual(len(visual_notes), 1)
        self.assertEqual(
            visual_notes[0]["evidence_id"],
            "visual.scene_0001",
        )
        ingest.assert_called_once_with(final_bundle, None)

    def test_snapshot_hides_absolute_frame_paths(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            self.write_visual_source(root, scene_count=1)
            vision.build_packet("v1", provider="human")

            snapshot = vision.review_snapshot()

        self.assertEqual(snapshot["status"], "AWAITING_HUMAN_REVIEW")
        self.assertNotIn(
            "path",
            snapshot["packets"][0]["frames"][0],
        )
        self.assertNotIn(
            "source_sha256",
            snapshot["packets"][0]["frames"][0],
        )


if __name__ == "__main__":
    unittest.main()
