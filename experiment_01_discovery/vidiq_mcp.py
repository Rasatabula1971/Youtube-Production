"""vidIQ MCP stdio bridge and fail-closed credit guard.

vidIQ's MCP endpoint uses OAuth 2.0. There is no vidIQ API key to paste into
this project. The local project launches the open-source mcp-remote bridge
through npx; mcp-remote performs the browser OAuth flow against vidIQ and stores
its OAuth state outside this repository.

The adapter deliberately permits only the small read-only tool allowlist used by
Experiment 01 opportunity research. It never calls a paid MCP tool unless:
1. vidIQ reports a remaining credit balance,
2. enough provider credits remain to preserve a one-credit reserve, and
3. the local YouTube Production budget stays below the hard 149-credit cap.

vidIQ currently documents 150 monthly AI credits on Free and says most MCP core
calls cost 5 credits. This project therefore budgets credits, not "calls".
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "vidiq"
BUDGET_FILE = OUTPUT_DIR / "budget_state.json"

DEFAULT_MCP_URL = "https://mcp.vidiq.com/mcp"
DEFAULT_MCP_REMOTE_PACKAGE = "mcp-remote@0.1.38"
FREE_PLAN_ALLOWANCE = 150
HARD_CREDIT_CAP = 149
PROVIDER_RESERVE_CREDITS = 1
DEFAULT_MAX_PAID_CALLS_PER_RUN = 9

ALLOWED_PAID_TOOLS = {
    "keyword_research": 5,
    "outliers": 5,
    "trending_videos": 5,
}


def declared_tool_credit_cost(tool: dict[str, Any]) -> int | None:
    """Return an unambiguous credit cost declared by the live tool metadata.

    The integration fails closed when the live MCP metadata does not advertise
    a single exact credit amount matching our allowlist expectation.
    """
    description = str(tool.get("description") or "")
    matches = re.findall(
        r"(?i)(\d+)\s*(?:AI\s*)?credits?\b",
        description,
    )
    values = {int(value) for value in matches}
    if len(values) == 1:
        return values.pop()
    return None


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def configured_credit_cap() -> int:
    raw = os.getenv("VIDIQ_MONTHLY_CREDIT_CAP", str(HARD_CREDIT_CAP))
    try:
        requested = int(raw)
    except ValueError:
        requested = HARD_CREDIT_CAP
    return max(0, min(requested, HARD_CREDIT_CAP))


def max_paid_calls_per_run() -> int:
    raw = os.getenv(
        "VIDIQ_MAX_PAID_CALLS_PER_RUN",
        str(DEFAULT_MAX_PAID_CALLS_PER_RUN),
    )
    try:
        requested = int(raw)
    except ValueError:
        requested = DEFAULT_MAX_PAID_CALLS_PER_RUN
    return max(0, min(requested, 29))


def load_budget_state(path: Path = BUDGET_FILE) -> dict[str, Any]:
    period = current_period()
    state = read_json(path)
    if state.get("period") != period:
        return {
            "period": period,
            "charged_credits": 0,
            "paid_calls_dispatched": 0,
            "updated_at": utc_now(),
        }
    return {
        "period": period,
        "charged_credits": int(state.get("charged_credits") or 0),
        "paid_calls_dispatched": int(state.get("paid_calls_dispatched") or 0),
        "updated_at": state.get("updated_at") or utc_now(),
    }


def budget_check(
    *,
    state: dict[str, Any],
    cost: int,
    provider_remaining: int | None,
    credit_cap: int | None = None,
) -> tuple[bool, str]:
    cap = configured_credit_cap() if credit_cap is None else min(
        max(int(credit_cap), 0),
        HARD_CREDIT_CAP,
    )
    charged = int(state.get("charged_credits") or 0)

    if provider_remaining is None:
        return False, "provider_credit_balance_unknown"
    if provider_remaining - cost < PROVIDER_RESERVE_CREDITS:
        return False, "provider_free_credit_reserve_would_be_crossed"
    if charged + cost > cap:
        return False, "local_149_credit_cap_would_be_crossed"
    return True, "allowed"


def reserve_budget(
    *,
    state: dict[str, Any],
    cost: int,
    path: Path = BUDGET_FILE,
) -> dict[str, Any]:
    updated = dict(state)
    updated["charged_credits"] = int(updated.get("charged_credits") or 0) + int(cost)
    updated["paid_calls_dispatched"] = int(
        updated.get("paid_calls_dispatched") or 0
    ) + 1
    updated["updated_at"] = utc_now()
    write_json(path, updated)
    return updated


def npx_path() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def proxy_available() -> bool:
    return npx_path() is not None


class VidIQMCPClient:
    """Small stdio MCP client backed by mcp-remote OAuth bridging."""

    def __init__(
        self,
        *,
        url: str = DEFAULT_MCP_URL,
        package: str | None = None,
        transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.url = url.strip() or DEFAULT_MCP_URL
        self.package = (
            package
            or os.getenv("VIDIQ_MCP_REMOTE_PACKAGE", DEFAULT_MCP_REMOTE_PACKAGE)
        ).strip()
        self._transport_override = transport
        self._next_id = 1
        self.initialized = False
        self.process: subprocess.Popen[str] | None = None
        atexit.register(self.close)

    def _start_proxy(self) -> None:
        if self._transport_override is not None or self.process is not None:
            return
        executable = npx_path()
        if not executable:
            raise RuntimeError(
                "npx was not found. Install Node.js/npm before using vidIQ MCP."
            )

        self.process = subprocess.Popen(
            [
                executable,
                "-y",
                self.package,
                self.url,
                "--transport",
                "http-only",
            ],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def _write_message(self, payload: dict[str, Any]) -> None:
        self._start_proxy()
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("vidIQ MCP proxy stdin is unavailable.")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _stdio_transport(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._write_message(payload)
        request_id = payload.get("id")
        if request_id is None:
            return {}

        if self.process is None or self.process.stdout is None:
            raise RuntimeError("vidIQ MCP proxy stdout is unavailable.")

        while True:
            line = self.process.stdout.readline()
            if line == "":
                code = self.process.poll()
                raise RuntimeError(
                    "vidIQ MCP OAuth bridge closed unexpectedly"
                    + (f" with exit code {code}" if code is not None else "")
                    + "."
                )
            raw = line.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue

            if message.get("id") == request_id and (
                "result" in message or "error" in message
            ):
                return message

            # Keep the bridge alive if the remote server pings the client.
            if message.get("method") == "ping" and message.get("id") is not None:
                self._write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "result": {},
                    }
                )

    def _transport(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._transport_override is not None:
            return self._transport_override(payload)
        return self._stdio_transport(payload)

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        response = self._transport(payload)
        if response.get("error") is not None:
            raise RuntimeError(f"vidIQ MCP {method} error: {response['error']}")
        return response.get("result")

    def _notify(self, method: str) -> None:
        self._transport({"jsonrpc": "2.0", "method": method})

    def initialize(self) -> dict[str, Any]:
        if self.initialized:
            return {}
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "youtube-production",
                    "version": "1.0",
                },
            },
        )
        self._notify("notifications/initialized")
        self.initialized = True
        return result if isinstance(result, dict) else {}

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        result = self._rpc("tools/list", {})
        if not isinstance(result, dict):
            return []
        tools = result.get("tools", [])
        return [item for item in tools if isinstance(item, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.initialize()
        return self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments},
        )

    def close(self) -> None:
        if self.process is None:
            return
        process = self.process
        self.process = None
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


def find_tool(
    tools: list[dict[str, Any]],
    logical_name: str,
) -> dict[str, Any] | None:
    needle = logical_name.casefold()
    for tool in tools:
        name = str(tool.get("name") or "")
        if name.casefold() == needle:
            return tool
    for tool in tools:
        name = str(tool.get("name") or "")
        normalized = name.casefold().replace("-", "_")
        if normalized.endswith(needle) or needle in normalized:
            return tool
    return None


def find_credit_balance_tool(
    tools: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return only the known free vidIQ balance utility.

    Do not use description-based fuzzy matching here: paid research tools may
    mention credit usage in their descriptions and must never be mistaken for
    the free balance utility.
    """
    accepted_names = {"vidiq_balance", "balance"}
    for tool in tools:
        name = str(tool.get("name") or "").strip().casefold()
        if name in accepted_names:
            return tool
    return None


