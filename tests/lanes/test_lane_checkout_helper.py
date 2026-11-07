"""Every lane checkout comes from one helper and shows no Mission status files.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP09 (FR-021, FR-040, SC-004;
ADR 2026-07-29-1 Amendment 2026-11-06 and ADR 2026-04-03-1 Amendment 2026-11-06).

Each test drives a REAL creation route against a real git repository:

* the allocator's fresh routes (coordination and ``lanes`` topology) and its
  crash-recovery route;
* the ``lifecycle_sync`` recreate;
* the review checkout (``agent/workflow.py::_create_review_worktree``);
* the ``implement --recover`` recreate (``lanes/recovery.py::recover_worktree``).

After every route the checkout must hold no ``status.events.jsonl`` /
``status.json`` on disk, while the lane branch tree still carries the
fork-time blob (C-008: no lane-side deletion commit). The every-route table is
keyed by the helper's route enum, so a new route without a driver here fails.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "checkout-helper-01KZQ7AB"
MISSION_ID = "01KZQ7ABCDEFGHJKMNPQRSTVWX"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LANE_ID = "lane-a"
LANE_BRANCH = f"kitty/mission-{MISSION_SLUG}-lane-a"
STATUS_FILES = ("status.events.jsonl", "status.json")
_EVENT_ROW = '{"actor":"tester","event_id":"01KZQ7AB000000000000000001","wp_id":"WP01"}\n'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def _manifest(*, mission_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-11-06T00:00:00Z",
        computed_from="test",
    )


def _seed_mission(tmp_path: Path, *, topology: str) -> Path:
    """A repository whose committed Mission dir carries both status files.

    ``topology`` is ``lanes`` (no coordination branch: the allocator's
    FRESH_LEGACY route) or ``lanes_with_coord`` (a ``coordination_branch`` in
    ``meta.json``: the FRESH_COORD route).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, str] = {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": "main",
        "topology": topology,
    }
    mission_branch = f"kitty/mission-{MISSION_SLUG}"
    if topology == "lanes_with_coord":
        meta["coordination_branch"] = COORD_BRANCH
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (feature_dir / "tasks" / "WP01-test.md").write_text("---\nwork_package_id: WP01\nexecution_mode: code_change\n---\n# WP01\n", encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text(_EVENT_ROW, encoding="utf-8")
    (feature_dir / "status.json").write_text("{}\n", encoding="utf-8")
    write_lanes_json(feature_dir, _manifest(mission_branch=mission_branch))
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed Mission")
    if topology == "lanes_with_coord":
        _git(repo, "branch", COORD_BRANCH)
    return repo


def _allocate(repo: Path, *, topology: str) -> tuple[Path, str]:
    from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

    mission_branch = COORD_BRANCH if topology == "lanes_with_coord" else f"kitty/mission-{MISSION_SLUG}"
    return allocate_lane_worktree(repo, MISSION_SLUG, "WP01", _manifest(mission_branch=mission_branch))


def _drop_checkout(repo: Path, checkout: Path) -> None:
    """Lose the checkout directory but keep the lane branch (a crash, a prune)."""
    shutil.rmtree(checkout)
    _git(repo, "worktree", "prune")


def _assert_no_status_files_on_disk(repo: Path, checkout: Path, branch: str) -> None:
    mission_dir = checkout / "kitty-specs" / MISSION_SLUG
    assert (mission_dir / "spec.md").exists(), "the rest of the Mission dir must stay on disk"
    for name in STATUS_FILES:
        assert not (mission_dir / name).exists(), f"{name} is on disk in the lane checkout {checkout}"
        # C-008: the fork-time blob stays in lane history -- no deletion commit.
        _git(repo, "cat-file", "-e", f"{branch}:kitty-specs/{MISSION_SLUG}/{name}")
    assert _git(checkout, "symbolic-ref", "-q", "HEAD") == f"refs/heads/{branch}", "a lane checkout is never detached"


# --- route drivers ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Opened:
    repo: Path
    checkout: Path
    branch: str


def _drive_allocation_fresh(tmp_path: Path) -> _Opened:
    repo = _seed_mission(tmp_path, topology="lanes_with_coord")
    checkout, branch = _allocate(repo, topology="lanes_with_coord")
    return _Opened(repo, checkout, branch)


def _drive_allocation_legacy(tmp_path: Path) -> _Opened:
    repo = _seed_mission(tmp_path, topology="lanes")
    checkout, branch = _allocate(repo, topology="lanes")
    return _Opened(repo, checkout, branch)


def _drive_recovery(tmp_path: Path) -> _Opened:
    repo = _seed_mission(tmp_path, topology="lanes")
    checkout, _branch = _allocate(repo, topology="lanes")
    _drop_checkout(repo, checkout)
    checkout, branch = _allocate(repo, topology="lanes")
    return _Opened(repo, checkout, branch)


def _drive_lifecycle_sync(tmp_path: Path) -> _Opened:
    from specify_cli.lanes.lifecycle_sync import sync_lane_after_coordination_commit

    repo = _seed_mission(tmp_path, topology="lanes_with_coord")
    checkout, branch = _allocate(repo, topology="lanes_with_coord")
    _drop_checkout(repo, checkout)
    report = sync_lane_after_coordination_commit(repo_root=repo, mission_slug=MISSION_SLUG, wp_id="WP01", coordination_branch=COORD_BRANCH)
    assert report is not None and report.succeeded
    return _Opened(repo, checkout, branch)


def _review_workspace(repo: Path) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="lane_workspace",
        workspace_name=f"{MISSION_SLUG}-{LANE_ID}",
        worktree_path=repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_ID}",
        branch_name=LANE_BRANCH,
        lane_id=LANE_ID,
        lane_wp_ids=["WP01"],
    )


