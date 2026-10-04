"""Atomic writes survive a briefly locked target on Windows."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline_integrity


class AtomicWriteTests(unittest.TestCase):
    def test_a_briefly_locked_target_is_retried(self):
        real_replace = os.replace
        calls = []

        def flaky(source, target):
            calls.append(target)
            if len(calls) < 3:
                raise PermissionError(5, "Access is denied")
            real_replace(source, target)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "summary.json"
            with patch.object(pipeline_integrity.os, "replace", side_effect=flaky), \
                    patch.object(pipeline_integrity.time, "sleep"):
                pipeline_integrity.atomic_write_json(target, {"ok": True})
            self.assertEqual(target.read_text(encoding="utf-8"), '{\n  "ok": true\n}')
            self.assertEqual(len(calls), 3)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["summary.json"])

    def test_a_target_that_stays_locked_still_fails_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "summary.json"
            with patch.object(pipeline_integrity.os, "replace", side_effect=PermissionError(5, "Access is denied")) as replace, \
                    patch.object(pipeline_integrity.time, "sleep"):
                with self.assertRaises(PermissionError):
                    pipeline_integrity.atomic_write_json(target, {"ok": True})
            self.assertEqual(replace.call_count, pipeline_integrity._REPLACE_ATTEMPTS)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
