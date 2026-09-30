"""The accept-time birth-cutover COORD leg resolves through the placement seam.

``accept._stamp_birth_cutover_for_accept`` used to hand-build its COORD leg as
``coord_worktree_root / KITTY_SPECS_DIR / mission_slug`` — a raw re-derivation of
placement the kind-aware seam already owns (and one that was latently wrong for
identity-suffixed ``<slug>-<mid8>`` mission dirs). It now routes through
``accept._coord_status_feature_dir``, which asks
``placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)`` — ``STATUS_STATE``
because ``cutover_mission``'s ``status_feature_dir`` argument IS the port target
where ``status.events.jsonl`` lives under coordination topology.

These tests pin the three behaviours the helper owns:

* a ``COORD`` surface stamp yields the seam's ``STATUS_STATE`` read dir verbatim
  (never a slug-joined reconstruction);
* every non-``COORD`` stamp yields ``None``, preserving the pre-existing contract
  that ``cutover_mission`` collapses both legs onto the PRIMARY ``feature_dir``;
* a traversal-unsafe handle is rejected before it can reach the seam.

The seam is stubbed at the ``mission_runtime`` module boundary (the helper imports
from it lazily, inside the function) rather than materialising a real coordination
worktree: the unit under test is the *routing decision*, and the seam's own
resolution is covered by ``tests/mission_runtime/``.
"""

from __future__ import annotations

from pathlib import Path

import mission_runtime
import pytest
from mission_runtime import MissionArtifactKind, TopologySurface
from mission_runtime.resolution import ResolvedSurface

from specify_cli.cli.commands import accept


pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "birth-cutover-seam-01KYHP67"


class _RecordingSeam:
    """Stand-in for :class:`mission_runtime.PlacementSeam` recording read kinds."""

    def __init__(self, read_dir: Path) -> None:
        self._read_dir = read_dir
        self.read_kinds: list[MissionArtifactKind] = []

    def read_dir(self, kind: MissionArtifactKind) -> Path:
        self.read_kinds.append(kind)
        return self._read_dir


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


def _install_seam(
    monkeypatch: pytest.MonkeyPatch,
    *,
    surface_kind: TopologySurface,
    seam_dir: Path,
) -> tuple[_RecordingSeam, list[MissionArtifactKind]]:
    """Stub ``resolve_artifact_surface``/``placement_seam`` on ``mission_runtime``."""
    seam = _RecordingSeam(seam_dir)
    resolved_kinds: list[MissionArtifactKind] = []

    def _fake_resolve(
        _repo_root: Path,
        _mission_slug: str,
        kind: MissionArtifactKind,
        *,
        owned: object | None = None,
    ) -> ResolvedSurface:
        resolved_kinds.append(kind)
        return ResolvedSurface(path=seam_dir, surface_kind=surface_kind)

    monkeypatch.setattr(mission_runtime, "resolve_artifact_surface", _fake_resolve)
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_args, **_kwargs: seam)
    return seam, resolved_kinds


def test_coord_status_feature_dir_uses_seam_status_state_read_dir(monkeypatch: pytest.MonkeyPatch, repo_root: Path, tmp_path: Path) -> None:
    """A COORD stamp returns the seam's dir — not a ``<root>/kitty-specs/<slug>`` join."""
    # Deliberately identity-suffixed and NOT equal to a slug-joined path, so a
    # reconstruction regression cannot accidentally produce the same answer.
    seam_dir = tmp_path / "coord-wt" / "kitty-specs" / f"{_SLUG}-01KYHP67"
    seam, resolved_kinds = _install_seam(monkeypatch, surface_kind=TopologySurface.COORD, seam_dir=seam_dir)

    result = accept._coord_status_feature_dir(repo_root, _SLUG)

    assert result == seam_dir
    assert seam.read_kinds == [MissionArtifactKind.STATUS_STATE]
    assert resolved_kinds == [MissionArtifactKind.STATUS_STATE]


@pytest.mark.parametrize(
    "surface_kind",
    [
        TopologySurface.PRIMARY,
        TopologySurface.LANE,
        TopologySurface.CONSOLIDATED,
    ],
)
def test_coord_status_feature_dir_is_none_off_the_coord_surface(
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
    tmp_path: Path,
    surface_kind: TopologySurface,
) -> None:
    """Non-COORD stamps collapse the stamp onto the PRIMARY leg (``None``)."""
    seam, _ = _install_seam(monkeypatch, surface_kind=surface_kind, seam_dir=tmp_path / "primary")

    assert accept._coord_status_feature_dir(repo_root, _SLUG) is None
    # The seam's read projection is never consulted off the coord surface.
    assert seam.read_kinds == []


def test_coord_status_feature_dir_rejects_unsafe_handle_before_the_seam(monkeypatch: pytest.MonkeyPatch, repo_root: Path, tmp_path: Path) -> None:
    """The traversal guard still fires, and fires ahead of any seam call."""
    seam, resolved_kinds = _install_seam(monkeypatch, surface_kind=TopologySurface.COORD, seam_dir=tmp_path / "coord")

    with pytest.raises(ValueError):
        accept._coord_status_feature_dir(repo_root, "../escape")

    assert resolved_kinds == []
    assert seam.read_kinds == []


def test_stamp_birth_cutover_passes_the_seam_dir_as_the_coord_leg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``_stamp_birth_cutover_for_accept`` hands the seam's dir to the cutover.

    read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): the PRIMARY
    leg used to be produced by the retiring ``primary_feature_dir_for_mission``
    wrapper (patched directly on ``accept``, since it was a plain top-level
    re-export); it is now a ``placement_seam(...).read_dir(PRIMARY_METADATA)``
    call the function makes via a lazy, function-local import, so the fake is
    installed on ``mission_runtime.placement_seam`` instead — the same
    ``_RecordingSeam`` stand-in used by the COORD-leg tests above, which also
    lets this test pin the kind (``PRIMARY_METADATA``).

    WP08 (T036): the caller-side ``_canonicalize_primary_read_handle`` fold
    this test used to patch (as a no-op identity stand-in) is DROPPED from
    the production body — redundant with the seam's own internal fold for a
    PRIMARY-partition kind — so there is no longer a module attribute to
    patch here; the seam mock alone now controls the resolved dir.
    """
    repo_root = tmp_path / "repo"
    primary_dir = repo_root / "kitty-specs" / _SLUG
    primary_dir.mkdir(parents=True)
    coord_dir = tmp_path / "coord-wt" / "kitty-specs" / f"{_SLUG}-01KYHP67"

    seam = _RecordingSeam(primary_dir)
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_args, **_kwargs: seam)
    monkeypatch.setattr(accept, "_coord_status_feature_dir", lambda _root, _slug, **_kwargs: coord_dir)

    captured: dict[str, object] = {}

    def _fake_stamp(feature_dir: Path, *, status_feature_dir: Path | None, owned: object | None = None) -> object:
        captured["feature_dir"] = feature_dir
        captured["status_feature_dir"] = status_feature_dir

        class _Result:
            error = None

        return _Result()

    monkeypatch.setattr("specify_cli.migration.runtime_state_cutover.stamp_accept_cutover", _fake_stamp)

    accept._stamp_birth_cutover_for_accept(repo_root, _SLUG)

    assert captured == {"feature_dir": primary_dir, "status_feature_dir": coord_dir}
    assert seam.read_kinds == [MissionArtifactKind.PRIMARY_METADATA]
