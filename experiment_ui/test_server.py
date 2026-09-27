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
        self.assertIn("exp13_restart", server.ACTION_DEFS)
        self.assertIn(
            "--restart-discovery",
            server.ACTION_DEFS["exp13_restart"]["command"],
        )
        for action in server.ACTION_DEFS.values():
            self.assertIsInstance(action["command"], list)
            self.assertTrue(action["command"])
            self.assertFalse(any(part in {"cmd", "powershell"} for part in action["command"]))

    def test_job_manager_sets_unbuffered_python_output(self):
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
                        (
                            "import os; "
                            "print(os.environ.get('PYTHONUNBUFFERED', 'missing'))"
                        ),
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
                manager.start("test_action")
                deadline = time.time() + 5
                while manager.running() and time.time() < deadline:
                    time.sleep(0.05)

                self.assertIn("1", manager.log_text())

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


    def test_current_job_state_is_json_serializable_while_running(self):
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
                        "import time; print('running'); time.sleep(1)",
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
                manager.start("test_action")
                current = manager.current()

                self.assertIsNotNone(current)
                self.assertNotIn("_log_handle", current)
                json.dumps(current)

                manager.stop()


    def test_checkpoint_complete_is_not_stage_complete_without_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"status": "COMPLETE"}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "DISCOVERY NEEDS RESUME",
            )
            self.assertEqual(stage["state"], "COMPLETE")

    def test_running_discovery_has_human_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"status": "COMPLETE"}),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(
                    server,
                    "current_action_id",
                    return_value="exp13_discover",
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "DISCOVERY RUNNING",
            )
            self.assertEqual(stage["tone"], "running")

    def test_velocity_ready_is_human_stage_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            exp13.mkdir()
            (exp13 / "cohort_manifest.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "topic_velocity.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 4,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
                patch.object(
                    server,
                    "exp13_cohort_readiness",
                    return_value={
                        "frozen_size": 6,
                        "required_unique_channels": 3,
                        "ready_cell_count": 1,
                        "max_unique_channels_in_cell": 3,
                        "sufficient": True,
                    },
                ),
                patch.object(
                    server,
                    "exp13_depth_ready_cell_count",
                    return_value=1,
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertTrue(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "STAGE COMPLETE",
            )
            self.assertTrue(
                all(item["done"] for item in stage["criteria"])
            )


    def test_insufficient_cohort_tells_user_to_rerun_not_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp13 = root / "01_3"
            exp14 = root / "01_4"
            exp15 = root / "01_5"
            exp2 = root / "02"
            checkpoint = root / "checkpoint.json"
            exp13.mkdir()

            (exp13 / "cohort_manifest.json").write_text(
                json.dumps(
                    {
                        "video_ids": ["only-video"],
                        "candidates": [
                            {
                                "video_id": "only-video",
                                "channel_id": "channel-1",
                                "format_candidate": "long_form_candidate",
                                "validated_topics": ["brakes"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (exp13 / "topic_velocity.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (exp13 / "summary.json").write_text(
                json.dumps(
                    {
                        "velocity_analysis": {
                            "valid_velocity_samples": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(server, "EXP13_DIR", exp13),
                patch.object(server, "EXP14_DIR", exp14),
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(server, "EXP13_CHECKPOINT", checkpoint),
                patch.object(server, "current_action_id", return_value=None),
                patch.object(
                    server,
                    "exp13_cohort_readiness",
                    return_value={
                        "frozen_size": 1,
                        "required_unique_channels": 3,
                        "ready_cell_count": 0,
                        "max_unique_channels_in_cell": 1,
                        "sufficient": False,
                    },
                ),
                patch.object(
                    server,
                    "exp13_depth_ready_cell_count",
                    return_value=0,
                ),
            ):
                stage = server.stage_statuses()[0]

            self.assertFalse(stage["complete"])
            self.assertEqual(
                stage["human_status"],
                "INSUFFICIENT COHORT — RERUN DISCOVERY",
            )
            self.assertIn(
                "Do not wait",
                stage["next_action"],
            )

    def test_refresh_is_disabled_for_insufficient_cohort(self):
        with (
            patch.object(
                server,
                "exp13_cohort_readiness",
                return_value={
                    "frozen_size": 1,
                    "required_unique_channels": 3,
                    "ready_cell_count": 0,
                    "max_unique_channels_in_cell": 1,
                    "sufficient": False,
                },
            ),
            patch.object(
                server,
                "exp13_depth_ready_cell_count",
                return_value=0,
            ),
        ):
            readiness = server.action_readiness()

        self.assertFalse(
            readiness["exp13_refresh"]["enabled"]
        )
        self.assertIn(
            "do not wait",
            readiness["exp13_refresh"]["reason"].lower(),
        )

    def test_unknown_action_is_rejected(self):
        manager = server.JobManager()
        with self.assertRaises(ValueError):
            manager.start("not_real")


    def test_experiment_02_prepare_requires_human_opportunity_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp15 = root / "experiment_01_5"
            exp2 = root / "experiment_02"
            exp15.mkdir()
            (exp15 / "study_set.json").write_text("[]", encoding="utf-8")

            with (
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "status": "AWAITING_HUMAN_DECISION",
                        "ready_for_experiment_02": False,
                        "gate_complete": False,
                        "opportunities": [],
                    },
                ),
            ):
                readiness = server.action_readiness()

            self.assertFalse(readiness["exp2_prepare"]["enabled"])
            self.assertIn(
                "approve",
                readiness["exp2_prepare"]["reason"].lower(),
            )

            with (
                patch.object(server, "EXP15_DIR", exp15),
                patch.object(server, "EXP2_OUTPUT", exp2),
                patch.object(
                    server,
                    "opportunity_gate_snapshot",
                    return_value={
                        "status": "APPROVED",
                        "ready_for_experiment_02": True,
                        "gate_complete": True,
                        "opportunities": [],
                    },
                ),
            ):
                readiness = server.action_readiness()

            self.assertTrue(readiness["exp2_prepare"]["enabled"])


if __name__ == "__main__":
    unittest.main()
