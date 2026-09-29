"""FR-022 (#5100): the lane allocator module is the single lane-context writer.

Every lane allocation path (implement, orchestrator API, crash recovery)
persists the lane ``WorkspaceContext`` through
``worktree_allocator.persist_lane_context`` -- the ONE call site of
``save_context`` under ``lanes/`` and ``orchestrator_api/``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli
from specify_cli.workspace.context import WorkspaceContext, save_context

pytestmark = pytest.mark.fast

_SRC = Path(specify_cli.__file__).parent
# The lane-context writer lives in specify_cli.workspace.context; the unrelated
# specify_cli.context.store.save_context (mission context tokens) must NOT count.
_WORKSPACE_MODULES = frozenset({"specify_cli.workspace", "specify_cli.workspace.context"})
_WRITER = "save_context"
_ALLOWED = ("specify_cli.lanes.worktree_allocator", "persist_lane_context")
_MODULE_LEVEL = "<module>"


def _module_name(path: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(_SRC.parent).with_suffix("").parts)
    is_init = parts[-1] == "__init__"
    return ".".join(parts[:-1] if is_init else parts), is_init


def _absolute_from(node: ast.ImportFrom, module: str, is_init: bool) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".") if is_init else module.split(".")[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


def _bindings(tree: ast.AST, module: str, is_init: bool) -> tuple[set[str], dict[str, str]]:
    """Names bound to the workspace ``save_context`` and aliases bound to workspace modules."""
    funcs: set[str] = set()
    mods: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = _absolute_from(node, module, is_init)
            for alias in node.names:
                bound = alias.asname or alias.name
                if source in _WORKSPACE_MODULES and alias.name in (_WRITER, "*"):
                    funcs.add(bound if alias.name != "*" else _WRITER)
                elif source in _WORKSPACE_MODULES and alias.name == "context":
                    mods[bound] = "specify_cli.workspace.context"
                elif source == "specify_cli" and alias.name == "workspace":
                    mods[bound] = "specify_cli.workspace"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name in _WORKSPACE_MODULES:
                    mods[alias.asname] = alias.name
    for node in ast.walk(tree):  # simple re-binding: ``sc = save_context``
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in funcs:
            funcs.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return funcs, mods


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


class _CallFinder(ast.NodeVisitor):
    def __init__(self, funcs: set[str], mods: dict[str, str]) -> None:
        self.funcs = funcs
        self.mods = mods
        self.stack: list[str] = []
        self.hits: list[str] = []

    def _enter(self, node: ast.AST, name: str) -> None:
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_writer(node.func):
            self.hits.append(self.stack[-1] if self.stack else _MODULE_LEVEL)
        self.generic_visit(node)

    def _is_writer(self, func: ast.expr) -> bool:
        if isinstance(func, ast.Name):
            return func.id in self.funcs
        if isinstance(func, ast.Attribute) and func.attr == _WRITER:
            owner = _dotted(func.value)
            if owner is None:
                return False
            head, _, rest = owner.partition(".")
            resolved = self.mods.get(head, head) + (f".{rest}" if rest else "")
            return resolved in _WORKSPACE_MODULES
        return False


def _writer_calls(source: str, module: str, is_init: bool = False) -> list[str]:
    """Enclosing-function names of every call to the workspace ``save_context`` in *source*."""
    tree = ast.parse(source)
    funcs, mods = _bindings(tree, module, is_init)
    finder = _CallFinder(funcs, mods)
    finder.visit(tree)
    return finder.hits


def _save_context_callers() -> list[tuple[str, str]]:
    """Return ``(module, enclosing_function)`` for every workspace ``save_context`` call in ``src/specify_cli``."""
    found: set[tuple[str, str]] = set()
    for path in sorted(_SRC.rglob("*.py")):
        module, is_init = _module_name(path)
        for name in _writer_calls(path.read_text(encoding="utf-8"), module, is_init):
            found.add((module, name))
    return sorted(found)


def test_persist_lane_context_is_the_only_save_context_caller() -> None:
    assert _save_context_callers() == [_ALLOWED]


@pytest.mark.parametrize(
    "source",
    [
        "from specify_cli.workspace.context import save_context as sc\ndef f():\n    sc(1, 2)\n",
        "from specify_cli.workspace import save_context\ndef f():\n    save_context(1, 2)\n",
        "from specify_cli.workspace.context import save_context\nsave_context(1, 2)\n",
        "from specify_cli.workspace import context as workspace_context\ndef f():\n    workspace_context.save_context(1, 2)\n",
        "import specify_cli.workspace.context as wc\ndef f():\n    wc.save_context(1, 2)\n",
        "import specify_cli.workspace.context\ndef f():\n    specify_cli.workspace.context.save_context(1, 2)\n",
        "from specify_cli import workspace\ndef f():\n    workspace.save_context(1, 2)\n",
        "from specify_cli.workspace.context import save_context\nsc = save_context\ndef f():\n    sc(1, 2)\n",
    ],
)
def test_scanner_detects_writer_call_forms(source: str) -> None:
    assert _writer_calls(source, "specify_cli.cli.commands.implement") != []


def test_scanner_resolves_relative_import_and_module_level_call() -> None:
    src = "from .context import save_context\nsave_context(1, 2)\n"
    assert _writer_calls(src, "specify_cli.workspace.other") == [_MODULE_LEVEL]


def test_scanner_ignores_the_unrelated_mission_context_save_context() -> None:
    src = (
        "from specify_cli.context.store import save_context\n"
        "from specify_cli.context import store\n"
        "def f():\n    save_context(1, 2)\n    store.save_context(1, 2)\n"
    )
    assert _writer_calls(src, "specify_cli.cli.commands.x") == []


def _context() -> WorkspaceContext:
    return WorkspaceContext(
        wp_id="WP01",
        mission_slug="083-a",
        worktree_path=".worktrees/083-a-lane-a",
        branch_name="kitty/mission-083-a-lane-a",
        base_branch="main",
        base_commit="0" * 40,
        dependencies=[],
        created_at="2026-09-29T00:00:00+00:00",
        created_by="test",
        vcs_backend="git",
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
        current_wp="WP01",
    )


def test_persist_lane_context_writes_what_save_context_writes(tmp_path: Path) -> None:
    from specify_cli.lanes.worktree_allocator import persist_lane_context

    direct_root = tmp_path / "direct"
    seam_root = tmp_path / "seam"
    direct_root.mkdir()
    seam_root.mkdir()

    direct = save_context(direct_root, _context())
    via_seam = persist_lane_context(seam_root, _context())

    assert via_seam.relative_to(seam_root) == direct.relative_to(direct_root)
    assert via_seam.read_bytes() == direct.read_bytes()
