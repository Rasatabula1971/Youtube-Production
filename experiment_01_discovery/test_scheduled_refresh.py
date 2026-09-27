from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scheduled_refresh as scheduler


class ScheduledRefreshTests(unittest.TestCase):
    def patch_paths(self, root: Path) -> ExitStack:
        output_root = root / "output"
        output_dir = output_root / "experiment_01_3"
        output_dir.mkdir(parents=True)

        stack = ExitStack()
        stack.enter_context(patch.object(scheduler, "PROJECT_ROOT", root))
        stack.enter_context(patch.object(scheduler, "OUTPUT_ROOT", output_root))
        stack.enter_context(patch.object(scheduler, "OUTPUT_DIR", output_dir))
        stack.enter_context(
            patch.object(
                scheduler,
                "MANIFEST_FILE",
                output_dir / "cohort_manifest.json",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "TOPIC_VELOCITY_FILE",
                output_dir / "topic_velocity.json",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "PERSISTENT_SNAPSHOT_FILE",
                output_root / "experiment_01_3_snapshot_history.jsonl",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "EXP14_CONFIG_FILE",
                root / "experiment_01_4_config.json",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "STATUS_FILE",
                output_dir / "scheduled_refresh_status.json",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "LOG_FILE",
                output_dir / "scheduled_refresh.log",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "LOCK_FILE",
                output_root / "experiment_01_3_scheduled_refresh.lock",
            )
        )
        stack.enter_context(
            patch.object(
                scheduler,
                "REFRESH_SCRIPT",
                root / "experiment_01_3.py",
            )
        )
        return stack

    def write_manifest(self, *, refresh_worthy: bool = True) -> None:
        scheduler.MANIFEST_FILE.write_text(
            json.dumps(
                {
                    "cohort_id": "test-cohort",
                    "video_ids": ["v1", "v2", "v3"],
                    "cohort_readiness": {
                        "refresh_worthy": refresh_worthy,
                    },
                }
            ),
            encoding="utf-8",
        )

    def write_01_4_config(self) -> None:
        scheduler.EXP14_CONFIG_FILE.write_text(
            json.dumps(
                {
                    "minimum_unique_channels": 3,
                    "minimum_velocity_samples": 3,
                }
            ),
            encoding="utf-8",
        )

    def write_topic_velocity(
        self,
        *,
        channels: int,
        velocity_samples: int,
        index: float | None,
    ) -> None:
        scheduler.TOPIC_VELOCITY_FILE.write_text(
            json.dumps(
                {
                    "topics": {
                        "brakes": {
                            "niche": "automotive_racing",
                            "by_format": {
                                "short_candidate": {
                                    "unique_channels": channels,
                                    "velocity_sample_count": velocity_samples,
                                    "age_matched_velocity_index": index,
                                }
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    def test_skips_when_no_frozen_cohort_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.patch_paths(Path(tmp)):
                result = scheduler.run_scheduled_refresh(
                    now=datetime(
                        2026,
                        9,
                        27,
                        12,
                        0,
                        tzinfo=timezone.utc,
                    )
                )

        self.assertEqual(result["status"], "SKIPPED_NO_COHORT")

    def test_skips_once_current_cohort_is_ready_for_01_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.patch_paths(Path(tmp)):
                self.write_manifest()
                self.write_01_4_config()
                self.write_topic_velocity(
                    channels=3,
                    velocity_samples=3,
                    index=1.4,
                )

                with patch.object(scheduler.subprocess, "run") as run:
                    result = scheduler.run_scheduled_refresh(
                        now=datetime(
                            2026,
                            9,
                            27,
                            12,
                            0,
                            tzinfo=timezone.utc,
                        )
                    )

                run.assert_not_called()

        self.assertEqual(result["status"], "SKIPPED_EVIDENCE_READY")

    def test_skips_recent_snapshot_to_avoid_duplicate_api_work(self):
        now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmp:
            with self.patch_paths(Path(tmp)):
                self.write_manifest()
                self.write_01_4_config()
                self.write_topic_velocity(
                    channels=3,
                    velocity_samples=0,
                    index=None,
                )
                scheduler.PERSISTENT_SNAPSHOT_FILE.write_text(
                    json.dumps(
                        {
                            "video_id": "v1",
                            "observed_at": (
                                now - timedelta(minutes=30)
                            ).isoformat(),
                            "views": 1000,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

                with patch.object(scheduler.subprocess, "run") as run:
                    result = scheduler.run_scheduled_refresh(
                        now=now,
                        minimum_interval_hours=1.5,
                    )

                run.assert_not_called()

        self.assertEqual(result["status"], "SKIPPED_RECENT_SNAPSHOT")

    def test_due_cohort_runs_refresh_only_and_releases_lock(self):
        now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.patch_paths(root):
                self.write_manifest()
                self.write_01_4_config()
                self.write_topic_velocity(
                    channels=3,
                    velocity_samples=0,
                    index=None,
                )
                scheduler.PERSISTENT_SNAPSHOT_FILE.write_text(
                    json.dumps(
                        {
                            "video_id": "v1",
                            "observed_at": (
                                now - timedelta(hours=3)
                            ).isoformat(),
                            "views": 1000,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

                completed = SimpleNamespace(
                    returncode=0,
                    stdout="refresh complete\n",
                    stderr="",
                )
                with patch.object(
                    scheduler.subprocess,
                    "run",
                    return_value=completed,
                ) as run:
                    result = scheduler.run_scheduled_refresh(
                        now=now,
                        minimum_interval_hours=1.5,
                        python_executable="python-test",
                    )

                run.assert_called_once()
                command = run.call_args.args[0]
                self.assertEqual(command[0], "python-test")
                self.assertEqual(
                    command[-2:],
                    ["--mode", "refresh"],
                )
                self.assertEqual(
                    Path(command[1]),
                    scheduler.REFRESH_SCRIPT,
                )
                self.assertFalse(scheduler.LOCK_FILE.exists())
                self.assertIn(
                    "refresh complete",
                    scheduler.LOG_FILE.read_text(encoding="utf-8"),
                )

        self.assertEqual(result["status"], "REFRESHED")

    def test_dry_run_reports_due_without_refreshing(self):
        now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmp:
            with self.patch_paths(Path(tmp)):
                self.write_manifest()
                self.write_01_4_config()
                self.write_topic_velocity(
                    channels=3,
                    velocity_samples=0,
                    index=None,
                )

                with patch.object(scheduler.subprocess, "run") as run:
                    result = scheduler.run_scheduled_refresh(
                        now=now,
                        dry_run=True,
                    )

                run.assert_not_called()

        self.assertEqual(result["status"], "DUE")


if __name__ == "__main__":
    unittest.main()
