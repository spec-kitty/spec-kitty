"""Red-first state-matrix tests for the write-location core (mission coord-artifact-single-home-01M3V4BE, WP03).

See ``contracts/write-location-accessor.md`` / ``contracts/seed.md``. Fixtures
come from the shared harness (``tests/_factories/coord_mission.py``, WP02).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, Establishment, MissionArtifactKind, MissionTopology, TopologySurface, placement_seam
from specify_cli.coordination.coord_seed import (
    COORD_SEED_TRAILER,
    CoordBranchUndeclaredAndAbsent,
    CoordSeedForkRefused,
    establish_coord_write_location,
)
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state
from specify_cli.status.locking import FeatureStatusLockTimeoutError, feature_status_lock
from tests._factories.coord_mission import (
    COORD_TOPOLOGIES,
    CoordMission,
    event_ids,
    index_entry_ids,
    make_coord_mission,
    make_fork_fixture,
    make_prefix_coord_mission,
)
from tests._owned_fixtures import mint_test_fact

_DECISION_LOG = "decisions.events.jsonl"

pytestmark = [pytest.mark.fast]

_STATUS_LOG = "status.events.jsonl"

_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)


def _refs(coord: CoordMission) -> tuple[str, str]:
    target = subprocess.run(
        ["git", "-C", str(coord.repo_root), "rev-parse", coord.target_branch],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "-C", str(coord.repo_root), "rev-parse", coord.coordination_branch],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return target, branch


def _trailer_mission_ids(coord: CoordMission) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(coord.repo_root), "log", f"--format=%(trailers:key={COORD_SEED_TRAILER},valueonly)", coord.coordination_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# T012: the write-side assertion through the pre-existing entry point (C-002).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_write_side_uses_coord_dir_while_read_dir_keeps_the_empty_fallback(tmp_path: Path, topology: MissionTopology) -> None:
    """The write side diverges from today's read-side EMPTY fallback (C-002 stays green)."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")

    # Today's read-side EMPTY fallback: no coordination Mission dir yet, so
    # ``read_dir`` degrades to the repository root checkout.
    read_dir = placement_seam(coord.repo_root, coord.mission_dir_name).read_dir(MissionArtifactKind.STATUS_STATE)
    assert read_dir == coord.root_mission_dir

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.path == coord.coord_mission_dir
    assert location.surface is TopologySurface.COORD
    assert location.establishment is Establishment.SEEDED
    assert (location.path / _STATUS_LOG).exists()
    assert event_ids(location.path / _STATUS_LOG) == event_ids(coord.root_mission_dir / _STATUS_LOG)


