from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import opportunity_research as research


class OpportunityResearchTests(unittest.TestCase):
    def patch_output_paths(self, stack: ExitStack, root: Path):
        exp13 = root / "experiment_01_3"
        exp14 = root / "experiment_01_4"
        exp15 = root / "experiment_01_5"
        exp13.mkdir(parents=True)
        exp14.mkdir(parents=True)
        exp15.mkdir(parents=True)
        stack.enter_context(patch.object(research, "OUTPUT_ROOT", root))
        stack.enter_context(patch.object(research, "EXP13_DIR", exp13))
        stack.enter_context(patch.object(research, "EXP14_DIR", exp14))
        stack.enter_context(patch.object(research, "EXP15_DIR", exp15))
        stack.enter_context(
            patch.object(
                research,
                "STATE_FILE",
                root / "opportunity_research_state.json",
            )
        )

    def test_waiting_state_arms_scheduler_when_velocity_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with ExitStack() as stack:
                self.patch_output_paths(stack, root)
                with (
                patch.object(research, "study_set_ready", return_value=False),
                patch.object(research, "velocity_ready", return_value=False),
                patch.object(
                    research.scheduled_refresh,
                    "run_scheduled_refresh",
                    return_value={
                        "status": "SKIPPED_RECENT_SNAPSHOT",
                        "message": "too recent",
                    },
                ),
                patch.object(
                    research,
                    "schedule_continuation",
                    return_value=True,
                ) as schedule,
            ):
                result = research.continue_research(
                    python_executable="python-test",
                    minimum_interval_hours=1.5,
                    max_refresh_attempts=3,
                    schedule_if_waiting=True,
                )

        self.assertEqual(
            result["status"],
            "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH",
        )
        self.assertTrue(result["scheduler_armed"])
        self.assertIsNotNone(result["next_refresh_due_at"])
        schedule.assert_called_once_with(
            python_executable="python-test",
            every_hours=2,
        )

    def test_three_refresh_attempts_stop_instead_of_looping_forever(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patch_output_paths(root)
            (root / "opportunity_research_state.json").write_text(
                json.dumps({"refresh_attempts": 2}),
                encoding="utf-8",
            )

            with (
                *patches,
                patch.object(research, "study_set_ready", return_value=False),
                patch.object(research, "velocity_ready", return_value=False),
                patch.object(
                    research.scheduled_refresh,
                    "run_scheduled_refresh",
                    return_value={
                        "status": "REFRESHED",
                        "message": "refreshed",
                    },
                ),
                patch.object(research, "remove_continuation_task") as remove,
                patch.object(research, "schedule_continuation") as schedule,
            ):
                result = research.continue_research(
                    python_executable="python-test",
                    minimum_interval_hours=1.5,
                    max_refresh_attempts=3,
                    schedule_if_waiting=True,
                )

        self.assertEqual(result["status"], "NEEDS_HUMAN_ATTENTION")
        self.assertEqual(result["refresh_attempts"], 3)
        remove.assert_called_once()
        schedule.assert_not_called()

    def test_ready_velocity_runs_01_4_then_01_5_and_stops_for_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patch_output_paths(root)
            exp14 = root / "experiment_01_4"
            exp15 = root / "experiment_01_5"

            def fake_run(command, label):
                if "BUILD 01.4" in label:
                    (exp14 / "expansion_plan.json").write_text(
                        json.dumps({"status": "READY"}),
                        encoding="utf-8",
                    )
                elif "EXECUTE 01.4" in label:
                    (exp14 / "summary.json").write_text(
                        json.dumps({"execution_status": "COMPLETE"}),
                        encoding="utf-8",
                    )
                elif "BUILD 01.5" in label:
                    (exp15 / "study_set.json").write_text(
                        json.dumps([{"video_id": "v1"}]),
                        encoding="utf-8",
                    )
                return 0

            with (
                *patches,
                patch.object(research, "velocity_ready", return_value=True),
                patch.object(research, "run_command", side_effect=fake_run) as run,
                patch.object(research, "remove_continuation_task") as remove,
            ):
                result = research.advance_downstream(
                    python_executable="python-test",
                    refresh_attempts=1,
                )

        self.assertEqual(
            result["status"],
            "AWAITING_HUMAN_OPPORTUNITY_REVIEW",
        )
        self.assertEqual(run.call_count, 3)
        remove.assert_called_once()

    def test_start_runs_discovery_then_enters_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patch_output_paths(root)
            exp13 = root / "experiment_01_3"

            def fake_run(command, label):
                (exp13 / "cohort_manifest.json").write_text(
                    json.dumps({"video_ids": ["v1"]}),
                    encoding="utf-8",
                )
                return 0

            expected = {
                "status": "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH",
                "message": "waiting",
            }
            with (
                *patches,
                patch.object(research, "run_command", side_effect=fake_run) as run,
                patch.object(
                    research,
                    "continue_research",
                    return_value=expected,
                ) as continuation,
                patch.object(research, "remove_continuation_task"),
            ):
                result = research.start_research(
                    python_executable="python-test",
                    minimum_interval_hours=1.5,
                    max_refresh_attempts=3,
                )

        self.assertEqual(result, expected)
        run.assert_called_once()
        continuation.assert_called_once_with(
            python_executable="python-test",
            minimum_interval_hours=1.5,
            max_refresh_attempts=3,
            schedule_if_waiting=True,
        )


if __name__ == "__main__":
    unittest.main()