def _drive_review(tmp_path: Path) -> _Opened:
    from specify_cli.cli.commands.agent.workflow import _create_review_worktree

    repo = _seed_mission(tmp_path, topology="lanes")
    workspace = _review_workspace(repo)
    _create_review_worktree(workspace, repo, "WP01", start_point="main")
    return _Opened(repo, repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_ID}", LANE_BRANCH)


def _drive_recreate(tmp_path: Path) -> _Opened:
    from specify_cli.lanes.recovery import RecoveryState, recover_worktree

    repo = _seed_mission(tmp_path, topology="lanes")
    _git(repo, "branch", LANE_BRANCH, "main")
    state = RecoveryState(
        wp_id="WP01",
        lane_id=LANE_ID,
        branch_name=LANE_BRANCH,
        branch_exists=True,
        worktree_exists=False,
        context_exists=False,
        status_lane="in_progress",
        has_commits=False,
        recovery_action="recreate_worktree",
    )
    recover_worktree(repo, MISSION_SLUG, state)
    return _Opened(repo, repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_ID}", LANE_BRANCH)


_ROUTE_DRIVERS: dict[str, Callable[[Path], _Opened]] = {
    "allocation_fresh": _drive_allocation_fresh,
    "allocation_legacy": _drive_allocation_legacy,
    "recovery": _drive_recovery,
    "lifecycle_sync": _drive_lifecycle_sync,
    "review": _drive_review,
    "recreate": _drive_recreate,
}


def test_every_helper_route_has_a_driver() -> None:
    """A route added to the helper without a driver here fails (no route can skip the exclusion)."""
    from specify_cli.lanes.lane_checkout import LaneCheckoutRoute

    assert {route.value for route in LaneCheckoutRoute} == set(_ROUTE_DRIVERS)


@pytest.mark.parametrize("route", sorted(_ROUTE_DRIVERS))
def test_every_route_checkout_has_no_status_files(route: str, tmp_path: Path) -> None:
    opened = _ROUTE_DRIVERS[route](tmp_path)
    _assert_no_status_files_on_disk(opened.repo, opened.checkout, opened.branch)


# --- named acceptance scenarios (T048) ---------------------------------------------------------


def test_lanes_topology_allocation_has_no_status_files_on_disk(tmp_path: Path) -> None:
    opened = _drive_allocation_legacy(tmp_path)
    _assert_no_status_files_on_disk(opened.repo, opened.checkout, opened.branch)


def test_review_checkout_has_no_status_files(tmp_path: Path) -> None:
    opened = _drive_review(tmp_path)
    _assert_no_status_files_on_disk(opened.repo, opened.checkout, opened.branch)


def test_crash_recovery_checkout_has_no_status_files(tmp_path: Path) -> None:
    opened = _drive_recovery(tmp_path)
    _assert_no_status_files_on_disk(opened.repo, opened.checkout, opened.branch)


