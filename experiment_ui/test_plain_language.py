"""Status codes become sentences (D-170)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plain_language as plain  # noqa: E402

ENGINES = ["production_engine", "packaging_engine", "research_engine", "story_script_engine",
           "format_engine", "experiment_02_analysis", "transformation_engine", "opportunity_engine"]


class PlainLanguageTests(unittest.TestCase):
    def test_known_codes_have_written_sentences(self) -> None:
        self.assertEqual(plain.sentence("WAITING_FOR_DRAFT_RESEARCH_PACKAGES"),
                         "Waiting for the research drafts; the automatic run writes them.")
        self.assertEqual(plain.sentence("awaiting_human_decision"), "Waiting for your decisions.")
        self.assertEqual(plain.sentence(None), "")
        self.assertEqual(plain.sentence("already a sentence"), "already a sentence")

    def test_unknown_codes_are_built_by_shape(self) -> None:
        self.assertEqual(plain.sentence("WAITING_FOR_SOMETHING_NEW"), "Waiting for something new.")
        self.assertEqual(plain.sentence("READY_FOR_THING"), "Ready for thing.")
        self.assertEqual(plain.sentence("HUMAN_VISUAL_RIGHTS_GATE"), "Waiting for your decision at the footage rights gate.")
        self.assertEqual(plain.sentence("HUMAN_NEW_THING_GATE"), "Waiting for your decision at the new thing gate.")
        self.assertEqual(plain.sentence("THING_REWORK_REQUIRED"), "Thing was sent back for rework.")
        self.assertEqual(plain.sentence("TOOL_UNAVAILABLE"), "Tool is not available.")
        self.assertEqual(plain.sentence("NO_STUDY_SET"), "No study set yet.")
        self.assertEqual(plain.sentence("SKIPPED_BUDGET"), "Skipped: budget.")
        self.assertEqual(plain.sentence("SOME_ODD_CODE"), "Some odd code.")

    def test_every_code_the_engines_emit_reads_as_a_sentence(self) -> None:
        root = Path(__file__).resolve().parent.parent
        codes: set[str] = set()
        pattern = re.compile(r'"(?:status|state)": "([A-Z][A-Z_]{5,})"')
        for folder in ENGINES + ["experiment_ui"]:
            for path in (root / folder).glob("*.py"):
                if path.name.startswith("test_"):
                    continue
                codes.update(pattern.findall(path.read_text(encoding="utf-8")))
        self.assertGreater(len(codes), 150)
        for code in sorted(codes):
            with self.subTest(code=code):
                text = plain.sentence(code)
                self.assertNotIn("_", text)
                self.assertTrue(text[0].isupper(), text)
                self.assertTrue(text.endswith("."), text)
                self.assertNotEqual(text.rstrip("."), code, "raw code leaked: " + text)


if __name__ == "__main__":
    unittest.main()
