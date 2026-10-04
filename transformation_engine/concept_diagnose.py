"""See exactly why a concept mechanism fails on a free model (diagnostic only).

FAIR reports a provider's refusal as PROVIDER_REJECTED_GENERATED_SCHEMA and
keeps neither the generated text nor the provider's reason. This sends the
same prompt and provider schema the runner sends, straight to Groq's
OpenAI-compatible endpoint, and saves everything that comes back:

- the HTTP status, error code and message;
- Groq's ``failed_generation`` (the text it refused), or the answer;
- finish reason and token usage (a cut-off answer shows as ``length``);
- whether the text parses as JSON, and the app's own per-concept
  validation errors when it does.

It writes nothing the pipeline reads; the report goes to
``output/concept_diagnostics/``. It uses the Groq key from the environment or
from FAIR's .env (GROQ_API_KEY), never prints it, and calls only the free
Groq endpoint.

    python transformation_engine/concept_diagnose.py --mechanism specificity
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import concept_model_runner as runner
from transformation_engine import OUTPUT_DIR, REQUESTS_DIR, load_config, safe_slug, validate_response

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DIAGNOSTICS_DIR = OUTPUT_DIR / "concept_diagnostics"


def groq_key() -> str:
    value = os.getenv("GROQ_API_KEY", "").strip()
    if value:
        return value
    try:
        env_file = runner.resolve_fair_paths(runner.load_runner_config())["env_file"]
        lines = Path(env_file).read_text(encoding="utf-8").splitlines()
    except (OSError, KeyError, SystemExit):
        return ""
    for line in lines:
        key, _, raw = line.partition("=")
        if key.strip() == "GROQ_API_KEY":
            return raw.strip().strip('"').strip("'")
    return ""


def post(body: dict[str, Any], key: str, timeout: float) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(  # noqa: S310 - fixed https Groq endpoint
        GROQ_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        # Groq sits behind Cloudflare, which answers 403 to urllib's default
        # "Python-urllib" user agent before the request reaches Groq.
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "youtube-production-concept-diagnose/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https Groq endpoint
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:4000]}


def local_check(text: str, request: dict[str, Any]) -> dict[str, Any]:
    """Does the text parse, and what does the app's validator say about it?"""
    out: dict[str, Any] = {"chars": len(text), "tail": text[-300:]}
    try:
        response = runner.parse_model_json(text)
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        out["parses"] = False
        out["parse_error"] = f"{type(exc).__name__}: {exc}"[:500]
        return out
    out["parses"] = True
    concepts = response.get("concepts") if isinstance(response, dict) else None
    out["concepts_returned"] = len(concepts) if isinstance(concepts, list) else None
    if isinstance(concepts, list) and concepts and isinstance(concepts[0], dict):
        expected = set(runner.response_schema(request)["properties"]["concepts"]["items"]["required"])
        out["unexpected_fields"] = sorted(set(concepts[0]) - expected)
        out["missing_fields"] = sorted(expected - set(concepts[0]))
    try:
        validation = validate_response(response, request, load_config())
        out["accepted"] = len(validation["accepted"])
        out["rejected"] = [{"index": r.get("index"), "errors": r.get("errors")} for r in validation["rejected"]]
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        out["validation_error"] = f"{type(exc).__name__}: {exc}"[:500]
    return out


def diagnose(mechanism: str, model: str, max_tokens: int, timeout: float, strict: bool = False) -> dict[str, Any]:
    request_path = REQUESTS_DIR / f"{safe_slug(mechanism)}.concept_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    config = runner.load_runner_config()
    prompt = runner.build_prompt(request, maximum_chars=int(config["runner"].get("max_prompt_chars", 95000)))
    schema = runner.provider_schema(runner.response_schema(request))
    key = groq_key()
    if not key:
        raise SystemExit("No GROQ_API_KEY in the environment or in FAIR's .env")

    json_schema: dict[str, Any] = {"name": "concepts", "schema": schema}
    if strict:
        # Constrained decoding: the model cannot leave the schema while writing.
        json_schema["strict"] = True
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "response_format": {"type": "json_schema", "json_schema": json_schema},
    }
    started = time.monotonic()
    status, payload = post(body, key, timeout)
    report: dict[str, Any] = {
        "mechanism_id": mechanism, "model": model, "strict": strict, "http_status": status,
        "seconds": round(time.monotonic() - started, 1),
        "prompt_chars": len(prompt), "schema_chars": len(json.dumps(schema, separators=(",", ":"))),
        "concept_count_requested": request.get("concept_count_requested"),
        "max_completion_tokens": max_tokens,
    }
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        report["error_code"] = error.get("code")
        report["error_type"] = error.get("type")
        report["error_message"] = str(error.get("message") or "")[:2000]
        failed = str(error.get("failed_generation") or "")
        report["failed_generation_check"] = local_check(failed, request) if failed else None
        text = failed
    elif status != 200:
        # Not Groq's error format (for example a gateway page): keep what came back.
        report["unexpected_response"] = json.dumps(payload, ensure_ascii=False)[:2000]
        text = ""
    else:
        choice = ((payload.get("choices") or [{}])[0]) if isinstance(payload, dict) else {}
        report["finish_reason"] = choice.get("finish_reason")
        report["usage"] = payload.get("usage") if isinstance(payload, dict) else None
        text = str((choice.get("message") or {}).get("content") or "")
        report["answer_check"] = local_check(text, request)

    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{safe_slug(mechanism)}.{safe_slug(model)}" + (".strict" if strict else "")
    (DIAGNOSTICS_DIR / f"{stem}.txt").write_text(text, encoding="utf-8")
    report["text_file"] = str(DIAGNOSTICS_DIR / f"{stem}.txt")
    (DIAGNOSTICS_DIR / f"{stem}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose a failing concept mechanism on Groq")
    parser.add_argument("--mechanism", required=True)
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--strict", action="store_true", help="ask Groq for constrained (strict) decoding")
    args = parser.parse_args()
    report = diagnose(args.mechanism, args.model, args.max_tokens, args.timeout, strict=args.strict)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