def test_lane_tip_hook_fires_in_helper_checkout(tmp_path: Path) -> None:
    """The review checkout is the first touch of this repository: the helper installs the hook."""
    from specify_cli.lanes.lane_tip import read_tip

    opened = _drive_review(tmp_path)
    (opened.checkout / "src" / "work.py").write_text("y = 2\n", encoding="utf-8")
    _git(opened.checkout, "add", "src/work.py")
    _git(opened.checkout, "commit", "-q", "-m", "lane work")
    assert read_tip(opened.repo, opened.branch) == _git(opened.checkout, "rev-parse", "HEAD")


def test_helper_refuses_a_detached_checkout(tmp_path: Path) -> None:
    """A ref that is not a local branch would check out detached and skip the hook: refused, nothing created."""
    from specify_cli.lanes.lane_checkout import LaneCheckoutError, LaneCheckoutRequest, LaneCheckoutRoute, open_lane_checkout

    repo = _seed_mission(tmp_path, topology="lanes")
    checkout = repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_ID}"
    request = LaneCheckoutRequest(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        mission_dir_name=MISSION_SLUG,
        lane_id=LANE_ID,
        branch=_git(repo, "rev-parse", "HEAD"),
        worktree_path=checkout,
        create_branch_from=None,
        route=LaneCheckoutRoute.RECREATE,
    )
    with pytest.raises(LaneCheckoutError):
        open_lane_checkout(request)
    assert not checkout.exists()


def test_status_exclusion_keeps_dirty_local_status_rows(tmp_path: Path) -> None:
    """Data safety (C-009): applying the exclusion never discards local status rows.

    git leaves a modified excluded file on disk (with a warning); the helper's
    exclusion step must not force it away.
    """
    from specify_cli.lanes.lane_checkout import exclude_lane_status_files

    repo = _seed_mission(tmp_path, topology="lanes")
    checkout = repo / ".worktrees" / "plain-lane"
    _git(repo, "worktree", "add", "-q", "-b", LANE_BRANCH, str(checkout), "main")
    log = checkout / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
    local_row = '{"actor":"tester","event_id":"01KZQ7AB000000000000000002","wp_id":"WP01"}\n'
    log.write_text(_EVENT_ROW + local_row, encoding="utf-8")

    exclude_lane_status_files(checkout, MISSION_SLUG)

    assert log.read_text(encoding="utf-8") == _EVENT_ROW + local_row
    assert not (checkout / "kitty-specs" / MISSION_SLUG / "status.json").exists(), "the clean status file still leaves the disk"


# --- the exclusion is Mission-managed sparse state on every topology (review cycle 1, issue 1) ---


_PREFLIGHT_COMMANDS = ("spec-kitty agent action implement", "spec-kitty consolidate")


@pytest.mark.parametrize("route", sorted(_ROUTE_DRIVERS))
def test_every_route_checkout_passes_the_sparse_checkout_preflight(route: str, tmp_path: Path) -> None:
    """The status exclusion is Mission-managed, not legacy sparse state, on every topology.

    Before the fix a ``lanes``-topology lane (and a review or recreate checkout
    of such a Mission) was classified ``LEGACY_USER``, so ``implement`` of any
    later WP and ``consolidate`` refused once the first lane was allocated.
    """
    from specify_cli.git.sparse_checkout import require_no_sparse_checkout, scan_repo

    opened = _ROUTE_DRIVERS[route](tmp_path)
    report = scan_repo(opened.repo)
    assert report.any_active, "the helper's exclusion must be live sparse-checkout state"
    assert not report.any_blocking, f"managed exclusion classified as blocking: {report.worktrees}"
    for command in _PREFLIGHT_COMMANDS:
        require_no_sparse_checkout(
            opened.repo,
            command=command,
            override_flag=False,
            actor="tester",
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
        )


@pytest.mark.parametrize("route", ["allocation_fresh", "allocation_legacy"])
def test_an_operator_sparse_pattern_beside_the_exclusion_stays_refused(route: str, tmp_path: Path) -> None:
    """The status exclusion is the only sparse pattern a lane may carry; anything else is operator state."""
    from specify_cli.git.sparse_checkout import SparseCheckoutPreflightError, require_no_sparse_checkout

    opened = _ROUTE_DRIVERS[route](tmp_path)
    sparse_file = Path(_git(opened.checkout, "rev-parse", "--git-path", "info/sparse-checkout"))
    if not sparse_file.is_absolute():
        sparse_file = opened.checkout / sparse_file
    sparse_file.write_text(sparse_file.read_text(encoding="utf-8") + "!src/\n", encoding="utf-8")

    with pytest.raises(SparseCheckoutPreflightError):
        require_no_sparse_checkout(
            opened.repo,
            command="spec-kitty consolidate",
            override_flag=False,
            actor="tester",
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
        )


