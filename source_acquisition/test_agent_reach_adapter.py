import json
import subprocess
import unittest
from unittest.mock import patch

import agent_reach_adapter as adapter


class AgentReachAdapterTests(unittest.TestCase):

    def test_console_json_is_cp1252_safe_with_unicode_messages(self):
        rendered = adapter.render_console_json(
            {
                "youtube": {
                    "status": "ok",
                    "message": "可提取视频信息和字幕",
                }
            }
        )

        rendered.encode("cp1252")
        self.assertIn("\\u53ef", rendered)
        self.assertEqual(
            json.loads(rendered)["youtube"]["message"],
            "可提取视频信息和字幕",
        )

    def test_missing_agent_reach_is_reported(self):
        with patch.object(
            adapter.shutil,
            "which",
            return_value=None,
        ):
            result = adapter.doctor()

        self.assertEqual(
            result["status"],
            "NOT_INSTALLED",
        )

    def test_doctor_parses_channel_json(self):
        payload = {
            "youtube": {
                "status": "ok",
                "message": "ready",
                "active_backend": "yt-dlp",
                "backends": ["yt-dlp"],
            }
        }

        def which(name):
            return (
                f"/bin/{name}"
                if name in {
                    "agent-reach",
                    "yt-dlp",
                }
                else None
            )

        with (
            patch.object(
                adapter.shutil,
                "which",
                side_effect=which,
            ),
            patch.object(
                adapter.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["agent-reach"],
                    0,
                    stdout=json.dumps(
                        payload
                    ),
                    stderr="",
                ),
            ),
        ):
            doctor = adapter.doctor()
            health = adapter.youtube_health(
                doctor
            )

        self.assertEqual(
            doctor["status"],
            "READY",
        )
        self.assertTrue(
            health["ready"]
        )
        self.assertEqual(
            health["active_backend"],
            "yt-dlp",
        )

    def test_warn_channel_is_not_ready(self):
        payload = {
            "status": "READY",
            "channels": {
                "youtube": {
                    "status": "warn",
                    "active_backend": "yt-dlp",
                    "message": "missing JS runtime",
                }
            },
        }

        with patch.object(
            adapter,
            "yt_dlp_path",
            return_value="/bin/yt-dlp",
        ):
            health = adapter.youtube_health(
                payload
            )

        self.assertFalse(
            health["ready"]
        )

    def test_search_uses_ytsearch_and_parses_json_lines(self):
        stdout = "\n".join(
            [
                json.dumps(
                    {
                        "id": "v1",
                        "title": "Video One",
                        "channel": "Channel",
                        "duration": 120,
                        "view_count": 1000,
                    }
                ),
                json.dumps(
                    {
                        "id": "v2",
                        "title": "Video Two",
                        "channel": "Channel",
                        "duration": 300,
                        "view_count": 2000,
                    }
                ),
            ]
        )

        def which(name):
            return (
                f"/bin/{name}"
                if name in {
                    "agent-reach",
                    "yt-dlp",
                }
                else None
            )

        with (
            patch.object(
                adapter,
                "youtube_health",
                return_value={
                    "ready": True,
                    "active_backend": "yt-dlp",
                },
            ),
            patch.object(
                adapter.shutil,
                "which",
                side_effect=which,
            ),
            patch.object(
                adapter.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["yt-dlp"],
                    0,
                    stdout=stdout,
                    stderr="",
                ),
            ) as run,
        ):
            result = adapter.search_youtube(
                "F1 brakes engineering",
                limit=2,
                strategy="relevance",
            )

        self.assertEqual(
            result["result_count"],
            2,
        )
        command = run.call_args.args[0]
        self.assertIn(
            "ytsearch2:F1 brakes engineering",
            command,
        )
        self.assertFalse(
            run.call_args.kwargs["shell"]
        )

    def test_date_strategy_uses_ytsearchdate(self):
        with (
            patch.object(
                adapter,
                "youtube_health",
                return_value={
                    "ready": True,
                    "active_backend": "yt-dlp",
                },
            ),
            patch.object(
                adapter,
                "yt_dlp_path",
                return_value="/bin/yt-dlp",
            ),
            patch.object(
                adapter.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["yt-dlp"],
                    0,
                    stdout="",
                    stderr="",
                ),
            ) as run,
        ):
            adapter.search_youtube(
                "query",
                limit=3,
                strategy="date",
            )

        self.assertIn(
            "ytsearchdate3:query",
            run.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
