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


if __name__ == "__main__":
    unittest.main()
