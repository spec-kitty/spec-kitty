"""Issue #4889 (P0): fail closed instead of silently re-cutting a destroyed lane.

Pre-fix, ``allocate_lane_worktree`` consulted no WP lane state before its
FRESH routes: when a lane's worktree AND local branch were both gone (agent
crash, an operator's manual cleanup, ...) while the WP was still non-terminal
and its committed work unreachable from the target branch, the allocator
silently cut a brand-new empty lane from the coordination tip, printed
``Lane worktree ready``, exited 0, and overwrote
``.kittify/workspaces/<slug>-lane-<id>.json`` -- stranding the WP's real,
committed work with nothing left pointing at it.

Red-first per ADR 2026-07-17-1: every assertion below describes the DESIRED
post-fix behavior (refusal), so before ``DestroyedLaneError`` existed these
tests were RED against the silent-recut defect.

Every test derives its OWN mission identity (:func:`_ids`) rather than
sharing a module constant: this fixture spans real git worktrees, branches,
and a coordination worktree, all keyed by ``mission_slug``/``mid8`` on disk.
The local test harness's temp-dir allocator was observed to truncate long
parametrized node ids to an identical prefix, which -- combined with a
shared mission slug -- produced cross-test ``.kittify/workspaces/*.json``
collisions (a later test's "no persisted context" precondition silently
inheriting an earlier test's saved context). Per-test identity sidesteps
that class of pollution independent of its root cause.

See ../../kitty-specs/implement-lane-recut-and-planning-commit-integrity-01M3CM55/
contracts/destroyed-lane-guard.md and data-model.md#4889-destroyed-lane-decision-table.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    DestroyedLaneError,
    allocate_lane_worktree,
)
from specify_cli.missions._create import ensure_coordination_branch
from specify_cli.missions._read_path_resolver import coord_feature_dir
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from specify_cli.workspace.context import (
    WorkspaceContext,
    get_context_path,
    save_context,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

WP_ID = "WP01"
LANE_ID = "lane-a"
TARGET_BRANCH = "main"


@dataclass(frozen=True)
class MissionIds:
    """Per-test mission identity (never shared across tests -- see module docstring)."""

    mid8: str
    mission_id: str
    mission_slug: str


def _ids(tag: str) -> MissionIds:
    """Derive a unique (mid8, mission_id, mission_slug) triple from ``tag``.

    ``tag`` should be the requesting test's own node id (``request.node.name``)
    so every test -- including every parametrized variant -- gets its own
    mission identity, independent of tmp_path allocation quirks.
    """
    digest = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:6].upper()
    mid8 = f"01{digest}"
    mission_id = mid8 + "0" * 18
    mission_slug = f"destroyed-lane-{digest.lower()}"
    return MissionIds(mid8=mid8, mission_id=mission_id, mission_slug=mission_slug)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", TARGET_BRANCH)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, ids: MissionIds, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": ids.mission_id,
        "mission_slug": ids.mission_slug,
        "mid8": ids.mid8,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "created_at": "2026-09-25T00:00:00+00:00",
        "friendly_name": "Destroyed lane fixture",
        "coordination_branch": coordination_branch,
    }
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_manifest(ids: MissionIds, coordination_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=ids.mission_slug,
        mission_id=ids.mission_id,
        mission_branch=coordination_branch,
        target_branch=TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-25T00:00:00Z",
        computed_from="test",
    )


def _append_status_event(coord_status_dir: Path, ids: MissionIds, from_lane: str, to_lane: str, suffix: str) -> None:
    event = StatusEvent(
        event_id=f"01AAAAAAAAAAAAAAAAAAAAAA{suffix}",
        mission_slug=ids.mission_slug,
        wp_id=WP_ID,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-09-25T10:00:00+00:00",
        actor="test",
        force=False,
        execution_mode="worktree",
    )
    append_event(coord_status_dir, event)


#: Realistic transition chains for each non-terminal post-allocation lane the
#: guard must trigger on (contract regression assertion #3 / US1-S6).
_TRANSITION_CHAINS: dict[str, list[tuple[str, str]]] = {
    "in_progress": [("genesis", "planned"), ("planned", "claimed"), ("claimed", "in_progress")],
    "blocked": [
        ("genesis", "planned"),
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "blocked"),
    ],
    "for_review": [
        ("genesis", "planned"),
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
    ],
    "in_review": [
        ("genesis", "planned"),
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
        ("for_review", "in_review"),
    ],
}


def _seed_status(coord_status_dir: Path, ids: MissionIds, to_lane: str) -> None:
    coord_status_dir.mkdir(parents=True, exist_ok=True)
    chain = _TRANSITION_CHAINS[to_lane]
    for index, (from_lane, dest_lane) in enumerate(chain):
        _append_status_event(coord_status_dir, ids, from_lane, dest_lane, str(index))


def _materialize_coord(repo: Path, ids: MissionIds) -> tuple[Path, Path]:
    """Materialize the coord worktree and return (coord_root, coord_status_dir).

    ``coord_status_dir`` is the ``kitty-specs/<slug>`` mission dir INSIDE the
    coord worktree -- the exact composition
    ``mission_runtime.resolution._classify_artifact_surface`` probes via
    ``probe_coord_state`` / ``coord_feature_dir`` to decide MATERIALIZED vs
    EMPTY. Status events must land here (never at the coord worktree root)
    or the probe classifies the coord surface as EMPTY and silently falls
    back to PRIMARY (production ``finalize-tasks`` creates this subdir; a
    hand-built fixture must mirror it).
    """
    coord_root = CoordinationWorkspace.resolve(repo, ids.mission_slug, ids.mid8)
    coord_status_dir = coord_feature_dir(repo, ids.mission_slug, ids.mid8)
    coord_status_dir.mkdir(parents=True, exist_ok=True)
    return coord_root, coord_status_dir


def _seed_base_mission(repo: Path, ids: MissionIds) -> str:
    """Init the repo, mint the coord branch, and commit meta.json. Returns coord_branch."""
    _init_repo(repo)
    coord_result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=ids.mission_slug,
        mission_id=ids.mission_id,
        target_branch=TARGET_BRANCH,
    )
    assert coord_result.created
    coord_branch = coord_result.branch_name

    feature_dir = repo / "kitty-specs" / ids.mission_slug
    _write_meta(feature_dir, ids, coordination_branch=coord_branch)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: meta")
    return coord_branch


def _save_context(repo: Path, ids: MissionIds, worktree_path: Path, branch: str, base_branch: str, base_commit: str) -> WorkspaceContext:
    context = WorkspaceContext(
        wp_id=WP_ID,
        mission_slug=ids.mission_slug,
        worktree_path=str(worktree_path.relative_to(repo)),
        branch_name=branch,
        base_branch=base_branch,
        base_commit=base_commit,
        dependencies=[],
        created_at="2026-09-25T10:00:00+00:00",
        created_by="test",
        vcs_backend="git",
        lane_id=LANE_ID,
        lane_wp_ids=[WP_ID],
        current_wp=WP_ID,
    )
    save_context(repo, context)
    return context


def _build_destroyed_lane_fixture(tmp_path: Path, ids: MissionIds, *, to_lane: str = "in_progress") -> tuple[Path, LanesManifest, Path, str, WorkspaceContext]:
    """Build a coord-topology mission, allocate lane-a, commit real work, then
    destroy the worktree + branch while the WP is still ``to_lane``.

    Returns (repo, manifest, worktree_path, branch, context) -- worktree_path
    and branch are what USED to exist (both gone by the time this returns);
    context is the persisted :class:`WorkspaceContext` snapshot.
    """
    repo = tmp_path / "repo"
    coord_branch = _seed_base_mission(repo, ids)

    # Materialize + advance the coordination worktree (status writes etc.) so
    # the coord tip diverges from ``main`` -- this is what makes the
    # ``base_commit`` ancestor-of-target check genuinely False below (the
    # #4889 defect condition), not an accident of same-SHA triviality.
    coord_dir, coord_status_dir = _materialize_coord(repo, ids)
    (coord_dir / "coord-marker.txt").write_text("coord progress\n", encoding="utf-8")
    _git(coord_dir, "add", "coord-marker.txt")
    _git(coord_dir, "commit", "-q", "-m", "coord: progress")

    _seed_status(coord_status_dir, ids, to_lane)

    manifest = _make_manifest(ids, coord_branch)
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=ids.mission_slug,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert branch_exists(repo, branch)

    # Real committed work in the lane -- genuinely unreachable from target
    # after the branch is deleted below (never merged, dangling post -D).
    (worktree_path / "feature.py").write_text("value = 42\n", encoding="utf-8")
    _git(worktree_path, "add", "feature.py")
    _git(worktree_path, "commit", "-q", "-m", "feat: WP01 real work")

    base_commit = _git(repo, "rev-parse", coord_branch)
    context = _save_context(repo, ids, worktree_path, branch, coord_branch, base_commit)

    # Confirm the base_commit really is NOT an ancestor of target -- otherwise
    # this fixture would not exercise the #4889 defect condition at all.
    reach = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base_commit, TARGET_BRANCH],
        capture_output=True,
        text=True,
    )
    assert reach.returncode != 0, "fixture bug: base_commit must NOT be reachable from target for the #4889 repro to be meaningful"

    # Destroy the lane: worktree removed, local branch force-deleted. The
    # committed work is now dangling -- reachable only via reflog/fsck.
    _git(repo, "worktree", "remove", "--force", str(worktree_path))
    _git(repo, "branch", "-D", branch)
    assert not worktree_path.exists()
    assert not branch_exists(repo, branch)

    return repo, manifest, worktree_path, branch, context


class TestDestroyedLaneRefusesViaCli:
    """T001: the real allocator entry point refuses instead of re-cutting."""

    def test_destroyed_lane_refuses_via_cli(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        ids = _ids(request.node.name)
        repo, manifest, worktree_path, branch, context = _build_destroyed_lane_fixture(tmp_path, ids)

        context_path = get_context_path(repo, f"{ids.mission_slug}-{LANE_ID}")
        before = context_path.read_text(encoding="utf-8")

        with pytest.raises(DestroyedLaneError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=ids.mission_slug,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        err = exc_info.value
        assert err.error_code == "DESTROYED_LANE"
        assert err.branch_name == branch
        assert err.wp_id == WP_ID
        assert err.lane_id == LANE_ID
        # Diagnostic names the missing branch and a concrete recovery path.
        assert branch in str(err)
        assert "reflog" in str(err) or "fsck" in str(err)
        assert err.to_dict()["error_code"] == "DESTROYED_LANE"
        assert err.to_dict()["branch_name"] == branch

        # No side effects: no new worktree/branch, lane metadata untouched.
        assert not worktree_path.exists()
        assert not branch_exists(repo, branch)
        assert context_path.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("to_lane", ["blocked", "for_review", "in_review"])
    def test_destroyed_lane_refuses_for_every_non_terminal_state(self, tmp_path: Path, to_lane: str, request: pytest.FixtureRequest) -> None:
        """Contract assertion #3 / US1-S6: NOT just ``in_progress``."""
        ids = _ids(request.node.name)
        repo, manifest, worktree_path, branch, context = _build_destroyed_lane_fixture(tmp_path, ids, to_lane=to_lane)

        with pytest.raises(DestroyedLaneError):
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=ids.mission_slug,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        assert not worktree_path.exists()
        assert not branch_exists(repo, branch)


