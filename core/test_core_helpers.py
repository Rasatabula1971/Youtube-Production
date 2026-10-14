"""Golden tests for the shared helpers in core (D-114).

Stored provenance hashes on disk were produced by the copies these helpers
replaced, so the outputs below must never change. The expected digests were
taken from the replaced copies and cross-checked with `sha256sum`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core import model_bridge, source_overlap
from core.hashing import canonical_sha256, sha256_file, sha256_text
from core.jsonio import load_json, load_json_or_exit
from core.slugs import safe_slug

# Derived from this file's location, not from core's own PROJECT_ROOT, so a
# wrong pin in core cannot hide itself.
REPO_ROOT = Path(__file__).resolve().parent.parent
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class HashingGoldenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_sha256_file(self) -> None:
        self.assertEqual(sha256_file(self.write("empty", b"")), EMPTY_SHA256)
        self.assertEqual(
            sha256_file(self.write("abc", b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )
        # Larger than the 1 MiB read chunk, so the chunk boundary is crossed.
        big = bytes((i * 31 + 7) % 251 for i in range(2 * 1024 * 1024 + 123))
        self.assertEqual(
            sha256_file(self.write("big", big)),
            "3b2fef82bab6c1589d8a2b2c7e6171ca1934596f36063aedf8c3a456bd399cdf",
        )

    def test_sha256_file_accepts_a_string_path(self) -> None:
        path = self.write("abc", b"abc")
        self.assertEqual(sha256_file(str(path)), sha256_file(path))

    def test_sha256_file_missing(self) -> None:
        with self.assertRaises(FileNotFoundError):
            sha256_file(self.root / "missing")

    def test_sha256_file_directory_is_not_reported_missing(self) -> None:
        # IsADirectoryError on Linux, PermissionError on Windows; never "missing".
        with self.assertRaises(OSError) as caught:
            sha256_file(self.root)
        self.assertNotIsInstance(caught.exception, FileNotFoundError)

    def test_canonical_sha256(self) -> None:
        cases = [
            ({}, "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
            (
                {"b": 1, "a": [1, 2, {"é": "ü"}]},
                "e06d8d50b6488ddf658590fccefb22ccbaf2b7570c4dc219edf10283182107a0",
            ),
            (
                {"x": 0.1, "y": 1.0, "n": None, "t": True},
                "796d8645da6dfab44aef608a1d95b150bb4ed44a63f6429e63dd801c976d1a33",
            ),
            (
                [3.0, "text", {"z": 1, "a": 2}],
                "38eaf5b10f02f01c0a7ded7e6c30e72a95b886542f2b89cd070ddc45e6ab1b60",
            ),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(canonical_sha256(value), expected)

    def test_canonical_sha256_ignores_key_order(self) -> None:
        self.assertEqual(canonical_sha256({"a": 1, "b": 2}), canonical_sha256({"b": 2, "a": 1}))

    def test_sha256_text(self) -> None:
        self.assertEqual(sha256_text(""), EMPTY_SHA256)
        self.assertEqual(
            sha256_text("héllo"),
            "3c48591d8d098a4538f5e013dfcf406e948eac4d3277b10bf614e295d6068179",
        )
        self.assertEqual(
            sha256_text("😀"),
            "f0443a342c5ef54783a111b51ba56c938e474c32324d90c3a60c9c8e3a37e2d9",
        )


class JsonioGoldenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_both_read_valid_json(self) -> None:
        path = self.write("ok.json", '{"é": [1, 2]}')
        self.assertEqual(load_json(path), {"é": [1, 2]})
        self.assertEqual(load_json_or_exit(path), {"é": [1, 2]})

    def test_both_raise_file_not_found_with_the_path(self) -> None:
        missing = self.root / "missing.json"
        for reader in (load_json, load_json_or_exit):
            with self.subTest(reader=reader.__name__):
                with self.assertRaises(FileNotFoundError) as caught:
                    reader(missing)
                self.assertEqual(caught.exception.args, (missing,))

    def test_a_directory_is_not_reported_missing(self) -> None:
        # Kept variants that use is_file() report a directory as missing; these
        # use exists(), so reading it fails with another OSError.
        for reader in (load_json, load_json_or_exit):
            with self.subTest(reader=reader.__name__):
                with self.assertRaises(OSError) as caught:
                    reader(self.root)
                self.assertNotIsInstance(caught.exception, FileNotFoundError)

    def test_load_json_lets_invalid_json_raise(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            load_json(self.write("bad.json", "{not json"))

    def test_load_json_or_exit_exits_with_a_message_on_invalid_json(self) -> None:
        path = self.write("bad.json", "{not json")
        with self.assertRaises(SystemExit) as caught:
            load_json_or_exit(path)
        self.assertTrue(str(caught.exception).startswith(f"Invalid JSON in {path}: "))


class PinnedPathTests(unittest.TestCase):
    """Moving code into core must not move the files and folders it reads."""

    def test_source_overlap_reads_the_same_folder(self) -> None:
        self.assertEqual(
            source_overlap.SOURCE_ROOT,
            REPO_ROOT / "source_acquisition" / "output" / "experiment_02",
        )

    def test_model_bridge_reads_its_files_where_they_were(self) -> None:
        exp2 = REPO_ROOT / "experiment_02_analysis"
        self.assertEqual(model_bridge.RUNNER_CONFIG_FILE, exp2 / "analysis_model_runner_config.json")
        self.assertEqual(model_bridge.FAIR_BRIDGE_FILE, exp2 / "fair_bridge.py")
        self.assertTrue(model_bridge.RUNNER_CONFIG_FILE.is_file())
        self.assertTrue(model_bridge.FAIR_BRIDGE_FILE.is_file())
        self.assertEqual(model_bridge.DEFAULT_FAIR_REPO, REPO_ROOT.parent / "FAIR Free AI Router")
        self.assertEqual(model_bridge.PROJECT_ENV_FILE, REPO_ROOT / ".env")


class SlugGoldenTests(unittest.TestCase):
    def test_safe_slug(self) -> None:
        cases = {
            "gear/ratio": "gear_ratio",
            "gear ratio": "gear_ratio",
            "..x..": "x",
            "": "unknown",
            "._": "unknown",
            "ünïcode café": "ünïcode_café",
            "日本語": "日本語",
            "-lead-": "-lead-",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(safe_slug(value), expected)


if __name__ == "__main__":
    unittest.main()
