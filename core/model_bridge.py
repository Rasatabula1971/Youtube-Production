"""Shared model bridge (D-175): FAIR subprocess calls, the free-only cost
check and the direct Gemini backup. Moved without change from
experiment_02_analysis/analysis_model_runner.py.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from core.jsonio import load_json_or_exit as load_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The bridge's config file and the FAIR bridge script stay where they were.
EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
RUNNER_CONFIG_FILE = EXP2_DIR / "analysis_model_runner_config.json"
FAIR_BRIDGE_FILE = EXP2_DIR / "fair_bridge.py"
DEFAULT_FAIR_REPO = PROJECT_ROOT.parent / "FAIR Free AI Router"
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"
DIRECT_GEMINI_BILLING_FILE = EXP2_DIR / "direct_gemini_billing.json"
DIRECT_GEMINI_KEY_ENV = "DIRECT_GEMINI_API_KEY"
DIRECT_GEMINI_MODEL_ENV = "DIRECT_GEMINI_MODEL"
DIRECT_GEMINI_MODELS_ENV = "DIRECT_GEMINI_MODELS"
DEFAULT_DIRECT_GEMINI_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
)
DIRECT_GEMINI_FAIR_FALLBACK_REASONS = {
    "ALL_FREE_MODELS_UNAVAILABLE",
}
DIRECT_GEMINI_REFUSED_REASONS = {
    "ALL_FREE_MODELS_FAILED_QUALITY": (
        "Free models answered but their output failed quality checks. Repair the "
        "prompt, schema or request and rerun on the free route; a paid fallback "
        "would hide the defect."
    ),
    "QUALITY_VERIFICATION_UNAVAILABLE": (
        "Quality verification was unavailable. Retry when the verifier is back; "
        "a paid fallback would skip verification rather than replace capacity."
    ),
    "INDEPENDENT_VERIFIER_UNAVAILABLE": (
        "The independent verifier was unavailable. Retry when it is back; a paid "
        "fallback would skip verification rather than replace capacity."
    ),
    "NO_ELIGIBLE_FREE_MODELS": (
        "No free route fits this request (schema, size or output floor), which "
        "is not proven provider exhaustion. Repair the request or the route "
        "configuration (run FAIR Doctor)."
    ),
}
DIRECT_GEMINI_BILLING_UNCONFIRMED = "DIRECT_GEMINI_BILLING_UNCONFIRMED"
DIRECT_GEMINI_NOT_CONFIGURED = "DIRECT_GEMINI_NOT_CONFIGURED"


def load_runner_config() -> dict[str, Any]:
    config = load_json(RUNNER_CONFIG_FILE)
    required = {"adapter", "fair", "runner"}
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Analysis model runner config is missing: " + ", ".join(missing)
        )
    if config["adapter"] != "fair_subprocess":
        raise SystemExit(
            f"Unsupported model adapter {config['adapter']!r}; "
            "currently supported: fair_subprocess"
        )
    return config


def read_env_file(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if path is None or not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def resolve_fair_paths(config: dict[str, Any]) -> dict[str, Path]:
    fair_config = config["fair"]

    repo_value = os.getenv("FAIR_REPO_PATH")
    fair_repo = Path(repo_value).expanduser() if repo_value else DEFAULT_FAIR_REPO
    fair_repo = fair_repo.resolve()

    env_value = os.getenv("FAIR_ENV_FILE")
    fair_env = (
        Path(env_value).expanduser().resolve()
        if env_value
        else (fair_repo / ".env").resolve()
    )

    python_value = os.getenv("FAIR_PYTHON")
    if python_value:
        fair_python = Path(python_value).expanduser().resolve()
    else:
        windows_python = fair_repo / ".venv" / "Scripts" / "python.exe"
        posix_python = fair_repo / ".venv" / "bin" / "python"
        if windows_python.exists():
            fair_python = windows_python.resolve()
        elif posix_python.exists():
            fair_python = posix_python.resolve()
        else:
            fallback = fair_config.get("python")
            fair_python = (
                Path(str(fallback)).expanduser().resolve()
                if fallback
                else Path(sys.executable).resolve()
            )

    return {
        "repo": fair_repo,
        "env_file": fair_env,
        "python": fair_python,
    }


def confirmed_free_providers(
    config: dict[str, Any],
    fair_env_file: Path | None,
) -> list[str]:
    confirmed = {
        str(value).strip()
        for value in config["fair"].get("confirmed_free_providers", [])
        if str(value).strip()
    }

    env_values = read_env_file(fair_env_file)
    raw = os.getenv(
        "FAIR_CONFIRMED_FREE_PROVIDERS",
        env_values.get("FAIR_CONFIRMED_FREE_PROVIDERS", ""),
    )
    confirmed.update(item.strip() for item in raw.split(",") if item.strip())
    return sorted(confirmed)


def parse_model_json(output: str) -> dict[str, Any]:
    text = output.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        lines = text.splitlines()
        if lines and lines[0].startswith(fence):
            lines = lines[1:]
        if lines and lines[-1].strip() == fence:
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Model output JSON must be an object")
    return payload


def safe_attempts(bridge_result: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_keys = {
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
        "prompt_token_count",
        "candidate_token_count",
        "total_token_count",
        "response_mode",
        # The bridge already reduces FAIR's quality report to overall_score,
        # hard_reject, reject_reasons, verification_state and validator_results.
        # Dropping it here is what left a model run saying only "QUALITY_FAILURE,
        # score 0.0" with no record of whether the JSON broke the schema, arrived
        # truncated or came back empty -- the one thing needed to act on it.
        "quality",
    }
    return [
        {key: value for key, value in attempt.items() if key in allowed_keys}
        for attempt in bridge_result.get("attempts", [])
        if isinstance(attempt, dict)
    ]


def bridge_payload(
    *,
    action: str,
    prompt: str | None,
    schema: dict[str, Any] | None,
    config: dict[str, Any],
    paths: dict[str, Path],
) -> dict[str, Any]:
    fair_config = config["fair"]
    payload: dict[str, Any] = {
        "action": action,
        "fair_repo_path": str(paths["repo"]),
        "env_file": str(paths["env_file"]),
        "confirmed_free_providers": confirmed_free_providers(
            config,
            paths["env_file"],
        ),
        "settings": {
            "quality_level": fair_config.get("quality_level", "standard"),
            "task_type": str(
                fair_config.get("task_type", "youtube_structured_pipeline")
            ),
            "max_attempts": int(fair_config.get("max_attempts", 3)),
            "max_unanswered_attempts": int(
                fair_config.get("max_unanswered_attempts", 6)
            ),
            "max_verification_attempts": int(
                fair_config.get("max_verification_attempts", 1)
            ),
            "timeout_seconds": float(fair_config.get("timeout_seconds", 45)),
            "cross_check_required": bool(
                fair_config.get("cross_check_required", False)
            ),
            "max_output_tokens": int(fair_config.get("max_output_tokens", 4096)),
            # The least an answer can be complete within. FAIR admits a route on
            # this and asks it for min(max_output_tokens, its own ceiling), so
            # raising max_output_tokens buys headroom without dropping the routes
            # whose ceiling is lower. Omitted, FAIR treats the whole budget as the
            # floor and those routes go unused.
            "min_output_tokens": (
                int(fair_config["min_output_tokens"])
                if fair_config.get("min_output_tokens") is not None
                else None
            ),
            "expected_schema_present": bool(schema is not None or action == "doctor"),
            "application_id": str(
                fair_config.get("application_id", "youtube-production")
            ),
            "cache_mode": str(fair_config.get("cache_mode", "bypass")),
            "priority": str(fair_config.get("priority", "P2")),
            "client_id": str(
                fair_config.get("client_id", "youtube-experiment-02-analysis")
            ),
        },
    }
    if action == "solve":
        payload["prompt"] = prompt
        payload["expected_schema"] = schema
    return payload


def direct_gemini_settings() -> dict[str, Any]:
    project_env = read_env_file(PROJECT_ENV_FILE)
    api_key = os.getenv(
        DIRECT_GEMINI_KEY_ENV,
        project_env.get(DIRECT_GEMINI_KEY_ENV, ""),
    ).strip()

    raw_models = os.getenv(
        DIRECT_GEMINI_MODELS_ENV,
        project_env.get(DIRECT_GEMINI_MODELS_ENV, ""),
    ).strip()
    if raw_models:
        candidates = [item.strip() for item in raw_models.split(",") if item.strip()]
    else:
        legacy_model = os.getenv(
            DIRECT_GEMINI_MODEL_ENV,
            project_env.get(DIRECT_GEMINI_MODEL_ENV, ""),
        ).strip()
        candidates = [DEFAULT_DIRECT_GEMINI_MODELS[0]]
        candidates.append(legacy_model or DEFAULT_DIRECT_GEMINI_MODELS[1])

    models: list[str] = []
    for model in candidates:
        if model not in models:
            models.append(model)

    return {
        "api_key": api_key,
        "models": models,
    }


def direct_gemini_billing_status() -> dict[str, Any]:
    """The operator's attestation that the key's project has no billing (D-161).

    Free-tier is a property of the Google Cloud project, not of this code, so
    it is a dated, explicit statement in a config file; until it is true no
    direct Gemini call is made.
    """
    try:
        payload = json.loads(DIRECT_GEMINI_BILLING_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    confirmed = payload.get("billing_disabled_confirmed") is True
    return {
        "confirmed": confirmed,
        "confirmed_on": payload.get("confirmed_on"),
        "file": str(DIRECT_GEMINI_BILLING_FILE),
        "problem": (
            ""
            if confirmed
            else "Direct Gemini is off until you confirm the key's Google Cloud project has no "
            f"billing account: set billing_disabled_confirmed to true in {DIRECT_GEMINI_BILLING_FILE.name}."
        ),
    }


def direct_gemini_billing_confirmed() -> bool:
    return bool(direct_gemini_billing_status()["confirmed"])


def direct_gemini_unavailable_reason() -> str | None:
    """Why the direct route cannot run now, or None when it can."""
    settings = direct_gemini_settings()
    if not (settings["api_key"] and settings["models"]):
        return DIRECT_GEMINI_NOT_CONFIGURED
    if not direct_gemini_billing_confirmed():
        return DIRECT_GEMINI_BILLING_UNCONFIRMED
    return None


def direct_gemini_available() -> bool:
    return direct_gemini_unavailable_reason() is None


def direct_gemini_fallback_decision(result: dict[str, Any]) -> dict[str, Any]:
    """Whether a FAIR result may fall back to direct Gemini, and why (D-129).

    The only shared gate: allowed only when FAIR escalated because the free
    pool was exhausted and nothing paid has run yet.
    """
    reason = str(result.get("reason_code") or "")
    if result.get("status") != "ESCALATION_REQUIRED":
        return {"eligible": False, "reason_code": reason, "explanation": "FAIR did not escalate."}
    if result.get("paid_inference_executed") is not False:
        return {
            "eligible": False,
            "reason_code": reason,
            "explanation": "Paid inference state is unknown or already used; no fallback.",
        }
    if reason in DIRECT_GEMINI_FAIR_FALLBACK_REASONS:
        return {
            "eligible": True,
            "reason_code": reason,
            "explanation": "Free-model capacity is exhausted; direct Gemini may replace it.",
        }
    return {
        "eligible": False,
        "reason_code": reason,
        "explanation": DIRECT_GEMINI_REFUSED_REASONS.get(
            reason, "Unrecognised escalation reason; no paid fallback without proof of exhaustion."
        ),
    }


def inference_cost_authorized(result: dict[str, Any]) -> bool:
    if (
        result.get("direct_backup_used") is True
        and result.get("billing_authorization") == "USER_APPROVED_DIRECT_GEMINI_BACKUP"
        and result.get("direct_backup_free_tier_only") is True
    ):
        return True
    return result.get("paid_inference_executed") is False


def gemini_compatible_schema(value: Any) -> Any:
    """Convert project JSON Schema to Gemini's supported structured-output subset."""
    if isinstance(value, list):
        return [gemini_compatible_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    allowed = {
        "$id",
        "$defs",
        "$ref",
        "$anchor",
        "type",
        "format",
        "title",
        "description",
        "enum",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "anyOf",
        "oneOf",
        "properties",
        "additionalProperties",
        "required",
        "propertyOrdering",
    }
    output: dict[str, Any] = {}
    if "const" in value and "enum" not in value:
        const_value = value["const"]
        # Gemini documents enum support for strings and numbers, not booleans.
        # Preserve boolean const shape as a boolean type and let the project's
        # deterministic validator enforce the exact True/False value afterward.
        if isinstance(const_value, bool):
            output["type"] = "boolean"
        elif isinstance(const_value, str):
            output["type"] = "string"
            output["enum"] = [const_value]
        elif isinstance(const_value, int):
            output["type"] = "integer"
            output["enum"] = [const_value]
        elif isinstance(const_value, float):
            output["type"] = "number"
            output["enum"] = [const_value]
        elif const_value is None:
            output["type"] = "null"

    for key, item in value.items():
        if key == "const" or key not in allowed:
            continue
        if key == "properties" and isinstance(item, dict):
            output[key] = {
                str(name): gemini_compatible_schema(schema)
                for name, schema in item.items()
            }
        else:
            output[key] = gemini_compatible_schema(item)
    return output


def _gemini_error_detail(exc: urllib.error.HTTPError, api_key: str) -> str:
    detail = f"HTTP_{exc.code}"
    try:
        raw_error = exc.read(4096).decode("utf-8", errors="replace")
    except (OSError, ValueError):
        raw_error = ""
    if api_key and raw_error:
        raw_error = raw_error.replace(api_key, "[REDACTED]")
    if raw_error:
        try:
            parsed_error = json.loads(raw_error)
            error = parsed_error.get("error", {})
            if isinstance(error, dict):
                status = str(error.get("status") or "").strip()
                message = " ".join(str(error.get("message") or "").split())
                parts = [part for part in (status, message) if part]
                if parts:
                    detail += ": " + ": ".join(parts)
            else:
                compact = " ".join(raw_error.split())
                if compact:
                    detail += ": " + compact
        except json.JSONDecodeError:
            compact = " ".join(raw_error.split())
            if compact:
                detail += ": " + compact
    return detail[:1000]


def _gemini_attempt(
    *,
    fair_attempt_count: int,
    prior_direct_attempts: int,
    model: str,
) -> dict[str, Any]:
    return {
        "attempt_number": fair_attempt_count + prior_direct_attempts + 1,
        "provider_id": "direct_gemini_backup",
        "model_id": model,
        "selection_score": None,
        "quota_remaining": None,
        "disposition": "INFRA_FAILURE",
        "latency_ms": None,
        "error_type": None,
        "error_detail": None,
        "role": "BACKUP",
        "prompt_token_count": None,
        "candidate_token_count": None,
        "total_token_count": None,
        "response_mode": None,
    }


def _gemini_endpoint(model: str) -> str:
    """The generateContent URL for a configured model, checked to stay on
    Google's fixed Gemini HTTPS host."""
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", model):
        raise ValueError("DIRECT_GEMINI model contains unsupported characters")
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent"
    )
    parsed_endpoint = urllib.parse.urlparse(endpoint)
    if (
        parsed_endpoint.scheme != "https"
        or parsed_endpoint.hostname != "generativelanguage.googleapis.com"
    ):
        raise ValueError("Direct Gemini endpoint failed host validation")
    return endpoint


