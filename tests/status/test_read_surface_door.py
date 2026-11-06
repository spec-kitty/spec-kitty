"""The one status read door: a declared source per topology and coordination state (WP05).

Mission lane-worktree-model-hardening, FR-001, FR-003, FR-004, FR-061, NFR-001; ADR
``2026-11-06-2-one-status-read-contract``. Every fixture is a real git repository built by the
WP04 matrix builder (no resolver is patched): the repository root checkout carries a stale
decoy log (``planned``), the coordination branch carries the authority (three events, ending
``in_progress``), and a registered lane worktree carries its fork-time copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.status.read_surface import (
    StatusReadSource,
    StatusReadSurface,
    materialize_status,
    read_status_events,
    read_status_stream,
    resolve_primary_partition_dir,
    resolve_status_read,
)
from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    CWD_COORD,
    CWD_LANE,
    CWD_ROOT,
    EMPTY,
    KITTY_SPECS,
    LANES,
    LANES_WITH_COORD,
    MATERIALIZED,
    MATRIX,
    MISSION_BRANCH,
    NOT_APPLICABLE,
    SINGLE_BRANCH,
    SLUG,
    UNMATERIALIZED,
    MatrixMission,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

COORD_REF = f"refs/heads/{COORD_BRANCH}"


def _lanes(events: list[Any]) -> list[str]:
    return [str(event.to_lane) for event in events]


def _cwd_root(mission: MatrixMission, cwd: str) -> Path:
    if cwd == CWD_LANE:
        assert mission.lane_worktree is not None
        return mission.lane_worktree
    if cwd == CWD_COORD:
        assert mission.coord_worktree is not None
        return mission.coord_worktree
    return mission.repo


def _empty_the_coord_worktree(mission: MatrixMission) -> None:
    """Check the coordination worktree out, then drop its Mission directory (the EMPTY state)."""
    coord_worktree = mission.repo / ".worktrees" / f"{SLUG}-coord"
    git(mission.repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    shutil.rmtree(coord_worktree / KITTY_SPECS / SLUG)


# ---------------------------------------------------------------------------
# User Story 1 scenario 1 (FR-003): the coordination branch is read when no worktree carries it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cwd", [CWD_ROOT, CWD_LANE])
def test_unmaterialized_coord_reads_branch_events(tmp_path: Path, cwd: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """No coordination worktree: the door reads the 3 committed events, never the root's stale copy."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    root = _cwd_root(mission, cwd)
    monkeypatch.chdir(root)

    surface = resolve_status_read(root, SLUG)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.ref == COORD_REF
    assert surface.path is None
    assert surface.fallback_reason is None
    assert surface.repo_root.resolve() == mission.repo.resolve()
    assert surface.mission_dir_name == SLUG
    assert surface.topology is MissionTopology.LANES_WITH_COORD
    assert _lanes(read_status_events(surface)) == ["planned", "claimed", "in_progress"]


def test_empty_coord_worktree_reads_branch(tmp_path: Path) -> None:
    """A checked-out coordination worktree without the Mission directory still reads the branch."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _empty_the_coord_worktree(mission)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.ref == COORD_REF
    assert _lanes(read_status_events(surface)) == ["planned", "claimed", "in_progress"]
    snapshot = materialize_status(surface)
    assert snapshot.work_packages["WP01"]["lane"] == "in_progress"


def test_materialized_coord_reads_the_worktree_file(tmp_path: Path) -> None:
    """A materialized coordination worktree is read from its file (uncommitted appends count)."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.COORD_WORKTREE
    assert surface.path is not None
    assert surface.path.resolve() == mission.coord_mission_dir.resolve()
    assert surface.ref is None
    assert _lanes(read_status_events(surface)) == ["planned", "claimed", "in_progress"]


