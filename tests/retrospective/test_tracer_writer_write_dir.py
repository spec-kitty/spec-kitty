"""Red-first: the tracer writer writes IN PLACE at ``write_dir(TRACER_FILE)`` (WP10, T053/T055).

Mission coord-artifact-single-home-01M3V4BE, WP10 (single-home rule, FR-003 /
FR-007 / SC-003). At base, ``tracer_writer._local_staging_path`` stages the
trace in the REPOSITORY ROOT checkout (via the read resolver
``candidate_feature_dir_for_mission``), and ``commit_router``'s legacy
``shutil.copy2`` then copies it onto the coordination worktree -- leaving a
stale root copy (or relying on ``primary_paths_created_this_invocation`` R6
cleanup, which depends on the coord copy existing and matching byte for byte).
This pins the single-home contract: the write lands directly on the
coordination Mission dir, with NO root-checkout residue, and a refused write
(remote-only coordination branch) touches no disk at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.retrospective.tracer_writer import append_tracer_finding
from tests._factories.coord_mission import (
    CoordMission,
    COORD_TOPOLOGIES,
    make_coord_mission,
    make_prefix_coord_mission,
)
from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SEED_TRAILER = "Spec-Kitty-Coordination-Seed"


def _root_porcelain(coord: CoordMission) -> str:
    relpath = f"kitty-specs/{coord.mission_dir_name}"
    return subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", relpath],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _seed_commit_count(coord: CoordMission) -> int:
    trailer = subprocess.run(
        [
            "git",
            "-C",
            str(coord.repo_root),
            "log",
            f"--format=%(trailers:key={_SEED_TRAILER},valueonly)",
            coord.coordination_branch,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len([line for line in trailer.splitlines() if line.strip()])


def _append(coord: CoordMission, *, category: str = "tooling-friction", entry: str = "a finding", actor: str = "tester") -> WriteSeamResult:
    policy = ProtectionPolicy.resolve(coord.repo_root)
    return append_tracer_finding(
        repo_root=coord.repo_root,
        mission_slug=coord.mission_dir_name,
        category=category,
        entry=entry,
        actor=actor,
        policy=policy,
        target_branch=coord.target_branch,
    )


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_tracer_append_lands_on_coord_with_no_root_residue(tmp_path: Path, topology: MissionTopology) -> None:
    """A MATERIALIZED coordination Mission: the finding lands on the
    coordination worktree's ``traces/<category>.md`` directly, and the root
    checkout carries no trace of the write (no staged file, no untracked
    residue)."""
    coord = make_coord_mission(tmp_path, topology, materialized=True)
    root_status_before = _root_porcelain(coord)

    result = _append(coord)

    assert result.status in ("committed", "unchanged")
    coord_file = coord.coord_mission_dir / "traces" / "tooling-friction.md"
    assert coord_file.exists()
    assert "a finding" in coord_file.read_text(encoding="utf-8")
    root_file = coord.root_mission_dir / "traces" / "tooling-friction.md"
    assert not root_file.exists()
    assert _root_porcelain(coord) == root_status_before


def test_tracer_append_prefix_empty_seeds_then_writes_in_place(tmp_path: Path) -> None:
    """Pre-fix EMPTY coordination surface: the first append seeds the
    surface from root content (one seed commit, trailer present), then the
    finding is written in place on the coordination Mission dir -- never
    staged on the root checkout."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_status_before = _root_porcelain(coord)

    result = _append(coord)

    assert result.status in ("committed", "unchanged")
    coord_file = coord.coord_mission_dir / "traces" / "tooling-friction.md"
    assert coord_file.exists()
    assert "a finding" in coord_file.read_text(encoding="utf-8")
    assert _seed_commit_count(coord) == 1
    root_file = coord.root_mission_dir / "traces" / "tooling-friction.md"
    assert not root_file.exists()
    assert _root_porcelain(coord) == root_status_before


