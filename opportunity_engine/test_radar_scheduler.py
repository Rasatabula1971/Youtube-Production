
import subprocess
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import radar_scheduler, scheduled_tick  # noqa: E402
from opportunity_engine import viral_radar as vr  # noqa: E402
from opportunity_engine.test_viral_radar import MATURE, NOW, FakeApi, RadarTestCase, item  # noqa: E402


class SchedulerTests(RadarTestCase):
    def setUp(self):
        super().setUp()
        for target in (
            patch.object(radar_scheduler, "STATUS_FILE", self.root / "viral" / "schedule.json"),
            patch.object(radar_scheduler, "LOCK_FILE", self.root / "viral" / "tick.lock"),
        ):
            target.start()
            self.addCleanup(target.stop)
        self.api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": "UC" + "a" * 22})
        self.calls = []

        def runner(**kwargs):
            self.calls.append(kwargs["mode"])
            return vr.run(api=self.api, searcher=lambda u, l, t: [], **kwargs)

        self.runner = runner

    def tick(self, hours):
        return radar_scheduler.tick(now=NOW + timedelta(hours=hours), runner=self.runner, config=self.config)

    def test_discovery_then_snapshots_then_nothing(self):
        first = self.tick(0)
        self.assertEqual(first["action"], "DISCOVERY")
        self.assertEqual(first["result"]["status"], "COMPLETE")
        self.assertEqual(first["tracked_count"], 1)
        # Under 48 hours old: next snapshot 6 h later; next discovery 8 h later.
        self.assertEqual(first["next_snapshot_due"], (NOW + timedelta(hours=6)).isoformat())
        self.assertEqual(first["next_discovery_due"], (NOW + timedelta(hours=8)).isoformat())

        self.assertEqual(self.tick(2)["action"], "NOT_DUE")
        calls_before = len(self.api.calls)
        snap = self.tick(6)
        self.assertEqual(snap["action"], "SNAPSHOTS")
        # Snapshot mode only measures tracked videos: one videos.list call, no crawl or search.
        self.assertEqual([c[0] for c in self.api.calls[calls_before:]], ["videos"])
        self.assertEqual(len(vr.SNAPSHOT_FILE.read_text().splitlines()), 2)
        self.assertEqual(self.tick(8)["action"], "DISCOVERY")
        self.assertEqual(self.calls, ["full", "snapshots", "full"])
        self.assertEqual(radar_scheduler.load_status()["action"], "DISCOVERY")

    def test_disabled_and_locked(self):
        self.config["radar_schedule"]["enabled"] = False
        self.assertEqual(self.tick(0)["action"], "DISABLED")
        self.assertEqual(self.calls, [])
        self.config["radar_schedule"]["enabled"] = True
        radar_scheduler.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        radar_scheduler.LOCK_FILE.write_text("{}", encoding="utf-8")
        with patch.object(radar_scheduler, "acquire_lock", return_value=False):
            self.assertEqual(self.tick(0)["action"], "LOCKED")
        self.assertEqual(self.calls, [])

    def test_lock_is_released_after_a_failing_run(self):
        def broken(**kwargs):
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            radar_scheduler.tick(now=NOW, runner=broken, config=self.config)
        self.assertFalse(radar_scheduler.LOCK_FILE.exists())

    def test_snapshot_mode_never_reports_an_empty_watchlist(self):
        summary = vr.run(api=FakeApi([]), searcher=lambda u, l, t: [], config=self.config, now=NOW, mode="snapshots")
        self.assertEqual(summary["status"], "COMPLETE")
        self.assertEqual(summary["api_calls"], 0)
        with self.assertRaises(ValueError):
            vr.run(api=FakeApi([]), config=self.config, now=NOW, mode="weekly")


class ScheduledTickTests(unittest.TestCase):
    def test_one_failing_step_never_skips_the_other(self):
        with (
            patch.object(scheduled_tick, "_log") as log,
            patch.object(scheduled_tick.subprocess, "run", side_effect=OSError("python missing")),
            patch.object(scheduled_tick.radar_scheduler, "tick", return_value={"action": "NOT_DUE", "result": None}),
        ):
            with self.assertRaises(SystemExit) as caught:
                scheduled_tick.main()
        self.assertEqual(caught.exception.code, 0)
        lines = [call.args[0] for call in log.call_args_list]
        self.assertTrue(lines[0].startswith("opportunity research: FAILED"))
        self.assertTrue(lines[1].startswith("viral radar: NOT_DUE"))

    def test_research_command_is_unchanged_and_shell_free(self):
        completed = subprocess.CompletedProcess([], 0, stdout="WAITING: nothing due\n", stderr="")
        with (
            patch.object(scheduled_tick, "_log"),
            patch.object(scheduled_tick.subprocess, "run", return_value=completed) as run,
        ):
            self.assertEqual(scheduled_tick.run_research_continue(), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[1:], [str(scheduled_tick.RESEARCH_RUNNER), "--mode", "continue"])
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_both_failing_exits_nonzero(self):
        with (
            patch.object(scheduled_tick, "_log"),
            patch.object(scheduled_tick, "run_research_continue", return_value=2),
            patch.object(scheduled_tick, "run_radar_tick", return_value=1),
        ):
            with self.assertRaises(SystemExit) as caught:
                scheduled_tick.main()
        self.assertEqual(caught.exception.code, 1)

    def test_install_script_points_at_the_combined_runner(self):
        script = (_ROOT / "scripts" / "install_experiment_01_3_auto_refresh.ps1").read_text(encoding="utf-8")
        self.assertIn('opportunity_engine\\scheduled_tick.py', script)
        self.assertNotIn("--mode continue", script)



if __name__ == "__main__":
    unittest.main()
