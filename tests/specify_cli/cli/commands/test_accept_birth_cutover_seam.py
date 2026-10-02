"""The accept-time birth-cutover COORD leg resolves through the placement seam.

``accept._stamp_birth_cutover_for_accept`` used to hand-build its COORD leg as
``coord_worktree_root / KITTY_SPECS_DIR / mission_slug`` — a raw re-derivation of
placement the kind-aware seam already owns (and one that was latently wrong for
identity-suffixed ``<slug>-<mid8>`` mission dirs). It now routes through
``accept._coord_status_feature_dir``, which asks
``placement_seam(...).write_dir(MissionArtifactKind.STATUS_STATE)`` — WRITE,
not READ (coord-artifact-single-home-01M3V4BE WP16, FR-003): the birth cutover
IS a write, and the read projection's declared EMPTY/UNMATERIALIZED fallback to
the PRIMARY checkout is a sanctioned READ-side degrade that must never leak
into a coordination-kind write (the exact single-home violation this mission
closes).

These tests pin the four behaviours the helper owns:

* a ``COORD``-surface ``write_dir`` yields its ``.path`` verbatim (never a
  slug-joined reconstruction);
* a declared-PRIMARY ``write_dir`` (a coord-less topology) yields ``None``,
  preserving the pre-existing contract that ``cutover_mission`` collapses both
  legs onto the PRIMARY ``feature_dir``;
* a traversal-unsafe handle is rejected before it can reach the seam;
* the stamp receives the seam's dir verbatim.

The seam is stubbed at the ``mission_runtime`` module boundary (the helper
imports from it lazily, inside the function) rather than materialising a real
coordination worktree: the unit under test is the *routing decision*, and the
seam's own resolution is covered by ``tests/mission_runtime/``.
"""

from __future__ import annotations

from pathlib import Path

import mission_runtime
import pytest
from mission_runtime import Establishment, MissionArtifactKind, TopologySurface, WriteLocation

from specify_cli.cli.commands import accept


pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "birth-cutover-seam-01KYHP67"


class _RecordingSeam:
    """Stand-in for :class:`mission_runtime.PlacementSeam` recording write kinds."""

    def __init__(self, write_location: WriteLocation) -> None:
        self._write_location = write_location
        self.write_kinds: list[MissionArtifactKind] = []

    def write_dir(self, kind: MissionArtifactKind) -> WriteLocation:
        self.write_kinds.append(kind)
        return self._write_location


def _write_location(*, surface: TopologySurface, path: Path) -> WriteLocation:
    return WriteLocation(
        path=path,
        checkout_root=path,
        surface=surface,
        coord_state_before=None,
        establishment=Establishment.NONE,
    )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


def _install_seam(monkeypatch: pytest.MonkeyPatch, *, surface: TopologySurface, seam_dir: Path) -> _RecordingSeam:
    """Stub ``placement_seam`` on ``mission_runtime`` with a ``write_dir``-only stand-in."""
    seam = _RecordingSeam(_write_location(surface=surface, path=seam_dir))
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_args, **_kwargs: seam)
    return seam


def test_coord_status_feature_dir_uses_seam_status_state_write_dir(monkeypatch: pytest.MonkeyPatch, repo_root: Path, tmp_path: Path) -> None:
    """A COORD-surface ``write_dir`` returns the seam's dir — not a ``<root>/kitty-specs/<slug>`` join."""
    # Deliberately identity-suffixed and NOT equal to a slug-joined path, so a
    # reconstruction regression cannot accidentally produce the same answer.
    seam_dir = tmp_path / "coord-wt" / "kitty-specs" / f"{_SLUG}-01KYHP67"
    seam = _install_seam(monkeypatch, surface=TopologySurface.COORD, seam_dir=seam_dir)

    result = accept._coord_status_feature_dir(repo_root, _SLUG)

    assert result == seam_dir
    assert seam.write_kinds == [MissionArtifactKind.STATUS_STATE]


