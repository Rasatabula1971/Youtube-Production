"""An emptied review folder is ready to prepare, not awaiting a decision (D-193)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from format_engine import format_review
from production_engine import voice_review


class EmptyGateFolderTests(unittest.TestCase):
    def test_an_empty_format_gate_folder_is_ready_to_prepare(self):
        """1 Nov 2026: a redone format plan left the folder empty; the run stopped at the gate."""
        with tempfile.TemporaryDirectory() as tmp, patch.object(format_review, "REVIEW_REQUESTS_DIR", Path(tmp)):
            snap = format_review.snapshot()
        self.assertEqual(snap["status"], "READY_TO_PREPARE")

    def test_an_empty_voice_gate_folder_is_ready_to_prepare(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(voice_review, "REVIEW_REQUESTS_DIR", Path(tmp)):
            snap = voice_review.snapshot()
        self.assertEqual(snap["status"], "READY_TO_PREPARE")


if __name__ == "__main__":
    unittest.main()
