"""Acquire real web evidence for prepared Research Engine plans.

This layer only searches and reads sources. It does not decide claim truth.
Search uses Agent Reach's documented Exa/mcporter path; page reads use its
documented Jina Reader path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import atomic_write_json, exit_code_for_status

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SOURCE_DIR = PROJECT_ROOT / "source_acquisition"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from agent_reach_adapter import (  # noqa: E402
    AcquisitionError,
    read_web_page,
    search_web,
)

PLANS_DIR = HERE / "output" / "plans"
OUTPUT_DIR = HERE / "output" / "acquired_evidence"
SUMMARY_FILE = HERE / "output" / "research_acquisition_summary.json"
CONFIG_FILE = HERE / "research_acquisition_config.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    ).strip("._")
    return cleaned or "unknown"


def load_config() -> dict[str, int]:
    raw = load_json(CONFIG_FILE)
    return {
        "search_results_per_question": int(raw["search_results_per_question"]),
        "pages_per_question": int(raw["pages_per_question"]),
        "max_unique_pages_per_concept": int(raw["max_unique_pages_per_concept"]),
        "max_chars_per_page": int(raw["max_chars_per_page"]),
        "max_total_content_chars": int(raw["max_total_content_chars"]),
    }


def acquire_plan(plan_path: Path, *, force: bool = False) -> dict[str, Any]:
    plan = load_json(plan_path)
    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Research plan requires concept_id")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_DIR / f"{safe_slug(concept_id)}.research_evidence.json"
    plan_hash = sha256_file(plan_path)

    if destination.exists() and not force:
        existing = load_json(destination)
        provenance = existing.get("provenance", {})
        if (
            isinstance(provenance, dict)
            and provenance.get("plan_sha256") == plan_hash
            and existing.get("status") == "COMPLETE"
        ):
            return {
                "status": "SKIPPED_CURRENT",
                "concept_id": concept_id,
                "evidence": str(destination),
            }

    config = load_config()
    questions = plan.get("research_questions", [])
    if not isinstance(questions, list) or not questions:
        raise ValueError("Research plan requires research_questions")

    used_urls: set[str] = set()
    pages: list[dict[str, Any]] = []
    question_searches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total_chars = 0

    for question in questions:
        question_id = str(question.get("question_id", "")).strip()
        query = str(question.get("question", "")).strip()
        if not question_id or not query:
            continue

        try:
            search = search_web(
                query,
                limit=config["search_results_per_question"],
            )
            urls = list(search.get("result_urls", []))
            question_searches.append(
                {
                    "question_id": question_id,
                    "query": query,
                    "backend": search.get("backend"),
                    "result_urls": urls,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "question_id": question_id,
                    "stage": "search",
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:1000],
                }
            )
            continue

        acquired_for_question = 0
        for url in urls:
            if acquired_for_question >= config["pages_per_question"]:
                break
            if len(used_urls) >= config["max_unique_pages_per_concept"]:
                break
            clean_url = str(url).strip()
            if not clean_url or clean_url in used_urls:
                continue
            if total_chars >= config["max_total_content_chars"]:
                break

            try:
                read = read_web_page(clean_url)
            except Exception as exc:
                errors.append(
                    {
                        "question_id": question_id,
                        "stage": "read",
                        "url": clean_url,
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:1000],
                    }
                )
                continue

            content = str(read.get("content") or "")
            remaining = config["max_total_content_chars"] - total_chars
            content = content[: min(config["max_chars_per_page"], remaining)]
            if not content:
                continue

            used_urls.add(clean_url)
            acquired_for_question += 1
            total_chars += len(content)
            pages.append(
                {
                    "source_id": f"web{len(pages) + 1:03d}",
                    "url": clean_url,
                    "backend": read.get("backend"),
                    "question_ids": [question_id],
                    "content": content,
                    "content_chars": len(content),
                }
            )

        # If a page was already acquired for another question, preserve linkage.
        for page in pages:
            if page["url"] in urls and question_id not in page["question_ids"]:
                page["question_ids"].append(question_id)

    required_question_ids = {
        str(question.get("question_id"))
        for question in questions
        if isinstance(question, dict) and question.get("question_id")
    }
    covered_question_ids = {
        str(question_id)
        for page in pages
        for question_id in page.get("question_ids", [])
    }
    unresolved_question_ids = sorted(
        required_question_ids - covered_question_ids
    )
    status = (
        "COMPLETE"
        if pages and not errors and not unresolved_question_ids
        else "PARTIAL"
        if pages
        else "FAILED"
    )
    payload = {
        "artifact": "research_acquired_evidence",
        "status": status,
        "concept_id": concept_id,
        "plan_source": str(plan_path),
        "provenance": {
            "plan_sha256": plan_hash,
            "search_backend": "exa.web_search_exa",
            "read_backend": "jina_reader",
        },
        "question_searches": question_searches,
        "pages": pages,
        "errors": errors,
        "unresolved_question_ids": unresolved_question_ids,
        "limits": config,
    }
    atomic_write_json(destination, payload)
    return {
        "status": status,
        "concept_id": concept_id,
        "pages": len(pages),
        "errors": len(errors),
        "evidence": str(destination),
    }


def run_batch(*, force: bool = False) -> dict[str, Any]:
    if not PLANS_DIR.exists():
        return {"status": "WAITING_FOR_RESEARCH_PLANS", "results": []}

    results = []
    for path in sorted(PLANS_DIR.glob("*.research_plan.json")):
        try:
            results.append(acquire_plan(path, force=force))
        except Exception as exc:
            results.append(
                {
                    "status": "ERROR",
                    "plan": str(path),
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:1000],
                }
            )

    usable = sum(
        item.get("status") in {"COMPLETE", "PARTIAL", "SKIPPED_CURRENT"}
        for item in results
    )
    complete = sum(
        item.get("status") in {"COMPLETE", "SKIPPED_CURRENT"}
        for item in results
    )
    status = (
        "COMPLETE"
        if results and complete == len(results)
        else "FAILED"
        if results and usable == 0
        else "PARTIAL"
    )
    summary = {
        "status": status,
        "plans": len(results),
        "usable": usable,
        "results": results,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire Research Engine web evidence")
    parser.add_argument("--mode", choices=("batch", "one"), required=True)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.mode == "one":
        if args.plan is None:
            raise SystemExit("--plan is required for one mode")
        result = acquire_plan(args.plan.resolve(), force=args.force)
    else:
        result = run_batch(force=args.force)

    print(json.dumps(result, indent=2, ensure_ascii=True))
    if args.mode == "batch":
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
