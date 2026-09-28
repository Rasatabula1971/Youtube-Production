import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import source_overlap


class SourceOverlapTests(unittest.TestCase):
    def test_ten_word_overlap_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "v1"
            video.mkdir()
            (video / "v1.txt").write_text(
                "one two three four five six seven eight nine ten eleven twelve",
                encoding="utf-8",
            )
            with patch.object(source_overlap, "SOURCE_ROOT", root):
                result = source_overlap.check_texts(
                    [
                        {
                            "field": "script",
                            "text": "zero one two three four five six seven eight nine ten finish",
                        }
                    ]
                )
        self.assertTrue(result["blocking"])
        self.assertGreaterEqual(result["matches"][0]["word_count"], 10)

    def test_six_word_overlap_warns_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "v1"
            video.mkdir()
            (video / "v1.txt").write_text(
                "alpha beta gamma delta epsilon zeta unrelated ending",
                encoding="utf-8",
            )
            with patch.object(source_overlap, "SOURCE_ROOT", root):
                result = source_overlap.check_texts(
                    [{"field": "title", "text": "alpha beta gamma delta epsilon zeta"}]
                )
        self.assertFalse(result["blocking"])
        self.assertEqual(result["matches"][0]["word_count"], 6)


if __name__ == "__main__":
    unittest.main()
