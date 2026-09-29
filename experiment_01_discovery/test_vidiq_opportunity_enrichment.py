from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import vidiq_opportunity_enrichment as enrich
import vidiq_mcp


class FakeClient:
    def __init__(self, starting_credits: int = 150):
        self.remaining = starting_credits
        self.calls: list[tuple[str, dict]] = []
        self.tools = [
            {
                "name": "credit_balance",
                "description": "Check remaining AI credit balance",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "keyword_research",
                "description": "Keyword research",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            },
            {
                "name": "outliers",
                "description": "Find outlier videos",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            },
            {
                "name": "trending_videos",
                "description": "Find trending videos",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            },
        ]

    def list_tools(self):
        return self.tools

    def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "credit_balance":
            return {
                "structuredContent": {
                    "remainingCredits": self.remaining,
                }
            }
        self.remaining -= 5
        return {
            "structuredContent": {
                "tool": name,
                "query": arguments.get("query"),
                "items": [{"title": f"{name} result"}],
            }
        }


class VidIQEnrichmentTests(unittest.TestCase):
    def study_set(self):
        return [
            {
                "topic": "tyre_pressure",
                "niche": "automotive",
                "format_candidate": "long_form_candidate",
                "video_id": "v1",
            },
            {
                "topic": "tyre_pressure",
                "niche": "automotive",
                "format_candidate": "long_form_candidate",
                "video_id": "v2",
            },
        ]

    def test_one_opportunity_uses_three_paid_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeClient()
            with (
                patch.object(enrich, "ENRICHMENT_FILE", root / "enrichment.json"),
                patch.object(enrich, "BUDGET_FILE", root / "budget.json"),
                patch.dict(
                    "os.environ",
                    {
                        "VIDIQ_MONTHLY_CREDIT_CAP": "149",
                        "VIDIQ_MAX_PAID_CALLS_PER_RUN": "9",
                    },
                    clear=False,
                ),
            ):
                result = enrich.run_enrichment(
                    client=client,
                    study_set=self.study_set(),
                )

        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["paid_calls_this_run"], 3)
        self.assertEqual(result["credits_reserved_this_run"], 15)
        paid = [name for name, _ in client.calls if name != "credit_balance"]
        self.assertEqual(
            paid,
            ["keyword_research", "outliers", "trending_videos"],
        )

    def test_identical_study_set_reuses_cached_paid_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeClient()
            with (
                patch.object(enrich, "ENRICHMENT_FILE", root / "enrichment.json"),
                patch.object(enrich, "BUDGET_FILE", root / "budget.json"),
                patch.dict(
                    "os.environ",
                    {
                        "VIDIQ_MONTHLY_CREDIT_CAP": "149",
                        "VIDIQ_MAX_PAID_CALLS_PER_RUN": "9",
                    },
                    clear=False,
                ),
            ):
                first = enrich.run_enrichment(
                    client=client,
                    study_set=self.study_set(),
                )
                before = len(
                    [name for name, _ in client.calls if name != "credit_balance"]
                )
                second = enrich.run_enrichment(
                    client=client,
                    study_set=self.study_set(),
                )
                after = len(
                    [name for name, _ in client.calls if name != "credit_balance"]
                )

        self.assertEqual(first["paid_calls_this_run"], 3)
        self.assertEqual(second["paid_calls_this_run"], 0)
        self.assertEqual(before, after)

    def test_local_149_credit_cap_blocks_additional_paid_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget = root / "budget.json"
            budget.write_text(
                json.dumps(
                    {
                        "period": vidiq_mcp.current_period(),
                        "charged_credits": 145,
                        "paid_calls_dispatched": 29,
                    }
                ),
                encoding="utf-8",
            )
            client = FakeClient()
            with (
                patch.object(enrich, "ENRICHMENT_FILE", root / "enrichment.json"),
                patch.object(enrich, "BUDGET_FILE", budget),
                patch.dict(
                    "os.environ",
                    {
                        "VIDIQ_MONTHLY_CREDIT_CAP": "149",
                        "VIDIQ_MAX_PAID_CALLS_PER_RUN": "9",
                    },
                    clear=False,
                ),
            ):
                result = enrich.run_enrichment(
                    client=client,
                    study_set=self.study_set(),
                )

        self.assertEqual(result["paid_calls_this_run"], 0)
        self.assertEqual(result["status"], "NO_PAID_RESULTS")
        paid = [name for name, _ in client.calls if name != "credit_balance"]
        self.assertEqual(paid, [])

    def test_unknown_provider_balance_fails_closed(self):
        class UnknownBalanceClient(FakeClient):
            def call_tool(self, name, arguments):
                self.calls.append((name, dict(arguments)))
                if name == "credit_balance":
                    return {"content": [{"type": "text", "text": "No balance data"}]}
                raise AssertionError("Paid tool must never be called")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = UnknownBalanceClient()
            with (
                patch.object(enrich, "ENRICHMENT_FILE", root / "enrichment.json"),
                patch.object(enrich, "BUDGET_FILE", root / "budget.json"),
            ):
                result = enrich.run_enrichment(
                    client=client,
                    study_set=self.study_set(),
                )

        self.assertEqual(result["status"], "FAIL_CLOSED_NO_CREDIT_BALANCE")
        self.assertEqual(result["paid_calls_this_run"], 0)


if __name__ == "__main__":
    unittest.main()
