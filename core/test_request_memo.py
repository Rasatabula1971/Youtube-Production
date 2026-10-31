"""Each packaging currency check runs once per read (D-189)."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
