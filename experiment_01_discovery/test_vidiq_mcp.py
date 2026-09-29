from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import vidiq_mcp as module


class VidIQMCPTests(unittest.TestCase):
    def test_hard_cap_is_never_above_149(self):
        with patch.dict(os.environ, {"VIDIQ_MONTHLY_CREDIT_CAP": "999"}, clear=False):
            self.assertEqual(module.configured_credit_cap(), 149)

    def test_budget_fails_closed_when_provider_balance_unknown(self):
        allowed, reason = module.budget_check(
            state={"charged_credits": 0},
            cost=5,
            provider_remaining=None,
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "provider_credit_balance_unknown")

    def test_budget_preserves_provider_credit_reserve(self):
        allowed, reason = module.budget_check(
            state={"charged_credits": 0},
            cost=5,
            provider_remaining=5,
        )
        self.assertFalse(allowed)
        self.assertEqual(
            reason,
            "provider_free_credit_reserve_would_be_crossed",
        )

    def test_budget_blocks_before_150_local_credits(self):
        allowed, reason = module.budget_check(
            state={"charged_credits": 145},
            cost=5,
            provider_remaining=150,
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "local_149_credit_cap_would_be_crossed")

    def test_credit_balance_tool_never_fuzzy_matches_paid_research_tool(self):
        tools = [
            {
                "name": "vidiq_outliers",
                "description": "Find outliers. Uses 5 credits from your balance.",
            },
            {
                "name": "vidiq_balance",
                "description": "Get current credit balance.",
            },
        ]
        found = module.find_credit_balance_tool(tools)
        self.assertEqual(found["name"], "vidiq_balance")

    def test_credit_balance_tool_returns_none_without_known_free_utility(self):
        tools = [
            {
                "name": "vidiq_outliers",
                "description": "Find outliers. Uses 5 credits from your balance.",
            }
        ]
        self.assertIsNone(module.find_credit_balance_tool(tools))

    def test_extract_credit_balance_prefers_renewable_over_add_on(self):
        result = {
            "structuredContent": {
                "totalCredits": 240,
                "renewableCredits": 140,
                "addOnCredits": 100,
            }
        }
        self.assertEqual(module.extract_credit_balance(result), 140)

    def test_extract_credit_balance_from_structured_content(self):
        result = {
            "structuredContent": {
                "plan": "Free",
                "remainingCredits": 137,
            }
        }
        self.assertEqual(module.extract_credit_balance(result), 137)

    def test_extract_credit_balance_from_text(self):
        result = {
            "content": [
                {
                    "type": "text",
                    "text": "You have 82 AI credits remaining.",
                }
            ]
        }
        self.assertEqual(module.extract_credit_balance(result), 82)

    def test_declared_tool_credit_cost_parses_single_live_cost(self):
        tool = {
            "description": "Search current YouTube trends. Uses 5 credits per call."
        }
        self.assertEqual(module.declared_tool_credit_cost(tool), 5)

    def test_declared_tool_credit_cost_fails_closed_when_missing(self):
        self.assertIsNone(
            module.declared_tool_credit_cost(
                {"description": "Search current YouTube trends."}
            )
        )

    def test_declared_tool_credit_cost_fails_closed_when_ambiguous(self):
        self.assertIsNone(
            module.declared_tool_credit_cost(
                {"description": "Uses 5 credits normally; 10 credits for deep mode."}
            )
        )

    def test_find_tool_accepts_prefixed_names(self):
        tools = [
            {
                "name": "vidiq_keyword_research",
                "description": "Keyword research",
            }
        ]
        found = module.find_tool(tools, "keyword_research")
        self.assertEqual(found["name"], "vidiq_keyword_research")

    def test_build_topic_arguments_uses_live_schema(self):
        tool = {
            "name": "keyword_research",
            "inputSchema": {
                "type": "object",
                "required": ["keyword"],
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "maximum": 3},
                },
            },
        }
        args = module.build_topic_arguments(tool, "automotive tyre pressure")
        self.assertEqual(
            args,
            {"keyword": "automotive tyre pressure", "limit": 3},
        )

    def test_reserve_budget_records_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.json"
            state = {
                "period": module.current_period(),
                "charged_credits": 0,
                "paid_calls_dispatched": 0,
            }
            updated = module.reserve_budget(
                state=state,
                cost=5,
                path=path,
            )
            on_disk = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(updated["charged_credits"], 5)
        self.assertEqual(updated["paid_calls_dispatched"], 1)
        self.assertEqual(on_disk["charged_credits"], 5)


if __name__ == "__main__":
    unittest.main()
