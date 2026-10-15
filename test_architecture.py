"""Architecture guard tests (D-175).

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
deliberately strict: a ``*_MODULE`` constant needs a matching path constant
(``<NAME>_SCRIPT``, or ``<NAME>`` itself), a "PYTHONPATH" literal fails unless
it only reads or removes the variable (a comparison, or ``.get``/``.pop``),
and a command list naming a ``.py`` file in non-test code fails. Code that
builds names at runtime is outside what a static check can see.

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

# Helper names core owns. Outside core they may only be defined where the
# behaviour deliberately differs (D-176): these load_json variants handle a
# missing file, invalid JSON or a non-object differently, and thumbnail_render's
# safe_slug is ASCII-only.
CORE_HELPER_NAMES = {
    "sha256_file",
    "file_sha256",
    "canonical_sha256",
    "content_sha256",
    "sha256_text",
    "load_json",
    "load_json_or_exit",
    "safe_slug",
}
KEPT_HELPER_VARIANTS = {
    ("experiment_01_discovery/experiment_01_4.py", "load_json"),
    ("experiment_01_discovery/scheduled_refresh.py", "load_json"),
    ("experiment_02_analysis/fair_bridge.py", "load_json"),
    ("experiment_02_analysis/vision_review.py", "load_json"),
    ("packaging_engine/packaging_brief.py", "load_json"),
    ("research_engine/research_acquisition.py", "load_json"),
    ("source_acquisition/experiment_02_evidence.py", "load_json"),
    ("production_engine/thumbnail_render.py", "safe_slug"),
}

# Normalized shapes (see helper_shape) of every helper copy Task 2 replaced
# with core, plus core's own. A function outside core with one of these shapes
# is a copy that should import from core instead.
REPLACED_HELPER_VARIANTS: dict[str, str] = {
    "def F(a0):\n    return hashlib.sha256(json.dumps(a0, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')).hexdigest()": 'core.hashing.canonical_sha256',
    "def F(a0):\n    v0 = json.dumps(a0, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')\n    return hashlib.sha256(v0).hexdigest()": 'core.hashing.canonical_sha256',
    'def F(a0):\n    return hashlib.sha256(Path(a0).read_bytes()).hexdigest()': 'core.hashing.sha256_file',
    'def F(a0):\n    return hashlib.sha256(a0.read_bytes()).hexdigest()': 'core.hashing.sha256_file',
    "def F(a0):\n    v0 = hashlib.sha256()\n    with Path(a0).open('rb') as v1:\n        for v2 in iter(lambda: v1.read(1024 * 1024), b''):\n            v0.update(v2)\n    return v0.hexdigest()": 'core.hashing.sha256_file',
    "def F(a0):\n    v0 = hashlib.sha256()\n    with a0.open('rb') as v1:\n        for v2 in iter(lambda: v1.read(1024 * 1024), b''):\n            v0.update(v2)\n    return v0.hexdigest()": 'core.hashing.sha256_file',
    "def F(a0):\n    return hashlib.sha256(a0.encode('utf-8')).hexdigest()": 'core.hashing.sha256_text',
    "def F(a0):\n    if not a0.exists():\n        raise FileNotFoundError(a0)\n    return json.loads(a0.read_text(encoding='utf-8'))": 'core.jsonio.load_json',
    "def F(a0):\n    if not a0.exists():\n        raise FileNotFoundError(a0)\n    try:\n        return json.loads(a0.read_text(encoding='utf-8'))\n    except json.JSONDecodeError as exc:\n        raise SystemExit(f'Invalid JSON in {a0}: {exc}') from exc": 'core.jsonio.load_json_or_exit',
    "def F(a0):\n    v0 = ''.join((v1 if v1.isalnum() or v1 in '-_.' else '_' for v1 in a0)).strip('._')\n    return v0 or 'unknown'": 'core.slugs.safe_slug',
}


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


def _pythonpath_reads(tree: ast.Module) -> set[int]:
    """ids of "PYTHONPATH" literals that only read or remove the variable:
    a comparison (`k != "PYTHONPATH"`, `"PYTHONPATH" in env`) or the key of a
    `.get(...)` / `.pop(...)` call. Setting it stays forbidden."""
    reads: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            reads.update(id(part) for part in [node.left, *node.comparators] if isinstance(part, ast.Constant))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "pop"}:
            reads.update(id(arg) for arg in node.args[:1] if isinstance(arg, ast.Constant))
    return reads


def sys_path_changes(tree: ast.Module) -> list[int]:
    aliases = _SysPathAliases(tree)
    pythonpath_reads = _pythonpath_reads(tree)
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
        elif isinstance(node, ast.Constant) and node.value == "PYTHONPATH" and id(node) not in pythonpath_reads:
            lines.append(node.lineno)
    return lines


def helper_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """A function's shape: its source with the name, docstring, annotations,
    parameter and local variable names, and keyword-argument order ignored."""
    clone = ast.parse(ast.unparse(node)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    if ast.get_docstring(clone) is not None:
        clone.body = clone.body[1:] or [ast.Pass()]
    func = ast.FunctionDef(name="F", args=clone.args, body=clone.body, decorator_list=[], returns=None, type_params=[])
    arguments = func.args
    all_args = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    all_args += [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
    rename: dict[str, str] = {}
    for index, arg in enumerate(all_args):
        rename[arg.arg] = f"a{index}"
        arg.annotation = None
    local = 0
    for sub in ast.walk(ast.Module(body=func.body, type_ignores=[])):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store) and sub.id not in rename:
            rename[sub.id] = f"v{local}"
            local += 1

    class Normalize(ast.NodeTransformer):
        def visit_arg(self, node: ast.arg) -> ast.arg:
            node.arg = rename.get(node.arg, node.arg)
            node.annotation = None
            return node

        def visit_Name(self, node: ast.Name) -> ast.Name:
            node.id = rename.get(node.id, node.id)
            return node

        def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
            self.generic_visit(node)
            if node.value is None:
                return ast.Pass()
            return ast.Assign(targets=[node.target], value=node.value)

        def visit_Call(self, node: ast.Call) -> ast.Call:
            self.generic_visit(node)
            node.keywords.sort(key=lambda k: k.arg or "")
            return node

    func = Normalize().visit(func)
    return ast.unparse(ast.fix_missing_locations(func))


def outside_core(path: Path) -> bool:
    return relative(path).parts[0] != "core"


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
        offenders = [
            f"{relative(path)}:{line}"
            for path in python_files()
            if relative(path) != FAIR_BRIDGE
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
                base = name.removesuffix("_MODULE")
                script = getattr(module, base + "_SCRIPT", None) or getattr(module, base, None)
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

    def test_core_imports_only_the_standard_library_and_core(self) -> None:
        offenders: list[str] = []
        core_files = [path for path in python_files() if not outside_core(path)]
        for path in core_files:
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                elif (
                    isinstance(node, ast.Call)
                    and ast.unparse(node.func) in DYNAMIC_IMPORTS
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    names = [node.args[0].value]
                else:
                    continue
                for name in names:
                    head = name.split(".")[0]
                    if head not in sys.stdlib_module_names and head not in {"core", "__future__"}:
                        offenders.append(f"{relative(path)}:{node.lineno} imports {name!r}")
        self.assertGreater(len(core_files), 0)
        self.assertEqual(offenders, [], "core must not import any engine")

    def test_no_copies_of_core_helpers_outside_core(self) -> None:
        offenders = [
            f"{relative(path)}:{node.lineno} {node.name} copies "
            f"{REPLACED_HELPER_VARIANTS[helper_shape(node)]}"
            for path in python_files(include_tests=False)
            if outside_core(path)
            for node in ast.walk(parse(path))  # nested functions and methods too
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and helper_shape(node) in REPLACED_HELPER_VARIANTS
        ]
        self.assertEqual(offenders, [], "import the helper from core instead")

    def test_core_helper_names_are_only_redefined_where_behaviour_differs(self) -> None:
        offenders = [
            f"{relative(path)}:{node.lineno} defines {node.name}"
            for path in python_files(include_tests=False)
            if outside_core(path)
            for node in parse(path).body
            if isinstance(node, ast.FunctionDef)
            and node.name in CORE_HELPER_NAMES
            and (relative(path).as_posix(), node.name) not in KEPT_HELPER_VARIANTS
        ]
        self.assertEqual(
            offenders,
            [],
            "use the core helper, or add the file to KEPT_HELPER_VARIANTS with "
            "the reason its behaviour must differ",
        )


if __name__ == "__main__":
    unittest.main()