# ---------------------------------------------------------------------------
# T017: state-row matrix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_materialized_is_side_effect_free(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_coord_mission(tmp_path, topology, materialized=True)
    before_target, before_branch = _refs(coord)

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.NONE
    assert location.coord_state_before is CoordState.MATERIALIZED
    after_target, after_branch = _refs(coord)
    assert (before_target, before_branch) == (after_target, after_branch)


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_unmaterialized_local_head_materializes(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.UNMATERIALIZED

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert coord.coord_worktree_path.exists()
    assert location.establishment is Establishment.SEEDED
    assert location.coord_state_before is CoordState.UNMATERIALIZED


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_remote_only_branch_refuses_and_writes_nothing(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, remote_only=True)

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert not coord.coord_worktree_path.exists()


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_deleted_branch_refuses(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, branch_deleted=True)

    with pytest.raises(CoordinationBranchDeleted):
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_prefix_empty_seeds(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.SEEDED
    assert location.seed is not None
    assert location.seed.coord_commit is not None
    mission_meta_id = _read_mission_id_for(coord)
    assert mission_meta_id in _trailer_mission_ids(coord)


def _read_mission_id_for(coord: CoordMission) -> str:
    import json

    meta = json.loads((coord.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    return str(meta["mission_id"])


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_post_fix_empty_restores_from_branch_with_loud_warning(tmp_path: Path, topology: MissionTopology, caplog: pytest.LogCaptureFixture) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    # First establish: pre-fix EMPTY -> SEEDED (the Mission becomes post-fix).
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.MATERIALIZED

    # Simulate the regression: the Mission dir is removed from the worktree.

    shutil.rmtree(coord.coord_mission_dir)
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.EMPTY

    with caplog.at_level("WARNING"):
        location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.RESTORED_FROM_BRANCH
    assert (coord.coord_mission_dir / _STATUS_LOG).exists()
    assert any("missing from worktree" in record.message for record in caplog.records)


def test_post_fix_empty_carries_root_only_records_too(tmp_path: Path) -> None:
    """B1 (review cycle 2, HIGH/data loss): a root-only record that lands AFTER
    the Mission went post-fix (e.g. a write that could not reach the coord
    surface before it was deleted) must still be carried by the restore-then-
    seed leg, not silently dropped because the re-probe sees MATERIALIZED and
    treats the restore as "nothing pending"."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    shutil.rmtree(coord.coord_mission_dir)
    with (coord.root_mission_dir / _STATUS_LOG).open("a", encoding="utf-8") as handle:
        handle.write('{"event_id": "01ROOTONLYAFTERSEED00000"}\n')

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.RESTORED_FROM_BRANCH
    ids = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    assert "01ROOTONLYAFTERSEED00000" in ids, ids


def test_post_fix_empty_restore_skipped_when_another_writer_already_won(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B2 (review cycle 2, concurrency/data loss): the restore-from-tip only
    happens under the lock, after a fresh re-probe. If the state is already
    MATERIALIZED by the time the lock is acquired (another writer's restore +
    seed already landed), this call must not re-run ``git checkout`` over it
    -- it falls through to the ordinary pending check instead."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    shutil.rmtree(coord.coord_mission_dir)
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.EMPTY

    from specify_cli.coordination import coord_seed as cs

    real_restore = cs._restore_coord_kind_paths_from_tip
    calls = {"n": 0}

    def _counting_restore(
        repo_root: Path,
        coordination_branch: str,
        mission_dir_name: str,
        coord_worktree: Path,
    ) -> tuple[str, ...]:
        calls["n"] += 1
        result: tuple[str, ...] = real_restore(repo_root, coordination_branch, mission_dir_name, coord_worktree)
        return result

    monkeypatch.setattr(cs, "_restore_coord_kind_paths_from_tip", _counting_restore)
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert calls["n"] == 1
    # A second establish call on an already-MATERIALIZED surface must never
    # call the restore helper again.
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# Fork refusal (NFR-002).
# ---------------------------------------------------------------------------


def test_fork_refuses_and_writes_nothing(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD, stream="status_log")
    root_before = (fixture.root_mission_dir / _STATUS_LOG).read_bytes()
    coord_before = (fixture.coord_mission_dir / _STATUS_LOG).read_bytes()

    with pytest.raises(CoordSeedForkRefused) as excinfo:
        establish_coord_write_location(fixture.repo_root, fixture.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    # The divergence is reported by the row's own ``event_id`` (the prefix/fork
    # classifier's unit), not the decision-payload id the fixture tracks
    # separately -- just assert both sides are named and genuinely differ.
    assert excinfo.value.first_divergence_root is not None
    assert excinfo.value.first_divergence_coord is not None
    assert excinfo.value.first_divergence_root != excinfo.value.first_divergence_coord
    assert excinfo.value.coord_ref == fixture.coordination_branch
    assert fixture.mission_dir_name in excinfo.value.coord_path
    assert (fixture.root_mission_dir / _STATUS_LOG).read_bytes() == root_before
    assert (fixture.coord_mission_dir / _STATUS_LOG).read_bytes() == coord_before


# ---------------------------------------------------------------------------
# Idempotence.
# ---------------------------------------------------------------------------


def test_second_call_is_idempotent(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    first = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert first.seed is not None and first.seed.coord_commit is not None

    before_ids = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    _, branch_before = _refs(coord)

    second = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    _, branch_after = _refs(coord)
    assert branch_before == branch_after
    assert second.seed is None
    after_ids = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    assert after_ids == before_ids
    assert len(set(after_ids)) == len(after_ids)


# ---------------------------------------------------------------------------
# Atomicity.
# ---------------------------------------------------------------------------


def test_rename_failure_cleans_up_temp_dir_and_next_call_heals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L3 (review cycle 2): a failed rename no longer leaves a stale temp dir --
    ``_write_merge_via_temp_rename`` removes it immediately on ``OSError``."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    import os as os_module

    real_rename = os_module.rename
    calls = {"n": 0}

    def _flaky_rename(src: str | Path, dst: str | Path) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated rename failure")
        real_rename(src, dst)

    monkeypatch.setattr(os_module, "rename", _flaky_rename)

    with pytest.raises(OSError, match="simulated rename failure"):
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.EMPTY
    stale = list((coord.coord_worktree_path / "kitty-specs").glob(f".{coord.mission_dir_name}.seed-*"))
    assert stale == [], "L3: the temp dir must not linger after a failed rename"

    monkeypatch.undo()
    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert location.establishment is Establishment.SEEDED
    assert not list((coord.coord_worktree_path / "kitty-specs").glob(f".{coord.mission_dir_name}.seed-*"))


# ---------------------------------------------------------------------------
# Root restoration.
# ---------------------------------------------------------------------------


def test_root_restoration_dirty_tracked_extra_events_removed(tmp_path: Path) -> None:
    """Root restoration, dirty-tracked variant: an extra uncommitted event appended
    to the already-committed root log is reset to HEAD after the carry."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty", extra_events=1)
    root_path = coord.root_mission_dir / _STATUS_LOG
    status_before = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", str(root_path.relative_to(coord.repo_root))],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status_before.strip().startswith("M") or "M" in status_before  # tracked + dirty (extra uncommitted event appended)

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.seed is not None
    assert str(root_path.relative_to(coord.repo_root)) in location.seed.restored_root
    status_after = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", str(root_path.relative_to(coord.repo_root))],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status_after.strip() == ""


def test_root_restoration_untracked_non_log_file_removed(tmp_path: Path) -> None:
    """Root restoration, untracked variant (B4 item 2): a root-only non-log COORD
    file that was never ``git add``-ed is carried then deleted from the root
    checkout, not merely reset (there is nothing tracked to reset to)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    untracked_path = coord.root_mission_dir / "issue-matrix.json"
    untracked_path.write_text('{"rows": {}}', encoding="utf-8")
    repo_relpath = str(untracked_path.relative_to(coord.repo_root))
    status_before = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", repo_relpath],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status_before.strip().startswith("??")

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.seed is not None
    assert "issue-matrix.json" in location.seed.carried
    assert repo_relpath in location.seed.restored_root
    assert not untracked_path.exists()
    assert (coord.coord_mission_dir / "issue-matrix.json").read_text(encoding="utf-8") == '{"rows": {}}'


# ---------------------------------------------------------------------------
# Lock reentrancy.
# ---------------------------------------------------------------------------


def test_lock_reentrancy_no_deadlock(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    with feature_status_lock(coord.repo_root, coord.mission_dir_name, timeout=5.0):
        location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.SEEDED


# ---------------------------------------------------------------------------
# NFR-002: event counts never shrink.
# ---------------------------------------------------------------------------


def test_nfr002_event_count_never_reduced(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty", extra_events=2)
    root_ids_before = event_ids(coord.root_mission_dir / _STATUS_LOG)

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    coord_ids_after = event_ids(location.path / _STATUS_LOG)
    assert set(root_ids_before) <= set(coord_ids_after)
    assert len(set(coord_ids_after)) == len(coord_ids_after)


# ---------------------------------------------------------------------------
# C-008 controls: non-coordination topologies pass through unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", [MissionTopology.LANES, MissionTopology.SINGLE_BRANCH])
def test_coordless_topology_is_primary_and_side_effect_free(tmp_path: Path, topology: MissionTopology) -> None:
    from specify_cli.core.mission_creation import create_mission_core
    from tests._factories import provision_test_charter
    from tests._support.git_template import clone_template

    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    subprocess.run(["git", "-C", str(repo), "add", ".kittify"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "chore(fixture): provision charter"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", "topic"], check=True, capture_output=True)
    create_mission_core(repo, "flat", topology=topology, target_branch="topic", allow_worktree_context=True)

    before = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout

    location = establish_coord_write_location(repo, "flat", MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.surface is TopologySurface.PRIMARY
    assert location.establishment is Establishment.NONE
    assert location.coord_state_before is None
    after = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
    assert before == after


# ---------------------------------------------------------------------------
# Negative test (round 5, X1): a pre-fix MATERIALIZED Mission (#5519 shape)
# with an extra uncommitted COORD record never gets a phantom seed commit.
# ---------------------------------------------------------------------------


def test_materialized_pre_fix_with_uncommitted_extra_record_never_seeds(tmp_path: Path) -> None:
    """Re-pinned (coord-artifact-single-home-01M3V4BE WP06 landed): a ``via="core"``
    create is now POST-fix (trailer-bearing) from birth (D4/D6), so
    ``make_coord_mission(materialized=True)`` no longer reaches the #5519
    pre-fix-but-MATERIALIZED shape this negative test needs -- it reaches a
    post-fix MATERIALIZED Mission instead. Build the #5519 shape explicitly:
    a genuine pre-fix Mission (``make_prefix_coord_mission``, branch cut
    before the Mission dir ever existed, no trailer) then materialized with a
    fixture seed commit that itself carries no trailer either (mirroring a
    Mission already forked and materialized outside this WP's own seed path).
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    worktree_path = CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)
    coord_dir = coord.coord_mission_dir
    coord_dir.mkdir(parents=True, exist_ok=True)
    root_log = coord.root_mission_dir / _STATUS_LOG
    (coord_dir / _STATUS_LOG).write_text(root_log.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree_path), "add", "kitty-specs"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(worktree_path), "commit", "-m", f"chore({coord.mission_dir_name}): fixture seed (no trailer)"],
        check=True,
        capture_output=True,
    )

    assert (
        COORD_SEED_TRAILER
        not in subprocess.run(
            ["git", "-C", str(coord.repo_root), "log", coord.coordination_branch],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    # Append an UNCOMMITTED extra row directly into the coordination copy.
    extra_row = '{"event_id": "01EXTRAUNCOMMITTEDROW0"}\n'
    with (coord.coord_mission_dir / _STATUS_LOG).open("a", encoding="utf-8") as handle:
        handle.write(extra_row)

    before_target, before_branch = _refs(coord)
    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    after_target, after_branch = _refs(coord)

    assert location.establishment is Establishment.NONE
    assert location.seed is None
    assert (before_target, before_branch) == (after_target, after_branch)
    assert not _trailer_mission_ids(coord)
    # The uncommitted row is untouched -- establish never commits, never discards it.
    assert extra_row.strip() in (coord.coord_mission_dir / _STATUS_LOG).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Defensive: a PRIMARY-partition kind returns the primary location (no probe).
# ---------------------------------------------------------------------------


def test_primary_kind_returns_primary_location_defensively(tmp_path: Path) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD)

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.SPEC, owned=None)

    assert location.surface is TopologySurface.PRIMARY
    assert location.establishment is Establishment.NONE
    assert location.path == coord.root_mission_dir


# ---------------------------------------------------------------------------
# B7/T016-step-6: a malformed or duplicate event-log row is translated into a
# structured, actionable error -- never a bare ``ValueError`` with no context.
# ---------------------------------------------------------------------------


def test_malformed_root_event_log_raises_structured_error(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    with (coord.root_mission_dir / _STATUS_LOG).open("a", encoding="utf-8") as handle:
        handle.write("not json at all\n")

    with pytest.raises(ActionContextError) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert excinfo.value.code == "COORD_SEED_EVENT_LOG_MALFORMED"
    message = str(excinfo.value)
    assert coord.mission_dir_name in message
    assert coord.coordination_branch in message


def test_duplicate_event_id_raises_structured_error(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    with (coord.root_mission_dir / _STATUS_LOG).open("a", encoding="utf-8") as handle:
        existing_id = event_ids(coord.root_mission_dir / _STATUS_LOG)[0]
        handle.write(json.dumps({"event_id": existing_id}) + "\n")

    with pytest.raises(ActionContextError) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert excinfo.value.code == "COORD_SEED_DUPLICATE_EVENT_ID"


# ---------------------------------------------------------------------------
# B4-1: the refused-then-retried seed commit (binding U1, T015).
# ---------------------------------------------------------------------------


class _RefusedCommit:
    status = "error"
    reason = "protected"
    commit_hash = None


def test_refused_seed_commit_then_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    from specify_cli.coordination import coord_seed as cs

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_log = coord.root_mission_dir / _STATUS_LOG
    root_bytes = root_log.read_bytes()
    # An untracked COORD record in the root checkout: carried by the first attempt,
    # its root copy must survive the refusal and go once a retry commits it.
    untracked_path = coord.root_mission_dir / "issue-matrix.json"
    untracked_path.write_text('{"rows": []}\n', encoding="utf-8")
    real_commit_seed = cs._commit_seed
    monkeypatch.setattr(cs, "_commit_seed", lambda req, paths: _RefusedCommit())

    with caplog.at_level("WARNING"):
        first = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert first.seed is not None
    assert first.seed.coord_commit is None
    assert first.seed.warnings
    assert any("not applied" in record.message for record in caplog.records)
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.MATERIALIZED
    assert not _trailer_mission_ids(coord)
    # Between the refusal and the retry the root copy is still there, untouched.
    assert first.seed.restored_root == ()
    assert root_log.read_bytes() == root_bytes
    assert untracked_path.exists()

    monkeypatch.setattr(cs, "_commit_seed", real_commit_seed)
    second = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert second.seed is not None
    assert second.seed.coord_commit is not None
    assert _trailer_mission_ids(coord)
    # The retry carried nothing, yet its successful commit restores the root copy.
    assert second.seed.carried == ()
    assert second.seed.restored_root, "a successful retry must restore the root copies it just committed"
    assert not untracked_path.exists()
    assert root_log.read_bytes() == root_bytes, "a tracked, clean root copy is left untouched (C-004)"

    before = subprocess.run(["git", "-C", str(coord.repo_root), "rev-parse", coord.coordination_branch], capture_output=True, text=True, check=True).stdout
    third = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    after = subprocess.run(["git", "-C", str(coord.repo_root), "rev-parse", coord.coordination_branch], capture_output=True, text=True, check=True).stdout
    assert before == after
    assert third.seed is None


def test_refused_seed_commit_keeps_the_root_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refused seed commit leaves the root copies in place.

    The coordination copy is then untracked content in the coordination worktree,
    the ONLY durable-looking copy of the carried records; unlinking the root
    copies too would leave a later create rollback ``rmtree``-ing the sole copy.
    """
    from specify_cli.coordination import coord_seed as cs

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_log = coord.root_mission_dir / _STATUS_LOG
    root_bytes = root_log.read_bytes()
    untracked_path = coord.root_mission_dir / "issue-matrix.json"
    untracked_path.write_text('{"rows": []}\n', encoding="utf-8")
    monkeypatch.setattr(cs, "_commit_seed", lambda req, paths: _RefusedCommit())

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.seed is not None
    assert location.seed.carried, "fixture invariant: the seed carried records out of the root checkout"
    assert location.seed.coord_commit is None
    assert location.seed.restored_root == ()
    assert location.seed.warnings
    assert root_log.read_bytes() == root_bytes
    assert untracked_path.exists()
    assert (location.path / _STATUS_LOG).exists()


@pytest.mark.parametrize("show_untracked_files", ["all", "no", "normal"])
def test_refused_seed_commit_retry_is_config_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, show_untracked_files: str) -> None:
    """B3: the pending-seed predicate must not depend on the operator's
    ``status.showUntrackedFiles``."""
    from specify_cli.coordination import coord_seed as cs

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    subprocess.run(["git", "-C", str(coord.repo_root), "config", "status.showUntrackedFiles", show_untracked_files], check=True, capture_output=True)
    real_commit_seed = cs._commit_seed
    monkeypatch.setattr(cs, "_commit_seed", lambda req, paths: _RefusedCommit())
    establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    monkeypatch.setattr(cs, "_commit_seed", real_commit_seed)
    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert location.seed is not None and location.seed.coord_commit is not None, location


# ---------------------------------------------------------------------------
# B4-3: I-SEED-5 non-log COORD file carry + conflicting-copies warning.
# ---------------------------------------------------------------------------


def test_non_log_coord_file_carried_conflict_warns_and_primary_never_copied(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    traces_dir = coord.root_mission_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    (traces_dir / "approach.md").write_text("root-only trace v1\n", encoding="utf-8")
    (coord.root_mission_dir / "spec.md").write_text("primary content\n", encoding="utf-8")

    first = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert first.seed is not None
    assert "traces/approach.md" in first.seed.carried
    assert (coord.coord_mission_dir / "traces" / "approach.md").read_text(encoding="utf-8") == "root-only trace v1\n"
    assert not (coord.coord_mission_dir / "spec.md").exists()  # I-SEED-9

    # Simulate the post-fix regression plus an independent root drift.
    shutil.rmtree(coord.coord_mission_dir)
    (traces_dir / "approach.md").write_text("root drifted v2\n", encoding="utf-8")

    second = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert second.establishment is Establishment.RESTORED_FROM_BRANCH
    assert second.seed is not None
    assert any("traces/approach.md" in warning for warning in second.seed.warnings)
    assert (coord.coord_mission_dir / "traces" / "approach.md").read_text(encoding="utf-8") == "root-only trace v1\n"
    assert (traces_dir / "approach.md").read_text(encoding="utf-8") == "root drifted v2\n"
    assert not (coord.coord_mission_dir / "spec.md").exists()  # I-SEED-9, again on the restore leg


# ---------------------------------------------------------------------------
# B4-4: D4 negative shape -- a branch cut AFTER the target commit (carrying
# PRIMARY files) is pre-fix, never RESTORED_FROM_BRANCH.
# ---------------------------------------------------------------------------


def test_d4_negative_branch_cut_after_target_commit_is_seeded_not_restored(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "d4@test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "D4"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")

    slug = "d4neg"
    mid8 = "01D4NEG0"
    coord_branch = CoordinationWorkspace.branch_name(slug, mid8)
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": (mid8 + "0" * 26)[:26],
        "mission_slug": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "friendly_name": "D4 negative",
        "topology": "coord",
        "coordination_branch": coord_branch,
        "mid8": mid8,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (mission_dir / "spec.md").write_text("primary spec content\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    # Cut the coordination branch AFTER the target commit: its tree carries
    # the PRIMARY files, without ever having been seeded (no trailer).
    subprocess.run(["git", "branch", coord_branch], cwd=repo, check=True)

    # Materialize for real, then delete the checked-out Mission dir to reach
    # the EMPTY state the D4 discriminator must classify correctly.
    coord_worktree = CoordinationWorkspace.resolve(repo, slug, mid8)
    shutil.rmtree(coord_worktree / "kitty-specs" / slug)
    assert probe_coord_state(repo, slug, mid8, coordination_branch=coord_branch) is CoordState.EMPTY

    with caplog.at_level("WARNING"):
        location = establish_coord_write_location(repo, slug, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.SEEDED
    assert not any("missing from worktree" in record.message for record in caplog.records)
    assert not (coord_worktree / "kitty-specs" / slug / "spec.md").exists()


# ---------------------------------------------------------------------------
# B4-5: the decisions stream (fork refusal and a normal carry).
# ---------------------------------------------------------------------------


def test_decisions_stream_fork_refuses(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD, stream="decision_log")

    with pytest.raises(CoordSeedForkRefused):
        establish_coord_write_location(fixture.repo_root, fixture.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)


def test_decisions_stream_carries_on_normal_seed(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    (coord.root_mission_dir / _DECISION_LOG).write_text('{"event_id": "01DECISIONROOTONLY0000"}\n', encoding="utf-8")

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.seed is not None
    assert _DECISION_LOG in location.seed.carried
    assert "01DECISIONROOTONLY0000" in event_ids(coord.coord_mission_dir / _DECISION_LOG)


# ---------------------------------------------------------------------------
# B4-6: the bounded status lock actually fires STATUS_LOCK_HELD.
# ---------------------------------------------------------------------------


def test_bounded_lock_fires_status_lock_held_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # ``coord_seed._seed_coord_surface`` reads the bound via
    # ``from specify_cli.status import BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`` (the
    # package re-export), so that is the binding to patch -- patching only
    # ``specify_cli.status.locking`` leaves the seed on the real 10 s bound.
    monkeypatch.setattr("specify_cli.status.BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", 1.0)
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    flag = tmp_path / "held"
    code = (
        "import time\nfrom pathlib import Path\nfrom specify_cli.status.locking import feature_status_lock\n"
        f"with feature_status_lock(Path({str(coord.repo_root)!r}), {coord.mission_dir_name!r}, timeout=20):\n"
        f"    Path({str(flag)!r}).write_text('x')\n"
        "    time.sleep(20)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], env=os.environ.copy())
    try:
        for _ in range(100):
            if flag.exists():
                break
            time.sleep(0.1)
        assert flag.exists(), "the holder subprocess never acquired the lock"

        with pytest.raises(FeatureStatusLockTimeoutError) as excinfo:
            establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
        assert excinfo.value.error_code == "STATUS_LOCK_HELD"
        assert excinfo.value.timeout == 1.0  # the patched bound reached the seed's acquire
        assert FeatureStatusLockTimeoutError.error_code == "STATUS_LOCK_HELD"
        assert not coord.coord_mission_dir.exists()
    finally:
        proc.kill()
        proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# B4-7: the owned arm (workspace-unavailable translation).
# ---------------------------------------------------------------------------


def test_owned_arm_translates_workspace_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.coordination import coord_seed as cs

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    owned_root = tmp_path / "owned-checkout"
    owned_mission_dir = owned_root / "kitty-specs" / coord.mission_dir_name
    owned_mission_dir.mkdir(parents=True)
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_mission_dir,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=MissionTopology.COORD,
    )

    def _boom(owned_arg: object, mission_slug: str, mid8: str) -> None:
        raise RuntimeError("workspace unavailable")

    monkeypatch.setattr(cs, "_establish_owned_coord_workspace", _boom)

    with pytest.raises(ActionContextError) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)
    assert excinfo.value.code == "OWNED_COORDINATION_WORKSPACE_UNAVAILABLE"


def test_owned_empty_pre_fix_seed_restores_against_owned_root_not_repository_root(tmp_path: Path) -> None:
    """WP04-review binding first step (WP07 prompt, coord-artifact-single-home-01M3V4BE):
    ``_restore_root_files`` / ``_to_repo_relpath`` (``coord_seed.py``) ran git
    against ``request.repo_root`` unconditionally, but for an owned checkout the
    root Mission dir lives under ``owned.owned_root`` -- a directory that is
    NEVER a subpath of the repository-root checkout (``OwnedCheckout``'s own
    invariant). Before the fix, ``Path.relative_to`` raises ``ValueError`` as
    soon as a pre-fix EMPTY seed actually carries a root record (this test's
    shape), instead of silently no-op'ing -- still a defect, just a loud one.

    Forward guard (owned+coordination is not yet reachable through a real CLI
    flow, T019 note in ``test_placement_seam_write_dir.py``): it becomes
    reachable as soon as an owned-capable writer migrates onto a coordination
    topology, so the seam's unconditional ``owned`` threading is pinned now.

    ``owned_root`` is a REAL second git worktree of the SAME repository
    (sharing one ``.git``, the production shape the owned-checkout docs
    describe -- see ``tests/_owned_fixtures.py``'s ``RSnapshotter``
    docstring), checked out onto the mission's own target branch, so the
    pre-fix root ``status.events.jsonl`` the fixture committed there is
    present, tracked and clean under ``owned_root`` -- never under
    ``coord.repo_root``.
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    owned_root = tmp_path / "owned-checkout"
    # Free ``coord.target_branch`` from the main worktree so it can be
    # checked out a second time at ``owned_root`` (git refuses the same
    # branch checked out in two worktrees at once).
    subprocess.run(["git", "-C", str(coord.repo_root), "checkout", "--detach", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "worktree", "add", "-q", str(owned_root), coord.target_branch], check=True, capture_output=True)
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=MissionTopology.COORD,
    )
    root_ids_before = event_ids(owned.mission_dir / _STATUS_LOG)
    assert root_ids_before  # the pre-fix root log genuinely carries records to restore/no-op over
    # Baseline snapshots, taken BEFORE the write: ``coord.repo_root``'s
    # ``kitty-specs`` tree already carries pre-existing fixture residue
    # unrelated to this seed (e.g. an uncommitted ``spec.md``), so the
    # control below asserts no NEW change rather than an absolute-empty
    # status.
    repo_root_status_before = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)

    assert location.establishment is Establishment.SEEDED
    assert location.seed is not None
    assert location.seed.carried  # non-empty: _restore_root_files actually iterates
    assert event_ids(location.path / _STATUS_LOG) == root_ids_before
    # the owned checkout's committed root copy is untouched (clean -> C-004 no-op),
    # and git never ran against the bare repository-root checkout for this path.
    owned_status = subprocess.run(
        ["git", "-C", str(owned_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert owned_status == ""
    repo_root_status_after = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert repo_root_status_after == repo_root_status_before


class _CommittedSeedCommit:
    status = "committed"
    reason = None
    commit_hash = "0" * 40


def test_owned_empty_pre_fix_seed_restores_dirty_root_copy_against_owned_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 1 N4: the sibling clean-root test above never actually
    exercises ``_restore_root_files``'s ``git checkout --`` branch (the
    "dirty" status arm) -- a clean root copy takes the no-op "clean" arm
    instead. This variant makes the owned root copy of the carried status
    log TRACKED and MODIFIED (uncommitted), so ``_git_path_status`` resolves
    it to ``"dirty"`` and the restore genuinely runs ``git checkout -- <path>``
    against ``owned_root`` -- never against ``coord.repo_root`` (same B4
    anchor-on-owned-root fix, now proven against the genuinely-dirty arm).

    The seed commit is stubbed as committed: the root restore only runs once the
    coordination copy is durable, and this fixture's real owned commit is
    refused (which would otherwise keep the root copy, see
    ``test_refused_seed_commit_keeps_the_root_copy``).
    """
    from specify_cli.coordination import coord_seed as cs

    monkeypatch.setattr(cs, "_commit_seed", lambda req, paths: _CommittedSeedCommit())
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    owned_root = tmp_path / "owned-checkout"
    subprocess.run(["git", "-C", str(coord.repo_root), "checkout", "--detach", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "worktree", "add", "-q", str(owned_root), coord.target_branch], check=True, capture_output=True)
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=MissionTopology.COORD,
    )
    root_log = owned.mission_dir / _STATUS_LOG
    committed_text = root_log.read_text(encoding="utf-8")
    root_ids_before = event_ids(root_log)
    assert root_ids_before

    # Dirty the tracked root copy (uncommitted local edit) under owned_root.
    with root_log.open("a", encoding="utf-8") as handle:
        handle.write('{"event_id": "01OWNEDDIRTYLOCALEDIT0000"}\n')
    owned_status_before = subprocess.run(
        ["git", "-C", str(owned_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert " M " in owned_status_before or owned_status_before.strip().startswith("M"), owned_status_before
    repo_root_status_before = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)

    assert location.establishment is Establishment.SEEDED
    assert location.seed is not None
    assert location.seed.carried
    # The carry step reads the root copy's CURRENT on-disk content (the
    # dirty, uncommitted edit included) before the restore step reverts it
    # -- so the dirty line is carried too, same as the pre-existing
    # committed rows.
    assert set(root_ids_before) < set(event_ids(location.path / _STATUS_LOG))
    assert "01OWNEDDIRTYLOCALEDIT0000" in event_ids(location.path / _STATUS_LOG)
    # The dirty local edit under owned_root was discarded by `git checkout
    # --` (restored to the committed HEAD content), proving the checkout ran
    # against owned_root, not the bare repository-root checkout.
    assert root_log.read_text(encoding="utf-8") == committed_text
    owned_status_after = subprocess.run(
        ["git", "-C", str(owned_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert owned_status_after == ""
    repo_root_status_after = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", "kitty-specs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert repo_root_status_after == repo_root_status_before


# ---------------------------------------------------------------------------
# B4-8 / B5: NFR-002 across fork-fixture shapes (b)/(c)/(d); shape (a) is
# covered by ``test_fork_refuses_and_writes_nothing`` above.
# ---------------------------------------------------------------------------


def test_nfr002_both_committed_shape_is_untouched(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD)
    root_ids_before = event_ids(fixture.root_mission_dir / _STATUS_LOG)
    coord_ids_before = event_ids(fixture.coord_mission_dir / _STATUS_LOG)

    establish_coord_write_location(fixture.repo_root, fixture.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert event_ids(fixture.root_mission_dir / _STATUS_LOG) == root_ids_before
    assert event_ids(fixture.coord_mission_dir / _STATUS_LOG) == coord_ids_before


def test_nfr002_fresh_clone_shape_preserves_both_histories(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "fresh_clone", MissionTopology.COORD)
    assert fixture.clone_root is not None
    coord_ids_before = event_ids(fixture.coord_mission_dir / _STATUS_LOG)
    root_ids_before = event_ids(fixture.root_mission_dir / _STATUS_LOG)
    assert coord_ids_before and root_ids_before and set(coord_ids_before) != set(root_ids_before)

    location = establish_coord_write_location(fixture.clone_root, fixture.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    coord_ids_after = event_ids(location.path / _STATUS_LOG)
    assert set(coord_ids_before) <= set(coord_ids_after)
    root_only = set(root_ids_before) - set(coord_ids_before)
    assert not (root_only & set(coord_ids_after))  # independent histories: never silently merged (C-003)


def test_nfr002_ledger_only_shape_preserves_the_decision(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    index_path = fixture.coord_mission_dir / "decisions" / "index.json"
    before_ids = index_entry_ids(index_path)
    assert fixture.decision_ids_coord[0] in before_ids

    establish_coord_write_location(fixture.repo_root, fixture.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    after_ids = index_entry_ids(index_path)
    assert before_ids <= after_ids
    assert fixture.decision_ids_coord[0] in after_ids


# ---------------------------------------------------------------------------
# B5: UNMATERIALIZED -> MATERIALIZED with no seed reports WORKTREE_MATERIALIZED.
# ---------------------------------------------------------------------------


def test_unmaterialized_to_materialized_without_seed_reports_worktree_materialized(tmp_path: Path) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "worktree", "remove", "--force", str(coord.coord_worktree_path)],
        check=True,
        capture_output=True,
    )
    assert probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch) is CoordState.UNMATERIALIZED

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.establishment is Establishment.WORKTREE_MATERIALIZED
    assert location.coord_state_before is CoordState.UNMATERIALIZED
    assert location.seed is None


# ---------------------------------------------------------------------------
# Review cycle 2 (B1-residual, Decision plan.design.undeclared-coord-branch):
# an UNDECLARED coordination_branch on a coordination-routed STORED topology
# must DERIVE the canonical branch (lanes.branch_naming) and proceed exactly
# as if declared when it exists, or refuse when it does not -- NEVER degrade
# to PRIMARY. A topology-less/legacy meta stays on the historical PRIMARY
# control, unaffected.
# ---------------------------------------------------------------------------


def _strip_coordination_branch_keep_topology(meta_path: Path) -> None:
    meta = json.loads(meta_path.read_text())
    assert meta.get("topology"), "fixture precondition: topology must survive the strip"
    del meta["coordination_branch"]
    meta_path.write_text(json.dumps(meta))


def _strip_topology_and_branch(meta_path: Path) -> None:
    meta = json.loads(meta_path.read_text())
    meta.pop("topology", None)
    meta.pop("coordination_branch", None)
    meta_path.write_text(json.dumps(meta))


def _add_owned_worktree_on_target(coord: CoordMission, owned_root: Path) -> None:
    subprocess.run(["git", "-C", str(coord.repo_root), "checkout", "--detach", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "worktree", "add", "-q", str(owned_root), coord.target_branch], check=True, capture_output=True)


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_undeclared_branch_derives_and_proceeds_non_owned(tmp_path: Path, topology: MissionTopology) -> None:
    """Non-owned: stored topology routes through coordination, the declared
    branch is absent, but the DERIVED canonical branch still exists in git --
    proceed exactly as if it had been declared (never PRIMARY)."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.surface is TopologySurface.COORD


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_undeclared_branch_refuses_when_derived_branch_absent_non_owned(tmp_path: Path, topology: MissionTopology) -> None:
    """Non-owned: the derived branch does not exist in git either ->
    CoordBranchUndeclaredAndAbsent, NEVER a silent PRIMARY degrade."""
    coord = make_prefix_coord_mission(tmp_path, topology, branch_deleted=True)
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")

    with pytest.raises(CoordBranchUndeclaredAndAbsent) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)
    assert excinfo.value.code == "COORD_BRANCH_UNDECLARED_AND_ABSENT"
    assert excinfo.value.derived_branch == coord.coordination_branch


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_undeclared_branch_derives_and_proceeds_owned(tmp_path: Path, topology: MissionTopology) -> None:
    """Owned: BOTH the owned copy and the repository-root fallback lack
    coordination_branch (a genuinely-undeclared Mission post-B1-fallback);
    the derived branch exists -> proceed exactly as if declared."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")
    owned_root = tmp_path / "owned-checkout"
    _add_owned_worktree_on_target(coord, owned_root)
    _strip_coordination_branch_keep_topology(owned_root / "kitty-specs" / coord.mission_dir_name / "meta.json")
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=topology,
    )

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)

    assert location.surface is TopologySurface.COORD


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_undeclared_branch_refuses_when_derived_branch_absent_owned(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, branch_deleted=True)
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")
    owned_root = tmp_path / "owned-checkout"
    _add_owned_worktree_on_target(coord, owned_root)
    _strip_coordination_branch_keep_topology(owned_root / "kitty-specs" / coord.mission_dir_name / "meta.json")
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=topology,
    )

    with pytest.raises(CoordBranchUndeclaredAndAbsent) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)
    assert excinfo.value.code == "COORD_BRANCH_UNDECLARED_AND_ABSENT"
    assert excinfo.value.derived_branch == coord.coordination_branch


def test_topology_less_legacy_meta_still_returns_primary_control(tmp_path: Path) -> None:
    """Positive control: a legacy / un-backfilled meta (no ``topology``, no
    ``coordination_branch``) is coord-LESS -- unaffected by the new gate;
    PRIMARY stays the historical answer."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    _strip_topology_and_branch(coord.root_mission_dir / "meta.json")

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=None)

    assert location.surface is TopologySurface.PRIMARY


def test_undeclared_branch_refuses_when_mid8_unresolvable(tmp_path: Path) -> None:
    """Edge case: topology routes through coordination, branch undeclared,
    and no mid8 disambiguator can even be resolved (bare slug, no mid8/
    mission_id in meta) -- still refuses, never degrades to PRIMARY."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="absent")
    meta_path = coord.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text())
    del meta["coordination_branch"]
    meta.pop("mid8", None)
    meta.pop("mission_id", None)
    meta_path.write_text(json.dumps(meta))

    with pytest.raises(CoordBranchUndeclaredAndAbsent) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_slug, MissionArtifactKind.STATUS_STATE, owned=None)
    assert excinfo.value.derived_branch is None


# ---------------------------------------------------------------------------
# Review cycle 3 (C3-B2): mutant M2 on _stored_topology_routes_through_
# coordination's owned clause (`return owned is not None and routes_through_
# coordination(owned.topology)` -> `return False`) survived every existing
# test, because every prior owned-arm test left the OWNED meta copy's own
# `topology` field intact -- satisfying the function's FIRST clause
# (`stored_topology_from_meta(meta)`) before the owned-specific clause is
# ever reached. These two cases strip the owned copy down to where ONLY
# `owned.topology` can save the Mission from degrading to PRIMARY -- the
# exact fail-open Decision plan.design.undeclared-coord-branch forbids.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["owned_meta_missing", "owned_meta_topologyless"])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_owned_topology_clause_resolves_coordination_when_meta_topology_is_unavailable(tmp_path: Path, topology: MissionTopology, case: str) -> None:
    """``owned.topology`` alone (never the owned meta copy's own ``topology``
    field, which this test strips/removes) must still route an owned
    coordination-routed Mission to the coordination surface, not PRIMARY."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")
    owned_root = tmp_path / "owned-checkout"
    _add_owned_worktree_on_target(coord, owned_root)
    owned_meta_path = owned_root / "kitty-specs" / coord.mission_dir_name / "meta.json"
    if case == "owned_meta_missing":
        owned_meta_path.unlink()
    else:
        assert case == "owned_meta_topologyless"
        meta = json.loads(owned_meta_path.read_text())
        meta.pop("coordination_branch", None)
        meta.pop("topology", None)
        owned_meta_path.write_text(json.dumps(meta))
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=topology,
    )

    location = establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)

    assert location.surface is TopologySurface.COORD


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_owned_topology_clause_refuses_when_meta_topology_and_derived_branch_are_both_absent(tmp_path: Path, topology: MissionTopology) -> None:
    """The absent-branch twin of the test above: owned meta missing AND the
    derived branch deleted from git -> CoordBranchUndeclaredAndAbsent, still
    reached only because ``owned.topology`` (not the meta copy) carries the
    coordination-routed verdict."""
    coord = make_prefix_coord_mission(tmp_path, topology, branch_deleted=True)
    _strip_coordination_branch_keep_topology(coord.root_mission_dir / "meta.json")
    owned_root = tmp_path / "owned-checkout"
    _add_owned_worktree_on_target(coord, owned_root)
    (owned_root / "kitty-specs" / coord.mission_dir_name / "meta.json").unlink()
    owned = mint_test_fact(
        repository_root=coord.repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / coord.mission_dir_name,
        mission_slug=coord.mission_dir_name,
        write_branch=coord.target_branch,
        topology=topology,
    )

    with pytest.raises(CoordBranchUndeclaredAndAbsent) as excinfo:
        establish_coord_write_location(coord.repo_root, coord.mission_dir_name, MissionArtifactKind.STATUS_STATE, owned=owned)
    assert excinfo.value.code == "COORD_BRANCH_UNDECLARED_AND_ABSENT"