@pytest.mark.parametrize("coord_state", [EMPTY, UNMATERIALIZED])
def test_preseed_window_declares_write_checkout_source(tmp_path: Path, coord_state: str) -> None:
    """The branch exists but holds no log yet: the declared, stamped WRITE_CHECKOUT fallback."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, EMPTY)
    if coord_state == UNMATERIALIZED:
        assert mission.coord_worktree is not None
        git(mission.repo, "worktree", "remove", "-f", str(mission.coord_worktree))

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.fallback_reason
    assert surface.ref is None
    assert surface.path is not None
    assert surface.path.resolve() == mission.root_mission_dir.resolve()
    assert _lanes(read_status_events(surface)) == ["planned"]


def test_deleted_coordination_branch_raises(tmp_path: Path) -> None:
    """Deleted without landing is data loss: the door fails closed (unchanged)."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    git(mission.repo, "branch", "-D", COORD_BRANCH)

    with pytest.raises(CoordinationBranchDeleted):
        resolve_status_read(mission.repo, SLUG)


def test_consolidated_mission_reads_the_target_copy_before_any_coord_probe(tmp_path: Path) -> None:
    """A landed Mission reads the target's copy, even with its coordination branch torn down."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    meta_path = mission.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-11-06T01:00:00+00:00"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    git(mission.repo, "branch", "-D", COORD_BRANCH)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.CONSOLIDATED_TARGET
    assert surface.path is not None
    assert surface.path.resolve() == mission.root_mission_dir.resolve()


@pytest.mark.parametrize("topology", [SINGLE_BRANCH, LANES])
@pytest.mark.parametrize("cwd", [CWD_ROOT, CWD_LANE])
def test_write_checkout_topologies_read_the_write_checkout(tmp_path: Path, topology: str, cwd: str) -> None:
    """``single_branch`` and ``lanes`` read the write checkout's working tree, never a lane copy."""
    if topology == SINGLE_BRANCH and cwd == CWD_LANE:
        pytest.skip("single_branch has no lane checkout")
    mission = build_matrix_mission(tmp_path, topology)

    surface = resolve_status_read(_cwd_root(mission, cwd), SLUG)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.fallback_reason is None
    assert surface.path is not None
    assert surface.path.resolve() == mission.root_mission_dir.resolve()
    assert _lanes(read_status_events(surface))[-1] == "in_progress"
    assert read_status_stream(surface).transitions[-1].to_lane == "in_progress"


def test_owned_checkout_unmaterialized_reads_ref_not_raises(tmp_path: Path) -> None:
    """FR-003: an owned checkout of a coordination Mission follows the same rule instead of raising."""
    from mission_runtime import OwnedCheckout

    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    owned_root = tmp_path / "owned-checkout"
    git(mission.repo, "worktree", "add", "-q", "-b", "owned-write", str(owned_root))
    fact = OwnedCheckout._mint(
        repository_root=mission.repo,
        owned_root=owned_root,
        mission_dir=owned_root / KITTY_SPECS / SLUG,
        mission_slug=SLUG,
        topology=MissionTopology.LANES_WITH_COORD,
        write_branch="owned-write",
    )

    surface = resolve_status_read(owned_root, SLUG, owned=fact)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert _lanes(read_status_events(surface)) == ["planned", "claimed", "in_progress"]


def test_owned_single_branch_reads_the_owned_mission_dir(tmp_path: Path) -> None:
    """The validated owned checkout IS the write checkout of an owned ``single_branch`` Mission."""
    from mission_runtime import OwnedCheckout

    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    owned_root = tmp_path / "owned-checkout"
    git(mission.repo, "worktree", "add", "-q", "-b", "owned-write", str(owned_root))
    fact = OwnedCheckout._mint(
        repository_root=mission.repo,
        owned_root=owned_root,
        mission_dir=owned_root / KITTY_SPECS / SLUG,
        mission_slug=SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="owned-write",
    )

    surface = resolve_status_read(owned_root, SLUG, owned=fact)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.path == owned_root / KITTY_SPECS / SLUG


