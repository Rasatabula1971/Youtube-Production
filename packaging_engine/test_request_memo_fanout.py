"""One Final Packaging read builds the pairing inputs once (D-189).

Kept out of core/: core may import only the standard library and core.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import request_memo


class FinalPackagingFanOutTests(unittest.TestCase):
    def test_one_read_of_the_final_packaging_gate_builds_the_pairing_inputs_once(self):
        """The 25-pair Short rebuilt them for every request file: /api/status took minutes."""
        from packaging_engine import final_packaging_review, package_pairing

        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp)
            for index in range(5):
                (requests / f"v--t{index}.package_pairing_request.json").write_text("{}", encoding="utf-8")
            briefs: list[int] = []

            def not_ready():
                briefs.append(1)
                raise ValueError("WAITING_FOR_PACKAGING_BRIEF")

            with (
                patch.object(package_pairing, "REQUESTS_DIR", requests),
                patch.object(package_pairing, "_current_briefs", side_effect=not_ready),
                request_memo.scope(),
            ):
                snapshot = final_packaging_review.public_snapshot()
        self.assertEqual(snapshot["status"], "WAITING_FOR_PACKAGE_VALIDATION")
        self.assertEqual(len(briefs), 1)


if __name__ == "__main__":
    unittest.main()