class TestDestroyedLaneNoSuccessLine:
    """T005: the refusal path must never claim success."""

    def test_no_lane_worktree_ready_on_refusal(self, tmp_path: Path, request: pytest.FixtureRequest, capsys: pytest.CaptureFixture[str]) -> None:
        ids = _ids(request.node.name)
        repo, manifest, _worktree_path, _branch, _context = _build_destroyed_lane_fixture(tmp_path, ids)

        with pytest.raises(DestroyedLaneError):
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=ids.mission_slug,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        captured = capsys.readouterr()
        assert "Lane worktree ready" not in captured.out
        assert "Lane worktree ready" not in captured.err


class TestControlArmsPreserved:
    """T007: REUSE / CRASH_RECOVERY / genuinely-fresh / re-open-after-merge
    must all still succeed -- NFR-001 zero false positives.
    """

    def test_reuse_no_false_refusal(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """Intact worktree -> REUSE no-op resume, even with non-terminal state."""
        ids = _ids(request.node.name)
        repo = tmp_path / "repo"
        coord_branch = _seed_base_mission(repo, ids)

        _coord_root, coord_status_dir = _materialize_coord(repo, ids)
        _seed_status(coord_status_dir, ids, "in_progress")

        manifest = _make_manifest(ids, coord_branch)
        worktree_path, branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        base_commit = _git(repo, "rev-parse", coord_branch)
        _save_context(repo, ids, worktree_path, branch, coord_branch, base_commit)

        # Worktree + branch are INTACT -- re-entering must resume, not refuse.
        result_path, result_branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        assert result_path == worktree_path
        assert result_branch == branch

    def test_crash_recovery_no_false_refusal(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """Branch intact, worktree gone -> CRASH_RECOVERY re-attach, not refusal."""
        ids = _ids(request.node.name)
        repo = tmp_path / "repo"
        coord_branch = _seed_base_mission(repo, ids)

        _coord_root, coord_status_dir = _materialize_coord(repo, ids)
        _seed_status(coord_status_dir, ids, "in_progress")

        manifest = _make_manifest(ids, coord_branch)
        worktree_path, branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        base_commit = _git(repo, "rev-parse", coord_branch)
        _save_context(repo, ids, worktree_path, branch, coord_branch, base_commit)

        # Remove ONLY the worktree; the branch survives (crash-recovery shape).
        _git(repo, "worktree", "remove", "--force", str(worktree_path))
        assert branch_exists(repo, branch)

        result_path, result_branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        assert result_path == worktree_path
        assert result_branch == branch
        assert result_path.exists()

    def test_genuinely_fresh_no_false_refusal(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """No persisted context at all -> ordinary fresh creation (FR-001)."""
        ids = _ids(request.node.name)
        repo = tmp_path / "repo"
        coord_branch = _seed_base_mission(repo, ids)

        manifest = _make_manifest(ids, coord_branch)
        # No WorkspaceContext saved, no status events -- a brand new WP.
        worktree_path, branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        assert worktree_path.exists()
        assert branch_exists(repo, branch)

    def test_reopen_after_merge_no_false_refusal(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """Persisted tip already an ancestor of target -> resume, no refusal (FR-009)."""
        ids = _ids(request.node.name)
        repo = tmp_path / "repo"
        coord_branch = _seed_base_mission(repo, ids)

        coord_dir, coord_status_dir = _materialize_coord(repo, ids)
        (coord_dir / "coord-marker.txt").write_text("coord progress\n", encoding="utf-8")
        _git(coord_dir, "add", "coord-marker.txt")
        _git(coord_dir, "commit", "-q", "-m", "coord: progress")
        # Status left non-terminal (a stale, un-updated snapshot -- exactly
        # the shape that would otherwise false-positive without the REACH
        # check).
        _seed_status(coord_status_dir, ids, "in_progress")

        manifest = _make_manifest(ids, coord_branch)
        worktree_path, branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        base_commit = _git(repo, "rev-parse", coord_branch)
        _save_context(repo, ids, worktree_path, branch, coord_branch, base_commit)

        # Simulate "the mission already merged" -- a real (non-squash) merge
        # of the coordination branch into target makes base_commit reachable
        # from target.
        _git(repo, "checkout", "-q", TARGET_BRANCH)
        _git(repo, "merge", "--no-ff", "-q", "-m", "merge coord into target", coord_branch)

        reach = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", base_commit, TARGET_BRANCH],
            capture_output=True,
            text=True,
        )
        assert reach.returncode == 0, "fixture bug: base_commit must be reachable from target for this control arm"

        # Destroy the lane, exactly like the defect repro -- but this time
        # REACH is True, so no refusal.
        _git(repo, "worktree", "remove", "--force", str(worktree_path))
        _git(repo, "branch", "-D", branch)

        result_path, result_branch = allocate_lane_worktree(repo_root=repo, mission_slug=ids.mission_slug, wp_id=WP_ID, lanes_manifest=manifest)
        assert result_path == worktree_path
        assert result_branch == branch
        assert result_path.exists()


class TestCanonicalStatusReadsCoordSurface:
    """T004: the guard must read status via the COORD surface, never a
    hand-rolled ``materialize(repo_root/"kitty-specs"/slug)`` PRIMARY read
    (which is sparse-excluded on coord topology and would silently no-op).
    """

    def test_status_dir_resolves_to_coord_worktree_not_primary(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        ids = _ids(request.node.name)
        repo, _manifest, _worktree_path, _branch, _context = _build_destroyed_lane_fixture(tmp_path, ids)

        status_dir = placement_seam(repo, ids.mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
        primary_dir = repo / "kitty-specs" / ids.mission_slug

        assert status_dir != primary_dir
        assert (status_dir / "status.events.jsonl").exists()
        assert not (primary_dir / "status.events.jsonl").exists()
