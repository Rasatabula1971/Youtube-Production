import unittest

from youtube_discovery_benchmark import (
    _agent_map,
    _reference_map,
    compare,
    query_plan,
)


class YoutubeDiscoveryBenchmarkTests(unittest.TestCase):
    def test_query_plan_uses_01_3_topic_queries(self):
        plan = query_plan(
            {
                "topics": [
                    {
                        "topic": "brakes",
                        "queries": [
                            "F1 brakes engineering"
                        ],
                    }
                ]
            }
        )

        self.assertEqual(
            plan,
            [
                {
                    "topic": "brakes",
                    "query": "F1 brakes engineering",
                }
            ],
        )

    def test_reference_map_unions_api_duration_branches(self):
        checkpoint = {
            "audit": [
                {
                    "target_topic": "brakes",
                    "query": "F1 brakes engineering",
                    "video_ids": ["a", "b"],
                },
                {
                    "target_topic": "brakes",
                    "query": "F1 brakes engineering",
                    "video_ids": ["b", "c"],
                },
            ]
        }

        mapped = _reference_map(
            checkpoint
        )

        self.assertEqual(
            mapped[
                (
                    "brakes",
                    "F1 brakes engineering",
                )
            ],
            {"a", "b", "c"},
        )

    def test_agent_map_unions_search_strategies(self):
        results = {
            "searches": [
                {
                    "topic": "brakes",
                    "query": "F1 brakes engineering",
                    "strategy": "relevance",
                    "results": [
                        {"video_id": "a"},
                        {"video_id": "d"},
                    ],
                },
                {
                    "topic": "brakes",
                    "query": "F1 brakes engineering",
                    "strategy": "date",
                    "results": [
                        {"video_id": "a"},
                        {"video_id": "e"},
                    ],
                },
            ]
        }

        mapped = _agent_map(results)

        self.assertEqual(
            mapped[
                (
                    "brakes",
                    "F1 brakes engineering",
                )
            ],
            {"a", "d", "e"},
        )

    def test_compare_reports_overlap_without_claiming_equivalence(self):
        checkpoint = {
            "experiment_id": "01.3",
            "status": "QUOTA_EXHAUSTED",
            "observed_at": "2026-09-26T12:00:00Z",
            "audit": [
                {
                    "target_topic": "brakes",
                    "query": "F1 brakes engineering",
                    "video_ids": [
                        "a",
                        "b",
                        "c",
                    ],
                }
            ],
        }
        results = {
            "searches": [
                {
                    "topic": "brakes",
                    "query": "F1 brakes engineering",
                    "results": [
                        {"video_id": "a"},
                        {"video_id": "c"},
                        {"video_id": "d"},
                    ],
                }
            ]
        }

        output = compare(
            results,
            checkpoint,
        )

        self.assertEqual(
            output["overall"][
                "overlap_count"
            ],
            2,
        )
        self.assertEqual(
            output["overall"][
                "api_reference_recall"
            ],
            0.6667,
        )
        self.assertTrue(
            any(
                "does not reproduce identically"
                in note
                for note in output["notes"]
            )
        )


if __name__ == "__main__":
    unittest.main()
