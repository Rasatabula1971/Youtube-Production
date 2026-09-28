"""Subprocess bridge between the YouTube project and FAIR.

Executed by FAIR's own Python environment. It never prints secrets or raw
provider errors. Input and output are temporary local JSON files controlled by
analysis_model_runner.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def safe_attempt(attempt: Any) -> dict[str, Any]:
    if hasattr(attempt, "model_dump"):
        payload = attempt.model_dump(mode="json")
    elif isinstance(attempt, dict):
        payload = dict(attempt)
    else:
        return {}

    allowed = {
        "attempt_number",
        "provider_id",
        "model_id",
        "selection_score",
        "quota_remaining",
        "disposition",
        "latency_ms",
        "error_type",
        "error_detail",
        "role",
    }
    safe = {key: value for key, value in payload.items() if key in allowed}
    quality = payload.get("quality")
    if isinstance(quality, dict):
        safe["quality"] = {
            "overall_score": quality.get("overall_score"),
            "hard_reject": quality.get("hard_reject"),
            "reject_reasons": quality.get("reject_reasons", []),
            "verification_state": quality.get("verification_state"),
            "validator_results": quality.get("validator_results", {}),
        }
    return safe


def compatibility_snapshot(fair: Any, settings: dict[str, Any]) -> dict[str, Any]:
    requested_output = int(settings.get("max_output_tokens", 4096))
    expected_schema = settings.get("expected_schema_present", False)
    routes: list[dict[str, Any]] = []
    structured_ready = False

    registry = getattr(fair, "_registry", None)
    providers = getattr(registry, "providers", {}) if registry is not None else {}
    for provider in providers.values() if isinstance(providers, dict) else []:
        for model in getattr(provider, "models", []) or []:
            capabilities = set(getattr(model, "capabilities", set()) or set())
            max_output = getattr(model, "max_output_tokens", None)
            output_ok = max_output is None or requested_output <= int(max_output)
            structured_ok = (not expected_schema) or (
                "structured_output" in capabilities
            )
            active = bool(getattr(model, "active", True))
            eligible = active and output_ok and structured_ok
            structured_ready = structured_ready or eligible
            routes.append(
                {
                    "provider_id": str(getattr(provider, "provider_id", "")),
                    "model_id": str(getattr(model, "model_id", "")),
                    "active": active,
                    "structured_output": "structured_output" in capabilities,
                    "max_output_tokens": max_output,
                    "compatible": eligible,
                }
            )
    return {
        "requested_output_tokens": requested_output,
        "expected_schema": bool(expected_schema),
        "compatible_route_available": structured_ready,
        "routes": routes,
    }


async def execute(payload: dict[str, Any]) -> dict[str, Any]:
    fair_repo = Path(str(payload["fair_repo_path"])).resolve()
    if not fair_repo.exists():
        return {
            "status": "BRIDGE_ERROR",
            "error_type": "FairRepositoryNotFound",
            "paid_inference_executed": False,
        }

    sys.path.insert(0, str(fair_repo))

    try:
        from fair import FAIR
    except Exception as exc:  # noqa: BLE001 - boundary converts failure to structured status
        return {
            "status": "BRIDGE_ERROR",
            "error_type": type(exc).__name__,
            "paid_inference_executed": False,
        }

    settings = payload.get("settings", {})
    env_file = str(payload.get("env_file") or "")
    confirmed = set(payload.get("confirmed_free_providers", []))

    try:
        fair = FAIR(
            env_file=env_file or None,
            confirmed_free_providers=confirmed,
            quality_level=str(settings.get("quality_level", "standard")),
            max_attempts=int(settings.get("max_attempts", 3)),
            max_unanswered_attempts=int(settings.get("max_unanswered_attempts", 6)),
            max_verification_attempts=int(settings.get("max_verification_attempts", 1)),
            timeout_seconds=float(settings.get("timeout_seconds", 45)),
            cross_check_required=bool(settings.get("cross_check_required", False)),
            application_id=str(settings.get("application_id", "youtube-production")),
        )
    except Exception as exc:  # noqa: BLE001 - boundary converts failure to structured status
        return {
            "status": "BRIDGE_ERROR",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:1200],
            "paid_inference_executed": False,
        }

    providers = fair.providers()
    skipped = dict(fair.skipped)
    compatibility = compatibility_snapshot(fair, settings)

    if payload.get("action") == "doctor":
        try:
            await fair.close()
        except Exception as exc:  # noqa: BLE001 - boundary converts failure to structured status
            return {
                "status": "DOCTOR_CLOSE_FAILED",
                "error_type": type(exc).__name__,
                "providers": providers,
                "skipped": skipped,
                "paid_inference_executed": False,
            }
        return {
            "status": (
                "READY"
                if compatibility.get("compatible_route_available")
                else "NO_COMPATIBLE_ROUTE"
            ),
            "providers": providers,
            "skipped": skipped,
            "compatibility": compatibility,
            "paid_inference_executed": False,
        }

    solve_dispatched = False
    try:
        solve_dispatched = True
        result = await fair.solve(
            str(payload.get("prompt") or ""),
            task_type=str(settings.get("task_type", "youtube_structured_pipeline")),
            expected_schema=payload.get("expected_schema"),
            quality_level=str(settings.get("quality_level", "standard")),
            cross_check_required=bool(settings.get("cross_check_required", False)),
            max_output_tokens=int(settings.get("max_output_tokens", 4096)),
            client_id=str(
                settings.get(
                    "client_id",
                    "youtube-experiment-02-analysis",
                )
            ),
            priority=str(settings.get("priority", "P2")),
            cache_mode=str(settings.get("cache_mode", "bypass")),
        )

        return {
            "status": result.status,
            "reason_code": result.reason_code,
            "request_id": result.request_id,
            "output": result.output,
            "provider_id": result.provider_id,
            "model_id": result.model_id,
            "best_quality_score": result.best_quality_score,
            "verification_state": result.verification_state,
            "paid_inference_executed": result.paid_inference_executed,
            "attempts": [safe_attempt(attempt) for attempt in result.attempts],
            "providers": providers,
            "skipped": skipped,
            "compatibility": compatibility,
        }
    except Exception as exc:  # noqa: BLE001 - boundary converts failure to structured status
        return {
            "status": "BRIDGE_ERROR",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:1200],
            "providers": providers,
            "skipped": skipped,
            "compatibility": compatibility,
            "paid_inference_executed": (None if solve_dispatched else False),
            "cost_state": (
                "UNKNOWN_AFTER_DISPATCH"
                if solve_dispatched
                else "NO_INFERENCE_DISPATCHED"
            ),
        }
    finally:
        try:
            await fair.close()
        except Exception:  # noqa: BLE001,S110 - cleanup must not mask the FAIR result
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = load_json(args.input)
        result = asyncio.run(execute(payload))
    except Exception as exc:  # noqa: BLE001 - boundary converts failure to structured status
        result = {
            "status": "BRIDGE_ERROR",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:1200],
            "paid_inference_executed": False,
        }

    write_json(args.output, result)


if __name__ == "__main__":
    main()
