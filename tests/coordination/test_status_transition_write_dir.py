"""Red-first: status writes across coordination-surface states.

Mission coord-artifact-single-home-01M3V4BE, WP07, T037. Pins the
user-observable contract through the real move-task CLI entry point
(charter ATDD-First, C-005, ADR 2026-07-17-1) -- the review cycle 1 (B2)
correction: a prior revision of this file claimed the UNMATERIALIZED/EMPTY
scenarios could not be driven through the CLI because ``_mt_current_event_
lane`` reads blank for a never-seeded mission; the reviewer's probe showed
this is wrong for the common shape (``_write_wp01_task_file`` commits WP01's
``planned`` row to the ROOT log, exactly as ``finalize-tasks`` does, and
move-task's own read resolves it fine without ``--force``). Every scenario
below drives the real ``spec-kitty agent tasks move-task`` CLI.

The one shape that still needs a transactional-shell-level patch is the
MATERIALIZED-forked fixture (``make_fork_fixture``): its coordination log
already diverges before WP01 exists there at all, so move-task's
MATERIALIZED-read (which consults the coordination log, not the root one)
finds no WP01 row until one is seeded directly onto the coordination branch
(see ``_seed_wp01_planned_on_coord``) -- documented inline at that test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import ulid as _ulid_mod
from typer.testing import CliRunner

from kernel.clock import now_utc_iso
from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests._factories.coord_mission import (
    CoordMission,
    event_ids,
    make_fork_fixture,
    make_prefix_coord_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_STATUS_LOG = "status.events.jsonl"
_COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)


def _repo_root_coord_dir_porcelain(coord: CoordMission) -> str:
    relpath = f"kitty-specs/{coord.mission_dir_name}"
    return subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", relpath],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _seed_commit_count(coord: CoordMission) -> int:
    """Count ``Spec-Kitty-Coordination-Seed`` trailers on the coordination branch."""
    trailer = subprocess.run(
        [
            "git",
            "-C",
            str(coord.repo_root),
            "log",
            "--format=%(trailers:key=Spec-Kitty-Coordination-Seed,valueonly)",
            coord.coordination_branch,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len([line for line in trailer.splitlines() if line.strip()])


def _write_wp01_task_file(coord: CoordMission) -> None:
    """Register WP01 as ``finalize-tasks`` would: a task file, lanes.json, and
    a committed ``planned`` row in the ROOT checkout's status log.

    move-task's own pre-write precondition (``_mt_current_event_lane``) reads
    a WP's "current lane" from whichever surface is the mission's current
    read authority: the ROOT checkout for an UNMATERIALIZED/EMPTY coordination
    surface (there is nothing committed on the coordination branch yet to read
    from), the COORDINATION worktree once MATERIALIZED. This helper covers the
    former; ``_seed_wp01_planned_on_coord`` below covers the latter.
    """
    tasks_dir = coord.root_mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-fixture.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Fixture WP01\nexecution_mode: code_change\nagent: testbot\nsubtasks: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    write_lanes_json(
        coord.root_mission_dir,
        LanesManifest(
            version=1,
            mission_slug=coord.mission_dir_name,
            mission_id=None,
            mission_branch=f"kitty/mission-{coord.mission_dir_name}",
            target_branch=coord.target_branch,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/wp01/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )
    append_event(
        coord.root_mission_dir,
        StatusEvent(
            event_id=str(_ulid_mod.ULID()),
            mission_slug=coord.mission_dir_name,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at=now_utc_iso(),
            actor="fixture",
            force=False,
            execution_mode="worktree",
        ),
    )
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "add", "kitty-specs"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "commit", "-q", "-m", "add WP01"],
        check=True,
        capture_output=True,
    )


def _seed_wp01_planned_on_coord(coord: CoordMission) -> None:
    """Register WP01's canonical ``planned`` status directly on the
    COORDINATION branch -- for a MATERIALIZED mission, move-task's read
    authority is the coordination worktree, not the root checkout, so a
    root-only ``planned`` row (as ``_write_wp01_task_file`` commits) is
    invisible to it. Also writes the task file / lanes.json to the ROOT
    checkout (still the canonical home for planning artifacts).
    """
    tasks_dir = coord.root_mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-fixture.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Fixture WP01\nexecution_mode: code_change\nagent: testbot\nsubtasks: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    write_lanes_json(
        coord.root_mission_dir,
        LanesManifest(
            version=1,
            mission_slug=coord.mission_dir_name,
            mission_id=None,
            mission_branch=f"kitty/mission-{coord.mission_dir_name}",
            target_branch=coord.target_branch,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/wp01/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "add", "kitty-specs"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "commit", "-q", "-m", "add WP01 task file"],
        check=True,
        capture_output=True,
    )
    append_event(
        coord.coord_mission_dir,
        StatusEvent(
            event_id=str(_ulid_mod.ULID()),
            mission_slug=coord.mission_dir_name,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at=now_utc_iso(),
            actor="fixture",
            force=False,
            execution_mode="worktree",
        ),
    )
    subprocess.run(
        ["git", "-C", str(coord.coord_worktree_path), "add", "kitty-specs"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(coord.coord_worktree_path), "commit", "-q", "-m", "add WP01 planned to coord"],
        check=True,
        capture_output=True,
    )


def _move_task(coord: CoordMission, to_lane: str, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, dict[str, object] | None]:
    """Drive the real move-task CLI entry point -- never ``--force`` (B2: the
    common pre-fix/post-fix shapes do not need it once WP01 has a genuine
    ``planned`` row on the read authority surface)."""
    monkeypatch.chdir(coord.repo_root)
    result = runner.invoke(
        app,
        [
            "move-task",
            "WP01",
            "--to",
            to_lane,
            "--mission",
            coord.mission_dir_name,
            "--agent",
            "testbot",
            "--json",
        ],
        catch_exceptions=False,
    )
    stdout = result.stdout or ""
    payload: dict[str, object] | None = None
    if stdout.strip().startswith("{"):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return result.exit_code, stdout, payload


# ---------------------------------------------------------------------------
# UNMATERIALIZED + local branch: the worktree is materialized first, and the
# event lands there -- never on the repository root checkout (US2.3).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_move_task_unmaterialized_local_branch_materializes_and_writes_coord(tmp_path: Path, topology: MissionTopology, monkeypatch: pytest.MonkeyPatch) -> None:
    """``make_prefix_coord_mission(worktree="absent")`` is UNMATERIALIZED with a
    never-seeded (pre-fix) coordination branch: once the worktree is
    materialized, the Mission dir is still absent from the branch (EMPTY), so
    the seed carries the root records over exactly as the pre-fix EMPTY
    scenario does -- this test's distinguishing assertion is the
    materialization itself (US2.3), not an absence of carried content.
    """
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    _write_wp01_task_file(coord)
    before_coord_worktree_exists = coord.coord_worktree_path.exists()
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, payload = _move_task(coord, "claimed", monkeypatch)

    assert exit_code == 0, stdout
    assert coord.coord_worktree_path.exists()
    assert not before_coord_worktree_exists
    coord_log = coord.coord_mission_dir / _STATUS_LOG
    assert coord_log.exists()
    assert payload is not None
    assert payload["event_id"] in coord_log.read_text(encoding="utf-8")
    # The root copy is restored (clean): no new untracked/modified COORD
    # residue beyond whatever pre-existing fixture state the baseline carries.
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# Pre-fix EMPTY: root records are carried over ONCE (the seed), the new event
# is appended after them, and the logical clock continues (US2.4/US2.5).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_move_task_prefix_empty_seeds_then_writes_coord(tmp_path: Path, topology: MissionTopology, monkeypatch: pytest.MonkeyPatch) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    _write_wp01_task_file(coord)
    root_ids_before = event_ids(coord.root_mission_dir / _STATUS_LOG)
    assert root_ids_before
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, payload = _move_task(coord, "claimed", monkeypatch)

    assert exit_code == 0, stdout
    assert payload is not None
    new_event_id = payload["event_id"]
    coord_ids_after = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    # coord log = carried root events + the new (transition plus any
    # companion annotation rows move-task's own fan-out appends in the same
    # call -- the CLI writes more than the bare lane-transition row, e.g. an
    # actor-resolution annotation, so this does not assert an exact "+1").
    assert set(root_ids_before) <= set(coord_ids_after)
    assert new_event_id in coord_ids_after
    assert len(coord_ids_after) > len(root_ids_before)
    assert len(coord_ids_after) == len(set(coord_ids_after))  # no duplicate event ids
    # The new content's logical ("Lamport") position in the coordination log
    # is strictly after every carried root event -- it never interleaves
    # before one of them. Plain lane-transition rows carry no explicit
    # numeric lamport field (``tests._factories.coord_mission._row_lamport``'s
    # own docstring: "plain lane-transition rows carry neither"), so append
    # ORDER is the observable proxy for that ordering: every carried id's
    # position precedes every genuinely-new id's position.
    carried_positions = [coord_ids_after.index(rid) for rid in root_ids_before]
    new_positions = [i for i, eid in enumerate(coord_ids_after) if eid not in root_ids_before]
    assert new_positions, "move-task appended nothing new"
    assert max(carried_positions) < min(new_positions)
    assert new_event_id in coord_ids_after
    # The coordination branch carries exactly one seed commit.
    assert _seed_commit_count(coord) == 1
    # The root copy is restored (clean): no new untracked/modified COORD
    # residue beyond whatever pre-existing fixture state the baseline carries.
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# Post-fix EMPTY (post-tasks squad R-m3): the Mission went post-fix (its
# coordination branch already carries the seed trailer), but its Mission dir
# has since been removed from the coord worktree -- the restore-from-tip leg,
# not the carry-from-root leg.
# ---------------------------------------------------------------------------


def test_move_task_post_fix_empty_restores_from_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    _write_wp01_task_file(coord)

    # First move-task: pre-fix EMPTY -> SEEDED (the mission becomes post-fix).
    exit_code, stdout, _payload = _move_task(coord, "claimed", monkeypatch)
    assert exit_code == 0, stdout
    assert _seed_commit_count(coord) == 1

    # Simulate the regression: the Mission dir is removed from the coord
    # worktree (contracts/seed.md's post-fix-EMPTY shape).
    shutil.rmtree(coord.coord_mission_dir)
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    with caplog.at_level(logging.WARNING):
        exit_code, stdout, payload = _move_task(coord, "in_progress", monkeypatch)

    assert exit_code == 0, stdout
    assert payload is not None
    # A loud WARNING names the regression before restoring.
    assert any("missing from worktree" in record.message for record in caplog.records)
    # The event lands on the restored coordination log.
    coord_log = coord.coord_mission_dir / _STATUS_LOG
    assert coord_log.exists()
    assert payload["event_id"] in coord_log.read_text(encoding="utf-8")
    # Nothing new is written to the root checkout.
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


def test_move_task_second_call_after_seed_carries_nothing_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    _write_wp01_task_file(coord)
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code1, stdout1, payload1 = _move_task(coord, "claimed", monkeypatch)
    assert exit_code1 == 0, stdout1
    ids_after_first = event_ids(coord.coord_mission_dir / _STATUS_LOG)

    exit_code2, stdout2, payload2 = _move_task(coord, "in_progress", monkeypatch)
    assert exit_code2 == 0, stdout2
    ids_after_second = event_ids(coord.coord_mission_dir / _STATUS_LOG)

    assert set(ids_after_first) <= set(ids_after_second)
    assert len(ids_after_second) == len(set(ids_after_second))  # no duplicate event ids
    # Each move-task call appends at least its own transition row (plus any
    # companion annotation rows its own fan-out writes) -- the second call's
    # own content is strictly new, never re-seeding what the first already
    # carried.
    assert len(ids_after_second) > len(ids_after_first)
    assert payload2 is not None
    assert payload2["event_id"] in ids_after_second
    assert payload2["event_id"] not in ids_after_first
    # The seed commit from the FIRST call is not repeated by the second.
    assert _seed_commit_count(coord) == 1
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# Remote-only branch: refused before anything is written (#4970 parity).
# ---------------------------------------------------------------------------


def test_move_task_remote_only_branch_refuses_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    _write_wp01_task_file(coord)
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, _payload = _move_task(coord, "claimed", monkeypatch)

    assert exit_code != 0
    assert "is unmaterialized" in stdout
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before
    assert not coord.coord_worktree_path.exists()


# ---------------------------------------------------------------------------
# DELETED branch: refused loudly with a recovery hint (US2.8).
# ---------------------------------------------------------------------------


def test_move_task_deleted_branch_refuses_with_recovery_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, branch_deleted=True)
    _write_wp01_task_file(coord)
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, _payload = _move_task(coord, "claimed", monkeypatch)

    assert exit_code != 0
    assert "declared in meta.json but deleted from git" in stdout
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# MATERIALIZED-forked (#5519 shape, fork builder (a)): the write succeeds and
# the event lands on the coordination log -- no COORD_SEED_FORK_REFUSED
# lockout (the seed only runs on EMPTY).
# ---------------------------------------------------------------------------


def test_move_task_materialized_forked_mission_is_not_locked_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``make_fork_fixture``'s coordination log already diverges from the root
    one before WP01 exists anywhere -- move-task's MATERIALIZED-state read
    consults the COORDINATION log (not root), so a root-only ``planned`` row
    (``_write_wp01_task_file``) is invisible to it; ``_seed_wp01_planned_on_
    coord`` seeds WP01 directly onto the coordination branch instead, the
    same place a real finalize-tasks run would have landed it for an
    already-materialized mission.
    """
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD)
    _seed_wp01_planned_on_coord(fixture)
    coord_ids_before = event_ids(fixture.coord_mission_dir / _STATUS_LOG)

    exit_code, stdout, payload = _move_task(fixture, "claimed", monkeypatch)

    assert exit_code == 0, stdout
    assert payload is not None
    coord_ids_after = event_ids(fixture.coord_mission_dir / _STATUS_LOG)
    assert set(coord_ids_before) <= set(coord_ids_after)
    assert payload["event_id"] in coord_ids_after
    # No COORD_SEED_FORK_REFUSED lockout: the write lands (at least the
    # transition row, plus any companion annotation rows move-task's own
    # fan-out appends in the same call).
    assert len(coord_ids_after) > len(coord_ids_before)


