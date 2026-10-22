"""Single home of the accept COORD stamp leg failure-mode pins (#5015).

Both ``tests/specify_cli/cli/test_accept_coord_surface_anchor.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_cli_accept_coord_surface_anchor.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mission_runtime
from mission_runtime import MissionArtifactKind, WriteLocation
from specify_cli.cli.commands import accept as accept_mod

_HANDLE = "demo-mission"
#: The seam's canonical ``<slug>-<mid8>`` dir, deliberately NOT the handle the
#: caller holds: a fixture whose two names agreed could not tell the seam's
#: answer apart from a re-composed join.
_CANONICAL_DIR_NAME = "demo-mission-01KYJGCQ"


@pytest.fixture
def surfaces(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    coord_dir = repo_root / ".worktrees" / f"{_CANONICAL_DIR_NAME}-coord" / "kitty-specs" / _CANONICAL_DIR_NAME
    primary_dir = repo_root / "kitty-specs" / _CANONICAL_DIR_NAME
    coord_dir.mkdir(parents=True)
    primary_dir.mkdir(parents=True)
    return {"repo_root": repo_root, "coord": coord_dir, "primary": primary_dir}


def test_coord_stamp_leg_does_not_round_trip_through_git(monkeypatch: pytest.MonkeyPatch, surfaces: dict[str, Path]) -> None:
    """The COORD anchor comes straight off the seam — no walk to the worktree root.

    ``run_git`` is replaced with a fail-fast stub rather than a stub returning a
    correct answer: the point is that the shell-out does not happen at all, since
    a non-answering ``git`` is precisely what used to downgrade the seed write to
    the PRIMARY partition.
    """
    from specify_cli.migration import runtime_state_cutover

    monkeypatch.setattr(
        accept_mod,
        "run_git",
        lambda *_a, **_k: pytest.fail("the COORD stamp leg must not shell out to git"),
    )

    class _Seam:
        def read_dir(self, kind: MissionArtifactKind) -> Path:
            # The PRIMARY_METADATA leg, resolved ahead of the COORD leg below.
            return surfaces["primary"]

        def write_dir(self, kind: MissionArtifactKind) -> WriteLocation:
            return WriteLocation(
                path=surfaces["coord"],
                surface_root=surfaces["coord"],
                surface=mission_runtime.TopologySurface.COORD,
                coord_state_before=None,
                establishment=mission_runtime.Establishment.NONE,
            )

    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _Seam())

    captured: list[Path | None] = []

    def _stamp(_feature_dir: Path, *, status_feature_dir: Path | None = None, owned: object | None = None) -> Any:
        captured.append(status_feature_dir)
        raise RuntimeError("stop after capture")  # absorbed by the best-effort guard

    monkeypatch.setattr(runtime_state_cutover, "stamp_accept_cutover", _stamp)

    accept_mod._stamp_birth_cutover_for_accept(surfaces["repo_root"], _HANDLE)

    assert captured == [surfaces["coord"]]


def test_coord_status_feature_dir_propagates_a_deleted_coordination_branch(monkeypatch: pytest.MonkeyPatch, surfaces: dict[str, Path]) -> None:
    """C3 fail-loud survives the write-dir migration.

    A deleted coordination branch at accept time carries unmerged status, so the
    refusal must propagate rather than be absorbed into a ``None`` — which would
    stamp the seed onto a stale PRIMARY and report success.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    class _RefusingSeam:
        def write_dir(self, kind: MissionArtifactKind) -> WriteLocation:
            raise CoordinationBranchDeleted(
                repo_root=surfaces["repo_root"],
                mission_slug=_HANDLE,
                mid8="01KYJGCQ",
                coord_candidate=surfaces["coord"],
                primary_candidate=surfaces["primary"],
                coordination_branch="kitty/mission-demo-01KYJGCQ-coord",
            )

    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _RefusingSeam())

    with pytest.raises(CoordinationBranchDeleted):
        accept_mod._coord_status_feature_dir(surfaces["repo_root"], _HANDLE)
