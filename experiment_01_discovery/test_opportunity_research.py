from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from experiment_01_discovery import opportunity_research as research


class OpportunityResearchTests(unittest.TestCase):
    def patch_output_paths(self, stack: ExitStack, root: Path) -> None:
        exp13 = root / "experiment_01_3"
        exp14 = root / "experiment_01_4"
        exp15 = root / "experiment_01_5"
        exp13.mkdir(parents=True)
        exp14.mkdir(parents=True)
        exp15.mkdir(parents=True)
        # These flows run on a frozen cohort (D-178: without one, the
        # continuation stops for the owner).
        (exp13 / "cohort_manifest.json").write_text("{}", encoding="utf-8")

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
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            stack.enter_context(
                patch.object(research, "study_set_ready", return_value=False)
            )
            stack.enter_context(
                patch.object(research, "velocity_ready", return_value=False)
            )
            stack.enter_context(
                patch.object(
                    research.scheduled_refresh,
                    "run_scheduled_refresh",
                    return_value={
                        "status": "SKIPPED_RECENT_SNAPSHOT",
                        "message": "too recent",
                    },
                )
            )
            schedule = stack.enter_context(
                patch.object(
                    research,
                    "schedule_continuation",
                    return_value=True,
                )
            )

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
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            (root / "opportunity_research_state.json").write_text(
                json.dumps({"refresh_attempts": 2}),
                encoding="utf-8",
            )
            stack.enter_context(
                patch.object(research, "study_set_ready", return_value=False)
            )
            stack.enter_context(
                patch.object(research, "velocity_ready", return_value=False)
            )
            stack.enter_context(
                patch.object(
                    research.scheduled_refresh,
                    "run_scheduled_refresh",
                    return_value={
                        "status": "REFRESHED",
                        "message": "refreshed",
                    },
                )
            )
            schedule = stack.enter_context(
                patch.object(research, "schedule_continuation")
            )

            result = research.continue_research(
                python_executable="python-test",
                minimum_interval_hours=1.5,
                max_refresh_attempts=3,
                schedule_if_waiting=True,
            )

        self.assertEqual(result["status"], "NEEDS_HUMAN_ATTENTION")
        self.assertEqual(result["refresh_attempts"], 3)
        schedule.assert_not_called()

    def test_ready_velocity_runs_01_4_then_01_5_and_stops_for_human(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
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

            stack.enter_context(
                patch.object(research, "velocity_ready", return_value=True)
            )
            run = stack.enter_context(
                patch.object(
                    research,
                    "run_command",
                    side_effect=fake_run,
                )
            )
            vidiq = stack.enter_context(
                patch.object(
                    research,
                    "run_vidiq_supplemental",
                    return_value=("COMPLETE", "vidIQ complete"),
                )
            )

            result = research.advance_downstream(
                python_executable="python-test",
                refresh_attempts=1,
            )

        self.assertEqual(
            result["status"],
            "AWAITING_HUMAN_OPPORTUNITY_REVIEW",
        )
        self.assertEqual(run.call_count, 3)
        vidiq.assert_called_once_with(python_executable="python-test")
        self.assertEqual(result["vidiq_status"], "COMPLETE")

    def test_existing_study_set_runs_vidiq_before_human_gate(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            exp15 = root / "experiment_01_5"
            (exp15 / "study_set.json").write_text(
                json.dumps([{"video_id": "v1"}]),
                encoding="utf-8",
            )
            vidiq = stack.enter_context(
                patch.object(
                    research,
                    "run_vidiq_supplemental",
                    return_value=("PARTIAL", "supplement partial"),
                )
            )

            result = research.continue_research(
                python_executable="python-test",
                minimum_interval_hours=1.5,
                max_refresh_attempts=3,
                schedule_if_waiting=True,
            )

        self.assertEqual(result["status"], "AWAITING_HUMAN_OPPORTUNITY_REVIEW")
        self.assertEqual(result["vidiq_status"], "PARTIAL")
        vidiq.assert_called_once_with(python_executable="python-test")

    def test_start_runs_discovery_then_enters_continuation(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
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
            run = stack.enter_context(
                patch.object(
                    research,
                    "run_command",
                    side_effect=fake_run,
                )
            )
            continuation = stack.enter_context(
                patch.object(
                    research,
                    "continue_research",
                    return_value=expected,
                )
            )

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


class SharedTaskTests(unittest.TestCase):
    """D-178 review: the one Windows task also runs the viral radar, so the
    research flow must never delete it (it used to on every finished, failed
    or started run)."""

    def test_no_research_path_deletes_the_scheduled_task(self):
        commands = []

        def fake_subprocess_run(command, *args, **kwargs):
            commands.append([str(part) for part in command])
            return SimpleNamespace(returncode=0)

        with patch.object(research.os, "name", "nt"), \
                patch.object(research.subprocess, "run", side_effect=fake_subprocess_run), \
                patch.object(research, "study_set_ready", return_value=True), \
                patch.object(research, "run_vidiq_supplemental", return_value=("COMPLETE", "ok")), \
                patch.object(research, "write_state", side_effect=lambda status, message, **kw: {"status": status}):
            research.continue_research(
                python_executable="python-test", minimum_interval_hours=1.5,
                max_refresh_attempts=3, schedule_if_waiting=True,
            )
        flat = [" ".join(command).lower() for command in commands]
        self.assertFalse(any("remove_experiment_01_3_auto_refresh" in c or "/delete" in c for c in flat), flat)
        self.assertFalse(hasattr(research, "remove_continuation_task"))


class ContinuationStopsTests(unittest.TestCase):
    """D-178 review: the shared task now ticks for good, so the continuation
    must stop at owner states and must not repeat the vidIQ supplement."""

    patch_output_paths = OpportunityResearchTests.patch_output_paths

    def run_continue(self, stack, **patches):
        for name, value in patches.items():
            stack.enter_context(patch.object(research, name, value))
        return research.continue_research(
            python_executable="python-test", minimum_interval_hours=1.5,
            max_refresh_attempts=3, schedule_if_waiting=True,
        )

    def test_no_cohort_stops_for_the_owner_and_stays_stopped(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            (root / "experiment_01_3" / "cohort_manifest.json").unlink()
            research.STATE_FILE.write_text(json.dumps({"status": "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH"}), encoding="utf-8")
            refresh = stack.enter_context(patch.object(research.scheduled_refresh, "run_scheduled_refresh"))
            first = self.run_continue(stack)
            second = research.continue_research(python_executable="python-test", minimum_interval_hours=1.5,
                                                max_refresh_attempts=3, schedule_if_waiting=True)
        self.assertEqual(first["status"], "NEEDS_HUMAN_ATTENTION")
        self.assertIn("Run Opportunity Research", first["message"])
        self.assertEqual(second, first)  # unchanged: no wait re-armed
        refresh.assert_not_called()

    def test_a_running_discovery_is_left_alone_until_it_goes_stale(self):
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            (root / "experiment_01_3" / "cohort_manifest.json").unlink()
            running = {"status": "DISCOVERY_RUNNING", "updated_at": (now - timedelta(hours=2)).isoformat()}
            research.STATE_FILE.write_text(json.dumps(running), encoding="utf-8")
            self.assertEqual(self.run_continue(stack, utc_now=lambda: now), running)
            running["updated_at"] = (now - timedelta(hours=13)).isoformat()
            research.STATE_FILE.write_text(json.dumps(running), encoding="utf-8")
            stale = research.continue_research(python_executable="python-test", minimum_interval_hours=1.5,
                                               max_refresh_attempts=3, schedule_if_waiting=True)
        self.assertEqual(stale["status"], "NEEDS_HUMAN_ATTENTION")

    def test_needs_attention_is_not_refreshed_past_the_cap(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            stopped = {"status": "NEEDS_HUMAN_ATTENTION", "refresh_attempts": 3, "message": "still insufficient"}
            research.STATE_FILE.write_text(json.dumps(stopped), encoding="utf-8")
            refresh = stack.enter_context(patch.object(research.scheduled_refresh, "run_scheduled_refresh"))
            result = self.run_continue(stack, velocity_ready=lambda: True)
        self.assertEqual(result, stopped)
        refresh.assert_not_called()

    def test_vidiq_runs_once_per_study_set(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            study = root / "experiment_01_5" / "study_set.json"
            study.write_text('[{"video_id": "a"}]', encoding="utf-8")
            vidiq = stack.enter_context(patch.object(research, "run_vidiq_supplemental", return_value=("COMPLETE", "ok")))
            for _ in range(3):
                result = research.continue_research(python_executable="python-test", minimum_interval_hours=1.5,
                                                    max_refresh_attempts=3, schedule_if_waiting=True)
            self.assertEqual(result["status"], "AWAITING_HUMAN_OPPORTUNITY_REVIEW")
            self.assertEqual(vidiq.call_count, 1)
            study.write_text('[{"video_id": "b"}]', encoding="utf-8")  # a rebuilt study set
            research.continue_research(python_executable="python-test", minimum_interval_hours=1.5,
                                       max_refresh_attempts=3, schedule_if_waiting=True)
            self.assertEqual(vidiq.call_count, 2)

    def test_a_handoff_from_before_d178_is_adopted_without_calling_vidiq(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_output_paths(stack, root)
            (root / "experiment_01_5" / "study_set.json").write_text('[{"video_id": "a"}]', encoding="utf-8")
            research.STATE_FILE.write_text(json.dumps({"status": "AWAITING_HUMAN_OPPORTUNITY_REVIEW", "message": "m",
                                                       "vidiq_status": "COMPLETE"}), encoding="utf-8")
            vidiq = stack.enter_context(patch.object(research, "run_vidiq_supplemental"))
            result = research.continue_research(python_executable="python-test", minimum_interval_hours=1.5,
                                                max_refresh_attempts=3, schedule_if_waiting=True)
        vidiq.assert_not_called()
        self.assertEqual(result["status"], "AWAITING_HUMAN_OPPORTUNITY_REVIEW")
        self.assertIsNotNone(result["study_set_sha256"])