# ---------------------------------------------------------------------------
# T043 step 3 (review-WP08.md B4): mark-status's write leg, driven through the
# real ``make_prefix_coord_mission(worktree="empty")`` fixture the prompt
# names (never ``make_mission``, which is UNMATERIALIZED with no carry).
# ---------------------------------------------------------------------------


def _write_wp01_task_file_with_subtask(coord: CoordMission) -> None:
    """Like :func:`_write_wp01_task_file`, but WP01 carries one subtask
    (``T001``) for ``mark-status`` to resolve and transition."""
    tasks_dir = coord.root_mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-fixture.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Fixture WP01\nexecution_mode: code_change\nagent: testbot\nsubtasks:\n  - T001\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (coord.root_mission_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(coord.repo_root), "add", "kitty-specs"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "commit", "-q", "-m", "add WP01 task file with T001"], check=True, capture_output=True)


def _mark_status(coord: CoordMission, task_id: str, status: str, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, dict[str, object] | None]:
    """Drive the real ``mark-status`` CLI entry point."""
    monkeypatch.chdir(coord.repo_root)
    result = runner.invoke(
        app,
        ["mark-status", task_id, "--status", status, "--mission", coord.mission_dir_name, "--json"],
        catch_exceptions=False,
    )
    stdout = result.stdout or ""
    payload: dict[str, object] | None = None
    if stdout.strip().startswith("{"):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return result.exit_code, stdout, payload


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_mark_status_prefix_empty_seeds_then_writes_coord(tmp_path: Path, topology: MissionTopology, monkeypatch: pytest.MonkeyPatch) -> None:
    """T043 step 3: a pre-fix EMPTY coordination surface is seeded with the
    root log's prior events, the new mark-status row lands strictly AFTER
    every carried event, and the ROOT log itself gains nothing (the write
    now lands on the coordination surface only, via ``ports.coord.
    feature_write_dir`` -- never ``resolve_status_surface(...).parent``)."""
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    _write_wp01_task_file_with_subtask(coord)
    root_ids_before = event_ids(coord.root_mission_dir / _STATUS_LOG)
    assert root_ids_before
    root_log_bytes_before = (coord.root_mission_dir / _STATUS_LOG).read_bytes()
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, payload = _mark_status(coord, "T001", "done", monkeypatch)

    assert exit_code == 0, stdout
    assert payload is not None
    coord_ids_after = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    assert set(root_ids_before) <= set(coord_ids_after)
    assert len(coord_ids_after) > len(root_ids_before)
    assert len(coord_ids_after) == len(set(coord_ids_after))  # no duplicate event ids
    # Carry order: every carried root event's position in the coordination
    # log precedes every genuinely-new id's position (same proxy
    # `test_move_task_prefix_empty_seeds_then_writes_coord` uses -- plain
    # lane-transition/subtask rows carry no explicit numeric lamport field).
    carried_positions = [coord_ids_after.index(rid) for rid in root_ids_before]
    new_positions = [i for i, eid in enumerate(coord_ids_after) if eid not in root_ids_before]
    assert new_positions, "mark-status appended nothing new"
    assert max(carried_positions) < min(new_positions)
    # The root log is byte-identical to before -- nothing is written there.
    assert (coord.root_mission_dir / _STATUS_LOG).read_bytes() == root_log_bytes_before
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


