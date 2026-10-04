"""Keep UI tests away from the real pipeline outputs on a working machine.

The server resolves ~90 artifact paths at import time (under the various
``output/`` folders and ``.experiment_ui``). On a laptop that has run the
pipeline, those folders hold real study sets, profiles and reviews, and a test
that patches only the paths it sets up still reads the others: patching a
parent folder does not move a child constant that was already resolved.

``isolate_outputs`` points every such constant at an empty mirror inside a
temporary directory for the duration of one test. Tests that need a specific
artifact still patch that constant themselves (an inner patch wins).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


def output_constants(module) -> dict[str, Path]:
    """Module-level Path constants that point into generated output."""
    root = Path(module.PROJECT_ROOT).resolve()
    found: dict[str, Path] = {}
    for name in dir(module):
        value = getattr(module, name)
        if not name.isupper() or not isinstance(value, Path):
            continue
        try:
            relative = value.resolve().relative_to(root)
        except ValueError:
            continue
        if "output" in relative.parts or relative.parts[:1] == (".experiment_ui",):
            found[name] = relative
    return found


def isolate_outputs(test: unittest.TestCase, module) -> Path:
    """Redirect ``module``'s output paths to a fresh empty tree; returns its root."""
    temporary = tempfile.TemporaryDirectory()
    test.addCleanup(temporary.cleanup)
    mirror = Path(temporary.name)
    for name, relative in output_constants(module).items():
        patcher = mock.patch.object(module, name, mirror / relative)
        patcher.start()
        test.addCleanup(patcher.stop)
    return mirror


class ModuleIsolation:
    """Module-wide variant for ``setUpModule``/``tearDownModule``.

    One empty mirror is shared by the tests of a module; per-test fixtures that
    patch their own paths are unaffected.
    """

    def __init__(self, module) -> None:
        self.module = module
        self.temporary: tempfile.TemporaryDirectory | None = None
        self.patchers: list = []

    def start(self) -> Path:
        self.temporary = tempfile.TemporaryDirectory()
        mirror = Path(self.temporary.name)
        for name, relative in output_constants(self.module).items():
            patcher = mock.patch.object(self.module, name, mirror / relative)
            patcher.start()
            self.patchers.append(patcher)
        return mirror

    def stop(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.patchers.clear()
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None
