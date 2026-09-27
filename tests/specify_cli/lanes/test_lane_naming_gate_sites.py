"""Regression tests for three gate-pinned sites (FR-008 remainder).

Each site hand-rolled a worktree/lane name match instead of routing through
the naming seam's parsers (``parse_lane_worktree_dir`` / ``lane_id_for_worktree_dir``).
This file guards each fix:

* ``core/vcs/detection.py::_get_locked_vcs_from_feature`` — the fake-branch
  round trip (``parse_mission_slug_from_branch(f"kitty/mission-{name}")``)
  under-matched a mid8-era worktree still carrying its ``NNN-`` prefix.
* ``cli/commands/_coordination_doctor.py::_check_lane_sparse_checkout_drift`` —
  a bare ``startswith(f"{mission_slug}-lane-")`` over-matched a same-prefix
  impostor mission (the ``057-foo`` vs ``057-foobar`` trap).
* ``lanes/lifecycle_sync.py::sync_lane_after_coordination_commit`` — the
  ``CorruptLanesError`` diagnostic no longer fabricates a lane-shaped
  ``<slug>-unknown`` worktree path.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands import _coordination_doctor as cd
from specify_cli.core.vcs.detection import _clear_detection_cache, _get_locked_vcs_from_feature, get_vcs
from specify_cli.core.vcs.types import VCSBackend

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    _clear_detection_cache()
    yield
    _clear_detection_cache()


# ---------------------------------------------------------------------------
# core/vcs/detection.py::_get_locked_vcs_from_feature
# ---------------------------------------------------------------------------


def test_mid8_worktree_with_nnn_prefix_resolves_mission_dir(tmp_path: Path) -> None:
    """``057-foo-01KV6510-lane-a`` resolves the ``057-foo-01KV6510`` Mission dir.

    Guards against the fake-branch round trip separating the mid8 token from
    the slug and recovering only ``057-foo`` -- which matches neither ``==``
    nor the ``endswith`` fallback against the real ``057-foo-01KV6510``
    Mission dir, which would make ``_get_locked_vcs_from_feature`` return
    ``None`` (silent lock loss) instead of the declared ``GIT`` lock.
    The fixture's ``meta.json`` MUST carry ``mission_id`` -- without it
    ``FsMissionResolver.all_missions()`` skips the mission entirely (C-001)
    and the lookup never matches in either version, masking the fix.
    """
    feature_dir = tmp_path / "kitty-specs" / "057-foo-01KV6510"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"vcs": "git", "mission_id": "01KV6510AAAAAAAAAAAAAAAAAA"}))

    worktree_root = tmp_path / ".worktrees" / "057-foo-01KV6510-lane-a"
    src_dir = worktree_root / "src"
    src_dir.mkdir(parents=True)

    assert _get_locked_vcs_from_feature(src_dir / "file.py") is VCSBackend.GIT


def test_legacy_worktree_dir_resolves_as_before(tmp_path: Path) -> None:
    """Legacy ``NNN-slug-lane-a`` worktree resolves the ``NNN-slug`` Mission dir."""
    feature_dir = tmp_path / "kitty-specs" / "057-foo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"vcs": "git", "mission_id": "01LEGACY0AAAAAAAAAAAAAAAAA"}))

    worktree_root = tmp_path / ".worktrees" / "057-foo-lane-a"
    src_dir = worktree_root / "src"
    src_dir.mkdir(parents=True)

    assert _get_locked_vcs_from_feature(src_dir / "file.py") is VCSBackend.GIT


def test_plain_worktree_dir_resolves_as_before(tmp_path: Path) -> None:
    """A bare (no ``NNN-``, no mid8) ``foo-lane-a`` worktree resolves ``foo``."""
    feature_dir = tmp_path / "kitty-specs" / "foo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"vcs": "git", "mission_id": "01PLAIN00AAAAAAAAAAAAAAAAA"}))

    worktree_root = tmp_path / ".worktrees" / "foo-lane-a"
    src_dir = worktree_root / "src"
    src_dir.mkdir(parents=True)

    assert _get_locked_vcs_from_feature(src_dir / "file.py") is VCSBackend.GIT


def test_prefix_collision_mission_dir_is_not_matched(tmp_path: Path) -> None:
    """A ``057-foobar`` mission dir must NOT satisfy a ``057-foo`` worktree.

    Guards against the ``endswith``/prefix trap the fake-branch round trip's
    fallback historically fell into: an unrelated same-prefix mission must
    never be picked because its name happens to end similarly. Asserts
    ``None`` directly (not the ``get_vcs`` auto-detect fallback, which is
    always ``GIT`` and would pass whether or not the lock was found).
    """
    unrelated = tmp_path / "kitty-specs" / "057-foobar"
    unrelated.mkdir(parents=True)
    (unrelated / "meta.json").write_text(json.dumps({"vcs": "git", "mission_id": "01COLLIDEAAAAAAAAAAAAAAAAA"}))

    worktree_root = tmp_path / ".worktrees" / "057-foo-lane-a"
    src_dir = worktree_root / "src"
    src_dir.mkdir(parents=True)

    # No matching Mission dir exists for "057-foo" -- the unrelated
    # "057-foobar" mission must never be picked by prefix accident.
    assert _get_locked_vcs_from_feature(src_dir / "file.py") is None

    # get_vcs still auto-detects git (the only backend), so the caller-facing
    # contract is unaffected by the missing lock.
    assert get_vcs(src_dir / "file.py").backend == VCSBackend.GIT


# ---------------------------------------------------------------------------
# cli/commands/_coordination_doctor.py::_check_lane_sparse_checkout_drift
# ---------------------------------------------------------------------------


def test_drift_check_skips_same_prefix_impostor_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A dir carrying an embedded impostor ``-lane-`` boundary is not scanned.

    Guards against ``startswith(f"{mission_slug}-lane-")`` over-matching
    ``057-foo-lane-bar-lane-a`` for Mission ``057-foo`` -- the literal prefix
    ``057-foo-lane-`` is present, but the dir is really
    ``057-foo-lane-bar``'s ``lane-a`` worktree, not ``057-foo``'s. Recognition
    by recomposition (:func:`lane_id_for_worktree_dir`) rejects it because
    re-composing ``057-foo`` + the recovered lane id does not reproduce the
    dir name byte-for-byte.
    """
    from specify_cli import coordination as coord_mod
    from specify_cli.lanes import branch_naming

    impostor = tmp_path / ".worktrees" / "057-foo-lane-bar-lane-a"
    impostor.mkdir(parents=True)
    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    monkeypatch.setattr(coord_mod, "lane_sparse_checkout_patterns", lambda *a: ["p"])

    scanned: list[Path] = []

    def _record(lane_dir: Path, _expected: object) -> None:
        scanned.append(lane_dir)

    monkeypatch.setattr(cd, "_scan_lane_sparse_drift", _record)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: str(impostor.resolve()) + "\n")

    meta: dict[str, object] = {
        "coordination_branch": "kitty/x",
        "mission_slug": "057-foo",
        "mission_id": "01ABCDEF",
    }
    out = cd._check_lane_sparse_checkout_drift(tmp_path, meta)

    assert scanned == []
    assert out[0].severity == "ok"


