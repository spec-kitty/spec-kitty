"""Always-on regression gate: the ``accept`` COORD stamp leg's two failure-mode pins.

Lifted from ``tests/specify_cli/cli/test_accept_coord_surface_anchor.py``,
whose directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

Two structural properties, both failure-mode claims rather than happy-path
ones (no git-network dependency — the seam and ``run_git`` are monkeypatched):

1. The COORD anchor comes straight off the placement seam — no shell-out to
   ``git rev-parse --show-toplevel``. A non-answering ``git`` used to
   downgrade the anchor to ``None``, silently writing the status seed onto
   the PRIMARY partition.
2. ``CoordinationBranchDeleted`` propagates out of
   ``_coord_status_feature_dir`` rather than being absorbed into ``None``
   (the C3 fail-loud posture) — an inherited resolver behaviour with no
   pinning test is one refactor away from silent absorption.

coord-artifact-single-home-01M3V4BE WP16: the seam now resolves via
:meth:`~mission_runtime.PlacementSeam.write_dir` (a WRITE resolution), not
:meth:`~mission_runtime.PlacementSeam.read_dir` — both pins below are
re-expressed against ``write_dir``, mirroring the sibling file this one lifts
from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mission_runtime
from mission_runtime import MissionArtifactKind, WriteLocation
from specify_cli.cli.commands import accept as accept_mod

pytestmark = [pytest.mark.architectural]

_HANDLE = "demo-mission"
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
    from specify_cli.migration import runtime_state_cutover

    monkeypatch.setattr(
        accept_mod,
        "run_git",
        lambda *_a, **_k: pytest.fail("the COORD stamp leg must not shell out to git"),
    )

    class _Seam:
        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return surfaces["primary"]

        def write_dir(self, kind: MissionArtifactKind) -> WriteLocation:
            return WriteLocation(
                path=surfaces["coord"],
                checkout_root=surfaces["coord"],
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
