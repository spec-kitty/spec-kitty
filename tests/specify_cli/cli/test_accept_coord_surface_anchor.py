"""Two residual properties of the ``accept`` birth-cutover COORD leg.

``_coord_status_feature_dir`` and its four direct properties are covered by
``tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py`` (the seam is
asked with ``STATUS_STATE``; ``None`` off COORD; an unsafe handle is refused
before the seam; the stamp receives the seam's dir). This file does **not**
restate those.

It pins the two properties that suite does not assert, both of which are
failure-mode claims rather than happy-path ones:

1. **No ``git`` round trip.** The historical bug was not only a wrong join — it
   was that the join's anchor came from ``git rev-parse --show-toplevel``, and a
   ``git`` call that did not answer downgraded the anchor to ``None``, silently
   writing the status seed onto the PRIMARY partition. Routing through the seam
   removes the shell-out; nothing else pins that it stays removed.

2. **``CoordinationBranchDeleted`` propagates.** ``_coord_status_feature_dir``'s
   docstring states the C3 fail-loud posture — accept must refuse rather than
   stamp a stale primary — but the behaviour is inherited from the resolver, and
   an inherited behaviour with no test is one refactor away from being absorbed
   into a ``None`` the way ``coord_read_dir_for`` absorbs it.

Both were RED before the routing change and are cheap to keep.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mission_runtime
from mission_runtime import TopologySurface
from mission_runtime.resolution import ResolvedSurface
from specify_cli.cli.commands import accept as accept_mod


pytestmark = [pytest.mark.unit, pytest.mark.fast]

_HANDLE = "demo-mission"
#: The seam's canonical ``<slug>-<mid8>`` dir, deliberately NOT the handle the
#: caller holds: a fixture whose two names agreed could not tell the seam's
#: answer apart from a re-composed join.
_CANONICAL_DIR_NAME = "demo-mission-01KYJGCQ"


@pytest.fixture
def surfaces(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    coord_dir = (
        repo_root
        / ".worktrees"
        / f"{_CANONICAL_DIR_NAME}-coord"
        / "kitty-specs"
        / _CANONICAL_DIR_NAME
    )
    primary_dir = repo_root / "kitty-specs" / _CANONICAL_DIR_NAME
    coord_dir.mkdir(parents=True)
    primary_dir.mkdir(parents=True)
    return {"repo_root": repo_root, "coord": coord_dir, "primary": primary_dir}


def test_coord_stamp_leg_does_not_round_trip_through_git(
    monkeypatch: pytest.MonkeyPatch, surfaces: dict[str, Path]
) -> None:
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
    monkeypatch.setattr(
        mission_runtime,
        "resolve_artifact_surface",
        lambda *_a, **_k: ResolvedSurface(
            path=surfaces["coord"], surface_kind=TopologySurface.COORD
        ),
    )
    monkeypatch.setattr(
        mission_runtime,
        "placement_seam",
        lambda *_a, **_k: type("_Seam", (), {"read_dir": lambda _s, _k2: surfaces["coord"]})(),
    )

    captured: list[Path | None] = []

    def _stamp(_feature_dir: Path, *, status_feature_dir: Path | None = None, owned: object | None = None) -> Any:
        captured.append(status_feature_dir)
        raise RuntimeError("stop after capture")  # absorbed by the best-effort guard

    monkeypatch.setattr(runtime_state_cutover, "stamp_accept_cutover", _stamp)

    accept_mod._stamp_birth_cutover_for_accept(surfaces["repo_root"], _HANDLE)

    assert captured == [surfaces["coord"]]


def test_coord_status_feature_dir_propagates_a_deleted_coordination_branch(
    monkeypatch: pytest.MonkeyPatch, surfaces: dict[str, Path]
) -> None:
    """C3 fail-loud survives the extraction.

    A deleted coordination branch at accept time carries unmerged status, so the
    refusal must propagate rather than be absorbed into a ``None`` — which would
    stamp the seed onto a stale PRIMARY and report success.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    def _raise(*_a: object, **_k: object) -> ResolvedSurface:
        raise CoordinationBranchDeleted(
            repo_root=surfaces["repo_root"],
            mission_slug=_HANDLE,
            mid8="01KYJGCQ",
            coord_candidate=surfaces["coord"],
            primary_candidate=surfaces["primary"],
            coordination_branch="kitty/mission-demo-01KYJGCQ-coord",
        )

    monkeypatch.setattr(mission_runtime, "resolve_artifact_surface", _raise)

    with pytest.raises(CoordinationBranchDeleted):
        accept_mod._coord_status_feature_dir(surfaces["repo_root"], _HANDLE)