def test_drift_check_scans_real_lane_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A genuine ``<mission_slug>-lane-a`` dir is still scanned (no regression)."""
    from specify_cli import coordination as coord_mod
    from specify_cli.lanes import branch_naming

    real = tmp_path / ".worktrees" / "057-foo-lane-a"
    real.mkdir(parents=True)
    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    monkeypatch.setattr(coord_mod, "lane_sparse_checkout_patterns", lambda *a: ["p"])

    scanned: list[Path] = []

    def _record(lane_dir: Path, _expected: object) -> None:
        scanned.append(lane_dir)

    monkeypatch.setattr(cd, "_scan_lane_sparse_drift", _record)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: str(real.resolve()) + "\n")

    meta: dict[str, object] = {
        "coordination_branch": "kitty/x",
        "mission_slug": "057-foo",
        "mission_id": "01ABCDEF",
    }
    cd._check_lane_sparse_checkout_drift(tmp_path, meta)

    assert scanned == [real]


# ---------------------------------------------------------------------------
# lanes/lifecycle_sync.py::sync_lane_after_coordination_commit
# ---------------------------------------------------------------------------


def test_corrupt_lanes_error_reports_no_lane_shaped_unknown_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The ``CorruptLanesError`` diagnostic no longer fabricates a worktree name.

    Guards against ``lane_worktree_path`` being
    ``repo_root / ".worktrees" / f"{mission_slug}-unknown"`` -- a hand-rolled,
    lane-shaped (albeit never-opened) worktree-dir compose outside the naming
    seam. The sentinel path must carry no lane token.
    """
    from specify_cli.lanes import lifecycle_sync
    from specify_cli.lanes.persistence import CorruptLanesError

    def _boom(_read_dir: Any) -> Any:
        raise CorruptLanesError("lanes.json: invalid JSON")

    monkeypatch.setattr(lifecycle_sync, "read_lanes_json", _boom)
    monkeypatch.setattr(
        lifecycle_sync,
        "placement_seam",
        lambda *_a, **_k: type("_Seam", (), {"read_dir": lambda self, _kind: tmp_path})(),
    )
    monkeypatch.setattr(lifecycle_sync, "_git_stdout", lambda *_a, **_k: "deadbeef")

    with pytest.raises(lifecycle_sync.LaneAutoRebaseSyncError) as excinfo:
        lifecycle_sync.sync_lane_after_coordination_commit(
            repo_root=tmp_path,
            mission_slug="057-foo",
            wp_id="WP01",
            coordination_branch="kitty/mission-057-foo",
        )

    path_str = str(excinfo.value.lane_worktree_path)
    assert "-unknown" not in path_str
    assert "-lane-" not in path_str
