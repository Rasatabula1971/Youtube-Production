from __future__ import annotations

import unittest

import edit_preview_render as module


class EditPreviewRenderTests(unittest.TestCase):
    def test_preview_segments_fill_gap_and_tail(self):
        manifest = {
            "duration": {"preview_seconds": 5.0},
            "visual_track": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "start_seconds": 1.0,
                    "end_seconds": 2.0,
                    "duration_seconds": 1.0,
                    "preview_mode": "PLACEHOLDER",
                },
                {
                    "scene_index": 1,
                    "shot_id": "s2",
                    "start_seconds": 2.0,
                    "end_seconds": 4.0,
                    "duration_seconds": 2.0,
                    "preview_mode": "ASSET",
                    "asset_file": "x.mp4",
                },
            ],
        }

        segments = module.preview_segments(manifest)

        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[0]["kind"], "PLACEHOLDER")
        self.assertEqual(segments[0]["reason"], "TIMELINE_GAP")
        self.assertEqual(segments[1]["shot_id"], "s1")
        self.assertEqual(segments[2]["shot_id"], "s2")
        self.assertEqual(segments[3]["reason"], "TIMELINE_TAIL")
        self.assertEqual(segments[3]["duration_seconds"], 1.0)

    def test_preview_segments_reject_overlap(self):
        manifest = {
            "duration": {"preview_seconds": 3.0},
            "visual_track": [
                {
                    "scene_index": 0,
                    "shot_id": "s1",
                    "start_seconds": 0.0,
                    "end_seconds": 2.0,
                    "duration_seconds": 2.0,
                    "preview_mode": "PLACEHOLDER",
                },
                {
                    "scene_index": 1,
                    "shot_id": "s2",
                    "start_seconds": 1.5,
                    "end_seconds": 3.0,
                    "duration_seconds": 1.5,
                    "preview_mode": "PLACEHOLDER",
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "overlapping scenes"):
            module.preview_segments(manifest)

    def test_narration_mix_filter_uses_absolute_delays(self):
        filters, label = module.narration_mix_filter([
            {"audio_start_seconds": 0.25},
            {"audio_start_seconds": 2.0},
        ])

        self.assertIn("[1:a]adelay=250:all=1[a1]", filters)
        self.assertIn("[2:a]adelay=2000:all=1[a2]", filters)
        self.assertTrue(any("amix=inputs=2" in item for item in filters))
        self.assertEqual(label, "[narration]")


if __name__ == "__main__":
    unittest.main()
