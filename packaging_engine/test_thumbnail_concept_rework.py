import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import thumbnail_concepts as tc


class ThumbnailConceptReworkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        angle_request = root / "angle_request.json"
        angle_request.write_text(
            json.dumps({"request_provenance": {"packaging_brief": str(root / "brief.json")}})
        )
        (root / "brief.json").write_text("{}")
        (root / "angles.json").write_text("{}")
        self.angle_item = {
            "video_id": "c1:long_form",
            "concept_id": "c1",
            "format": "long_form",
            "request_file": str(angle_request),
            "angles": [{"angle_id": "angle-1", "evidence_refs": ["clm001"]}],
        }
        for item in (
            patch.object(tc, "angle_item_is_current", return_value=True),
            patch.object(tc, "brief_is_current", return_value={"approved_claims": []}),
            patch.object(tc, "ANGLES_FILE", root / "angles.json"),
            patch.object(tc, "REWORK_FILE", root / "thumbnail_concept_rework.json"),
            patch.object(tc, "niche_conventions", return_value={}),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_request_unchanged_without_rework(self):
        request = tc.build_request(self.angle_item)
        self.assertNotIn("human_rework", request)
        self.assertFalse(any("human_rework" in line for line in request["instructions"]))

    def test_rework_note_changes_only_that_video_request(self):
        before = tc.build_request(self.angle_item)
        previous = [{"thumbnail_id": "t1", "text": "OLD"}]
        tc.request_rework(
            video_id="c1:long_form",
            note="Show the glowing rotor, not the driver.",
            source="FINAL_PACKAGING_GATE",
            previous_concepts=previous,
        )
        after = tc.build_request(self.angle_item)
        self.assertNotEqual(before, after)
        self.assertEqual(after["human_rework"]["iteration"], 1)
        self.assertEqual(after["human_rework"]["previous_concepts"], previous)
        self.assertTrue(any("human_rework" in line for line in after["instructions"]))

        other = dict(self.angle_item, video_id="c1:short", format="short")
        self.assertNotIn("human_rework", tc.build_request(other))

        tc.request_rework(
            video_id="c1:long_form",
            note="Second try.",
            source="FINAL_PACKAGING_GATE",
            previous_concepts=[],
        )
        self.assertEqual(tc.build_request(self.angle_item)["human_rework"]["iteration"], 2)

    def test_rework_requires_note(self):
        with self.assertRaises(ValueError):
            tc.request_rework(
                video_id="c1:long_form", note=" ", source="x", previous_concepts=[]
            )


if __name__ == "__main__":
    unittest.main()
