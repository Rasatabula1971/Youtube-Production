import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ExperimentUiTests(unittest.TestCase):
    def test_action_allowlist_contains_no_shell_strings(self):
        self.assertIn("exp13_discover", server.ACTION_DEFS)
        for action in server.ACTION_DEFS.values():
            self.assertIsInstance(action["command"], list)
            self.assertTrue(action["command"])
            self.assertFalse(any(part in {"cmd", "powershell"} for part in action["command"]))

    def test_velocity_samples_default_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = Path(tmp)
            with patch.object(server, "EXP13_DIR", fake_dir):
                self.assertEqual(server.exp13_valid_velocity_samples(), 0)

    def test_velocity_samples_read_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_dir = Path(tmp)
            (fake_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 7,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(server, "EXP13_DIR", fake_dir):
                self.assertEqual(server.exp13_valid_velocity_samples(), 7)

    def test_job_manager_runs_allowlisted_command_without_deadlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "jobs"
            state = root / "job_state.json"
            actions = {
                "test_action": {
                    "label": "Test",
                    "stage": "test",
                    "command": [
                        sys.executable,
                        "-c",
                        "print('hello-ui')",
                    ],
                    "description": "test",
                }
            }

            manager = server.JobManager()
            with (
                patch.object(server, "ACTION_DEFS", actions),
                patch.object(
                    server,
                    "action_readiness",
                    return_value={
                        "test_action": {
                            "enabled": True,
                            "reason": "test",
                        }
                    },
                ),
                patch.object(server, "PROJECT_ROOT", root),
                patch.object(server, "JOB_LOG_DIR", jobs),
                patch.object(server, "UI_OUTPUT_DIR", root),
                patch.object(server, "JOB_STATE_FILE", state),
            ):
                job = manager.start("test_action")
                self.assertEqual(job["status"], "RUNNING")

                deadline = time.time() + 5
                while manager.running() and time.time() < deadline:
                    time.sleep(0.05)

                final = manager.current()
                self.assertEqual(final["status"], "SUCCEEDED")
                self.assertIn("hello-ui", manager.log_text())

    def test_unknown_action_is_rejected(self):
        manager = server.JobManager()
        with self.assertRaises(ValueError):
            manager.start("not_real")


if __name__ == "__main__":
    unittest.main()
