"""Unit tests for the ``resolve_lanes_dir`` pure seam (#1993).

The seam is the single derivation of the ``lanes.json`` path from a feature
directory. These tests pin its pure, deterministic behavior and assert (by
source inspection) that no ad-hoc ``feature_dir / lanes.json`` join survives
outside the seam in the owned files (verification-by-deletion).
"""

from __future__ import annotations

import inspect
from pathlib import Path, PureWindowsPath

import pytest

from specify_cli.lanes import persistence as persistence_module
from specify_cli.lanes.persistence import LANES_FILENAME, resolve_lanes_dir

pytestmark = [pytest.mark.fast]


def test_resolve_lanes_dir_composes_lanes_filename(tmp_path: Path) -> None:
    """The seam returns ``feature_dir / lanes.json`` and nothing else."""
    # Topology-true: a real kitty-specs/<mission> feature dir layout.
    feature_dir = (
        tmp_path
        / "kitty-specs"
        / "read-path-error-fidelity-adoption-01KV8NPC"
    )
    feature_dir.mkdir(parents=True)

    resolved = resolve_lanes_dir(feature_dir)

    assert resolved == feature_dir / LANES_FILENAME
    assert resolved.name == "lanes.json"
    assert resolved.parent == feature_dir


def test_resolve_lanes_dir_is_pure_no_io(tmp_path: Path) -> None:
    """The seam performs no I/O: it never creates the file or the dir."""
    feature_dir = tmp_path / "kitty-specs" / "absent-mission-01KV8NPCABSENT00000000"

    resolved = resolve_lanes_dir(feature_dir)

    # No side effects: neither the feature dir nor the lanes file are created.
    assert not feature_dir.exists()
    assert not resolved.exists()


def test_resolve_lanes_dir_is_deterministic(tmp_path: Path) -> None:
    """Repeated calls on the same input return equal paths."""
    feature_dir = tmp_path / "feature"
    first_resolved = resolve_lanes_dir(feature_dir)
    second_resolved = resolve_lanes_dir(feature_dir)
    assert first_resolved == second_resolved


def test_no_ad_hoc_lanes_join_outside_the_seam_in_persistence() -> None:
    """persistence.py derives the lanes path only inside ``resolve_lanes_dir``.

    Verification-by-deletion guard: the ad-hoc ``feature_dir / LANES_FILENAME``
    joins at the old read/write call-sites must be gone — the only remaining
    derivation is the seam body itself.
    """
    source = inspect.getsource(persistence_module)
    join_occurrences = source.count("feature_dir / LANES_FILENAME")
    # Exactly one: the single derivation inside resolve_lanes_dir.
    assert join_occurrences == 1, (
        "Expected exactly one feature_dir/lanes join (the seam); "
        f"found {join_occurrences}"
    )


def test_non_git_lanes_lock_for_windows_path_stays_under_temp_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A drive-qualified non-Git path becomes a safe, stable temp lock name."""
    monkeypatch.setattr(persistence_module.tempfile, "gettempdir", lambda: str(tmp_path))
    windows_lanes_path = PureWindowsPath(r"C:\work\mission\lanes.json")

    lock_path = persistence_module._non_git_lanes_lock_path(windows_lanes_path)

    assert lock_path.is_relative_to(tmp_path)
    assert lock_path.parent == tmp_path / "spec-kitty-lanes-locks"
    assert lock_path.name.endswith(".lock")
    assert lock_path == persistence_module._non_git_lanes_lock_path(windows_lanes_path)
