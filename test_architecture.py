"""Architecture guard tests (D-114).

These pin the rules that make module names stable:
- every code folder is a regular package;
- modules import siblings by package-qualified name, never by bare file name;
- nothing changes sys.path except fair_bridge.py (external FAIR repository);
- every Experiment UI action starts its step with ``python -m`` from the
  project root, and the module it names exists.

Run from the project root:  python -m unittest test_architecture
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".github", ".venv", "__pycache__", "output", "archive"}
# Loads the external FAIR repository; the only sanctioned sys.path change.
SYS_PATH_ALLOWED = {Path("experiment_02_analysis/fair_bridge.py")}
POWERSHELL_ACTIONS_DIR = "scripts/"


def code_packages() -> list[Path]:
    return sorted(
        path
        for path in PROJECT_ROOT.iterdir()
        if path.is_dir()
        and path.name not in SKIP_DIRS
        and not path.name.startswith(".")
        and any(path.glob("*.py"))
    )


def python_files() -> list[Path]:
    files = [path for path in PROJECT_ROOT.glob("*.py")]
    for package in code_packages():
        files.extend(
            path
            for path in package.rglob("*.py")
            if not SKIP_DIRS.intersection(path.relative_to(PROJECT_ROOT).parts)
        )
    return sorted(files)


def module_stems_by_package() -> dict[str, str]:
    stems: dict[str, str] = {}
    for package in code_packages():
        for path in package.glob("*.py"):
            if path.stem != "__init__":
                stems[path.stem] = package.name
    return stems


def is_sys_path(node: ast.AST) -> bool:
    return ast.unparse(node) == "sys.path" if isinstance(node, ast.Attribute) else False


class ArchitectureGuardTests(unittest.TestCase):
    def test_every_code_folder_is_a_regular_package(self) -> None:
        missing = [
            package.name
            for package in code_packages()
            if not (package / "__init__.py").exists()
        ]
        self.assertEqual(
            missing,
            [],
            "folders with Python code must have __init__.py, or their modules "
            "silently become namespace packages and resolve by path order",
        )

    def test_no_bare_sibling_imports(self) -> None:
        stems = module_stems_by_package()
        packages = {package.name for package in code_packages()}
        offenders: list[str] = []
        for path in python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                for name in names:
                    head = name.split(".")[0]
                    if head in stems and head not in packages:
                        offenders.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                            f"imports {name!r}; use '{stems[head]}.{head}'"
                        )
        self.assertEqual(offenders, [])

    def test_only_fair_bridge_changes_sys_path(self) -> None:
        offenders: list[str] = []
        for path in python_files():
            relative = path.relative_to(PROJECT_ROOT)
            if relative in SYS_PATH_ALLOWED:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mutates = False
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    mutates = is_sys_path(node.func.value) and node.func.attr in {
                        "insert",
                        "append",
                        "extend",
                        "remove",
                        "clear",
                        "pop",
                    }
                elif isinstance(node, (ast.Assign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        base = target.value if isinstance(target, ast.Subscript) else target
                        mutates = mutates or is_sys_path(base)
                if mutates:
                    offenders.append(f"{relative}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_every_ui_action_starts_a_module_from_the_project_root(self) -> None:
        from experiment_ui import server

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
            module = command[2]
            if importlib.util.find_spec(module) is None:
                problems.append(f"{action_id}: module {module!r} not found")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