def test_tracer_append_two_sequential_appends_merge(tmp_path: Path) -> None:
    """The second append sees the first's entry and appends after it --
    never clobbering with a from-scratch file (the read-before-write
    contract, now routed through the OWNING coordination copy)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    first = _append(coord, entry="first finding")
    assert first.status in ("committed", "unchanged")
    second = _append(coord, entry="second finding")
    assert second.status in ("committed", "unchanged")

    coord_file = coord.coord_mission_dir / "traces" / "tooling-friction.md"
    content = coord_file.read_text(encoding="utf-8")
    assert "first finding" in content
    assert "second finding" in content
    # Exactly one seed commit -- the second append never re-seeds.
    assert _seed_commit_count(coord) == 1


def test_tracer_append_remote_only_refuses_before_any_write(tmp_path: Path) -> None:
    """A remote-only coordination branch (#4970 parity): the write is
    refused, with NO coordination worktree created, no seed, and nothing
    written anywhere on disk."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    root_status_before = _root_porcelain(coord)

    result = _append(coord)

    assert result.status == "refused"
    assert not coord.coord_worktree_path.exists()
    assert _root_porcelain(coord) == root_status_before
    assert result.surfaces == ()


# ---------------------------------------------------------------------------
# Coordinator check (from WP09/lane-o): on lane-o (WP07 tip, WITHOUT WP10's
# write_dir migration), ``tracer-append`` raised ``SafeCommitPathPolicyError``
# from the OLD ``_local_staging_path`` (``candidate_feature_dir_for_mission``)
# once the coordination Mission dir already carried committed content -- WP09
# reproduced it with no decision code involved, i.e. ANY pre-existing
# committed content in the coord dir was enough. This drives the REAL
# ``move-task`` CLI (a genuine status transition, not a hand-rolled fixture
# write) to commit real content onto the coordination branch first, then
# confirms ``tracer-append`` still succeeds and lands on that SAME branch.
# ---------------------------------------------------------------------------


def _commit_real_status_transition(coord: CoordMission) -> None:
    """Drive the REAL ``move-task`` CLI to land a genuine, committed status
    transition on the coordination Mission dir (never a hand-rolled git write)."""
    import json as _json

    import ulid as _ulid_mod
    from typer.testing import CliRunner

    from kernel.clock import now_utc_iso
    from specify_cli.cli.commands.agent.tasks import app as tasks_app
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

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
    subprocess.run(["git", "-C", str(coord.repo_root), "add", "kitty-specs"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "commit", "-q", "-m", "add WP01"], check=True, capture_output=True)

    runner = CliRunner()
    result = runner.invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "claimed", "--mission", coord.mission_dir_name, "--agent", "testbot", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    payload = _json.loads(next(line for line in result.stdout.splitlines() if line.strip().startswith("{")))
    assert payload.get("event_id"), result.stdout


def test_tracer_append_succeeds_after_a_real_status_transition_already_committed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Coordinator check (WP09/lane-o cross-report): a coordination Mission
    whose coordination Mission dir already carries committed content FROM A
    REAL STATUS TRANSITION (``move-task``, not tracer-append's own writer)
    must not block a SUBSEQUENT ``tracer-append`` -- the finding still lands
    on the SAME coordination branch."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    monkeypatch.chdir(coord.repo_root)
    _commit_real_status_transition(coord)
    assert (coord.coord_mission_dir / "status.events.jsonl").exists(), (
        "fixture invariant: the move-task CLI must have committed real content onto the coordination Mission dir"
    )

    result = _append(coord)

    assert result.status in ("committed", "unchanged"), result.diagnostic
    coord_file = coord.coord_mission_dir / "traces" / "tooling-friction.md"
    assert coord_file.exists()
    assert "a finding" in coord_file.read_text(encoding="utf-8")
    # Lands on the SAME coordination branch the status transition committed to.
    shown = subprocess.run(
        ["git", "-C", str(coord.repo_root), "show", f"{coord.coordination_branch}:kitty-specs/{coord.mission_dir_name}/traces/tooling-friction.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "a finding" in shown


@pytest.mark.parametrize("topology", (MissionTopology.SINGLE_BRANCH, MissionTopology.LANES))
def test_tracer_append_non_coord_topology_writes_at_same_primary_path(tmp_path: Path, topology: MissionTopology) -> None:
    """C-008: ``lanes``/``single_branch`` Missions (no coordination surface
    at all) write at the SAME primary path as before this WP, committed to
    the same ref."""
    slug = "no-coord-tracer-demo"
    # A non-default working branch: ``main``/``master`` are protected by
    # default (``ProtectionPolicy._DEFAULT_PROTECTED_BRANCHES``), which would
    # refuse the write for an orthogonal reason (FR-008) this test does not
    # exercise.
    _init_git_repo(tmp_path, branch="topic")
    result = _create_mission(tmp_path, slug, topology)
    feature_dir = result.feature_dir
    policy = ProtectionPolicy.resolve(tmp_path)

    write_result = append_tracer_finding(
        repo_root=tmp_path,
        mission_slug=slug,
        category="tooling-friction",
        entry="a finding",
        actor="tester",
        policy=policy,
        target_branch=result.target_branch,
    )

    assert write_result.status in ("committed", "unchanged")
    primary_file = feature_dir / "traces" / "tooling-friction.md"
    assert primary_file.exists()
    assert "a finding" in primary_file.read_text(encoding="utf-8")
