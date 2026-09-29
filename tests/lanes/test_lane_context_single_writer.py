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
_SCANNED_DIRS = ("lanes", "orchestrator_api")
_ALLOWED = ("lanes/worktree_allocator.py", "persist_lane_context")


def _save_context_callers() -> list[tuple[str, str]]:
    """Return ``(relative_path, enclosing_function)`` for every ``save_context(...)`` call."""
    found: list[tuple[str, str]] = []
    for sub in _SCANNED_DIRS:
        for path in sorted((_SRC / sub).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for func in ast.walk(tree):
                if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                for node in ast.walk(func):
                    if not isinstance(node, ast.Call):
                        continue
                    callee = node.func
                    name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else ""
                    if name == "save_context":
                        found.append((path.relative_to(_SRC).as_posix(), func.name))
    return sorted(set(found))


def test_persist_lane_context_is_the_only_save_context_caller() -> None:
    assert _save_context_callers() == [_ALLOWED]


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
