import json
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

STATIC = Path(__file__).resolve().parent / "static"


class StaticAssetPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "static" / "css").mkdir(parents=True)
        (root / "static" / "js").mkdir()
        (root / "static" / "css" / "tokens.css").write_text(":root{}")
        (root / "static" / "js" / "app.js").write_text("1;")
        (root / "static" / "css" / ".hidden.css").write_text("x")
        (root / "static" / "css" / "wrong.js").write_text("x")
        (root / "secret.css").write_text("secret")
        self.static = root / "static"
        self.patch = mock.patch.object(server, "STATIC_DIR", self.static)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.tmp.cleanup()

    def test_allowed_assets_resolve_inside_their_folder(self) -> None:
        self.assertEqual(
            server.static_asset_path("/css/tokens.css"),
            (self.static / "css" / "tokens.css").resolve(),
        )
        self.assertEqual(
            server.static_asset_path("/js/app.js"),
            (self.static / "js" / "app.js").resolve(),
        )

    def test_rejects_traversal_wrong_type_dotfiles_and_nesting(self) -> None:
        for route in [
            "/css/../../secret.css",
            "/css/..%2f..%2fsecret.css",
            "/css/wrong.js",
            "/js/tokens.css",
            "/css/.hidden.css",
            "/css/missing.css",
            "/css/sub/tokens.css",
            "/css/",
            "/img/logo.css",
            "/css/..\\secret.css",
        ]:
            with self.subTest(route=route):
                self.assertIsNone(server.static_asset_path(route))

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_rejects_symlink_that_escapes_the_folder(self) -> None:
        (self.static / "css" / "escape.css").symlink_to(
            Path(self.tmp.name) / "secret.css"
        )
        self.assertIsNone(server.static_asset_path("/css/escape.css"))


class ProductionUpdatedAtTests(unittest.TestCase):
    def test_newest_artifact_time_per_concept_by_file_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.mkdir()
            b.mkdir()
            (a / "c1.research_plan.json").write_text("{}")
            (b / "c1.long.script_draft.json").write_text("{}")
            (b / "c10.research_plan.json").write_text("{}")
            os.utime(a / "c1.research_plan.json", (1_000_000, 1_000_000))
            os.utime(b / "c1.long.script_draft.json", (2_000_000, 2_000_000))
            os.utime(b / "c10.research_plan.json", (3_000_000, 3_000_000))
            with mock.patch.object(server, "PRODUCTION_ARTIFACT_DIRS", (a, b, Path(tmp) / "missing")):
                updated = server.production_updated_at(["c1", "c10", "c2"])
        self.assertEqual(updated["c1"], "1970-01-24T03:33:20+00:00")
        self.assertEqual(updated["c10"], "1970-02-04T17:20:00+00:00")
        self.assertNotIn("c2", updated)

    def test_unknown_production_detail_is_404(self) -> None:
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(server, "production_detail", return_value=None):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{httpd.server_address[1]}/api/production?concept_id=nope",
                        timeout=5,
                    )
            self.assertEqual(caught.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()


class ShellHttpTests(unittest.TestCase):
    httpd: server.ThreadingHTTPServer
    base: str
    thread: threading.Thread

    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path: str) -> tuple[int, str, bytes]:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, response.headers["Content-Type"], response.read()

    def test_serves_split_css_and_js_with_types(self) -> None:
        status, ctype, body = self.get("/css/tokens.css")
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/css"))
        self.assertIn(b"--status-human", body)
        status, ctype, _ = self.get("/js/command-center.js")
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/javascript"))

    def test_traversal_is_404(self) -> None:
        for path in ["/css/../server.py", "/js/../../README.md", "/css/server.py"]:
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.get(path)
                self.assertEqual(caught.exception.code, 404)

    def test_radar_overview_api(self) -> None:
        fake = {"themes": [], "tracked": [], "window_days": 15}
        with mock.patch.object(server.viral_radar, "radar_overview", return_value=fake):
            status, _, body = self.get("/api/opportunity/viral/overview")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), fake)

    def test_new_pages_serve_the_app(self) -> None:
        for path in ["/radar", "/opportunity/review"]:
            with self.subTest(path=path):
                status, ctype, _ = self.get(path)
                self.assertEqual(status, 200)
                self.assertTrue(ctype.startswith("text/html"))

    def test_productions_route_serves_the_app(self) -> None:
        status, ctype, body = self.get("/productions")
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/html"))
        self.assertIn(b'id="viewProductions"', body)

    def test_productions_api_returns_derived_snapshot(self) -> None:
        fake = {"source": "derived_from_files", "count": 0, "productions": []}
        with mock.patch.object(server, "productions_snapshot", return_value=fake):
            status, ctype, body = self.get("/api/productions")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), fake)


class ShellMarkupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")

    def test_every_linked_asset_exists_and_is_servable(self) -> None:
        refs = re.findall(r'(?:href|src)="(/[^"]+\.(?:css|js))"', self.html)
        self.assertIn("/css/tokens.css", refs)
        self.assertLess(refs.index("/css/tokens.css"), refs.index("/styles.css"))
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertTrue((STATIC / ref.lstrip("/")).is_file())
                if ref.startswith(("/css/", "/js/")):
                    self.assertIsNotNone(server.static_asset_path(ref))

    def test_module_targets_exist(self) -> None:
        for name in ["command-center.js", "radar.js"]:
            script = (STATIC / "js" / name).read_text(encoding="utf-8")
            ids = set(re.findall(r'\$\("([A-Za-z]+)"\)', script))
            self.assertTrue(ids, name)
            for element_id in ids:
                with self.subTest(module=name, id=element_id):
                    self.assertIn(f'id="{element_id}"', self.html)
        review = (STATIC / "js" / "opportunity-review.js").read_text(encoding="utf-8")
        self.assertIn('getElementById("opportunityReview")', review)
        self.assertIn('id="opportunityReview"', self.html)

    def test_gate_review_roots_exist(self) -> None:
        script = (STATIC / "js" / "gate-reviews.js").read_text(encoding="utf-8")
        gates = re.search(r'const GATES = \[([^\]]+)\]', script)
        assert gates is not None
        for gate in re.findall(r'"([a-z]+)"', gates.group(1)):
            with self.subTest(gate=gate):
                self.assertIn(f'id="gateReview-{gate}"', self.html)
                self.assertIn(f'data-subroute="{gate}"', self.html)
        self.assertIn('id="gateReviewSwitcher"', self.html)

    def test_gate_reviews_post_the_classic_payloads(self) -> None:
        script = (STATIC / "js" / "gate-reviews.js").read_text(encoding="utf-8")
        app = (STATIC / "app.js").read_text(encoding="utf-8")
        for endpoint in [
            "/api/human-analysis-review",
            "/api/concept-gate",
            "/api/research-gate",
            "/api/script-gate",
            "/api/script-section-review",
            "/api/format-gate",
            "/api/performance-gate",
            "/api/narration-preview-gate",
        ]:
            with self.subTest(endpoint=endpoint):
                self.assertIn(f'"{endpoint}"', script)
                self.assertIn(f'"{endpoint}"', app)
                self.assertIn(endpoint, server.HUMAN_GATE_MUTATION_ROUTES)

    def test_script_review_offers_only_server_rework_reasons(self) -> None:
        import sys as _sys

        _sys.path.insert(0, str(server.STORY_DIR))
        from script_section_state import ALLOWED_REWORK_REASONS

        script = (STATIC / "js" / "gate-reviews.js").read_text(encoding="utf-8")
        block = re.search(r"const REWORK_REASONS = \[(.*?)\n  \];", script, re.S)
        assert block is not None
        offered = set(re.findall(r'\["([A-Z_]+)", ', block.group(1)))
        self.assertEqual(offered, set(ALLOWED_REWORK_REASONS))

    def test_packaging_page_covers_the_gate_config(self) -> None:
        script = (STATIC / "js" / "packaging.js").read_text(encoding="utf-8")
        for tab in re.findall(r'\["([a-z]+)", "[^"]+"\]', script.split("const FORMATS")[0]):
            with self.subTest(tab=tab):
                self.assertIn(f'id="packaging-{tab}"', self.html)
        self.assertIn('id="packagingTabs"', self.html)
        for endpoint in ["/api/title-direction-gate", "/api/final-packaging-gate"]:
            with self.subTest(endpoint=endpoint):
                self.assertIn(f'"{endpoint}"', script)
                self.assertIn(endpoint, server.HUMAN_GATE_MUTATION_ROUTES)
        config = json.loads(
            (server.PROJECT_ROOT / "packaging_engine" / "final_packaging_gate_config.json").read_text(
                encoding="utf-8"
            )
        )
        labels = re.search(r"const CRITERIA_LABELS = \{(.*?)\};", script, re.S)
        rework = re.search(r"const REWORK_LABELS = \{(.*?)\};", script, re.S)
        assert labels is not None and rework is not None
        for criterion in config["required_accept_criteria"] + [config["image_criterion"]]:
            with self.subTest(criterion=criterion):
                self.assertIn(criterion + ":", labels.group(1))
        for target in config["rework_targets"]:
            with self.subTest(target=target):
                self.assertIn(target + ":", rework.group(1))

    def test_preview_review_offers_only_server_decisions(self) -> None:
        import sys as _sys

        _sys.path.insert(0, str(server.PRODUCTION_DIR))
        from narration_preview_review import DECISIONS

        script = (STATIC / "js" / "gate-reviews.js").read_text(encoding="utf-8")
        block = script.split("const preview = {", 1)[1].split("const CONFIGS", 1)[0]
        offered = set(re.findall(r'value: "([A-Z_]+)"', block))
        self.assertEqual(offered, set(DECISIONS))

    def test_produce_page_decisions_match_the_server(self) -> None:
        import sys as _sys

        _sys.path.insert(0, str(server.PRODUCTION_DIR))
        import edit_preview_review
        import final_export_review

        script = (STATIC / "js" / "produce.js").read_text(encoding="utf-8")
        tabs = re.findall(r'\["([a-z]+)", "[^"]+"\]', script.split("let activeTab")[0])
        self.assertEqual(len(tabs), 11)
        for tab in tabs:
            with self.subTest(tab=tab):
                self.assertIn(f'id="produce-{tab}"', self.html)
                self.assertIn(f'data-subroute="{tab}"', self.html)

        def values(start: str, end: str) -> set[str]:
            block = script.split(start, 1)[1].split(end, 1)[0]
            found = re.findall(r'value: "([A-Z_]+)"|noteRework\("([A-Z_]+)"', block)
            return {a or b for a, b in found}

        # Server-side decision sets, copied from each gate module's validation.
        import narration_final_review
        import visual_plan_review

        self.assertEqual(values("const plan = {", "const narration = {"), set(visual_plan_review.DECISIONS))

        self.assertEqual(values("const narration = {", "const finalAudio = {"), {"ACCEPT", "REWORK", "REJECT"})
        self.assertEqual(values("const finalAudio = {", "const visuals = {"), set(narration_final_review.DECISIONS))
        self.assertEqual(values("const visuals = {", "const rights = {"), {"SELECT", "NEEDS_BETTER_VISUAL", "REJECT_ALL"})
        self.assertEqual(values("const rights = {", "const roughcut = {"), {"APPROVE_CONTEXT_USE", "REJECT_USE"})
        self.assertEqual(
            values("const roughcut = {", "const spend = {"),
            {"APPROVE_WITH_GAPS", "REWORK_VISUAL", "REWORK_PACING", "REWORK_AUDIO"},
        )
        self.assertEqual(
            values("const spend = {", "const generate = {"),
            {"AUTHORIZE_GENERATION", "KEEP_PLACEHOLDER", "RETRY_EXISTING"},
        )
        self.assertEqual(values("const generate = {", "function videoGate"), {"GENERATE", "CHOOSE"})
        returns = {"RETURN_TO_VISUALS", "RETURN_TO_NARRATION", "RETURN_TO_SOUND"}
        self.assertEqual(returns | {"APPROVE_EDIT_DIRECTION"}, set(edit_preview_review.DECISIONS))
        self.assertEqual(returns | {"APPROVE_EXPORT"}, set(final_export_review.DECISIONS))
        self.assertEqual(values("function videoGate", "const edit = "), returns)
        for endpoint in [
            "/api/narration-spend-gate",
            "/api/final-audio-gate",
            "/api/visual-plan-gate",
            "/api/visual-dispatch",
            "/api/publish-gate",
            "/api/visual-candidate-review",
            "/api/visual-rights-review",
            "/api/visual-rough-cut-review",
            "/api/visual-spend-review",
            "/api/edit-preview-review",
            "/api/final-export-review",
        ]:
            with self.subTest(endpoint=endpoint):
                self.assertIn(f'"{endpoint}"', script)
                self.assertIn(endpoint, server.HUMAN_GATE_MUTATION_ROUTES)

    def test_tools_page_markup_and_endpoints(self) -> None:
        tools = self.html.split('id="viewTools"', 1)[1].split("</main>", 1)[0]
        for marker in ['id="toolsHealth"', 'id="toolsJobs"', 'id="toolsRefresh"', 'id="toolActions"', 'id="stageGrid"']:
            with self.subTest(marker=marker):
                self.assertIn(marker, tools)
        # Health and jobs come before the Advanced controls.
        self.assertLess(tools.index('id="toolsHealth"'), tools.index("Advanced"))
        self.assertLess(tools.index("Advanced"), tools.index('id="toolActions"'))
        self.assertIn('<script src="/js/tools.js"></script>', self.html)
        self.assertIn('href="/css/tools.css"', self.html)
        script = (STATIC / "js" / "tools.js").read_text(encoding="utf-8")
        self.assertIn('"/api/tools"', script)
        self.assertIn('"/api/job-log?id="', script)
        # Diagnostics never post anything except the predefined actions.
        self.assertNotIn("method:", script)

    def test_shell_accessibility_contract(self) -> None:
        # Skip link first, pointing at the focusable main landmark.
        body = self.html.split("<body>", 1)[1]
        self.assertTrue(body.lstrip().startswith('<a class="skip-link" href="#mainContent">'))
        self.assertIn('<main class="view-container" id="mainContent" tabindex="-1">', self.html)
        self.assertIn('<h1 id="pageTitle" tabindex="-1">', self.html)
        self.assertIn('aria-controls="sidebar" aria-expanded="false"', self.html)
        # Drawers are modal dialogs and inert while closed (never aria-hidden
        # around focusable controls).
        for drawer in ["jobDrawer", "evidenceDrawer"]:
            with self.subTest(drawer=drawer):
                tag = re.search(r'<aside[^>]*id="' + drawer + r'"[^>]*>', self.html)
                assert tag is not None
                self.assertIn('role="dialog"', tag.group(0))
                self.assertIn('aria-modal="true"', tag.group(0))
                self.assertIn(" inert", tag.group(0))
                self.assertNotIn("aria-hidden", tag.group(0))
        self.assertIn('<div class="toast" id="toast" role="status" aria-live="polite"', self.html)
        scripts = re.findall(r'<script src="([^"]+)"', self.html)
        self.assertEqual(scripts[0], "/js/a11y.js")
        self.assertIn('href="/css/a11y.css"', self.html)

    def test_primary_button_fill_meets_text_contrast(self) -> None:
        def luminance(hex_color: str) -> float:
            channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        css = (STATIC / "css" / "a11y.css").read_text(encoding="utf-8")
        tokens = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
        fill = re.search(r"--accent-fill: (#[0-9a-fA-F]{6});", css)
        text = re.search(r"--text-primary: (#[0-9a-fA-F]{6});", tokens)
        assert fill is not None and text is not None
        light, dark = sorted([luminance(text.group(1)), luminance(fill.group(1))], reverse=True)
        self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5)
        self.assertIn("button,\n.button-link { background: var(--accent-fill); }", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_app_does_not_hide_focusable_drawers_with_aria_hidden(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('Drawer.setAttribute("aria-hidden"', script)
        self.assertNotIn('behavior: "smooth"', script)

    def test_craft_consistency(self) -> None:
        # Step navigation uses one tab style on every gate page.
        for module in ["gate-reviews.js", "produce.js", "packaging.js"]:
            with self.subTest(module=module):
                script = (STATIC / "js" / module).read_text(encoding="utf-8")
                self.assertIn('class="pw-tab', script)
                self.assertNotIn('class="inbox-tab', script)
        # Buttons have one base size; empty states have one style.
        legacy = (STATIC / "styles.css").read_text(encoding="utf-8")
        button = legacy.split("\nbutton,\n.button-link {", 1)[1].split("}", 1)[0]
        self.assertIn("font-size: var(--text-sm);", button)
        empty = legacy.split("\n.empty-state {", 1)[1].split("}", 1)[0]
        self.assertIn("font-size: var(--text-sm);", empty)
        self.assertIn("grid-column: 1 / -1;", empty)
        # The retired page name is not shown anywhere.
        sources = [self.html, (STATIC / "app.js").read_text(encoding="utf-8")]
        sources.append((Path(server.__file__)).read_text(encoding="utf-8"))
        for text in sources:
            self.assertNotIn("Analyze & Create", text)
            self.assertNotIn("Analyze &amp; Create", text)

    def test_web_interface_guidelines_contract(self) -> None:
        sources = {"index.html": self.html}
        for name in ["app.js", "js/command-center.js", "js/gate-reviews.js", "js/opportunity-review.js",
                     "js/packaging.js", "js/produce.js", "js/production-workspace.js", "js/radar.js"]:
            sources[name] = (STATIC / name).read_text(encoding="utf-8")
        # Links are links: nothing that navigates is a <button>.
        for name, text in sources.items():
            with self.subTest(source=name):
                self.assertIsNone(re.search(r"<button[^>]*data-route=", text))
        self.assertGreaterEqual(sum(text.count('class="button-link') for text in sources.values()), 40)
        app = sources["app.js"]
        self.assertIn('routeTarget.tagName === "A" && (event.metaKey || event.ctrlKey', app)
        # Never transition: all (a bare duration animates every property).
        for name in ["styles.css", "css/shell.css", "css/a11y.css", "css/tokens.css"]:
            css = (STATIC / name).read_text(encoding="utf-8")
            with self.subTest(css=name):
                self.assertIsNone(re.search(r"transition:\s*(all\b|[.0-9])", css))
        a11y = (STATIC / "css" / "a11y.css").read_text(encoding="utf-8")
        for rule in ["overscroll-behavior: contain", "touch-action: manipulation", "min-height: 44px",
                     "textarea { font-size: 16px; }", "select { background-color:"]:
            with self.subTest(rule=rule):
                self.assertIn(rule, a11y)
        self.assertIn('<meta name="theme-color" content="#0d1117">', self.html)
        # Placeholders that describe (not exemplify) end with an ellipsis.
        self.assertIn('placeholder="What made you think of it…"', self.html)
        self.assertIn('placeholder="What caught your eye…"', self.html)
        # Unsaved review notes warn before the tab closes.
        workspace = (STATIC / "js" / "review-workspace.js").read_text(encoding="utf-8")
        self.assertIn('window.addEventListener("beforeunload"', workspace)
        # Inbox tabs are deep-linkable.
        self.assertIn('history.replaceState({}, "", "/opportunity#" + subroute)', app)

    def test_every_app_route_has_a_view(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        for route in server.APP_ROUTES:
            with self.subTest(route=route):
                match = re.search(r'"' + re.escape(route) + r'": \{\s*view: "([a-z-]+)"', script)
                self.assertIsNotNone(match, route)
                assert match is not None
                self.assertIn(f'data-view="{match.group(1)}"', self.html)

    def test_modules_load_before_app_js(self) -> None:
        scripts = re.findall(r'<script src="([^"]+)"', self.html)
        self.assertEqual(scripts[-1], "/app.js")
        for module in ["/js/review-workspace.js", "/js/opportunity-review.js", "/js/radar.js"]:
            self.assertIn(module, scripts)
        self.assertLess(
            scripts.index("/js/review-workspace.js"), scripts.index("/js/opportunity-review.js")
        )

    def test_nav_routes_are_app_routes(self) -> None:
        for route in set(re.findall(r'data-route="([^"]+)"', self.html)):
            with self.subTest(route=route):
                self.assertIn(route, server.APP_ROUTES)

    def test_legacy_variables_alias_semantic_tokens(self) -> None:
        tokens = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
        legacy = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn(":root {\n  --bg:", legacy)
        used = set(re.findall(r"var\((--[a-z0-9-]+)\)", legacy))
        defined = set(re.findall(r"(--[a-z0-9-]+):", tokens))
        self.assertEqual(sorted(used - defined), [])


if __name__ == "__main__":
    unittest.main()