def test_mark_status_remote_only_branch_renders_hint_not_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T045 edge case: a remote-only coordination branch cannot be
    materialized for a write -- mark-status must refuse with the same
    recovery-hint message move-task renders (``"is unmaterialized"``), never
    an unhandled traceback, and must write nothing to the root checkout
    first."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    _write_wp01_task_file_with_subtask(coord)
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    exit_code, stdout, _payload = _mark_status(coord, "T001", "done", monkeypatch)

    assert exit_code != 0
    assert "is unmaterialized" in stdout, stdout
    assert "Traceback" not in stdout, stdout
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# T042: the single write-location accessor's own seed L1
# (``feature_status_lock``, keyed by the coord mission's dir name) is
# re-entrant within a caller's thread, and refuses loudly (``STATUS_LOCK_HELD``)
# against a genuinely different holder. Exercised directly at the
# ``write_dir`` boundary (the accessor WP03/WP04 delivered and this WP's
# writers all route through) rather than through the full transactional
# emit: ``status_transition.py``'s OUTER L1 acquire wraps the whole emit with
# its own (effectively unbounded) wait, which would otherwise mask the
# seed's own bounded timeout behind a successful-after-the-holder-releases
# retry -- exactly the layer this WP owns and changed.
# ---------------------------------------------------------------------------


