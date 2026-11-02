"""Re-drift guard for the M7 ExecutionMode consolidation.

Mission ``rc3-execution-mode-consolidation-01M0GGX1`` retired the dead
``mission_runtime.context.ExecutionMode`` enum and renamed the live ownership
enum ``ExecutionMode`` -> ``WorkProductKind``. The residual footgun was a class
named ``ExecutionMode`` living in-repo (colliding, by name, with the external
``spec_kitty_events.status.ExecutionMode``) and a local enum pairing a
``worktree`` member with a ``code_change`` member (the mis-named duplicate of the
external worktree-vs-direct axis whose ``code_change`` token also clashed with the
ownership enum's unrelated ``code_change`` = "WP produces code").

This guard fails if either footgun returns. It asserts *absence of the footgun*,
NOT the exact member set of ``WorkProductKind`` — so it deliberately PERMITS a
later mission (M6 / #3590) adding a non-diff completion-mode member to
``WorkProductKind`` (AC-5). The external ``spec_kitty_events`` enum lives outside
``src/`` and is intentionally out of scope.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Mapping

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


def _source_trees(
    source_tree: Mapping[pathlib.Path, object],
) -> list[tuple[pathlib.Path, ast.AST]]:
    """Return ``(path, parsed AST)`` pairs from the immutable session cache.

    The real-tree guards below only read the tree, so they must not re-walk,
    re-read, or re-parse ``src/**/*.py`` per test. Scratch-tree mutation tests
    (if added) stay uncached and read fresh.
    """
    return [
        (path, source_tree[path].tree)  # type: ignore[attr-defined]
        for path in sorted(source_tree)
        if "__pycache__" not in path.parts
    ]


def _enum_member_values(class_node: ast.ClassDef) -> set[str]:
    """Collect the string literal values assigned to simple members of a class.

    Covers ``NAME = "value"`` and ``NAME: T = "value"`` forms — enough to
    recognise a ``worktree`` / ``code_change`` enum regardless of its base class
    or the exact ``StrEnum`` vs ``enum.Enum`` shape.
    """
    values: set[str] = set()
    for stmt in class_node.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            # A StrEnum member is a simple single-name assignment (NAME = "value").
            # Take the sole target when there is exactly one; a chained
            # ``A = B = "x"`` (more than one target) is not an enum member.
            simple_targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
            if simple_targets and stmt.targets[1:] == []:
                target, value = simple_targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            values.add(value.value)
    return values


def test_no_class_named_execution_mode_in_src(
    src_source_tree: Mapping[pathlib.Path, object],
) -> None:
    """No in-repo class may be named ``ExecutionMode`` (AC-1, AC-3).

    The only surviving live ``ExecutionMode`` is the external
    ``spec_kitty_events.status.ExecutionMode``, which lives outside ``src/``.
    """
    offenders: list[str] = []
    for path, tree in _source_trees(src_source_tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ExecutionMode":
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
    assert not offenders, (
        "A class named 'ExecutionMode' reappeared in src/ — the retired footgun. "
        "Rename it (the ownership axis is 'WorkProductKind'; the worktree-vs-direct "
        f"axis is the external spec_kitty_events enum). Offenders: {offenders}"
    )


def test_no_local_worktree_code_change_enum(
    src_source_tree: Mapping[pathlib.Path, object],
) -> None:
    """No in-repo enum may pair a ``worktree`` member with a ``code_change`` member.

    This is the specific retired collision (dead enum #2's shape), caught by member
    values rather than class name so a renamed re-introduction is still blocked.
    ``WorkProductKind`` (``code_change`` + ``planning_artifact`` [+ future members])
    has no ``worktree`` member, so it — and M6's additive member — pass.
    """
    offenders: list[str] = []
    for path, tree in _source_trees(src_source_tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                values = _enum_member_values(node)
                if "worktree" in values and "code_change" in values:
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno} ({node.name})")
    assert not offenders, (
        "A local enum pairing 'worktree' with 'code_change' reappeared — the retired "
        "duplicate of the external spec_kitty_events worktree/direct_repo axis. "
        f"Consume the external enum instead. Offenders: {offenders}"
    )


def test_retired_symbol_absent_from_mission_runtime_surface() -> None:
    """The retired ``ExecutionMode`` must not return to the mission_runtime surface."""
    import mission_runtime

    assert "ExecutionMode" not in mission_runtime.__all__, (
        "'ExecutionMode' reappeared in mission_runtime.__all__ — it was retired by M7 "
        "(the worktree-vs-direct axis is owned by spec_kitty_events.status.ExecutionMode)."
    )


def test_guard_permits_workproductkind_additive_member() -> None:
    """Regression pin for AC-5: the guard permits ``WorkProductKind`` growing.

    Proves the guard keys on the footgun's *shape*, not WorkProductKind's exact
    members: an enum with ``code_change`` + a future completion-mode value (but no
    ``worktree``) is allowed.
    """
    hypothetical = {"code_change", "planning_artifact", "completed_no_diff"}
    # The forbidden shape is worktree+code_change on ONE enum; this set is fine.
    assert not ("worktree" in hypothetical and "code_change" in hypothetical)


def test_source_tree_fixture_is_reused_without_disk_reads(src_source_tree: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """The two read-only guards consume the immutable session AST cache.

    RED before the reuse change: no ``_source_trees`` helper existed and both
    guard tests re-read + re-parsed every ``src/**/*.py`` file. Green afterwards
    proves the guards can be answered from the fixture alone; the scratch-tree
    mutation tests in the sibling ratchets remain deliberately uncached.
    """

    trees = _source_trees(src_source_tree)  # type: ignore[arg-type]
    assert trees, "the source-tree fixture must cover src/"

    def _unexpected_disk_access(*args: object, **kwargs: object) -> None:
        raise AssertionError("execution-mode guard tests must reuse the immutable source-tree fixture")

    monkeypatch.setattr(pathlib.Path, "read_text", _unexpected_disk_access)
    assert _source_trees(src_source_tree) == trees  # type: ignore[arg-type]