def _tool_text(result: Any) -> str:
    if isinstance(result, dict):
        if isinstance(result.get("structuredContent"), dict):
            return json.dumps(result["structuredContent"], ensure_ascii=False)
        content = result.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and item.get("text") is not None:
                    parts.append(str(item["text"]))
            if parts:
                return "\n".join(parts)
    return json.dumps(result, ensure_ascii=False)


def extract_credit_balance(result: Any) -> int | None:
    """Extract renewable/monthly credits only.

    vidIQ's balance utility can also report add-on credits. The Opportunity
    Engine intentionally ignores add-on/top-up credits so this integration
    cannot rely on purchased credit pools.
    """

    priority_keys = (
        "renewablecredits",
        "remainingcredits",
        "creditsremaining",
        "creditbalance",
        "balance",
        "remaining",
    )

    def number(value: Any) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def walk_for_key(value: Any, target: str) -> int | None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z]", "", str(key).casefold())
                if normalized == target:
                    parsed = number(item)
                    if parsed is not None:
                        return parsed
            for item in value.values():
                found = walk_for_key(item, target)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk_for_key(item, target)
                if found is not None:
                    return found
        return None

    for key in priority_keys:
        found = walk_for_key(result, key)
        if found is not None:
            return found

    text = _tool_text(result)
    patterns = [
        r"(?i)renewable[^0-9]{0,30}(\d+(?:\.\d+)?)\s*(?:ai\s*)?credits?",
        r"(?i)(?:remaining|balance)[^0-9]{0,30}(\d+(?:\.\d+)?)\s*(?:ai\s*)?credits?",
        r"(?i)(\d+(?:\.\d+)?)\s*(?:ai\s*)?credits?\s*(?:remaining|left)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(float(match.group(1)))
    return None


def build_topic_arguments(
    tool: dict[str, Any],
    query: str,
) -> dict[str, Any]:
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        return {"query": query}

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required")
    if not isinstance(required, list):
        required = []

    args: dict[str, Any] = {}
    query_keys = (
        "query",
        "keyword",
        "topic",
        "q",
        "search_term",
        "searchTerm",
        "term",
    )
    chosen = next((key for key in query_keys if key in properties), None)
    if chosen:
        args[chosen] = query
    elif len(required) == 1:
        only = str(required[0])
        prop = properties.get(only, {})
        if isinstance(prop, dict) and prop.get("type") == "string":
            args[only] = query

    for key in ("limit", "max_results", "maxResults", "count"):
        prop = properties.get(key)
        if not isinstance(prop, dict):
            continue
        maximum = prop.get("maximum")
        desired = 6
        if isinstance(maximum, (int, float)):
            desired = min(desired, int(maximum))
        minimum = prop.get("minimum")
        if isinstance(minimum, (int, float)):
            desired = max(desired, int(minimum))
        args[key] = desired
        break

    missing = []
    for key in required:
        if key in args:
            continue
        prop = properties.get(key, {})
        if isinstance(prop, dict) and "default" in prop:
            args[key] = prop["default"]
        else:
            missing.append(str(key))
    if missing:
        raise ValueError(
            "Cannot safely construct vidIQ arguments; required fields unknown: "
            + ", ".join(missing)
        )
    return args


def result_preview(result: Any, maximum: int = 1800) -> str:
    text = _tool_text(result).strip()
    if len(text) <= maximum:
        return text
    return text[: maximum - 1] + "…"