def call_direct_gemini_image(
    prompt: str,
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """One free-tier Gemini request with a single image attached (D-179).

    Same key, model list, host check and billing attestation (D-161) as the
    text route: until the operator has attested that the key's project cannot
    bill, no request is made. The answer is the model's JSON text; the caller
    validates it. A model that is out of quota or unavailable (404, 429, 5xx)
    hands over to the next configured model.
    """
    reason = direct_gemini_unavailable_reason()
    if reason is not None:
        return {
            "status": "UNAVAILABLE",
            "reason_code": reason,
            "message": (
                direct_gemini_billing_status()["problem"]
                if reason == DIRECT_GEMINI_BILLING_UNCONFIRMED
                else f"Set {DIRECT_GEMINI_KEY_ENV} in .env to use the free Gemini API."
            ),
            "paid_inference_executed": False,
            "attempts": [],
        }
    settings = direct_gemini_settings()
    api_key = str(settings["api_key"])
    encoded = base64.b64encode(image_bytes).decode("ascii")
    attempts: list[dict[str, Any]] = []
    for model in list(settings["models"]):
        endpoint = _gemini_endpoint(model)
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": encoded}},
                    ],
                }
            ],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        attempt: dict[str, Any] = {"model_id": model, "error_detail": None}
        try:
            # _gemini_endpoint keeps this on Google's fixed Gemini HTTPS host.
            with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                request,
                timeout=min(max(timeout_seconds, 5.0), 180.0),
            ) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            candidates = parsed.get("candidates") if isinstance(parsed, dict) else None
            if not isinstance(candidates, list) or not candidates:
                raise ValueError("Gemini returned no candidates")
            parts = (candidates[0].get("content") or {}).get("parts") or []
            output = "".join(
                str(part.get("text") or "") for part in parts if isinstance(part, dict)
            ).strip()
            if not output:
                raise ValueError("Gemini returned an empty response")
            attempts.append({**attempt, "disposition": "ACCEPTED"})
            return {
                "status": "ACCEPTED",
                "output": output,
                "model_id": model,
                # The operator attested the project has no billing (D-161).
                "paid_inference_executed": False,
                "billing_disabled_confirmed_on": direct_gemini_billing_status()["confirmed_on"],
                "attempts": attempts,
            }
        except urllib.error.HTTPError as exc:
            attempts.append({**attempt, "disposition": "HTTP_ERROR", "error_detail": _gemini_error_detail(exc, api_key)})
            if exc.code in {404, 429, 500, 502, 503, 504}:
                continue
            break
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            attempts.append({**attempt, "disposition": type(exc).__name__, "error_detail": str(exc)[:300]})
            continue
    return {
        "status": "FAILED",
        "reason_code": "DIRECT_GEMINI_IMAGE_FAILED",
        "message": (attempts[-1]["error_detail"] if attempts else "No Gemini model configured."),
        "paid_inference_executed": False,
        "attempts": attempts,
    }


