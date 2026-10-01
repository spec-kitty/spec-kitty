"""``finalize-tasks`` lifecycle events land in the canonical status log (#5440).

``_lifecycle_event_dir`` routes ``TasksStarted`` / ``WPCreated`` /
``TasksCompleted`` to the directory the status surface resolves to, and keeps
the primary planning dir whenever that resolution cannot name an existing
directory. The coordination-routed happy path is exercised end to end by
``tests/e2e/test_coord_status_off_target_lifecycle.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mission_runtime import OwnedCheckout

from specify_cli.cli.commands.agent import mission_finalize
from specify_cli.coordination.surface_resolver import ResolvedStatusSurface

pytestmark = [pytest.mark.fast]

_RESOLVER = "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor"


def _resolve_to(surface_dir: Path) -> Callable[..., ResolvedStatusSurface]:
    def _resolve(_repo_root: Path, _mission_slug: str, *, for_write: bool) -> ResolvedStatusSurface:
        assert for_write is True
        return ResolvedStatusSurface(surface_path=surface_dir / "status.events.jsonl", primary_anchor=surface_dir)

    return _resolve


def test_resolved_existing_surface_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planning_dir = tmp_path / "kitty-specs" / "m"
    coord_dir = tmp_path / ".worktrees" / "m-coord" / "kitty-specs" / "m"
    coord_dir.mkdir(parents=True)
    monkeypatch.setattr(_RESOLVER, _resolve_to(coord_dir))

    assert mission_finalize._lifecycle_event_dir(planning_dir, tmp_path, "m", owned=None) == coord_dir


def test_unmaterialized_surface_keeps_planning_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planning_dir = tmp_path / "kitty-specs" / "m"
    monkeypatch.setattr(_RESOLVER, _resolve_to(tmp_path / ".worktrees" / "m-coord" / "kitty-specs" / "m"))

    assert mission_finalize._lifecycle_event_dir(planning_dir, tmp_path, "m", owned=None) == planning_dir


def test_unresolvable_surface_keeps_planning_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planning_dir = tmp_path / "kitty-specs" / "m"

    def _missing_meta(*_args: object, **_kwargs: object) -> ResolvedStatusSurface:
        raise FileNotFoundError("meta.json not found")

    monkeypatch.setattr(_RESOLVER, _missing_meta)

    assert mission_finalize._lifecycle_event_dir(planning_dir, tmp_path, "m", owned=None) == planning_dir


def test_owned_checkout_keeps_planning_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planning_dir = tmp_path / "kitty-specs" / "m"

    def _never(*_args: object, **_kwargs: object) -> ResolvedStatusSurface:
        raise AssertionError("an owned checkout must not consult the status-surface resolver")

    monkeypatch.setattr(_RESOLVER, _never)
    owned = cast(OwnedCheckout, object())

    assert mission_finalize._lifecycle_event_dir(planning_dir, tmp_path, "m", owned=owned) == planning_dir
