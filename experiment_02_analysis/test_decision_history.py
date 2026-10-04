"""Append-only Analysis Gate and vision review decision history (D-133)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import human_review
import test_human_review as analysis_tests
import test_vision_review as vision_tests
import vision_review as vision
from human_review import apply_review_action, build_review_request
from pipeline_integrity import read_jsonl


class AnalysisHistoryTests(unittest.TestCase):
    def test_changed_decisions_keep_the_earlier_ones(self):
        fixture = analysis_tests.HumanReviewTests()
        fixture.setUp()
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            dirs = {name: root / name for name in ("analyzed", "requests", "responses", "reviewed", "reports")}
            for path in dirs.values():
                path.mkdir()
            (dirs["analyzed"] / "v1.json").write_text(json.dumps(fixture.profile()), encoding="utf-8")
            request = build_review_request(fixture.profile(), fixture.experiment_config, fixture.review_config)
            (dirs["requests"] / "v1.review_request.json").write_text(json.dumps(request), encoding="utf-8")
            for attribute, key in (
                ("DEFAULT_ANALYZED_DIR", "analyzed"),
                ("REVIEW_REQUESTS_DIR", "requests"),
                ("REVIEW_RESPONSES_DIR", "responses"),
                ("REVIEWED_PROFILES_DIR", "reviewed"),
                ("REVIEW_REPORTS_DIR", "reports"),
            ):
                stack.enter_context(patch.object(human_review, attribute, dirs[key]))
            stack.enter_context(patch.object(human_review, "run_apply"))
            item_id = request["items"][0]["item_id"]
            apply_review_action(video_id="v1", item_id=item_id, decision="ACCEPT", note="")
            snapshot = apply_review_action(video_id="v1", item_id=item_id, decision="REJECT", note="Too broad.")
            events = read_jsonl(human_review.history_file())
            self.assertEqual(human_review.history_file().parent, root)

        self.assertEqual([event["decision"] for event in events], ["ACCEPT", "REJECT"])
        self.assertEqual(events[1]["previous_decision"], "ACCEPT")
        self.assertEqual(events[1]["gate"], "analysis")
        item = next(row for row in snapshot["items"] if row["item_id"] == item_id)
        self.assertEqual(item["decision"], "REJECT")
        self.assertEqual(len(item["decision_history"]), 2)


class VisionHistoryTests(unittest.TestCase):
    def test_frame_decisions_are_logged(self):
        fixture = vision_tests.VisionReviewTests()
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            fixture.patch_paths(stack, root)
            fixture.write_visual_source(root, scene_count=3)
            packet = vision.build_packet("v1", provider="human")
            frame_id = packet["frames"][0]["frame_id"]
            vision.apply_review_action(
                action="ACCEPT_FRAME", video_id="v1", frame_id=frame_id, observation="A tyre in close-up."
            )
            vision.apply_review_action(action="REJECT_FRAME", video_id="v1", frame_id=frame_id)
            history = vision.frame_history("v1")
        self.assertEqual([event["decision"] for event in history[frame_id]], ["ACCEPT", "REJECT"])
        self.assertEqual(history[frame_id][0]["final_observation"], "A tyre in close-up.")


if __name__ == "__main__":
    unittest.main()
