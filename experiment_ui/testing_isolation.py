"""Keep UI tests away from the real pipeline outputs on a working machine.

The server and the engine modules it imports resolve their artifact paths at
import time (under the various ``output/`` folders and ``.experiment_ui``). On
a laptop that has run the pipeline, those folders hold real study sets,
profiles, frames and reviews, and a test that patches only the paths it sets
up still reads the others: patching a parent folder does not move a child
constant that was already resolved.

The helpers point every such constant, in the given module and in every other
loaded project module, at an empty mirror inside a temporary directory. Tests
that need a specific artifact still patch that constant themselves (an inner
patch wins).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock


def output_constants(module: ModuleType, root: Path) -> dict[str, Path]:
    """Module-level Path constants of ``module`` that point into generated output."""
    found: dict[str, Path] = {}
    for name, value in list(vars(module).items()):
        if not name.isupper() or not isinstance(value, Path):
            continue
        try:
            relative = value.resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        if "output" in relative.parts or relative.parts[:1] == (".experiment_ui",):
            found[name] = relative
    return found


def project_modules(root: Path) -> list[ModuleType]:
    """Loaded modules whose source file lives inside the repository."""
    modules = []
    for module in list(sys.modules.values()):
        source = getattr(module, "__file__", None)
        if not source:
            continue
        try:
            Path(source).resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        modules.append(module)
    return modules


def _patchers(module: ModuleType, mirror: Path) -> list[Any]:
    root = Path(module.PROJECT_ROOT).resolve()
    patchers = []
    for target in project_modules(root):
        for name, relative in output_constants(target, root).items():
            patchers.append(mock.patch.object(target, name, mirror / relative))
    return patchers


def isolate_outputs(test: unittest.TestCase, module: ModuleType) -> Path:
    """Redirect every project output path to a fresh empty tree; returns its root."""
    temporary = tempfile.TemporaryDirectory()
    test.addCleanup(temporary.cleanup)
    mirror = Path(temporary.name)
    for patcher in _patchers(module, mirror):
        patcher.start()
        test.addCleanup(patcher.stop)
    return mirror


class ModuleIsolation:
    """Module-wide variant for ``setUpModule``/``tearDownModule``.

    One empty mirror is shared by the tests of a module; per-test fixtures that
    patch their own paths are unaffected.
    """

    def __init__(self, module: ModuleType) -> None:
        self.module = module
        self.temporary: tempfile.TemporaryDirectory | None = None
        self.patchers: list[Any] = []

    def start(self) -> Path:
        self.temporary = tempfile.TemporaryDirectory()
        mirror = Path(self.temporary.name)
        self.patchers = _patchers(self.module, mirror)
        for patcher in self.patchers:
            patcher.start()
        return mirror

    def stop(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.patchers.clear()
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None
