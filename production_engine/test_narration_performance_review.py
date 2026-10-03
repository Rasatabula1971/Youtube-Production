import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import narration_performance_review as npr


def delivery(**overrides):
    value = {
        "emotion": "neutral",
        "intensity": 4,
        "speed": 1,
        "pause_before_ms": 0,
        "pause_after_ms": 0,
        "emphasis_terms": [],
    }
    value.update(overrides)
    return value


class NarrationPerformanceReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def patch_dirs(self, **dirs):
        for name, path in dirs.items():
            patcher = patch.object(npr, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_segment_revision_is_local_and_words_locked(self):
        manifests = self.root / "manifests"
        revs = self.root / "revs"
        audio = self.root / "audio"
        responses = self.root / "responses"
        approved = self.root / "approved"
        for directory in (manifests, audio, responses, approved):
            directory.mkdir()
        self.patch_dirs(
            MANIFESTS=manifests,
            REVISIONS=revs,
            AUDIO=audio,
            RESPONSES=responses,
            APPROVED=approved,
        )
        p = manifests / "c.long.narration_preview.json"
        wav = audio / "c.long.preview.wav"
        wav.write_bytes(b"old audio")
        wav.with_suffix(".meta.json").write_text("{}", encoding="utf-8")
        (responses / "c.long.preview_review.json").write_text("{}", encoding="utf-8")
        (approved / "c.long.approved_preview.json").write_text("{}", encoding="utf-8")
        p.write_text(
            json.dumps(
                {
                    "concept_id": "c",
                    "format": "long",
                    "segments": [
                        {"segment_id": "s1", "immutable_narration": "Locked words.", "delivery": delivery()},
                        {"segment_id": "s2", "immutable_narration": "Other words.", "delivery": delivery()},
                    ],
                }
            ),
            encoding="utf-8",
        )

        out = npr.revise(
            manifest_file=str(p),
            segment_id="s1",
            instruction="quieter",
            delivery_changes={"emotion": "calm", "speed": 0.9},
        )
        data = json.loads(p.read_text())

        self.assertEqual(out["performance_version"], 2)
        self.assertIs(out["invalidation"]["other_segments"], False)
        self.assertEqual(data["segments"][0]["immutable_narration"], "Locked words.")
        self.assertEqual(data["segments"][1]["delivery"]["speed"], 1)
        self.assertFalse(wav.exists())
        self.assertFalse(wav.with_suffix(".meta.json").exists())
        self.assertFalse((responses / "c.long.preview_review.json").exists())
        self.assertFalse((approved / "c.long.approved_preview.json").exists())

    def test_words_cannot_change_at_performance_gate(self):
        manifests = self.root / "manifests"
        manifests.mkdir()
        self.patch_dirs(
            MANIFESTS=manifests,
            REVISIONS=self.root / "revs",
            AUDIO=self.root / "audio",
            RESPONSES=self.root / "responses",
            APPROVED=self.root / "approved",
        )
        p = manifests / "x.json"
        p.write_text(
            json.dumps({"segments": [{"segment_id": "s", "immutable_narration": "x", "delivery": {}}]}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Rework Script"):
            npr.revise(
                manifest_file=str(p),
                segment_id="s",
                instruction="new words",
                delivery_changes={"text": "new"},
            )


if __name__ == "__main__":
    unittest.main()
