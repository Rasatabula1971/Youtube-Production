"""FAIR-backed Research Engine claim-structuring runner.

The model receives only the prepared research plan plus web pages that were
actually acquired by research_acquisition.py. It may structure claims and
evidence links, but it may not invent sources outside that acquired set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from typing import Any

from pipeline_integrity import (
    atomic_write_json,
    atomic_write_text,
    batch_status,
    exit_code_for_status,
    tolerant_load_json,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from analysis_model_runner import (
    bridge_payload,
    call_fair_bridge,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

from research_engine import (
    PLANS_DIR,
    RESPONSES_DIR,
    load_config,
    load_json,
    run_apply,
    safe_slug,
    validate_research_response,
)

EVIDENCE_DIR = HERE / "output" / "acquired_evidence"
MODEL_RUNS_DIR = HERE / "output" / "research_model_runs"
RAW_OUTPUTS_DIR = HERE / "output" / "raw_research_outputs"
BATCH_SUMMARY_FILE = HERE / "output" / "research_model_batch_summary.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def response_schema(plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    concept_id = str(plan["concept_id"])
    question_ids = [
        str(item["question_id"]) for item in plan.get("research_questions", [])
    ]
    acquired_urls = [
        str(page["url"])
        for page in evidence.get("pages", [])
        if str(page.get("url", "")).strip()
    ]
    source_ids = [
        str(page["source_id"])
        for page in evidence.get("pages", [])
        if str(page.get("source_id", "")).strip()
    ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concept_id", "sources", "claims"],
        "properties": {
            "concept_id": {"type": "string", "const": concept_id},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_id",
                        "title",
                        "publisher",
                        "url",
                        "source_type",
                        "published_at",
                        "accessed_at",
                        "provenance_note",
                    ],
                    "properties": {
                        "source_id": {"type": "string", "enum": source_ids},
                        "title": {"type": "string", "minLength": 1},
                        "publisher": {"type": "string", "minLength": 1},
                        "url": {"type": "string", "enum": acquired_urls},
                        "source_type": {
                            "type": "string",
                            "enum": [
                                "primary",
                                "secondary",
                                "dataset",
                                "documentation",
                                "expert_statement",
                            ],
                        },
                        "published_at": {"type": ["string", "null"]},
                        "accessed_at": {"type": ["string", "null"]},
                        "provenance_note": {"type": "string", "minLength": 1},
                    },
                },
            },
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "claim_id",
                        "statement",
                        "role",
                        "question_ids",
                        "evidence_links",
                    ],
                    "properties": {
                        "claim_id": {"type": "string", "minLength": 1},
                        "statement": {"type": "string", "minLength": 1},
                        "role": {
                            "type": "string",
                            "enum": ["core", "supporting", "context"],
                        },
                        "question_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string", "enum": question_ids},
                        },
                        "evidence_links": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "source_id",
                                    "stance",
                                    "locator",
                                    "evidence_note",
                                    "evidence_quote",
                                ],
                                "properties": {
                                    "source_id": {
                                        "type": "string",
                                        "enum": source_ids,
                                    },
                                    "stance": {
                                        "type": "string",
                                        "enum": [
                                            "SUPPORTS",
                                            "CONTRADICTS",
                                            "QUALIFIES",
                                        ],
                                    },
                                    "locator": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "evidence_note": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "evidence_quote": {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": 500,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def build_prompt(
    plan: dict[str, Any],
    evidence: dict[str, Any],
    *,
    maximum_chars: int,
) -> str:
    compact_pages = [
        {
            "source_id": page.get("source_id"),
            "url": page.get("url"),
            "question_ids": page.get("question_ids", []),
            "content": page.get("content", ""),
        }
        for page in evidence.get("pages", [])
    ]
    payload = {
        "concept_id": plan.get("concept_id"),
        "working_title": plan.get("working_title"),
        "premise": plan.get("premise"),
        "audience_promise": plan.get("audience_promise"),
        "viewer_problem": plan.get("viewer_problem"),
        "viewer_moment": plan.get("viewer_moment"),
        "desired_outcome": plan.get("desired_outcome"),
        "packaging": plan.get("packaging"),
        "research_questions": plan.get("research_questions", []),
        "acquired_pages": compact_pages,
    }
    prompt = (
        "You are structuring research evidence for a YouTube script pipeline. "
        "Return JSON only.\n\n"
        "Hard rules:\n"
        "1. Use ONLY the acquired_pages supplied below. Never invent a URL, source, publisher, date, locator, or fact.\n"
        "2. source_id and URL must exactly match an acquired page.\n"
        "3. A claim must be supported, contradicted, or qualified by text actually present in the linked page.\n"
        "4. Keep evidence_note short and paraphrased. Also provide evidence_quote as a short exact excerpt copied from the linked acquired page; never invent or normalize wording inside evidence_quote.\n"
        "5. If evidence is insufficient for a research question, emit no unsupported claim for it; leave it unresolved for the human Research Gate.\n"
        "6. Record contradiction or qualification when the acquired evidence contains it. Do not silently harmonize disagreements.\n"
        "7. Do not infer audience demand from a HYPOTHESIS or UNASSESSED content gap.\n"
        "8. The approved package promise constrains relevance but does not authorize invented evidence.\n"
        "9. Do not call a claim verified or true merely because multiple sources agree.\n"
        "10. Locators must be useful textual section/heading/paragraph descriptions visible in the acquired content.\n\n"
        "RESEARCH INPUT:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Research prompt is {len(prompt):,} characters; configured maximum is "
            f"{maximum_chars:,}. Reduce research acquisition limits."
        )
    return prompt


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def validate_acquired_source_boundary(
    response: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    pages = {
        str(page.get("source_id")): page
        for page in evidence.get("pages", [])
        if isinstance(page, dict) and page.get("source_id")
    }
    allowed = {(source_id, str(page.get("url"))) for source_id, page in pages.items()}
    for source in response.get("sources", []):
        pair = (str(source.get("source_id")), str(source.get("url")))
        if pair not in allowed:
            raise ValueError(
                "Model returned a source outside acquired evidence: "
                f"{pair[0]} {pair[1]}"
            )

    for claim in response.get("claims", []):
        links = claim.get("evidence_links", [])
        if not isinstance(links, list) or not links:
            raise ValueError("Every research claim requires supporting evidence_links")
        for link in links:
            source_id = str(link.get("source_id", ""))
            page = pages.get(source_id)
            if page is None:
                raise ValueError(
                    f"Claim references unavailable acquired source: {source_id}"
                )
            quote = _normalized_text(link.get("evidence_quote"))
            if not quote:
                raise ValueError(
                    f"Claim evidence link {source_id} requires evidence_quote"
                )
            content = _normalized_text(page.get("content"))
            if quote not in content:
                raise ValueError(
                    f"Claim evidence_quote is not present in acquired page {source_id}"
                )


def run_one(
    plan_path: Path,
    evidence_path: Path,
    *,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    plan_path = plan_path.resolve()
    evidence_path = evidence_path.resolve()
    plan = load_json(plan_path)
    evidence = load_json(evidence_path)
    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id or concept_id != str(evidence.get("concept_id", "")):
        raise ValueError("Research plan and acquired evidence concept_id must match")

    plan_hash = sha256_file(plan_path)
    evidence_plan_hash = evidence.get("provenance", {}).get("plan_sha256")
    if evidence_plan_hash != plan_hash:
        raise ValueError(
            "STALE_RESEARCH_EVIDENCE: acquired evidence does not match current research plan"
        )
    evidence_hash = sha256_file(evidence_path)
    slug = safe_slug(concept_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"

    if report_path.exists() and response_path.exists() and not force:
        report = tolerant_load_json(report_path) or {}
        response = load_json(response_path)
        provenance = response.get("response_provenance", {})
        if (
            report.get("status") == "VALIDATED"
            and isinstance(provenance, dict)
            and provenance.get("plan_sha256") == plan_hash
            and provenance.get("evidence_sha256") == evidence_hash
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "report": str(report_path),
            }

    if not evidence.get("pages"):
        return {
            "status": "NO_ACQUIRED_PAGES",
            "concept_id": concept_id,
        }

    prompt = build_prompt(
        plan,
        evidence,
        maximum_chars=int(runner_config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = response_schema(plan, evidence)
    paths = resolve_fair_paths(runner_config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=runner_config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-research"

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bridge_result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                runner_config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        report = {
            "concept_id": concept_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "plan_sha256": plan_hash,
            "evidence_sha256": evidence_hash,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "concept_id": concept_id,
        "plan_sha256": plan_hash,
        "evidence_sha256": evidence_hash,
        "fair_request_id": bridge_result.get("request_id"),
        "fair_status": bridge_result.get("status"),
        "fair_reason_code": bridge_result.get("reason_code"),
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
        "paid_inference_executed": bridge_result.get("paid_inference_executed"),
        "attempts": safe_attempts(bridge_result),
    }
    if not inference_cost_authorized(bridge_result):
        report = {**base, "status": "COST_POLICY_VIOLATION"}
        atomic_write_json(report_path, report)
        return report
    if bridge_result.get("status") != "ACCEPTED":
        report = {
            **base,
            "status": (
                "MODEL_ESCALATION_REQUIRED"
                if bridge_result.get("status") == "ESCALATION_REQUIRED"
                else "MODEL_FAILED"
            ),
        }
        atomic_write_json(report_path, report)
        return report

    raw_output = str(bridge_result.get("output") or "")
    raw_path = RAW_OUTPUTS_DIR / f"{slug}.txt"
    atomic_write_text(raw_path, raw_output)

    try:
        response = parse_model_json(raw_output)
        validate_acquired_source_boundary(response, evidence)
        validate_research_response(response, plan, load_config())
    except Exception as exc:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    response["response_provenance"] = {
        "plan_source": str(plan_path),
        "plan_sha256": plan_hash,
        "evidence_source": str(evidence_path),
        "evidence_sha256": evidence_hash,
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
    }
    atomic_write_json(response_path, response)
    report = {
        **base,
        "status": "VALIDATED",
        "model_response": str(response_path),
        "raw_output": str(raw_path),
        "sources": len(response.get("sources", [])),
        "claims": len(response.get("claims", [])),
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(*, force: bool, maximum_requests: int | None) -> dict[str, Any]:
    config = load_runner_config()
    plans = sorted(PLANS_DIR.glob("*.research_plan.json")) if PLANS_DIR.exists() else []
    limit = int(
        maximum_requests
        if maximum_requests is not None
        else config["runner"].get("max_requests_per_batch", 4)
    )
    results = []
    invoked = 0
    for plan_path in plans:
        if invoked >= limit:
            break
        plan = load_json(plan_path)
        concept_id = str(plan.get("concept_id", "")).strip()
        evidence_path = EVIDENCE_DIR / f"{safe_slug(concept_id)}.research_evidence.json"
        if not evidence_path.exists():
            results.append(
                {
                    "status": "WAITING_FOR_ACQUIRED_EVIDENCE",
                    "concept_id": concept_id,
                }
            )
            continue
        result = run_one(
            plan_path,
            evidence_path,
            force=force,
            runner_config=config,
        )
        results.append(result)
        if result.get("status") != "SKIPPED_ALREADY_VALIDATED":
            invoked += 1
        if result.get("status") in {
            "COST_POLICY_VIOLATION",
            "RUNNER_ERROR",
            "MODEL_FAILED",
        }:
            break

    merge = run_apply()
    summary = {
        "status": batch_status(
            results,
            expected_count=len(plans),
            processed_count=len(results),
        ),
        "plans_found": len(plans),
        "model_runs_invoked": invoked,
        "batch_limit": limit,
        "results": results,
        "merge": merge,
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="FAIR-backed Research Engine runner")
    parser.add_argument("--mode", choices=("batch", "run"), required=True)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.mode == "run":
        if args.plan is None or args.evidence is None:
            raise SystemExit("--plan and --evidence are required for run mode")
        result = run_one(
            args.plan,
            args.evidence,
            force=args.force,
            runner_config=load_runner_config(),
        )
    else:
        result = run_batch(
            force=args.force,
            maximum_requests=args.max_requests,
        )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if args.mode == "batch":
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
