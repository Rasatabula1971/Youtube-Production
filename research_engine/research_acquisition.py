"""Acquire real web evidence for prepared Research Engine plans.

This layer only searches and reads sources. It does not decide claim truth.
Search uses Agent Reach's documented Exa/mcporter path first, then the free
DuckDuckGo HTML and Wikipedia API backends when Exa is unavailable or finds
nothing. Page reads use the Jina Reader path first, then a direct fetch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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

from agent_reach_adapter import (
    read_web_page_with_fallback,
    search_web_with_fallback,
)

PLANS_DIR = HERE / "output" / "plans"
OUTPUT_DIR = HERE / "output" / "acquired_evidence"
SUMMARY_FILE = HERE / "output" / "research_acquisition_summary.json"
CONFIG_FILE = HERE / "research_acquisition_config.json"
DEFAULT_MAX_SEARCH_ROUNDS = 2
NO_SOURCES = "NO_SOURCES"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_" for char in value
    ).strip("._")
    return cleaned or "unknown"


DEFAULT_SEARCH_BACKENDS = ["exa", "duckduckgo", "wikipedia"]
DEFAULT_READ_BACKENDS = ["jina_reader", "direct"]


def load_config() -> dict[str, Any]:
    raw = load_json(CONFIG_FILE)
    return {
        "search_results_per_question": int(raw["search_results_per_question"]),
        "pages_per_question": int(raw["pages_per_question"]),
        "max_unique_pages_per_concept": int(raw["max_unique_pages_per_concept"]),
        "max_chars_per_page": int(raw["max_chars_per_page"]),
        "max_total_content_chars": int(raw["max_total_content_chars"]),
        "search_backends": [
            str(x) for x in raw.get("search_backends", DEFAULT_SEARCH_BACKENDS)
        ],
        "read_backends": [
            str(x) for x in raw.get("read_backends", DEFAULT_READ_BACKENDS)
        ],
        # After this many acquisition rounds with no usable page, a question
        # is given up (recorded as unsourced) instead of blocking research (D-163).
        "max_search_rounds_per_question": max(
            1, int(raw.get("max_search_rounds_per_question", DEFAULT_MAX_SEARCH_ROUNDS))
        ),
    }


_QUERY_STOPWORDS = frozenset(
    "a an and are as at be been by can could do does did for from has have how if in into is it its "
    "of on or so than that the their them then there these they this to was were what when where "
    "which while who whom whose why will with would most more exact exactly actually really just "
    "about many much some any each every your you our we".split()
)


def keyword_query(question: str, *, max_words: int = 8) -> str:
    """A short keyword version of a research question (D-152).

    Search engines often return nothing for a long, specific question; the
    same question as a few keywords usually finds pages.
    """
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.%/+-]*", question)
    kept = [w.rstrip(".") for w in words if w.lower().rstrip(".") not in _QUERY_STOPWORDS]
    return " ".join(kept[:max_words])


def _search(query: str, config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Search the question; if every backend finds nothing, retry as keywords."""
    try:
        return search_web_with_fallback(
            query, limit=config["search_results_per_question"], backends=config["search_backends"]
        ), query
    except Exception as first:
        short = keyword_query(query)
        if not short or short.lower() == query.lower():
            raise
        try:
            return search_web_with_fallback(
                short, limit=config["search_results_per_question"], backends=config["search_backends"]
            ), short
        except Exception as second:
            raise RuntimeError(f"{first}; keyword retry \"{short}\": {second}") from second


