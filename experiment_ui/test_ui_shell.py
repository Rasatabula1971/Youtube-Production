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
