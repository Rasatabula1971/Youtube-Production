"""Regression tests for the UI-19 adversarial audit (D-127)."""

import os
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    # Never read the real pipeline outputs of the machine running the tests.
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()

STATIC = Path(server.__file__).resolve().parent / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


class ServerHardeningTests(unittest.TestCase):
    def test_api_reads_refuse_a_foreign_host(self) -> None:
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/tools", headers={"Host": f"evil.example:{port}"}
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=10)
            self.assertEqual(caught.exception.code, 403)
            # The page itself still loads for any Host; only the API is guarded.
            page = urllib.request.Request(f"http://127.0.0.1:{port}/", headers={"Host": f"evil.example:{port}"})
            with urllib.request.urlopen(page, timeout=10) as response:
                self.assertEqual(response.status, 200)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tools", timeout=10) as response:
                self.assertEqual(response.status, 200)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_updated_at_uses_the_longest_matching_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "foo.research_plan.json").write_text("{}")
            (folder / "foo.v2.research_plan.json").write_text("{}")
            os.utime(folder / "foo.research_plan.json", (1_000_000, 1_000_000))
            os.utime(folder / "foo.v2.research_plan.json", (3_000_000, 3_000_000))
            with mock.patch.object(server, "PRODUCTION_ARTIFACT_DIRS", (folder,)):
                updated = server.production_updated_at(["foo", "foo.v2"])
        self.assertEqual(updated["foo"], "1970-01-12T13:46:40+00:00")
        self.assertEqual(updated["foo.v2"], "1970-02-04T17:20:00+00:00")


class ClientHardeningTests(unittest.TestCase):
    MODULES = [
        "app.js",
        "js/gate-reviews.js",
        "js/opportunity-review.js",
        "js/packaging.js",
        "js/produce.js",
        "js/production-workspace.js",
    ]

    def test_hash_decoding_never_throws(self) -> None:
        for name in self.MODULES:
            with self.subTest(module=name):
                self.assertNotIn("decodeURIComponent(", read(name))
        self.assertIn("window.YPUtil = {", read("js/a11y.js"))

    def test_id_keyed_state_maps_have_no_prototype(self) -> None:
        maps = {
            "js/packaging.js": ["titleChoices", "packageChoice", "criteriaTicks", "pendingFocus"],
            "js/produce.js": ["spendTicks", "visualChoice", "rightsContext", "maxCost", "pendingFocus"],
            "js/gate-reviews.js": ["pendingFocus", "sectionSnapshots", "sectionLoading"],
            "js/review-workspace.js": ["drafts", "typed"],
        }
        for name, names in maps.items():
            text = read(name)
            for variable in names:
                with self.subTest(module=name, variable=variable):
                    self.assertRegex(text, r"(const|let) " + variable + r" = Object\.create\(null\);")

    def test_refused_decisions_keep_the_reviewers_choices(self) -> None:
        for name in ["js/gate-reviews.js", "js/packaging.js", "js/produce.js"]:
            text = read(name)
            post = text.split("async function post(url, body, okMessage) {", 1)[1].split("\n  }\n", 1)[0]
            with self.subTest(module=name):
                self.assertIn("return true;", post)
                self.assertIn("return false;", post)
                self.assertIsNone(re.search(r"\.then\(function \(\) \{ delete ", text))
        self.assertIn("if (outcome !== false) delete typed[draft.key];", read("js/review-workspace.js"))

    def test_pending_rough_cuts_are_listed(self) -> None:
        self.assertNotIn("review_current !== false", read("js/produce.js"))
        self.assertNotIn("review_current !== false", read("app.js"))

    def test_decided_gates_stay_locked_like_the_classic_panels(self) -> None:
        self.assertIn("item.approved_for_paid_quote", read("js/gate-reviews.js").split("locked: function (item)", 1)[1][:200])
        produce = read("js/produce.js")
        self.assertEqual(produce.count("locked: function (item)"), 3)  # option wiring + narration + video gates
        for name in ["js/gate-reviews.js", "js/produce.js"]:
            with self.subTest(module=name):
                self.assertIn("config.locked && config.locked(item) ? [] : config.decisions(item)", read(name))

    def test_rejected_packaging_routes_to_the_classic_panels(self) -> None:
        app = read("app.js")
        states = app.split("const packagingStates = {", 1)[1].split("};", 1)[0]
        self.assertNotIn("REJECTED", states)
        self.assertIn('return { type: "route", value: "/analysis", label: classicRework[workflow.state] };', app)

    def test_skip_link_and_media_keys_do_not_trigger_routing(self) -> None:
        self.assertIn('event.target.closest(".skip-link")', read("js/a11y.js"))
        self.assertIn('tag === "audio" || tag === "video"', read("js/review-workspace.js"))

    def test_module_failures_are_isolated_and_polls_repaint_on_change(self) -> None:
        app = read("app.js")
        render_all = app.split("function renderAll(data) {", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("window.CommandCenter.render", render_all)
        self.assertIn('isolated("CommandCenter"', render_all)
        command_center = read("js/command-center.js")
        self.assertIn("function paint(element, html)", command_center)
        self.assertNotIn(".innerHTML = ", command_center.split("function paint(element, html)", 1)[1].replace(
            "element.innerHTML = html;", ""))


if __name__ == "__main__":
    unittest.main()