# ---------------------------------------------------------------------------
# NFR-001: one batched object read per Mission per command
# ---------------------------------------------------------------------------


def test_ref_read_spawns_one_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolving and then reading events, stream and snapshot spawns ONE ``git cat-file``."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    real_run = subprocess.run
    object_reads: list[list[str]] = []

    def _counting_run(args: Any, *pargs: Any, **kwargs: Any) -> Any:
        if isinstance(args, (list, tuple)) and "cat-file" in [str(arg) for arg in args]:
            object_reads.append([str(arg) for arg in args])
        return real_run(args, *pargs, **kwargs)

    monkeypatch.setattr(subprocess, "run", _counting_run)

    surface = resolve_status_read(mission.repo, SLUG)
    events = read_status_events(surface)
    stream = read_status_stream(surface)
    snapshot = materialize_status(surface)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert len(events) == len(stream.transitions) == 3
    assert snapshot.work_packages["WP01"]["lane"] == "in_progress"
    assert len(object_reads) == 1, object_reads
    assert "--batch" in object_reads[0]


# ---------------------------------------------------------------------------
# FR-004: a bad ref is not an absent file
# ---------------------------------------------------------------------------


def test_unreadable_ref_raises_never_reads_as_genesis(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    surface = StatusReadSurface(
        topology=MissionTopology.LANES_WITH_COORD,
        source=StatusReadSource.COORD_BRANCH_REF,
        mission_dir_name=SLUG,
        path=None,
        repo_root=mission.repo,
        ref="refs/heads/no-such-coordination-branch",
        fallback_reason=None,
    )

    with pytest.raises(StatusSurfaceRefUnreadable):
        read_status_events(surface)


def test_absent_log_on_a_readable_ref_is_an_empty_history(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, EMPTY)
    surface = StatusReadSurface(
        topology=MissionTopology.LANES_WITH_COORD,
        source=StatusReadSource.COORD_BRANCH_REF,
        mission_dir_name=SLUG,
        path=None,
        repo_root=mission.repo,
        ref=COORD_REF,
        fallback_reason=None,
    )

    assert read_status_events(surface) == []


# ---------------------------------------------------------------------------
# Value-object invariants (data model §2)
# ---------------------------------------------------------------------------


def test_surface_requires_exactly_one_of_path_and_ref(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        StatusReadSurface(
            topology=MissionTopology.LANES,
            source=StatusReadSource.WRITE_CHECKOUT,
            mission_dir_name=SLUG,
            path=tmp_path,
            repo_root=tmp_path,
            ref="refs/heads/x",
            fallback_reason=None,
        )
    with pytest.raises(ValueError, match="exactly one"):
        StatusReadSurface(
            topology=MissionTopology.LANES,
            source=StatusReadSource.WRITE_CHECKOUT,
            mission_dir_name=SLUG,
            path=None,
            repo_root=tmp_path,
            ref=None,
            fallback_reason=None,
        )


def test_surface_path_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        StatusReadSurface(
            topology=MissionTopology.LANES,
            source=StatusReadSource.WRITE_CHECKOUT,
            mission_dir_name=SLUG,
            path=tmp_path / "missing",
            repo_root=tmp_path,
            ref=None,
            fallback_reason=None,
        )


@pytest.mark.parametrize(
    ("topology", "source"),
    [
        (MissionTopology.LANES, StatusReadSource.WRITE_CHECKOUT),
        (MissionTopology.LANES_WITH_COORD, StatusReadSource.COORD_WORKTREE),
    ],
)
def test_fallback_reason_only_on_a_coordination_write_checkout(tmp_path: Path, topology: MissionTopology, source: StatusReadSource) -> None:
    with pytest.raises(ValueError, match="fallback_reason"):
        StatusReadSurface(
            topology=topology,
            source=source,
            mission_dir_name=SLUG,
            path=tmp_path,
            repo_root=tmp_path,
            ref=None,
            fallback_reason="pre-seed",
        )


# ---------------------------------------------------------------------------
# Invariants 1 and 2 across the WP04 matrix
# ---------------------------------------------------------------------------


_MATRIX_CELLS = sorted({(topology, state, cwd) for topology, state, cwd in MATRIX})


@pytest.mark.parametrize(("topology", "coord_state", "cwd"), _MATRIX_CELLS)
def test_never_returns_nonexistent_path(
    tmp_path: Path,
    topology: str,
    coord_state: str,
    cwd: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every matrix cell: ``path`` is None or exists, and is never inside a lane checkout."""
    mission = build_matrix_mission(tmp_path, topology, coord_state)
    root = _cwd_root(mission, cwd)
    monkeypatch.chdir(root)

    surface = resolve_status_read(root, SLUG)

    assert (surface.path is None) != (surface.ref is None)
    if surface.path is not None:
        assert surface.path.exists()
        if mission.lane_worktree is not None:
            assert not surface.path.resolve().is_relative_to(mission.lane_worktree.resolve())
    # One declared source per cell, and the same one from every cwd.
    assert surface.repo_root.resolve() == mission.repo.resolve()
    if topology != LANES_WITH_COORD:
        assert surface.source is StatusReadSource.WRITE_CHECKOUT
    elif coord_state == MATERIALIZED:
        assert surface.source is StatusReadSource.COORD_WORKTREE
    else:
        # The EMPTY matrix cell's branch holds no log: the declared pre-seed fallback.
        expected = StatusReadSource.WRITE_CHECKOUT if coord_state == EMPTY else StatusReadSource.COORD_BRANCH_REF
        assert surface.source is expected


# ---------------------------------------------------------------------------
# FR-061: PRIMARY partition of a ``topology_source: default`` Mission
# ---------------------------------------------------------------------------


def _make_default(mission: MatrixMission) -> None:
    """Stamp the matrix Mission as a provisional default create held on its topic branch."""
    meta_path = mission.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"topology_source": "default", "topology_settled": False, "create_return_branch": "main"})
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    git(mission.repo, "checkout", "-q", "-b", MISSION_BRANCH)
    git(mission.repo, "add", "-A")
    git(mission.repo, "commit", "-q", "-m", "default create")


def test_default_mission_primary_partition_is_the_topic_branch_checkout(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default(mission)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.path is not None
    assert surface.path.resolve() == mission.root_mission_dir.resolve()
    primary = resolve_primary_partition_dir(mission.repo, SLUG)
    assert primary is not None
    assert primary.resolve() == mission.root_mission_dir.resolve()


def test_default_mission_off_its_topic_branch_reads_the_topic_branch(tmp_path: Path) -> None:
    """Open point (WP01 review): the repository root checkout moved off the topic branch.

    The write checkout no longer holds the Mission's branch, and no other checkout does: the
    declared source is the committed topic branch, never the root's working tree.
    """
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default(mission)
    git(mission.repo, "checkout", "-q", "-b", "second-default-create")
    decoy = mission.root_mission_dir / "status.events.jsonl"
    decoy.write_text("", encoding="utf-8")

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.MISSION_BRANCH_REF
    assert surface.ref == f"refs/heads/{MISSION_BRANCH}"
    assert _lanes(read_status_events(surface))[-1] == "in_progress"
    assert resolve_primary_partition_dir(mission.repo, SLUG) is None


def test_default_mission_topic_branch_in_another_checkout_reads_that_checkout(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default(mission)
    git(mission.repo, "checkout", "-q", "main")
    holder = tmp_path / "topic-holder"
    git(mission.repo, "worktree", "add", "-q", str(holder), MISSION_BRANCH)
    # The root checkout (on ``main``) still shows the Mission's untracked copy? No: ``main``
    # never carried it, so give the read a meta to find, as a leftover copy would.
    shutil.copytree(holder / KITTY_SPECS / SLUG, mission.root_mission_dir, dirs_exist_ok=True)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.path is not None
    assert surface.path.resolve() == (holder / KITTY_SPECS / SLUG).resolve()
    primary = resolve_primary_partition_dir(mission.repo, SLUG)
    assert primary is not None
    assert primary.resolve() == (holder / KITTY_SPECS / SLUG).resolve()


def _hold_topic_branch_elsewhere(mission: MatrixMission, holder: Path) -> None:
    """Root checkout back on ``main`` with a decoy copy; *holder* checks the topic branch out."""
    git(mission.repo, "checkout", "-q", "main")
    git(mission.repo, "worktree", "add", "-q", str(holder), MISSION_BRANCH)
    shutil.copytree(holder / KITTY_SPECS / SLUG, mission.root_mission_dir, dirs_exist_ok=True)
    (mission.root_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")


def test_default_mission_topic_branch_held_by_a_lane_worktree_reads_the_branch(tmp_path: Path) -> None:
    """Review cycle 1, N2: a lane worktree is never a status read source (ADR 2026-11-06-2).

    The topic branch is checked out in a registered lane worktree: the door skips it and reads
    the committed topic branch; the PRIMARY-partition location is not the lane's copy.
    """
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default(mission)
    lane = mission.repo / ".worktrees" / f"{SLUG}-lane-a"
    _hold_topic_branch_elsewhere(mission, lane)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.MISSION_BRANCH_REF
    assert surface.ref == f"refs/heads/{MISSION_BRANCH}"
    assert _lanes(read_status_events(surface))[-1] == "in_progress"
    assert resolve_primary_partition_dir(mission.repo, SLUG) is None


def test_default_mission_holder_without_mission_dir_reads_the_branch(tmp_path: Path) -> None:
    """Review cycle 1, N3: a holder with no Mission directory never falls back to the root's copy.

    The root checkout carries an emptied decoy log; the declared source is the committed topic
    branch, so the read sees its history, not the decoy's empty one.
    """
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default(mission)
    holder = tmp_path / "topic-holder"
    _hold_topic_branch_elsewhere(mission, holder)
    shutil.rmtree(holder / KITTY_SPECS / SLUG)

    surface = resolve_status_read(mission.repo, SLUG)

    assert surface.source is StatusReadSource.MISSION_BRANCH_REF
    assert surface.ref == f"refs/heads/{MISSION_BRANCH}"
    assert _lanes(read_status_events(surface))[-1] == "in_progress"
    assert resolve_primary_partition_dir(mission.repo, SLUG) is None


def test_one_status_read_source_enum() -> None:
    """Review cycle 1, N6: the status contract layer and the door share ONE read-source enum."""
    from specify_cli.coordination import status_service
    from specify_cli.status import read_surface

    assert status_service.StatusReadSource is read_surface.StatusReadSource
    assert status_service.EventLogReadContract.primary_checkout(Path("x")).source is StatusReadSource.WRITE_CHECKOUT


def test_runtime_bridge_reads_the_one_landed_reader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Review cycle 1, N5: the runtime bridge's landed check delegates to ``mission_has_landed``."""
    import mission_runtime
    from runtime.next import runtime_bridge

    seen: list[Path] = []

    def _fake(primary_dir: Path) -> bool:
        seen.append(primary_dir)
        return True

    monkeypatch.setattr(mission_runtime, "mission_has_landed", _fake)

    assert runtime_bridge._primary_mission_is_completed(tmp_path) is True
    assert seen == [tmp_path]


def test_explicit_topology_mission_keeps_target_placement(tmp_path: Path) -> None:
    """Positive control (FR-061): an explicit ``--topology`` Mission keeps today's placement."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)

    assert resolve_primary_partition_dir(mission.repo, SLUG) is None


def test_matrix_not_applicable_is_reexported() -> None:
    """Guard the shared fixture vocabulary this module depends on."""
    assert NOT_APPLICABLE == "n/a"