def acquire_plan(plan_path: Path, *, force: bool = False) -> dict[str, Any]:
    plan = load_json(plan_path)
    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Research plan requires concept_id")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_DIR / f"{safe_slug(concept_id)}.research_evidence.json"
    plan_hash = sha256_file(plan_path)

    previous_rounds: dict[str, int] = {}
    if destination.exists():
        existing = load_json(destination)
        provenance = existing.get("provenance", {})
        if isinstance(provenance, dict) and provenance.get("plan_sha256") == plan_hash:
            if existing.get("status") == "COMPLETE" and not force:
                return {
                    "status": "SKIPPED_CURRENT",
                    "concept_id": concept_id,
                    "evidence": str(destination),
                }
            if existing.get("status") == NO_SOURCES and not force:
                # Every question was already searched to the limit with no
                # page: searching again only repeats it (audit 2).
                return {
                    "status": NO_SOURCES,
                    "concept_id": concept_id,
                    "evidence": str(destination),
                    "unsourced_questions": len(existing.get("unsourced_question_ids") or []),
                }
            # The same plan was searched before: count those rounds (D-163).
            rounds = existing.get("search_rounds")
            if isinstance(rounds, dict):
                previous_rounds = {
                    str(key): int(value)
                    for key, value in rounds.items()
                    if isinstance(value, int) and value > 0
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

    rework_statements = {
        str(request.get("question_id") or ""): str((request.get("original_claim") or {}).get("statement") or "")
        for request in plan.get("human_rework_requests") or []
        if isinstance(request, dict)
    }
    for question in questions:
        question_id = str(question.get("question_id", "")).strip()
        query = str(question.get("question", "")).strip()
        if question.get("origin") == "human_rework":
            # A rework note is an instruction for the model, not a search
            # query: search the reworked claim's statement instead (D-153).
            query = rework_statements.get(question_id, "").strip() or query
        if not question_id or not query:
            continue

        try:
            search, query_used = _search(query, config)
            urls = list(search.get("result_urls", []))
            question_searches.append(
                {
                    "question_id": question_id,
                    "query": query,
                    "query_used": query_used,
                    "backend": search.get("backend"),
                    "attempts": search.get("attempts", []),
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
                read = read_web_page_with_fallback(
                    clean_url, backends=config["read_backends"]
                )
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

    # Rework instructions never block (research_gate); only original questions must have a source.
    required_question_ids = {
        str(question.get("question_id"))
        for question in questions
        if isinstance(question, dict) and question.get("question_id")
        and question.get("origin") != "human_rework"
    }
    covered_question_ids = {
        str(question_id)
        for page in pages
        for question_id in page.get("question_ids", [])
    }
    searched_ids = {str(item["question_id"]) for item in question_searches} | {
        str(item.get("question_id") or "") for item in errors if item.get("stage") == "search"
    }
    search_rounds = {
        question_id: previous_rounds.get(question_id, 0) + (1 if question_id in searched_ids else 0)
        for question_id in sorted(required_question_ids | set(previous_rounds))
    }
    uncovered = required_question_ids - covered_question_ids
    # A question still without a page after the configured rounds is given
    # up with a record of the searches, so research can go on; the Research
    # Gate waives it automatically with that note (D-163).
    unsourced_question_ids = sorted(
        question_id
        for question_id in uncovered
        if search_rounds.get(question_id, 0) >= config["max_search_rounds_per_question"]
    )
    unresolved_question_ids = sorted(uncovered - set(unsourced_question_ids))
    blocking_errors = [
        item for item in errors if str(item.get("question_id") or "") not in unsourced_question_ids
    ]
    status = (
        "COMPLETE"
        if pages and not blocking_errors and not unresolved_question_ids
        else "PARTIAL" if pages
        # No page for any question after the rounds: research cannot proceed
        # on this concept, and saying so beats retrying forever (audit 2).
        else NO_SOURCES if required_question_ids and set(unsourced_question_ids) == required_question_ids
        else "FAILED"
    )
    payload = {
        "artifact": "research_acquired_evidence",
        "status": status,
        "concept_id": concept_id,
        "plan_source": str(plan_path),
        "provenance": {
            "plan_sha256": plan_hash,
            "search_backends": config["search_backends"],
            "read_backends": config["read_backends"],
        },
        "question_searches": question_searches,
        "pages": pages,
        "errors": errors,
        "unresolved_question_ids": unresolved_question_ids,
        "unsourced_question_ids": unsourced_question_ids,
        "search_rounds": search_rounds,
        "limits": config,
    }
    atomic_write_json(destination, payload)
    return {
        "status": status,
        "concept_id": concept_id,
        "pages": len(pages),
        "errors": len(blocking_errors),
        "unsourced_questions": len(unsourced_question_ids),
        "first_error": (
            f"{blocking_errors[0]['stage']}: {blocking_errors[0]['message']}"
            if blocking_errors
            else None
        ),
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
        # NO_SOURCES is a settled answer, not a failure of this run: the batch
        # ends PARTIAL so the run names it and goes on with other work.
        item.get("status") in {"COMPLETE", "PARTIAL", "SKIPPED_CURRENT", NO_SOURCES}
        for item in results
    )
    complete = sum(
        item.get("status") in {"COMPLETE", "SKIPPED_CURRENT"} for item in results
    )
    status = (
        "COMPLETE"
        if results and complete == len(results)
        else "FAILED" if results and usable == 0 else "PARTIAL"
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
