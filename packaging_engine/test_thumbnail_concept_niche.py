import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import niche_thumbnail_study
import thumbnail_concepts as tc


class ThumbnailConceptNicheConventionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = copy.deepcopy(tc.load_config())
        self.config["channel_niche"] = None
        angle_request = root / "angle_request.json"
        angle_request.write_text(
            json.dumps({"request_provenance": {"packaging_brief": str(root / "brief.json")}})
        )
        (root / "brief.json").write_text("{}")
        (root / "angles.json").write_text("{}")
        self.angle_item = {
            "video_id": "c1-long_form",
            "concept_id": "c1",
            "format": "long_form",
            "request_file": str(angle_request),
            "angles": [{"angle_id": "angle-1", "evidence_refs": ["clm001"]}],
        }
        self.study_root = root / "niche"
        for item in (
            patch.object(tc, "angle_item_is_current", return_value=True),
            patch.object(tc, "brief_is_current", return_value={"approved_claims": []}),
            patch.object(tc, "ANGLES_FILE", root / "angles.json"),
            patch.object(tc, "load_config", side_effect=lambda: self.config),
            patch.object(niche_thumbnail_study, "STUDY_ROOT", self.study_root),
        ):
            item.start()
            self.addCleanup(item.stop)

    def write_tabulation(self, niche="automotive_racing", video_format="long_form"):
        path = niche_thumbnail_study.tabulation_path(niche, video_format)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "tabulated_at": "ignored",
                    "color": {"crowded_hue_families": ["red"]},
                }
            )
        )

    def test_request_unchanged_without_configured_niche(self):
        self.write_tabulation()
        request = tc.build_request(self.angle_item)
        self.assertNotIn("niche_thumbnail_conventions", request)
        self.assertFalse(any("niche_thumbnail_conventions" in line for line in request["instructions"]))

    def test_request_unchanged_when_niche_has_no_study(self):
        self.config["channel_niche"] = "automotive_racing"
        request = tc.build_request(self.angle_item)
        self.assertNotIn("niche_thumbnail_conventions", request)

    def test_configured_niche_study_is_attached_for_matching_format(self):
        self.config["channel_niche"] = "automotive_racing"
        self.write_tabulation()
        request = tc.build_request(self.angle_item)
        conventions = request["niche_thumbnail_conventions"]
        self.assertEqual(conventions["color"]["crowded_hue_families"], ["red"])
        self.assertNotIn("tabulated_at", conventions)
        self.assertTrue(any("crowded hue" in line for line in request["instructions"]))

        short_item = dict(self.angle_item, format="short")
        self.assertNotIn("niche_thumbnail_conventions", tc.build_request(short_item))


if __name__ == "__main__":
    unittest.main()