def _write_dir(coord: CoordMission) -> Path:
    from mission_runtime import MissionArtifactKind, placement_seam

    return placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.STATUS_STATE).path


def test_seed_lock_is_reentrant_for_a_caller_already_holding_it(tmp_path: Path) -> None:
    """A caller that already holds ``feature_status_lock`` for this mission
    can still trigger a seed-performing ``write_dir`` call on the SAME
    thread without deadlocking -- the lock is re-entrant per thread
    (``status/locking.py::feature_status_lock`` docstring), and the seed's
    own acquire (``coord_seed.py``) must honor that, not introduce a second,
    non-reentrant lock object keyed the same way.
    """
    from specify_cli.status.locking import feature_status_lock

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_ids_before = event_ids(coord.root_mission_dir / _STATUS_LOG)
    assert root_ids_before

    with feature_status_lock(coord.repo_root, coord.mission_dir_name, timeout=5.0):
        resolved = _write_dir(coord)

    assert resolved == coord.coord_mission_dir
    coord_ids_after = event_ids(resolved / _STATUS_LOG)
    assert set(root_ids_before) <= set(coord_ids_after)


def test_seed_lock_contention_from_a_different_holder_refuses_status_lock_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuinely different holder (a separate thread, never this test's own
    thread) blocking the SAME lock key must make a seed-triggering
    ``write_dir`` call refuse with ``FeatureStatusLockTimeoutError``
    (``error_code == "STATUS_LOCK_HELD"``) -- and leave nothing written: no
    coord log, no root-checkout residue.
    """
    import threading

    import specify_cli.status as status_package
    from specify_cli.status.locking import FeatureStatusLockTimeoutError, feature_status_lock

    # ``coord_seed._seed_coord_surface`` does
    # ``from specify_cli.status import BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS``
    # LOCALLY on every call, so the name it reads is the re-export on the
    # ``specify_cli.status`` PACKAGE -- not the defining
    # ``specify_cli.status.locking`` attribute (a re-export is a second,
    # independent binding; patching only the defining module leaves the
    # seed on the real 10 s bound, which outlives the holder's 5 s hold and
    # lets the seed acquire the lock -- the "DID NOT RAISE" failure).
    seed_budget_seconds = 0.3
    monkeypatch.setattr(status_package, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", seed_budget_seconds)
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_status_before = _repo_root_coord_dir_porcelain(coord)

    holder_ready = threading.Event()
    release_holder = threading.Event()

    def _hold_lock() -> None:
        with feature_status_lock(coord.repo_root, coord.mission_dir_name, timeout=5.0):
            holder_ready.set()
            release_holder.wait(timeout=5.0)

    holder_thread = threading.Thread(target=_hold_lock)
    holder_thread.start()
    try:
        assert holder_ready.wait(timeout=5.0), "the holder thread never acquired the lock"

        with pytest.raises(FeatureStatusLockTimeoutError) as exc_info:
            _write_dir(coord)
        assert exc_info.value.error_code == "STATUS_LOCK_HELD"
        # Proves the bounded budget the seed actually used is the patched one
        # (and that the refusal came from the seed's own acquire), so a
        # patch that silently misses the read site can never pass vacuously.
        assert exc_info.value.timeout == seed_budget_seconds
    finally:
        release_holder.set()
        holder_thread.join(timeout=5.0)

    # Nothing was written: the coord Mission dir was never seeded, and the
    # root checkout carries no new residue from the refused attempt.
    assert not coord.coord_mission_dir.exists()
    assert _repo_root_coord_dir_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# Review cycle 1 B3 (diff coverage): the two ``_canonical_coord_mission_slug``
# fallback branches no existing fixture's mission-slug shape ever reaches --
# every ``make_prefix_coord_mission``/``make_fork_fixture`` mission dir name
# is ALREADY the canonical ``<slug>-<mid8>`` form, so the literal
# ``read_primary_meta`` probe always declares on the first try and neither
# the owned short-circuit nor the degenerate "composing changes nothing"
# fallback is ever exercised through those fixtures. Pinned here directly
# against both sibling copies (``status_transition.py`` and
# ``transaction.py``) with a unit-level construction instead.
# ---------------------------------------------------------------------------


def test_status_transition_canonical_coord_mission_slug_owned_short_circuits(tmp_path: Path) -> None:
    """``identity.owned is not None`` returns ``owned.mission_slug`` with zero
    I/O -- ``seam_repo_root`` is never touched, so a nonexistent path proves
    no filesystem read happened."""
    from tests._owned_fixtures import mint_test_fact

    from specify_cli.coordination.status_transition import _canonical_coord_mission_slug, _TransactionIdentity

    owned = mint_test_fact(
        repository_root=tmp_path / "does-not-exist-repo",
        owned_root=tmp_path / "does-not-exist-owned",
        mission_dir=tmp_path / "does-not-exist-owned" / "kitty-specs" / "demo-01ABCDEF",
        mission_slug="demo-01ABCDEF",
        write_branch="main",
        topology=MissionTopology.COORD,
    )
    identity = _TransactionIdentity(
        repo_root=tmp_path / "does-not-exist-repo",
        feature_dir=tmp_path / "does-not-exist-repo" / "kitty-specs" / "demo-01ABCDEF",
        mission_id=None,
        mid8="01ABCDEF",
        destination_ref="main",
        meta_exists=False,
        coordination_branch=None,
        transaction_meta_exists=False,
        owned=owned,
    )

    assert _canonical_coord_mission_slug(identity, "whatever-caller-passed") == "demo-01ABCDEF"


def test_status_transition_canonical_coord_mission_slug_degenerate_composition(tmp_path: Path) -> None:
    """A literal ``mission_slug`` that already embeds ``mid8`` but whose
    ``meta.json`` does not declare coordination (no meta.json at all here):
    composing is a no-op (``composed == mission_slug``), so the function
    gives up and returns the literal rather than attempting a second,
    identical read."""
    from specify_cli.coordination.status_transition import _canonical_coord_mission_slug, _TransactionIdentity

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    identity = _TransactionIdentity(
        repo_root=repo_root,
        feature_dir=repo_root / "kitty-specs" / "demo-01ABCDEF",
        mission_id=None,
        mid8="01ABCDEF",
        destination_ref="main",
        meta_exists=False,
        coordination_branch=None,
        transaction_meta_exists=False,
        owned=None,
    )

    assert _canonical_coord_mission_slug(identity, "demo-01ABCDEF") == "demo-01ABCDEF"


def test_transaction_canonical_coord_mission_slug_owned_short_circuits(tmp_path: Path) -> None:
    from tests._owned_fixtures import mint_test_fact

    from specify_cli.coordination.transaction import _canonical_coord_mission_slug

    owned = mint_test_fact(
        repository_root=tmp_path / "does-not-exist-repo",
        owned_root=tmp_path / "does-not-exist-owned",
        mission_dir=tmp_path / "does-not-exist-owned" / "kitty-specs" / "demo-01ABCDEF",
        mission_slug="demo-01ABCDEF",
        write_branch="main",
        topology=MissionTopology.COORD,
    )

    result = _canonical_coord_mission_slug(tmp_path / "does-not-exist-repo", "whatever-caller-passed", "01ABCDEF", owned=owned)

    assert result == "demo-01ABCDEF"


def test_transaction_canonical_coord_mission_slug_degenerate_composition(tmp_path: Path) -> None:
    from specify_cli.coordination.transaction import _canonical_coord_mission_slug

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = _canonical_coord_mission_slug(repo_root, "demo-01ABCDEF", "01ABCDEF", owned=None)

    assert result == "demo-01ABCDEF"


def test_transaction_resolve_coord_worktree_root_wraps_unexpected_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuinely unexpected ``write_dir`` failure (not one of the four typed
    coordination refusals) becomes :class:`BookkeepingWorktreeMissing`,
    naming the coordination identity and wrapping the original cause --
    never an unclassified exception reaching a caller that only expects this
    module's own error hierarchy."""
    import specify_cli.coordination.transaction as transaction_module
    from specify_cli.coordination.transaction import (
        BookkeepingWorktreeMissing,
        _resolve_coord_worktree_root_for_transaction,
    )

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("placement seam exploded")

    monkeypatch.setattr(transaction_module, "placement_seam", _boom)

    with pytest.raises(BookkeepingWorktreeMissing) as excinfo:
        _resolve_coord_worktree_root_for_transaction(
            repo_root=tmp_path,
            mission_slug="demo-01ABCDEF",
            mid8="01ABCDEF",
            owned=None,
        )
    assert "demo-01ABCDEF" in str(excinfo.value)
    assert "placement seam exploded" in str(excinfo.value)


