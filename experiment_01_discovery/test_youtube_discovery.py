from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import youtube_discovery


def http_error(code: int, reason: str | None = None, retry_after: str | None = None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    body = {"error": {"errors": ([{"reason": reason}] if reason is not None else [])}}
    return urllib.error.HTTPError(
        url="https://www.googleapis.com/youtube/v3/test",
        code=code,
        msg="test",
        hdrs=headers,
        fp=io.BytesIO(json.dumps(body).encode("utf-8")),
    )


def success_response(payload: dict):
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


class YoutubeDiscoveryCheckpointTests(unittest.TestCase):
    def test_search_checkpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search_checkpoint.json"
            signature = youtube_discovery.discovery_checkpoint_signature(
                {
                    "niches": [
                        {
                            "name": "automotive",
                            "queries": ["f1 gearbox"],
                        }
                    ]
                },
                published_after="2026-01-01T00:00:00Z",
                region_code="US",
                language="en",
            )

            youtube_discovery.save_search_checkpoint(
                path,
                signature=signature,
                discovered={"v1": {"automotive"}},
                query_matches={
                    "v1": [
                        {
                            "niche": "automotive",
                            "query": "f1 gearbox",
                            "rank": 1,
                        }
                    ]
                },
                query_search_results=[
                    {
                        "niche": "automotive",
                        "query": "f1 gearbox",
                        "video_ids": ["v1"],
                    }
                ],
                completed_jobs={"automotive::f1 gearbox"},
                search_calls=1,
            )

            loaded = youtube_discovery.load_search_checkpoint(
                path,
                signature,
            )

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["search_calls"], 1)
        self.assertEqual(
            loaded["completed_jobs"],
            ["automotive::f1 gearbox"],
        )
        self.assertEqual(
            loaded["discovered"]["v1"],
            ["automotive"],
        )

    def test_search_checkpoint_ignores_changed_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search_checkpoint.json"
            original = {"queries": [], "region_code": "US"}
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "signature": original,
                    }
                ),
                encoding="utf-8",
            )

            loaded = youtube_discovery.load_search_checkpoint(
                path,
                {"queries": [], "region_code": "GB"},
            )

        self.assertIsNone(loaded)


class YoutubeDiscoveryApiTests(unittest.TestCase):
    @patch("youtube_discovery.time.sleep")
    @patch("youtube_discovery.urllib.request.urlopen")
    def test_5xx_retries_with_backoff(self, urlopen, sleep):
        urlopen.side_effect = [
            http_error(503, "backendError"),
            success_response({"items": []}),
        ]

        result = youtube_discovery.api_get("videos", "key", part="snippet")

        self.assertEqual(result, {"items": []})
        sleep.assert_called_once_with(1.0)
        self.assertEqual(urlopen.call_count, 2)

    @patch("youtube_discovery.time.sleep")
    @patch("youtube_discovery.urllib.request.urlopen")
    def test_429_uses_retry_after(self, urlopen, sleep):
        urlopen.side_effect = [
            http_error(429, "rateLimitExceeded", retry_after="7"),
            success_response({"items": []}),
        ]

        result = youtube_discovery.api_get("search", "key", part="snippet")

        self.assertEqual(result, {"items": []})
        sleep.assert_called_once_with(7.0)
        self.assertEqual(urlopen.call_count, 2)

    @patch("youtube_discovery.time.sleep")
    @patch("youtube_discovery.urllib.request.urlopen")
    def test_403_rate_limit_retries(self, urlopen, sleep):
        urlopen.side_effect = [
            http_error(403, "rateLimitExceeded"),
            success_response({"items": []}),
        ]

        result = youtube_discovery.api_get("search", "key", part="snippet")

        self.assertEqual(result, {"items": []})
        sleep.assert_called_once_with(1.0)
        self.assertEqual(urlopen.call_count, 2)

    @patch("youtube_discovery.time.sleep")
    @patch("youtube_discovery.urllib.request.urlopen")
    def test_403_quota_exceeded_fails_closed_without_retry(self, urlopen, sleep):
        urlopen.side_effect = http_error(403, "quotaExceeded")

        with self.assertRaises(SystemExit) as context:
            youtube_discovery.api_get("search", "key", part="snippet")

        self.assertIn("quotaExceeded", str(context.exception))
        sleep.assert_not_called()
        self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
