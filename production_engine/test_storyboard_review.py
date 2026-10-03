import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import storyboard_review as sr
from storyboard_review import revise


class StoryboardReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.story = root / "storyboards"
        self.search = root / "search"
        self.story.mkdir()
        self.search.mkdir()
        for name, path in (
            ("STORYBOARDS", self.story),
            ("REVISIONS", root / "revisions"),
            ("SEARCH_RESULTS", self.search),
        ):
            patcher = patch.object(sr, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_shot_revision_versions_and_locks_timing(self):
        p = self.story / "c.long.storyboard.json"
        p.write_text(
            json.dumps(
                {
                    "concept_id": "c",
                    "format": "long",
                    "status": "READY_FOR_VISUAL_SEARCH",
                    "cards": [
                        {
                            "shot_id": "shot-001",
                            "beat_id": "b1",
                            "time_range": {"start_seconds": 0, "end_seconds": 4},
                            "desired_visual": "old",
                            "search_terms": ["old"],
                            "cinematic_direction": {"camera_angle": "eye"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        request = self.search / "c.long.visual_search_request.json"
        result = self.search / "c.long.visual_search_results.json"
        request.write_text("{}", encoding="utf-8")
        result.write_text("{}", encoding="utf-8")

        out = revise(
            storyboard_file=str(p),
            shot_id="shot-001",
            instruction="lower and tighter",
            changes={"desired_visual": "hammer impact", "cinematic_direction": {"camera_angle": "low"}},
        )

        self.assertEqual(out["creative_version"], 2)
        self.assertIs(out["invalidation"]["other_shots"], False)
        self.assertIs(out["narration_timing_changed"], False)
        self.assertEqual(json.loads(p.read_text())["cards"][0]["time_range"]["end_seconds"], 4)
        self.assertFalse(request.exists())
        self.assertFalse(result.exists())

    def test_shot_revision_rejects_timing_change(self):
        p = self.story / "c.long.storyboard.json"
        p.write_text(
            json.dumps({"concept_id": "c", "format": "long", "cards": [{"shot_id": "s", "time_range": {}}]}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "locked"):
            revise(
                storyboard_file=str(p),
                shot_id="s",
                instruction="change time",
                changes={"time_range": {"start_seconds": 1}},
            )


if __name__ == "__main__":
    unittest.main()