def call_direct_gemini_backup(
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    fair_result: dict[str, Any],
) -> dict[str, Any]:
    settings = direct_gemini_settings()
    api_key = str(settings["api_key"])
    models = list(settings["models"])
    if not api_key or not models:
        return fair_result
    if not direct_gemini_billing_confirmed():
        # No call at all until the operator has attested that the key's
        # project cannot bill (D-161): unknown cost is not zero cost.
        return {
            **fair_result,
            "status": "ESCALATION_REQUIRED",
            "reason_code": DIRECT_GEMINI_BILLING_UNCONFIRMED,
            "paid_inference_executed": False,
            "direct_backup_attempted": False,
            "direct_backup_used": False,
            "direct_backup_refused": direct_gemini_billing_status()["problem"],
        }

    prompt = str(payload.get("prompt") or "")
    schema = payload.get("expected_schema")
    if not prompt or not isinstance(schema, dict):
        return fair_result

    base_attempts = list(fair_result.get("attempts", []))
    direct_attempts: list[dict[str, Any]] = []

    def accepted_result(
        *,
        model: str,
        output: str,
        parsed: dict[str, Any],
        attempt: dict[str, Any],
        response_mode: str,
    ) -> dict[str, Any]:
        usage = parsed.get("usageMetadata", {})
        if isinstance(usage, dict):
            attempt["prompt_token_count"] = usage.get("promptTokenCount")
            attempt["candidate_token_count"] = usage.get("candidatesTokenCount")
            attempt["total_token_count"] = usage.get("totalTokenCount")
        attempt["disposition"] = "ACCEPTED"
        direct_attempts.append(attempt)

        fair_summary = {
            "status": fair_result.get("status"),
            "reason_code": fair_result.get("reason_code"),
            "provider_id": fair_result.get("provider_id"),
            "model_id": fair_result.get("model_id"),
            "paid_inference_executed": fair_result.get(
                "paid_inference_executed"
            ),
        }
        return {
            "status": "ACCEPTED",
            "reason_code": "DIRECT_GEMINI_BACKUP",
            "request_id": "direct-gemini-" + uuid.uuid4().hex,
            "output": output,
            "provider_id": "direct_gemini_backup",
            "model_id": model,
            "best_quality_score": None,
            "verification_state": (
                "STRUCTURE_REQUESTED"
                if response_mode == "STRUCTURED_SCHEMA"
                else "JSON_MODE_DETERMINISTIC_VALIDATION_REQUIRED"
            ),
            # The operator attested the project has no billing (D-161), so
            # this call cannot have been paid for.
            "paid_inference_executed": False,
            "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
            "billing_disabled_confirmed_on": direct_gemini_billing_status()["confirmed_on"],
            "direct_backup_attempted": True,
            "direct_backup_used": True,
            "direct_backup_free_tier_only": True,
            "direct_backup_may_bill": False,
            "direct_backup_response_mode": response_mode,
            "fair_primary_result": fair_summary,
            "direct_backup_usage": {
                "prompt_token_count": attempt["prompt_token_count"],
                "candidate_token_count": attempt["candidate_token_count"],
                "total_token_count": attempt["total_token_count"],
            },
            "attempts": [*base_attempts, *direct_attempts],
        }

    for model in models:
        endpoint = _gemini_endpoint(model)

        for response_mode in ("STRUCTURED_SCHEMA", "JSON_ONLY"):
            generation_config: dict[str, Any] = {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            }
            request_prompt = prompt
            if response_mode == "STRUCTURED_SCHEMA":
                generation_config["responseJsonSchema"] = gemini_compatible_schema(
                    schema
                )
            else:
                # When Gemini rejects a deep structured-output schema, JSON-only
                # mode must still receive the exact contract. Otherwise the model
                # knows only that JSON is required, not the nested object shape.
                request_prompt = (
                    prompt
                    + "\n\nEXPECTED JSON SCHEMA (follow this exact structure):\n"
                    + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
                    + "\nReturn only one JSON object matching this schema."
                )

            body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": request_prompt}],
                    }
                ],
                "generationConfig": generation_config,
            }
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                method="POST",
            )
            attempt = _gemini_attempt(
                fair_attempt_count=len(base_attempts),
                prior_direct_attempts=len(direct_attempts),
                model=model,
            )
            attempt["response_mode"] = response_mode

            try:
                # Endpoint is validated to Google's fixed Gemini HTTPS host above.
                with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                    request,
                    timeout=min(max(timeout_seconds, 5.0), 180.0),
                ) as response:
                    raw_response = response.read().decode("utf-8")
                parsed = json.loads(raw_response)
                candidates = parsed.get("candidates")
                if not isinstance(candidates, list) or not candidates:
                    raise ValueError("Gemini returned no candidates")
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                text_parts = [
                    str(part.get("text") or "")
                    for part in parts
                    if isinstance(part, dict) and part.get("text")
                ]
                output = "".join(text_parts).strip()
                if not output:
                    raise ValueError("Gemini returned an empty JSON response")
                return accepted_result(
                    model=model,
                    output=output,
                    parsed=parsed,
                    attempt=attempt,
                    response_mode=response_mode,
                )
            except urllib.error.HTTPError as exc:
                attempt["error_type"] = "HTTP_ERROR"
                attempt["error_detail"] = _gemini_error_detail(exc, api_key)
                direct_attempts.append(attempt)

                if response_mode == "STRUCTURED_SCHEMA" and exc.code == 400:
                    # Gemini documents that large/deep structured-output schemas
                    # may be rejected as INVALID_ARGUMENT. Retry the same model
                    # in JSON-only mode and let the stage's deterministic
                    # validator enforce the full contract.
                    continue

                if exc.code in {404, 429, 500, 502, 503, 504}:
                    # Model-specific quota/capacity/unavailability: try the next
                    # configured free-tier model.
                    break

                return {
                    **fair_result,
                    "reason_code": "FAIR_AND_DIRECT_GEMINI_FAILED",
                    "direct_backup_attempted": True,
                    "direct_backup_used": False,
                    "direct_backup_free_tier_only": True,
                    "direct_backup_may_bill": False,
                    "direct_backup_models": models,
                    "attempts": [*base_attempts, *direct_attempts],
                }
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                json.JSONDecodeError,
                ValueError,
            ) as exc:
                attempt["error_type"] = type(exc).__name__
                attempt["error_detail"] = str(exc)[:300]
                direct_attempts.append(attempt)
                # Transport/capacity behavior can differ across free models.
                break
        else:
            continue

    return {
        **fair_result,
        "reason_code": "FAIR_AND_DIRECT_GEMINI_FAILED",
        "direct_backup_attempted": True,
        "direct_backup_used": False,
        "direct_backup_free_tier_only": True,
        "direct_backup_may_bill": False,
        "direct_backup_models": models,
        "attempts": [*base_attempts, *direct_attempts],
    }


