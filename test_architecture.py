"""Architecture guard tests (D-114).

These pin the rules that make module names stable:
- every folder that holds Python code is a regular package;
- modules import project code by package-qualified name, never by bare file
  name, statically or through importlib/__import__;
- nothing changes sys.path or PYTHONPATH except fair_bridge.py, which loads
  the external FAIR repository;
- project modules are started with ``python -m`` (fair_bridge.py excepted),
  every Experiment UI action names a real project module with a
  ``__main__`` guard, and the UI starts every action from the project root;
- Windows .bat/.cmd/.ps1 scripts start modules, not .py files.

The checks are static and read the files git tracks (what CI sees), so an
untracked local folder such as a virtualenv never trips them. They are
deliberately strict: a ``*_MODULE`` constant needs a matching ``*_SCRIPT``,
and any "PYTHONPATH" literal or command list naming a ``.py`` file in
non-test code fails. Code that builds names at runtime is outside what a
static check can see.

Run from the project root:  python -m unittest test_architecture
"""

from __future__ import annotations

import ast
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".github", ".venv", "__pycache__", "output", "archive"}
# Loads the external FAIR repository; the only sanctioned sys.path change and
# the only project file still launched by path (it imports only the stdlib).
FAIR_BRIDGE = Path("experiment_02_analysis/fair_bridge.py")
SYS_PATH_MUTATORS = {
    "insert",
    "append",
    "extend",
    "remove",
    "clear",
    "pop",
    "sort",
    "reverse",
    "__setitem__",
    "__delitem__",
    "__iadd__",
}
DYNAMIC_IMPORTS = {"importlib.import_module", "import_module", "__import__"}
PYTHON_EXECUTABLES = {"sys.executable", "python_executable", "str(python_executable)"}
UI_LAUNCHERS = (
    Path("experiment_ui/server.py"),
    Path("experiment_ui/workflow_automation.py"),
)
UI_LAUNCH_CWD = {"PROJECT_ROOT", "control.PROJECT_ROOT"}
POWERSHELL_ACTIONS_DIR = "scripts/"


def _skipped(path: Path) -> bool:
    parts = path.relative_to(PROJECT_ROOT).parts
    return any(part in SKIP_DIRS or part.startswith(".") for part in parts)


def project_files(pattern: str) -> list[Path]:
    """Files tracked by git (what CI sees), so local untracked folders such as
    a virtualenv or personal tools never trip the guards. Falls back to the
    working tree when this is not a git checkout."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", pattern],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        paths = [PROJECT_ROOT / name for name in listed.split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        paths = list(PROJECT_ROOT.rglob(pattern))
    return sorted(path for path in paths if path.is_file() and not _skipped(path))


def code_folders() -> list[Path]:
    """Every folder (at any depth) that directly holds Python files."""
    folders = {
        path.parent
        for path in project_files("*.py")
        if path.parent != PROJECT_ROOT
    }
    return sorted(folders)


def top_level_packages() -> set[str]:
    return {
        folder.relative_to(PROJECT_ROOT).parts[0] for folder in code_folders()
    }


def python_files(*, include_tests: bool = True) -> list[Path]:
    return [
        path
        for path in project_files("*.py")
        if include_tests or not path.name.startswith("test_")
    ]


def module_stems() -> dict[str, str]:
    """Bare module file name -> the package it lives in."""
    stems: dict[str, str] = {}
    for package in sorted(top_level_packages()):
        for path in (PROJECT_ROOT / package).glob("*.py"):
            if path.stem != "__init__":
                stems[path.stem] = package
    return stems


def package_exports(package: str) -> set[str]:
    """Names `from <package> import name` may use: submodules plus anything
    the package's __init__.py defines or imports."""
    folder = PROJECT_ROOT / package
    names = {path.stem for path in folder.glob("*.py") if path.stem != "__init__"}
    init = folder / "__init__.py"
    if not init.exists():  # reported by test_every_code_folder_is_a_regular_package
        return names
    tree = ast.parse(init.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def relative(path: Path) -> Path:
    return path.relative_to(PROJECT_ROOT)


class _SysPathAliases:
    """Names that refer to `sys` or to `sys.path` in one module."""

    def __init__(self, tree: ast.Module) -> None:
        self.sys_names = {"sys"}
        self.path_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sys":
                        self.sys_names.add(alias.asname or "sys")
            elif isinstance(node, ast.ImportFrom) and node.module == "sys":
                for alias in node.names:
                    if alias.name == "path":
                        self.path_names.add(alias.asname or "path")
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and self.is_path(node.value):
                self.path_names.update(
                    t.id for t in node.targets if isinstance(t, ast.Name)
                )

    def is_path(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Attribute) and node.attr == "path":
            return isinstance(node.value, ast.Name) and node.value.id in self.sys_names
        return isinstance(node, ast.Name) and node.id in self.path_names


def sys_path_changes(tree: ast.Module) -> list[int]:
    aliases = _SysPathAliases(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in SYS_PATH_MUTATORS and aliases.is_path(node.func.value):
                lines.append(node.lineno)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.Delete):
                targets = node.targets
            else:
                targets = [node.target]
            for target in targets:
                base = target.value if isinstance(target, ast.Subscript) else target
                if aliases.is_path(base):
                    lines.append(node.lineno)
        elif isinstance(node, ast.Constant) and node.value == "PYTHONPATH":
            lines.append(node.lineno)
    return lines


def has_main_guard(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.If)
        and ast.unparse(node.test).replace("'", '"') == '__name__ == "__main__"'
        for node in tree.body
    )


