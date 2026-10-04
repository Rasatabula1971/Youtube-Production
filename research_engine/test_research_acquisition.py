import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import research_acquisition as module


def plan(root: Path) -> Path:
    path = root / "c1.research_plan.json"
    path.write_text(
        json.dumps(
            {
                "concept_id": "c1",
                "research_questions": [
                    {"question_id": "q1", "question": "Why are aircraft tyres filled with nitrogen?"},
                    {"question_id": "q2", "question": "How hot do aircraft tyres get on landing?"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


class ResearchAcquisitionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = patch.object(module, "OUTPUT_DIR", self.root / "evidence")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_configured_backends_and_records_attempts(self):
        def search(query, *, limit, backends):
            self.assertEqual(backends, ["exa", "duckduckgo", "wikipedia"])
            return {
                "backend": "wikipedia_api",
                "result_urls": [f"https://en.wikipedia.org/wiki/{query[:3]}"],
                "attempts": [
                    {"backend": "exa", "status": "FAILED", "error": "mcporter missing"},
                    {"backend": "wikipedia", "status": "COMPLETE", "results": 1},
                ],
            }

        def read(url, *, backends):
            self.assertEqual(backends, ["jina_reader", "direct"])
            return {"backend": "wikipedia_extract", "content": "Evidence text for " + url}

        with (
            patch.object(module, "search_web_with_fallback", side_effect=search),
            patch.object(module, "read_web_page_with_fallback", side_effect=read),
        ):
            result = module.acquire_plan(plan(self.root))
        self.assertEqual(result["status"], "COMPLETE")
        self.assertIsNone(result["first_error"])
        evidence = json.loads(Path(result["evidence"]).read_text())
        self.assertEqual(evidence["question_searches"][0]["backend"], "wikipedia_api")
        self.assertEqual(evidence["question_searches"][0]["attempts"][0]["backend"], "exa")
        self.assertEqual(evidence["pages"][0]["backend"], "wikipedia_extract")
        self.assertEqual(
            evidence["provenance"]["search_backends"], ["exa", "duckduckgo", "wikipedia"]
        )

    def test_failure_reports_first_real_error(self):
        def search(query, *, limit, backends):
            raise RuntimeError("Every web search backend failed: exa: mcporter missing")

        with patch.object(module, "search_web_with_fallback", side_effect=search):
            result = module.acquire_plan(plan(self.root))
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["errors"], 2)
        self.assertIn("search: Every web search backend failed", result["first_error"])

    def test_a_rework_note_searches_the_claim_and_does_not_block(self):
        path = self.root / "c2.research_plan.json"
        path.write_text(json.dumps({
            "concept_id": "c2",
            "research_questions": [
                {"question_id": "q1", "question": "Why are aircraft tyres filled with nitrogen?"},
                {"question_id": "hrw_clm_001", "question": "find the answer elsewhere or discontinue",
                 "origin": "human_rework", "rework_claim_id": "clm_001"},
            ],
            "human_rework_requests": [{"question_id": "hrw_clm_001", "claim_id": "clm_001",
                                       "note": "find the answer elsewhere or discontinue",
                                       "original_claim": {"statement": "Nitrogen leaks through rubber more slowly."}}],
        }), encoding="utf-8")
        queries = []

        def search(query, *, limit, backends):
            queries.append(query)
            if query.startswith("Nitrogen"):
                raise RuntimeError("no results")
            return {"backend": "exa", "result_urls": ["https://example.org/n2"], "attempts": []}

        def read(url, *, backends):
            return {"backend": "direct", "content": "Evidence text"}

        with (
            patch.object(module, "search_web_with_fallback", side_effect=search),
            patch.object(module, "read_web_page_with_fallback", side_effect=read),
        ):
            result = module.acquire_plan(path)
        self.assertNotIn("find the answer elsewhere or discontinue", queries)
        self.assertIn("Nitrogen leaks through rubber more slowly.", queries)
        evidence = json.loads(Path(result["evidence"]).read_text())
        self.assertEqual(evidence["unresolved_question_ids"], [])

    def test_keyword_query_drops_question_words(self):
        self.assertEqual(
            module.keyword_query(
                "At what exact gram threshold do most drivers begin to perceive steering wheel vibration at 100 km/h?"
            ),
            "gram threshold drivers begin perceive steering wheel vibration",
        )
        self.assertEqual(module.keyword_query("Why are aircraft tyres filled with nitrogen?"),
                         "aircraft tyres filled nitrogen")

    def test_a_question_with_no_results_is_retried_as_keywords(self):
        queries = []

        def search(query, *, limit, backends):
            queries.append(query)
            if query.endswith("?"):
                raise RuntimeError("Every web search backend failed: duckduckgo: no results")
            return {"backend": "duckduckgo", "result_urls": [f"https://example.org/{len(queries)}"], "attempts": []}

        def read(url, *, backends):
            return {"backend": "direct", "content": "Evidence text for " + url}

        with (
            patch.object(module, "search_web_with_fallback", side_effect=search),
            patch.object(module, "read_web_page_with_fallback", side_effect=read),
        ):
            result = module.acquire_plan(plan(self.root))
        self.assertEqual(result["status"], "COMPLETE")
        evidence = json.loads(Path(result["evidence"]).read_text())
        self.assertEqual(evidence["question_searches"][0]["query_used"], "aircraft tyres filled nitrogen")
        self.assertEqual(len(queries), 4)

    def test_a_failed_keyword_retry_reports_both_errors(self):
        def search(query, *, limit, backends):
            raise RuntimeError(f"no results for {query}")

        with patch.object(module, "search_web_with_fallback", side_effect=search):
            result = module.acquire_plan(plan(self.root))
        self.assertEqual(result["status"], "FAILED")
        self.assertIn('keyword retry "aircraft tyres filled nitrogen"', result["first_error"])


if __name__ == "__main__":
    unittest.main()


class SearchRoundTests(unittest.TestCase):
    """A question with no source is given up after the configured rounds (D-163)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = patch.object(module, "OUTPUT_DIR", self.root / "evidence")
        patcher.start()
        self.addCleanup(patcher.stop)

    def two_question_plan(self):
        path = plan(self.root)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["research_questions"].append(
            {"question_id": "rq002", "question": "How long does it last?"}
        )
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def acquire(self, path, *, force=False):
        def search(query, *, limit, backends):
            if "last" in query:
                return {"backend": "duckduckgo", "result_urls": [], "attempts": []}
            return {"backend": "wikipedia_api", "result_urls": ["https://example.org/a"], "attempts": []}

        def read(url, *, backends):
            return {"backend": "direct", "content": "Evidence text"}

        with (
            patch.object(module, "search_web_with_fallback", side_effect=search),
            patch.object(module, "read_web_page_with_fallback", side_effect=read),
        ):
            return module.acquire_plan(path, force=force)

    def test_second_round_without_a_source_gives_the_question_up(self):
        path = self.two_question_plan()
        first = self.acquire(path)
        self.assertEqual(first["status"], "PARTIAL")
        evidence = json.loads(Path(first["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["unresolved_question_ids"], ["rq002"])
        self.assertEqual(evidence["unsourced_question_ids"], [])
        self.assertEqual(evidence["search_rounds"], {"q1": 1, "q2": 1, "rq002": 1})

        second = self.acquire(path, force=True)
        self.assertEqual(second["status"], "COMPLETE")
        self.assertEqual(second["unsourced_questions"], 1)
        evidence = json.loads(Path(second["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["unresolved_question_ids"], [])
        self.assertEqual(evidence["unsourced_question_ids"], ["rq002"])
        self.assertEqual(evidence["search_rounds"], {"q1": 2, "q2": 2, "rq002": 2})

    def test_a_changed_plan_starts_the_count_again(self):
        path = self.two_question_plan()
        self.acquire(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["research_questions"][1]["question"] = "How long does it really last?"
        path.write_text(json.dumps(payload), encoding="utf-8")
        again = self.acquire(path, force=True)
        self.assertEqual(again["status"], "PARTIAL")
        evidence = json.loads(Path(again["evidence"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["search_rounds"]["rq002"], 1)