def test_coord_status_feature_dir_is_none_off_the_coord_surface(
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    """A declared-PRIMARY ``write_dir`` (coord-less topology) collapses the stamp onto the PRIMARY leg (``None``)."""
    seam = _install_seam(monkeypatch, surface=TopologySurface.PRIMARY, seam_dir=tmp_path / "primary")

    assert accept._coord_status_feature_dir(repo_root, _SLUG) is None
    # The seam's write projection WAS consulted (it is the only way to learn
    # the declared surface) but its answer is discarded.
    assert seam.write_kinds == [MissionArtifactKind.STATUS_STATE]


def test_coord_status_feature_dir_rejects_unsafe_handle_before_the_seam(monkeypatch: pytest.MonkeyPatch, repo_root: Path, tmp_path: Path) -> None:
    """The traversal guard still fires, and fires ahead of any seam call."""
    seam = _install_seam(monkeypatch, surface=TopologySurface.COORD, seam_dir=tmp_path / "coord")

    with pytest.raises(ValueError):
        accept._coord_status_feature_dir(repo_root, "../escape")

    assert seam.write_kinds == []


def test_stamp_birth_cutover_passes_the_seam_dir_as_the_coord_leg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``_stamp_birth_cutover_for_accept`` hands the seam's dir to the cutover.

    The PRIMARY leg is produced by a ``placement_seam(...).read_dir(PRIMARY_METADATA)``
    call made via a lazy, function-local import; the COORD leg is produced by
    ``_coord_status_feature_dir`` (stubbed directly here, as its own seam call
    shape is pinned by the tests above).
    """
    repo_root = tmp_path / "repo"
    primary_dir = repo_root / "kitty-specs" / _SLUG
    primary_dir.mkdir(parents=True)
    coord_dir = tmp_path / "coord-wt" / "kitty-specs" / f"{_SLUG}-01KYHP67"

    class _ReadSeam:
        def __init__(self, read_dir: Path) -> None:
            self._read_dir = read_dir
            self.read_kinds: list[MissionArtifactKind] = []

        def read_dir(self, kind: MissionArtifactKind) -> Path:
            self.read_kinds.append(kind)
            return self._read_dir

    seam = _ReadSeam(primary_dir)
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


# ---------------------------------------------------------------------------
# WP16 (T089): the two NEW ``write_dir`` refusals the stamp call site converts
# into an actionable ``AcceptanceError``, plus the UNCHANGED ``CoordinationBranchDeleted``
# fail-loud propagation through the SAME call site (not just ``_coord_status_feature_dir``
# in isolation, which ``test_accept_coord_surface_anchor.py`` already pins).
# ---------------------------------------------------------------------------


def _primary_seam(primary_dir: Path) -> object:
    class _ReadSeam:
        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return primary_dir

    return _ReadSeam()


def _unmaterialized_remote_only_exc() -> Exception:
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    return CoordinationWorktreeUnmaterialized(
        repo_root=Path("/repo"),
        mission_slug=_SLUG,
        mid8="01KYHP67",
        coord_candidate=Path("/repo/.worktrees/x"),
        primary_candidate=Path("/repo/kitty-specs/x"),
        coordination_branch="kitty/mission-x-01KYHP67",
    )


def _fork_refused_exc() -> Exception:
    from specify_cli.coordination.coord_seed import CoordSeedForkRefused

    return CoordSeedForkRefused(
        root_path=Path("/repo/kitty-specs/x/status.events.jsonl"),
        coord_path="kitty-specs/x/status.events.jsonl",
        coord_ref="kitty/mission-x-01KYHP67",
        first_divergence_root="evt-root",
        first_divergence_coord="evt-coord",
        reconcile_steps=(),
    )


def _status_lock_held_exc() -> Exception:
    from specify_cli.status.locking import FeatureStatusLockTimeoutError

    return FeatureStatusLockTimeoutError("lock held")


@pytest.mark.parametrize(
    "build_exc",
    [_unmaterialized_remote_only_exc, _fork_refused_exc, _status_lock_held_exc],
    ids=["unmaterialized_remote_only", "fork_refused", "status_lock_held"],
)
def test_stamp_converts_new_write_dir_refusals_to_acceptance_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, build_exc: object) -> None:
    """T089: ``CoordinationWorktreeUnmaterialized`` / ``CoordSeedForkRefused`` / ``FeatureStatusLockTimeoutError``
    all become an actionable ``AcceptanceError`` at the stamp call site, never an unstructured crash.
    """
    from specify_cli.acceptance import AcceptanceError

    repo_root = tmp_path / "repo"
    primary_dir = repo_root / "kitty-specs" / _SLUG
    primary_dir.mkdir(parents=True)

    exc = build_exc()  # type: ignore[operator]

    def _raising_coord_status_feature_dir(_root: Path, _slug: str, **_kwargs: object) -> Path | None:
        raise exc

    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _primary_seam(primary_dir))
    monkeypatch.setattr(accept, "_coord_status_feature_dir", _raising_coord_status_feature_dir)

    with pytest.raises(AcceptanceError) as exc_info:
        accept._stamp_birth_cutover_for_accept(repo_root, _SLUG)

    assert _SLUG in str(exc_info.value)


def test_stamp_still_propagates_a_deleted_coordination_branch_raw(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``CoordinationBranchDeleted`` is UNCHANGED by WP16: it still crashes the stamp call site raw.

    Mirrors ``test_stamp_birth_cutover_resolves_primary_dir_regardless_of_coord_state``'s
    own docstring: "fail-loud is the intended contract for a real accept-time
    cutover, not a diagnostic" -- so this must NOT be softened into an
    ``AcceptanceError`` the way the two refusals above are.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    repo_root = tmp_path / "repo"
    primary_dir = repo_root / "kitty-specs" / _SLUG
    primary_dir.mkdir(parents=True)

    def _raising_coord_status_feature_dir(_root: Path, _slug: str, **_kwargs: object) -> Path | None:
        raise CoordinationBranchDeleted(
            repo_root=repo_root,
            mission_slug=_SLUG,
            mid8="01KYHP67",
            coord_candidate=repo_root / ".worktrees" / "x",
            primary_candidate=primary_dir,
            coordination_branch="kitty/mission-x-01KYHP67",
        )

    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _primary_seam(primary_dir))
    monkeypatch.setattr(accept, "_coord_status_feature_dir", _raising_coord_status_feature_dir)

    with pytest.raises(CoordinationBranchDeleted):
        accept._stamp_birth_cutover_for_accept(repo_root, _SLUG)