# #7276: merging the status exclusion into an operator's own non-cone patterns.


def test_merge_status_exclusion_full_list_when_no_patterns() -> None:
    from specify_cli.coordination.workspace import lane_status_exclusion_patterns
    from specify_cli.lanes.lane_checkout import merge_status_exclusion

    assert merge_status_exclusion([], "m-1") == lane_status_exclusion_patterns("m-1")


def test_merge_status_exclusion_keeps_patterns_and_moves_negations_last() -> None:
    from specify_cli.lanes.lane_checkout import merge_status_exclusion, status_exclusion_in_place

    merged = merge_status_exclusion(["!kitty-specs/m-1/status.json", "/src/", ""], "m-1")
    assert merged == ["/src/", "!kitty-specs/m-1/status.events.jsonl", "!kitty-specs/m-1/status.json"]
    assert status_exclusion_in_place(merged, "m-1")


def test_status_exclusion_not_in_place_when_missing_or_reincluded() -> None:
    from specify_cli.lanes.lane_checkout import status_exclusion_in_place

    assert not status_exclusion_in_place(["/*", "!kitty-specs/m-1/status.json"], "m-1")
    assert not status_exclusion_in_place(["!kitty-specs/m-1/status.events.jsonl", "!kitty-specs/m-1/status.json", "/kitty-specs/"], "m-1")


def test_exclude_lane_status_files_refuses_cone_mode(tmp_path: Path) -> None:
    import subprocess

    from specify_cli.lanes.lane_checkout import LaneCheckoutError, exclude_lane_status_files

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=T", "-c", "user.email=t@e", "commit", "-q", "--allow-empty", "-m", "b"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "sparse-checkout", "set", "--cone", "src"], check=True)
    with pytest.raises(LaneCheckoutError, match="cone-mode"):
        exclude_lane_status_files(tmp_path, "m-1")


def test_helper_leaves_a_genuinely_legacy_mission_lane_status_files_in_place(tmp_path: Path) -> None:
    """A pre-SSOT Mission writes status into its lane checkout, so the helper must not exclude it."""
    repo = _seed_mission(tmp_path, topology="lanes")
    meta_path = repo / "kitty-specs" / MISSION_SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["topology"]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "make the Mission genuinely legacy")

    checkout, _branch = _allocate(repo, topology="lanes")

    for name in STATUS_FILES:
        assert (checkout / "kitty-specs" / MISSION_SLUG / name).exists(), f"{name} must stay in a legacy lane checkout"


def test_exclusion_is_applied_in_one_sparse_checkout_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`sparse-checkout init` applies `/*` and `!/*/` at once; a later failure would leave the lane without its subdirectories."""
    from specify_cli.lanes import lane_checkout

    repo = _seed_mission(tmp_path, topology="lanes")
    checkout = tmp_path / "lane-checkout"
    _git(repo, "worktree", "add", "-q", "-b", LANE_BRANCH, str(checkout), "main")
    calls: list[tuple[str, ...]] = []
    real_git = lane_checkout._git

    def _recording(cwd: Path, *args: str, **kwargs: str) -> str:
        calls.append(args)
        return real_git(cwd, *args, **kwargs)

    monkeypatch.setattr(lane_checkout, "_git", _recording)

    lane_checkout.exclude_lane_status_files(checkout, MISSION_SLUG)

    sparse_calls = [args for args in calls if args[0] == "sparse-checkout"]
    assert len(sparse_calls) == 1, sparse_calls
    assert sparse_calls[0][:3] == ("sparse-checkout", "set", "--no-cone")
    assert (checkout / "src" / "app.py").exists(), "subdirectories stay on disk"
    assert not (checkout / "kitty-specs" / MISSION_SLUG / "status.json").exists()
    patterns = _git(checkout, "sparse-checkout", "list").splitlines()
    assert patterns[0] == "/*"
    assert patterns[-2:] == [f"!kitty-specs/{MISSION_SLUG}/status.events.jsonl", f"!kitty-specs/{MISSION_SLUG}/status.json"]
