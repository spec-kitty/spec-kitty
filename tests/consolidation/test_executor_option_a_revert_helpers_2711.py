"""Focused unit coverage for the #2711 coordination-checkpoint helpers (executor.py).

Pins the fast no-op / early-return branches a coord-topology merge never reaches:
``_coord_worktree_root`` (no events path, not under ``.worktrees``) and
``_capture_pre_target_coord_ref_sha`` (unresolvable placement, resolved tip).

History: this module also unit-tested ``_revert_coord_done_commit``, the
forward ``git revert`` of the committed coordination ``done``. That helper was
retired with #5385: the single rollback door (``executor._report_rollback`` ->
``rollback.rollback_to_snapshot``) now restores the coordination branch, and
``tests/consolidation/test_single_rollback_authority.py`` forbids its return.

The ``run`` argument is a light ``SimpleNamespace`` stand-in: each helper reads
only a handful of ``_MergeRunState`` attributes (test-scaffolding-as-design-smell
-- the pure seams take their inputs off a plain object). mypy checks this test
with ``follow_imports = skip`` for ``specify_cli.*`` (pyproject test override), so
the helpers collapse to ``Any`` and accept the stand-in.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (see #2711 harness)

from specify_cli.consolidation import executor
from specify_cli.consolidation.executor import (
    _capture_pre_target_coord_ref_sha,
    _coord_worktree_root,
)

pytestmark = pytest.mark.fast

_CAPTURED_SHA = "f76bd91297db0000000000000000000000000000"

# ---------------------------------------------------------------------------
# _coord_worktree_root (lines 448-455)
# ---------------------------------------------------------------------------


def test_coord_worktree_root_none_when_no_events_path() -> None:
    run = SimpleNamespace(canonical_events_path=None)
    assert _coord_worktree_root(run) is None


def test_coord_worktree_root_none_when_not_under_worktrees(tmp_path: Path) -> None:
    events = tmp_path / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    run = SimpleNamespace(canonical_events_path=events)
    assert _coord_worktree_root(run) is None


def test_coord_worktree_root_strips_to_worktree_root(tmp_path: Path) -> None:
    worktree = tmp_path / ".worktrees" / "slug-01ab"
    events = worktree / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    run = SimpleNamespace(canonical_events_path=events)
    assert _coord_worktree_root(run) == worktree


# ---------------------------------------------------------------------------
# _capture_pre_target_coord_ref_sha (lines 423-437)
# ---------------------------------------------------------------------------


def test_capture_skips_on_unresolvable_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    """A placement that cannot resolve (non-coord / legacy) leaves both fields None."""

    def _raise(*_a: object, **_k: object) -> object:
        raise RuntimeError("no placement")

    monkeypatch.setattr(executor, "resolve_placement_only", _raise)
    run = SimpleNamespace(
        main_repo=Path("/repo"),
        mission_slug="slug-01ab",
        pre_target_coord_ref=None,
        pre_target_coord_sha=None,
    )
    _capture_pre_target_coord_ref_sha(run)
    assert run.pre_target_coord_ref is None
    assert run.pre_target_coord_sha is None


def test_capture_records_ref_and_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolvable coord ref whose tip resolves records both fields."""
    monkeypatch.setattr(
        executor,
        "resolve_placement_only",
        lambda *_a, **_k: SimpleNamespace(ref="kitty/mission-x"),
    )
    monkeypatch.setattr(
        executor, "run_command", lambda *_a, **_k: (0, _CAPTURED_SHA + "\n", "")
    )
    run = SimpleNamespace(
        main_repo=Path("/repo"),
        mission_slug="slug-01ab",
        pre_target_coord_ref=None,
        pre_target_coord_sha=None,
    )
    _capture_pre_target_coord_ref_sha(run)
    assert run.pre_target_coord_ref == "kitty/mission-x"
    assert run.pre_target_coord_sha == _CAPTURED_SHA
