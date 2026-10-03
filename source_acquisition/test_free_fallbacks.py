import json
import subprocess
import unittest
from unittest.mock import patch

import agent_reach_adapter as adapter

# Trimmed from DuckDuckGo's no-JavaScript results page.
DDG_HTML = """
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.faa.gov%2Faircraft%2Ftires&amp;rut=abc">FAA tires</a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.faa.gov%2Faircraft%2Ftires">snippet</a>
</div>
<div class="result results_links results_links_deep result--ad">
  <a class="result__a" href="https://duckduckgo.com/y.js?ad_domain=example.com">Ad</a>
</div>
<div class="result">
  <a href="https://www.goodyearaviation.com/nitrogen" class="result__a">Goodyear</a>
</div>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.faa.gov%2Faircraft%2Ftires">dup</a>
</div>
"""

WIKI_SEARCH = {
    "query": {
        "search": [
            {"title": "Aircraft tire"},
            {"title": "Nitrogen inflation"},
        ]
    }
}


def completed(stdout, code=0, stderr=""):
    return subprocess.CompletedProcess(["x"], code, stdout=stdout, stderr=stderr)


class FreeSearchBackendTests(unittest.TestCase):
    def test_duckduckgo_html_parsing_unwraps_redirects_and_skips_ads(self):
        self.assertEqual(
            adapter.parse_duckduckgo_html(DDG_HTML),
            [
                "https://www.faa.gov/aircraft/tires",
                "https://www.goodyearaviation.com/nitrogen",
            ],
        )

    def test_duckduckgo_search_uses_curl_without_shell(self):
        with (
            patch.object(adapter, "curl_path", return_value="/bin/curl"),
            patch.object(adapter.subprocess, "run", return_value=completed(DDG_HTML)) as run,
        ):
            result = adapter.search_duckduckgo("aircraft tyre nitrogen", limit=1)
        self.assertEqual(result["backend"], "duckduckgo_html")
        self.assertEqual(result["result_urls"], ["https://www.faa.gov/aircraft/tires"])
        command = run.call_args.args[0]
        self.assertEqual(command[-1], "https://html.duckduckgo.com/html/?q=aircraft+tyre+nitrogen")
        self.assertIn("--fail", command)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_wikipedia_search_builds_article_urls(self):
        with (
            patch.object(adapter, "curl_path", return_value="/bin/curl"),
            patch.object(
                adapter.subprocess, "run", return_value=completed(json.dumps(WIKI_SEARCH))
            ) as run,
        ):
            result = adapter.search_wikipedia("aircraft tire", limit=5)
        self.assertEqual(
            result["result_urls"],
            [
                "https://en.wikipedia.org/wiki/Aircraft_tire",
                "https://en.wikipedia.org/wiki/Nitrogen_inflation",
            ],
        )
        self.assertTrue(run.call_args.args[0][-1].startswith("https://en.wikipedia.org/w/api.php?"))

    def test_fallback_order_and_attempt_record(self):
        def exa(query, limit):
            raise adapter.AcquisitionError("mcporter is not available on PATH")

        def ddg(query, limit):
            return {"result_urls": [], "backend": "duckduckgo_html"}

        def wiki(query, limit):
            return {"result_urls": ["https://en.wikipedia.org/wiki/Tire"], "backend": "wikipedia_api"}

        with patch.dict(adapter.SEARCH_BACKENDS, {"exa": exa, "duckduckgo": ddg, "wikipedia": wiki}):
            result = adapter.search_web_with_fallback("tyre", limit=3)
        self.assertEqual(result["backend"], "wikipedia_api")
        self.assertEqual(
            [(a["backend"], a["status"]) for a in result["attempts"]],
            [("exa", "FAILED"), ("duckduckgo", "NO_RESULTS"), ("wikipedia", "COMPLETE")],
        )
        self.assertIn("mcporter", result["attempts"][0]["error"])

    def test_first_backend_with_results_wins(self):
        calls = []

        def exa(query, limit):
            calls.append("exa")
            return {"result_urls": ["https://a.example"], "backend": "exa.web_search_exa"}

        def never(query, limit):
            calls.append("other")
            raise AssertionError("fallback should not run")

        with patch.dict(adapter.SEARCH_BACKENDS, {"exa": exa, "duckduckgo": never, "wikipedia": never}):
            result = adapter.search_web_with_fallback("tyre")
        self.assertEqual(result["backend"], "exa.web_search_exa")
        self.assertEqual(calls, ["exa"])

    def test_all_backends_failing_names_each_error(self):
        def fail(name):
            def search(query, limit):
                raise adapter.AcquisitionError(f"{name} down")

            return search

        with patch.dict(
            adapter.SEARCH_BACKENDS,
            {"exa": fail("exa"), "duckduckgo": fail("ddg"), "wikipedia": fail("wiki")},
        ):
            with self.assertRaises(adapter.AcquisitionError) as caught:
                adapter.search_web_with_fallback("tyre")
        message = str(caught.exception)
        for part in ("exa: exa down", "duckduckgo: ddg down", "wikipedia: wiki down"):
            self.assertIn(part, message)

    def test_unknown_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            adapter.search_web_with_fallback("tyre", backends=["bing"])


class FreeReadBackendTests(unittest.TestCase):
    def test_html_to_text_drops_scripts_and_navigation(self):
        text = adapter.html_to_text(
            "<html><head><style>p{}</style><script>var x=1</script></head><body>"
            "<nav>Menu Home</nav><h1>Aircraft tyres</h1><p>Filled with   nitrogen.</p>"
            "<footer>Copyright</footer></body></html>"
        )
        self.assertEqual(text, "Aircraft tyres\nFilled with nitrogen.")

    def test_direct_read_uses_wikipedia_extract_for_articles(self):
        extract = {"query": {"pages": {"1": {"extract": "An aircraft tire is..."}}}}
        with (
            patch.object(adapter, "curl_path", return_value="/bin/curl"),
            patch.object(adapter.subprocess, "run", return_value=completed(json.dumps(extract))) as run,
        ):
            result = adapter.read_web_page_direct("https://en.wikipedia.org/wiki/Aircraft_tire")
        self.assertEqual(result["backend"], "wikipedia_extract")
        self.assertEqual(result["content"], "An aircraft tire is...")
        self.assertIn("titles=Aircraft+tire", run.call_args.args[0][-1])

    def test_read_falls_back_from_jina_to_direct_fetch(self):
        responses = [
            completed("", code=22, stderr="curl: (22) The requested URL returned error: 429"),
            completed("<p>Railway wheels are steel.</p>"),
        ]
        with (
            patch.object(adapter, "curl_path", return_value="/bin/curl"),
            patch.object(adapter.subprocess, "run", side_effect=responses) as run,
        ):
            result = adapter.read_web_page_with_fallback("https://example.com/rail")
        self.assertEqual(result["backend"], "direct_fetch")
        self.assertEqual(result["content"], "Railway wheels are steel.")
        self.assertIn("429", result["fallback_from"][0])
        self.assertEqual(run.call_args.args[0][-1], "https://example.com/rail")

    def test_read_reports_every_failure(self):
        with (
            patch.object(adapter, "curl_path", return_value="/bin/curl"),
            patch.object(
                adapter.subprocess,
                "run",
                return_value=completed("", code=6, stderr="curl: (6) Could not resolve host"),
            ),
        ):
            with self.assertRaises(adapter.AcquisitionError) as caught:
                adapter.read_web_page_with_fallback("https://example.com/x")
        self.assertIn("jina_reader:", str(caught.exception))
        self.assertIn("direct:", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