def script_launches(tree: ast.Module) -> list[tuple[int, str]]:
    """Command lists that start a project file by path instead of `-m`."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List) or not node.elts:
            continue
        rendered = [ast.unparse(element) for element in node.elts]
        if any("FAIR_BRIDGE_FILE" in part for part in rendered):
            continue
        by_path = any(
            isinstance(element, ast.Constant)
            and isinstance(element.value, str)
            and element.value.endswith(".py")
            for element in node.elts
        ) or any("_SCRIPT)" in part or part.endswith("_SCRIPT") for part in rendered)
        python_without_m = rendered[0] in PYTHON_EXECUTABLES and (
            len(rendered) < 2 or rendered[1] != "'-m'"
        )
        if by_path or python_without_m:
            found.append((node.lineno, "[" + ", ".join(rendered[:3]) + ", ...]"))
    return found


class ArchitectureGuardTests(unittest.TestCase):
    def test_guards_scan_a_non_empty_project(self) -> None:
        from experiment_ui import server

        self.assertGreater(len(code_folders()), 0)
        self.assertGreater(len(python_files(include_tests=False)), 0)
        self.assertGreater(len(server.ACTION_DEFS), 0)

    def test_windows_scripts_start_modules_not_files(self) -> None:
        offenders = [
            f"{relative(path)}:{number}: {line.strip()}"
            for pattern in ("*.bat", "*.cmd", "*.ps1")
            for path in project_files(pattern)
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if re.search(r"\.py\b", line) and "fair_bridge" not in line
        ]
        self.assertEqual(offenders, [])

    def test_every_code_folder_is_a_regular_package(self) -> None:
        required: set[Path] = set()
        for folder in code_folders():
            # The folder and every parent below the project root.
            current = folder
            while current != PROJECT_ROOT:
                required.add(current)
                current = current.parent
        missing = sorted(
            str(relative(folder))
            for folder in required
            if not (folder / "__init__.py").exists()
        )
        self.assertEqual(
            missing,
            [],
            "folders with Python code must have __init__.py, or their modules "
            "silently become namespace packages and resolve by path order",
        )

    def test_no_bare_or_dynamic_bare_imports(self) -> None:
        stems = module_stems()
        packages = top_level_packages()
        exports = {package: package_exports(package) for package in packages}
        offenders: list[str] = []

        def check(path: Path, line: int, name: str) -> None:
            head = name.split(".")[0]
            if head in stems and head not in packages:
                offenders.append(
                    f"{relative(path)}:{line} imports {name!r}; "
                    f"use '{stems[head]}.{head}'"
                )

        for path in python_files():
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        check(path, node.lineno, alias.name)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    check(path, node.lineno, node.module)
                    if node.module in packages:
                        for alias in node.names:
                            if alias.name not in exports[node.module]:
                                offenders.append(
                                    f"{relative(path)}:{node.lineno} "
                                    f"'from {node.module} import {alias.name}': "
                                    f"{alias.name!r} is not a submodule of {node.module}"
                                )
                elif (
                    isinstance(node, ast.Call)
                    and ast.unparse(node.func) in DYNAMIC_IMPORTS
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    check(path, node.lineno, node.args[0].value)
        self.assertEqual(offenders, [])

    def test_only_fair_bridge_changes_the_import_path(self) -> None:
        this_file = relative(Path(__file__).resolve())  # names "PYTHONPATH" itself
        offenders = [
            f"{relative(path)}:{line}"
            for path in python_files()
            if relative(path) not in {FAIR_BRIDGE, this_file}
            for line in sys_path_changes(parse(path))
        ]
        self.assertEqual(offenders, [], "sys.path / PYTHONPATH changes")

    def test_project_modules_are_launched_with_dash_m(self) -> None:
        offenders = [
            f"{relative(path)}:{line} {command}"
            for path in python_files(include_tests=False)
            for line, command in script_launches(parse(path))
        ]
        self.assertEqual(offenders, [])

    def test_launch_module_constants_match_their_script_files(self) -> None:
        checked = 0
        problems: list[str] = []
        for path in python_files(include_tests=False):
            names = [
                target.id
                for node in parse(path).body
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name) and target.id.endswith("_MODULE")
            ]
            if not names:
                continue
            module_name = ".".join(relative(path).with_suffix("").parts)
            module = importlib.import_module(module_name)
            for name in names:
                checked += 1
                launched = getattr(module, name)
                script = getattr(module, name.removesuffix("_MODULE") + "_SCRIPT", None)
                if script is None:
                    problems.append(f"{module_name}.{name}: no matching *_SCRIPT")
                    continue
                expected = ".".join(Path(script).relative_to(PROJECT_ROOT).with_suffix("").parts)
                if launched != expected:
                    problems.append(f"{module_name}.{name} = {launched!r}, file is {expected!r}")
                target = importlib.import_module(launched)
                if not has_main_guard(parse(Path(str(target.__file__)))):
                    problems.append(f"{launched} has no __main__ guard")
        self.assertEqual(problems, [])
        self.assertGreater(checked, 0)

    def test_every_ui_action_starts_a_project_module(self) -> None:
        from experiment_ui import server

        packages = top_level_packages()
        problems: list[str] = []
        for action_id, action in server.ACTION_DEFS.items():
            command = [str(part) for part in action["command"]]
            if command[0] == "powershell.exe":
                scripts = [part for part in command if part.endswith(".ps1")]
                if len(scripts) != 1 or not scripts[0].startswith(POWERSHELL_ACTIONS_DIR):
                    problems.append(f"{action_id}: unexpected PowerShell command")
                continue
            if command[0] != sys.executable or len(command) < 3 or command[1] != "-m":
                problems.append(f"{action_id}: must be [sys.executable, '-m', module, ...]")
                continue
            module_name = command[2]
            if module_name.split(".")[0] not in packages:
                problems.append(f"{action_id}: {module_name!r} is not a project module")
                continue
            module = importlib.import_module(module_name)
            if not has_main_guard(parse(Path(str(module.__file__)))):
                problems.append(f"{action_id}: {module_name} has no __main__ guard")
        self.assertEqual(problems, [])

    def test_ui_starts_actions_from_the_project_root(self) -> None:
        problems: list[str] = []
        for launcher in UI_LAUNCHERS:
            launches = 0
            for node in ast.walk(parse(PROJECT_ROOT / launcher)):
                if not (
                    isinstance(node, ast.Call)
                    and node.args
                    and ast.unparse(node.args[0]).replace("'", '"') == 'action["command"]'
                    and ast.unparse(node.func).startswith("subprocess.")
                ):
                    continue
                launches += 1
                cwd = {k.arg: ast.unparse(k.value) for k in node.keywords}.get("cwd")
                if cwd not in UI_LAUNCH_CWD:
                    problems.append(f"{launcher}:{node.lineno} cwd={cwd}")
            if launches == 0:
                problems.append(f"{launcher}: no action launch found (guard is stale)")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
