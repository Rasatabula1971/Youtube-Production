"""One corrected attempt when a packaging answer fails validation (D-186).

The packaging validators catch real slips: a number no claim states, a
refused word, a duplicated angle. Each slip stopped the automatic run and the
owner pressed Continue again for a fresh answer that might slip elsewhere.
Instead, the model is asked once more in the same run with the validator's
exact error and its previous answer. The corrected answer passes through the
same validator and the same cost policy as the first; nothing is relaxed.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from core.model_bridge import inference_cost_authorized, parse_model_json, safe_attempts

PREVIOUS_ANSWER_LIMIT = 20000


def repair_prompt(prompt: str, raw: str, error: str) -> str:
    return (
        prompt
        + "\n\nYOUR PREVIOUS ANSWER WAS REJECTED by the validator:\n"
        + error
        + "\nReturn the complete corrected JSON answer. Change only what the error "
        "requires and keep everything else as it was.\nPREVIOUS ANSWER:\n"
        + raw[:PREVIOUS_ANSWER_LIMIT]
    )


def attempt_repair(
    *,
    payload: dict[str, Any],
    raw: str,
    error: str,
    call: Callable[[dict[str, Any]], dict[str, Any]],
    check: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Ask once more with the validator's error; return what happened.

    ``status`` is REPAIRED (with ``parsed`` and the new ``bridge_result``),
    or the reason the corrected attempt did not pass.
    """
    repaired = copy.deepcopy(payload)
    repaired["prompt"] = repair_prompt(str(payload.get("prompt") or ""), raw, error)
    try:
        result = call(repaired)
    except Exception as exc:
        return {"status": "REPAIR_RUNNER_ERROR", "error": f"{type(exc).__name__}: {exc}", "raw": "", "bridge_result": {}}
    if not inference_cost_authorized(result):
        return {"status": "COST_POLICY_VIOLATION", "error": "corrected attempt broke the cost policy", "raw": "", "bridge_result": result}
    if result.get("status") != "ACCEPTED":
        return {
            "status": "REPAIR_MODEL_FAILED",
            "error": str(result.get("reason_code") or result.get("status") or "not accepted"),
            "raw": "",
            "bridge_result": result,
        }
    raw_answer = str(result.get("output") or "")
    try:
        parsed = parse_model_json(raw_answer)
        check(parsed)
    except Exception as exc:
        return {"status": "REPAIR_VALIDATION_ERROR", "error": str(exc), "raw": raw_answer, "bridge_result": result}
    return {"status": "REPAIRED", "parsed": parsed, "raw": raw_answer, "bridge_result": result}


def repair_report(repair: dict[str, Any]) -> dict[str, Any]:
    return {
        "validation_repair_attempted": True,
        "validation_repair_status": repair["status"],
        "validation_repair_error": repair.get("error"),
        "validation_repair_attempts": safe_attempts(repair.get("bridge_result") or {}),
    }


def failure_status(repair: dict[str, Any]) -> str:
    return "COST_POLICY_VIOLATION" if repair["status"] == "COST_POLICY_VIOLATION" else "MODEL_OUTPUT_VALIDATION_ERROR"
