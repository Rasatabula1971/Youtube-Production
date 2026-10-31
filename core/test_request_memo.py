"""Each packaging currency check runs once per read (D-189)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import request_memo
from core.request_memo import memoized

CALLS: list[object] = []


@memoized
def answer(value):
    CALLS.append(value)
    return {"value": value, "items": [1, 2]}


@memoized
def refuse():
    CALLS.append("refuse")
    raise ValueError("WAITING_FOR_PACKAGING_BRIEF")


class RequestMemoTests(unittest.TestCase):
    def setUp(self):
        CALLS.clear()

    def test_outside_a_scope_every_call_runs(self):
        answer(1)
        answer(1)
        self.assertEqual(CALLS, [1, 1])
        self.assertFalse(request_memo.active())

    def test_inside_a_scope_each_argument_list_runs_once(self):
        with request_memo.scope():
            answer(1)
            answer(1)
            answer(2)
        self.assertEqual(CALLS, [1, 2])

    def test_a_caller_changing_its_copy_does_not_change_the_next_answer(self):
        with request_memo.scope():
            first = answer(1)
            first["items"].append(3)
            self.assertEqual(answer(1)["items"], [1, 2])

    def test_a_refusal_is_remembered_too(self):
        with request_memo.scope():
            for _ in range(3):
                with self.assertRaisesRegex(ValueError, "WAITING"):
                    refuse()
        self.assertEqual(CALLS, ["refuse"])

    def test_unhashable_arguments_are_keyed_by_their_content(self):
        with request_memo.scope():
            answer({"a": [1]})
            answer({"a": [1]})
            answer({"a": [2]})
        self.assertEqual(len(CALLS), 2)

    def test_the_cache_ends_with_the_scope_and_a_nested_scope_shares_it(self):
        with request_memo.scope():
            answer(1)
            with request_memo.scope():
                answer(1)
        with request_memo.scope():
            answer(1)
        self.assertEqual(CALLS, [1, 1])


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