def call_fair_bridge(
    payload: dict[str, Any],
    *,
    python_executable: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    if not python_executable.exists():
        raise FileNotFoundError(
            f"FAIR Python executable not found: {python_executable}"
        )
    if not FAIR_BRIDGE_FILE.exists():
        raise FileNotFoundError(f"FAIR bridge not found: {FAIR_BRIDGE_FILE}")

    with tempfile.TemporaryDirectory(prefix="exp02_fair_") as temp_dir:
        root = Path(temp_dir)
        input_path = root / "input.json"
        output_path = root / "output.json"
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        try:
            completed = subprocess.run(
                [
                    str(python_executable),
                    str(FAIR_BRIDGE_FILE),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"FAIR bridge exceeded {timeout_seconds:.0f}s timeout"
            ) from exc

        if not output_path.exists():
            raise RuntimeError(
                f"FAIR bridge exited with code {completed.returncode} "
                "without producing a result"
            )

        result = load_json(output_path)
        if not isinstance(result, dict):
            raise RuntimeError("FAIR bridge result must be a JSON object")
        decision = direct_gemini_fallback_decision(result)
        if decision["eligible"] and direct_gemini_available():
            return call_direct_gemini_backup(
                payload,
                timeout_seconds=timeout_seconds,
                fair_result=result,
            )
        if result.get("status") == "ESCALATION_REQUIRED":
            # Record why no paid fallback ran, for the run report and the UI.
            result = {**result, "direct_gemini_fallback": decision}
        return result