def test_commit_idempotent_no_ops_when_the_seed_already_committed_everything(tmp_path: Path) -> None:
    """Review cycle 1 N1 / cycle 2 R1 (the no-op half): the single
    write-location accessor's seed can commit a pre-fix EMPTY mission's root
    records onto the coordination branch as a side effect of
    ``BookkeepingTransaction.acquire`` resolving WHERE to write -- before
    this caller ever stages anything. ``commit_idempotent`` must then no-op
    successfully (not raise ``BookkeepingCommitFailed``), because THIS
    transaction's own acquire just seeded the surface
    (``_seed_committed_this_txn`` is True, set from the ``Establishment``
    ``write_dir`` returned -- ``SEEDED`` for a pre-fix EMPTY mission)."""
    import json

    from specify_cli.coordination.transaction import BookkeepingTransaction

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    meta = json.loads((coord.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(meta["mission_id"])

    with BookkeepingTransaction.acquire(
        repo_root=coord.repo_root,
        mission_id=mission_id,
        mission_slug=coord.mission_slug,
        mid8=coord.mid8,
        destination_ref=coord.coordination_branch,
        operation="N1 seed-already-committed no-op",
    ) as txn:
        assert not txn._staged_paths
        assert txn._seed_committed_this_txn  # THIS acquire's own seed ran
        receipt = txn.commit_idempotent("status: should no-op")

    assert receipt is not None
    assert (coord.coord_mission_dir / _STATUS_LOG).exists()
