"""vidIQ supplemental validation for Experiment 01 opportunities.

This stage is intentionally supplemental. It does not replace YouTube Data API
measurements, does not calculate a composite score, and does not change PASS /
REVIEW / HOLD decisions. It adds a second source of current market intelligence
for the Human Opportunity Gate.

Paid tool use is constrained by vidiq_mcp.py:
- hard local ceiling: 149 credits,
- provider balance checked before every paid call,
- one provider credit is always reserved,
- only three read-only 5-credit tools are allowed,
- cached results are reused for an unchanged study set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vidiq_mcp import (
    ALLOWED_PAID_TOOLS,
    BUDGET_FILE,
    BudgetStateUnreadable,
    DEFAULT_MCP_URL,
    ENV_FILE,
    HARD_CREDIT_CAP,
    VidIQMCPClient,
    budget_check,
    build_topic_arguments,
    configured_credit_cap,
    declared_tool_credit_cost,
    extract_credit_balance,
    find_credit_balance_tool,
    find_tool,
    load_budget_state,
    load_env_file,
    max_paid_calls_per_run,
    proxy_available,
    reserve_budget,
    result_preview,
)

HERE = Path(__file__).resolve().parent
OUTPUT_ROOT = HERE / "output"
EXP15_DIR = OUTPUT_ROOT / "experiment_01_5"
STUDY_SET_FILE = EXP15_DIR / "study_set.json"

OUTPUT_DIR = OUTPUT_ROOT / "vidiq"
ENRICHMENT_FILE = OUTPUT_DIR / "opportunity_enrichment.json"
DOCTOR_FILE = OUTPUT_DIR / "doctor.json"

TOOL_ORDER = ("keyword_research", "outliers", "trending_videos")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def opportunity_id(item: dict[str, Any]) -> str:
    topic = str(item.get("topic") or "").strip()
    fmt = str(item.get("format_candidate") or "").strip()
    niche = str(item.get("niche") or "").strip()
    return f"{niche}:{topic}:{fmt}" if niche else f"{topic}:{fmt}"


def opportunity_query(item: dict[str, Any]) -> str:
    topic = str(item.get("topic") or "").replace("_", " ").strip()
    niche = str(item.get("niche") or "").replace("_", " ").strip()
    if niche and niche.casefold() not in topic.casefold():
        return f"{niche} {topic}".strip()
    return topic


def unique_opportunities(study_set: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in study_set:
        if not isinstance(item, dict):
            continue
        key = opportunity_id(item)
        if not key or key in grouped:
            continue
        grouped[key] = {
            "opportunity_id": key,
            "topic": item.get("topic"),
            "niche": item.get("niche"),
            "format_candidate": item.get("format_candidate"),
            "query": opportunity_query(item),
        }
    return list(grouped.values())


def configured_client() -> VidIQMCPClient | None:
    load_env_file(ENV_FILE)
    if not proxy_available():
        return None
    url = os.getenv("VIDIQ_MCP_URL", DEFAULT_MCP_URL).strip() or DEFAULT_MCP_URL
    return VidIQMCPClient(url=url)


def tool_inventory(
    client: VidIQMCPClient,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any] | None]]:
    tools = client.list_tools()
    selected = {
        logical: find_tool(tools, logical)
        for logical in TOOL_ORDER
    }
    selected["credit_balance"] = find_credit_balance_tool(tools)
    return tools, selected


def provider_balance(
    client: VidIQMCPClient,
    balance_tool: dict[str, Any] | None,
) -> tuple[int | None, Any]:
    if balance_tool is None:
        return None, None
    name = str(balance_tool.get("name") or "")
    if not name:
        return None, None
    result = client.call_tool(name, {})
    return extract_credit_balance(result), result


def doctor(client: VidIQMCPClient | None = None) -> dict[str, Any]:
    client = client or configured_client()
    if client is None:
        payload = {
            "status": "NOT_CONFIGURED",
            "configured": False,
            "paid_calls": 0,
            "hard_credit_cap": HARD_CREDIT_CAP,
            "message": (
                "Node.js/npm npx was not found. vidIQ MCP uses OAuth, not an API key. "
                "Install Node.js/npm so the local OAuth bridge can run."
            ),
        }
        write_json(DOCTOR_FILE, payload)
        return payload

    try:
        tools, selected = tool_inventory(client)
        remaining, _ = provider_balance(client, selected["credit_balance"])
    except Exception as exc:  # noqa: BLE001 - external boundary
        payload = {
            "status": "UNAVAILABLE",
            "configured": True,
            "paid_calls": 0,
            "hard_credit_cap": HARD_CREDIT_CAP,
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(DOCTOR_FILE, payload)
        return payload

    missing = [
        logical
        for logical in TOOL_ORDER
        if selected.get(logical) is None
    ]
    declared_costs = {
        logical: (
            declared_tool_credit_cost(selected[logical])
            if isinstance(selected.get(logical), dict)
            else None
        )
        for logical in TOOL_ORDER
    }
    unsafe_costs = [
        logical
        for logical in TOOL_ORDER
        if selected.get(logical) is not None
        and declared_costs.get(logical) != ALLOWED_PAID_TOOLS[logical]
    ]
    if selected.get("credit_balance") is None:
        missing.append("credit_balance_utility")

    payload = {
        "status": (
            "READY"
            if not missing and not unsafe_costs and remaining is not None
            else "PARTIAL"
        ),
        "configured": True,
        "paid_calls": 0,
        "hard_credit_cap": configured_credit_cap(),
        "provider_remaining_credits": remaining,
        "tools_visible": len(tools),
        "required_tools": {
            key: (
                str(value.get("name"))
                if isinstance(value, dict)
                else None
            )
            for key, value in selected.items()
        },
        "missing": missing,
        "declared_credit_costs": declared_costs,
        "unsafe_credit_cost_tools": unsafe_costs,
        "message": (
            "Doctor uses only protocol operations and the free credit-balance utility; no paid research tool is called."
        ),
    }
    write_json(DOCTOR_FILE, payload)
    return payload


def _load_previous(source_hash: str) -> dict[str, Any]:
    if not ENRICHMENT_FILE.exists():
        return {}
    try:
        payload = load_json(ENRICHMENT_FILE)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("source_study_set_sha256") != source_hash:
        return {}
    return payload


def run_enrichment(
    client: VidIQMCPClient | None = None,
    *,
    study_set: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    client = client or configured_client()
    if client is None:
        return {
            "status": "NOT_CONFIGURED",
            "paid_calls_this_run": 0,
            "message": (
                "Node.js/npm npx was not found. vidIQ MCP uses OAuth, not an API key."
            ),
        }

    if study_set is None:
        if not STUDY_SET_FILE.exists():
            return {
                "status": "WAITING_FOR_01_5",
                "paid_calls_this_run": 0,
            }
        loaded = load_json(STUDY_SET_FILE)
        if not isinstance(loaded, list):
            raise ValueError("Experiment 01.5 study_set.json must contain a list.")
        study_set = loaded

    if not study_set:
        return {
            "status": "NO_OPPORTUNITIES",
            "paid_calls_this_run": 0,
        }

    source_hash = canonical_sha256(study_set)
    previous = _load_previous(source_hash)
    previous_opportunities = previous.get("opportunities", {})
    if not isinstance(previous_opportunities, dict):
        previous_opportunities = {}

    tools, selected = tool_inventory(client)
    balance_tool = selected.get("credit_balance")
    remaining, _ = provider_balance(client, balance_tool)
    if balance_tool is None or remaining is None:
        payload = {
            "artifact": "vidiq_opportunity_enrichment",
            "status": "FAIL_CLOSED_NO_CREDIT_BALANCE",
            "source_study_set_sha256": source_hash,
            "created_at": utc_now(),
            "paid_calls_this_run": 0,
            "provider_remaining_credits": remaining,
            "message": (
                "Paid vidIQ tools were not called because the free credit balance could not be verified."
            ),
        }
        write_json(ENRICHMENT_FILE, payload)
        return payload

    missing_tools = [
        logical for logical in TOOL_ORDER if selected.get(logical) is None
    ]
    try:
        state = load_budget_state(BUDGET_FILE)
    except BudgetStateUnreadable as exc:
        payload = {
            "artifact": "vidiq_opportunity_enrichment",
            "status": "FAIL_CLOSED_BUDGET_STATE_UNREADABLE",
            "source_study_set_sha256": source_hash,
            "created_at": utc_now(),
            "paid_calls_this_run": 0,
            "provider_remaining_credits": remaining,
            "reason": "budget_state_unreadable",
            "message": str(exc),
        }
        write_json(ENRICHMENT_FILE, payload)
        return payload

    run_limit = max_paid_calls_per_run()
    paid_calls = 0
    run_reserved_credits = 0
    stopped_reason: str | None = None
    output_opportunities: dict[str, Any] = {}

    for opportunity in unique_opportunities(study_set):
        key = opportunity["opportunity_id"]
        query = str(opportunity["query"])
        prior = previous_opportunities.get(key, {})
        prior_tools = prior.get("tools", {}) if isinstance(prior, dict) else {}
        if not isinstance(prior_tools, dict):
            prior_tools = {}

        tool_results: dict[str, Any] = {}
        for logical in TOOL_ORDER:
            old = prior_tools.get(logical)
            if (
                isinstance(old, dict)
                and old.get("status") == "OK"
                and old.get("query") == query
            ):
                tool_results[logical] = old
                continue

            tool = selected.get(logical)
            if tool is None:
                tool_results[logical] = {
                    "status": "TOOL_UNAVAILABLE",
                    "query": query,
                }
                continue

            if paid_calls >= run_limit:
                stopped_reason = "per_run_call_limit_reached"
                tool_results[logical] = {
                    "status": "SKIPPED_BUDGET",
                    "query": query,
                    "reason": stopped_reason,
                }
                continue

            expected_cost = int(ALLOWED_PAID_TOOLS[logical])
            live_cost = declared_tool_credit_cost(tool)
            if live_cost != expected_cost:
                tool_results[logical] = {
                    "status": "SKIPPED_UNVERIFIED_COST",
                    "query": query,
                    "tool_name": str(tool.get("name") or ""),
                    "expected_credit_cost": expected_cost,
                    "declared_credit_cost": live_cost,
                    "reason": (
                        "Live vidIQ tool metadata did not declare the exact "
                        "allowed credit cost."
                    ),
                }
                stopped_reason = "live_tool_cost_unverified"
                continue

            # Re-check provider balance immediately before every paid call.
            remaining, _ = provider_balance(client, balance_tool)
            cost = live_cost
            allowed, reason = budget_check(
                state=state,
                cost=cost,
                provider_remaining=remaining,
            )
            if not allowed:
                stopped_reason = reason
                tool_results[logical] = {
                    "status": "SKIPPED_BUDGET",
                    "query": query,
                    "reason": reason,
                    "provider_remaining_credits": remaining,
                }
                continue

            actual_name = str(tool.get("name") or "")
            try:
                arguments = build_topic_arguments(tool, query)
            except ValueError as exc:
                tool_results[logical] = {
                    "status": "ARGUMENT_SCHEMA_UNSUPPORTED",
                    "query": query,
                    "tool_name": actual_name,
                    "error": str(exc),
                }
                continue

            # Reserve locally before dispatch. If transport fails after dispatch,
            # the conservative ledger still assumes vidIQ may have charged it.
            state = reserve_budget(state=state, cost=cost, path=BUDGET_FILE)
            paid_calls += 1
            run_reserved_credits += cost

            try:
                result = client.call_tool(actual_name, arguments)
            except Exception as exc:  # noqa: BLE001 - external boundary
                tool_results[logical] = {
                    "status": "CALL_FAILED",
                    "query": query,
                    "tool_name": actual_name,
                    "credit_cost_reserved": cost,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                continue

            tool_results[logical] = {
                "status": "OK",
                "query": query,
                "tool_name": actual_name,
                "credit_cost_reserved": cost,
                "arguments": arguments,
                "result": result,
                "preview": result_preview(result),
            }

        output_opportunities[key] = {
            **opportunity,
            "tools": tool_results,
        }

    final_remaining, _ = provider_balance(client, balance_tool)
    successful = sum(
        item.get("status") == "OK"
        for opportunity in output_opportunities.values()
        for item in opportunity.get("tools", {}).values()
        if isinstance(item, dict)
    )
    expected = len(output_opportunities) * len(TOOL_ORDER)

    if successful == expected:
        status = "COMPLETE"
    elif successful:
        status = "PARTIAL"
    else:
        status = "NO_PAID_RESULTS"

    payload = {
        "artifact": "vidiq_opportunity_enrichment",
        "status": status,
        "source_study_set_sha256": source_hash,
        "created_at": utc_now(),
        "provider": "vidIQ MCP",
        "mcp_url": os.getenv("VIDIQ_MCP_URL", DEFAULT_MCP_URL),
        "authentication": "OAuth 2.0 via mcp-remote",
        "hard_credit_cap": configured_credit_cap(),
        "free_plan_reference_allowance": 150,
        "provider_reserve_credits": 1,
        "paid_calls_this_run": paid_calls,
        "credits_reserved_this_run": run_reserved_credits,
        "local_period": state.get("period"),
        "local_charged_credits": state.get("charged_credits"),
        "provider_remaining_credits": final_remaining,
        "per_run_paid_call_limit": run_limit,
        "stopped_reason": stopped_reason,
        "missing_tools": missing_tools,
        "declared_credit_costs": {
            logical: (
                declared_tool_credit_cost(selected[logical])
                if isinstance(selected.get(logical), dict)
                else None
            )
            for logical in TOOL_ORDER
        },
        "tools_visible": len(tools),
        "opportunities": output_opportunities,
        "notes": [
            "vidIQ evidence is supplemental and does not modify Experiment 01.5 gate status.",
            "YouTube Data API measurements remain canonical for project-owned velocity and metadata.",
            "Cached OK results for the same study-set hash and query are reused without another paid call.",
            "No paid call is allowed when provider remaining credits cannot be verified.",
        ],
    }
    write_json(ENRICHMENT_FILE, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="vidIQ Opportunity Intelligence")
    parser.add_argument(
        "--mode",
        choices=("doctor", "enrich"),
        required=True,
    )
    args = parser.parse_args()

    result = doctor() if args.mode == "doctor" else run_enrichment()
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("status") in {
        "UNAVAILABLE",
        "FAIL_CLOSED_NO_CREDIT_BALANCE",
    }:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
