"""Tesseract project exchange is a locked human route (D-144)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import server
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()


class EditorExchangeIntegrationTests(unittest.TestCase):
    def test_route_is_locked_during_jobs(self):
        self.assertIn("/api/editor-exchange", server.HUMAN_GATE_MUTATION_ROUTES)
        with patch.object(server.JOB_MANAGER, "running", return_value=True):
            self.assertIsNotNone(server.human_gate_mutation_block_reason("/api/editor-exchange"))

    def test_server_and_final_export_gate_share_one_module(self):
        # Paths patched or configured on one are seen by the other.
        self.assertIs(server.tesseract_exchange, sys.modules["final_export_review"].tesseract_exchange)

    def test_state_degrades_instead_of_raising(self):
        with patch.object(server.tesseract_exchange, "snapshot", side_effect=ValueError("boom")):
            state = server.editor_exchange_state()
        self.assertEqual(state, {"status": "ERROR", "error": "boom", "items": []})


if __name__ == "__main__":
    unittest.main()
