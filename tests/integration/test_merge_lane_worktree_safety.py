"""WP03/T014 — pin the lane/coord-worktree pre-mutation safety regression (#4753).

Prior to WP03, ``_phase_cleanup_worktrees_and_branches`` force-removed every
lane worktree with a bare ``git worktree remove <path> --force`` and printed
"Removed worktree" with exit ``0`` -- even when the worktree held uncommitted
work never integrated into the lane branch. WP03/T010 hoists a pre-mutation
preflight into the OUTER ``_run_lane_based_merge`` that detects a dirty lane
worktree BEFORE any ref advance and refuses fail-closed; WP03/T012 additionally
routes the cleanup loop itself through the WP01
:func:`~specify_cli.git.destructive_guard.guarded_worktree_remove` chokepoint
as defense-in-depth.

Two scenarios:

1. **Lane worktree** (core #4753, FR-003/US2 AC1) -- exercised through the
   real CLI entry point (``_run_lane_based_merge``), matching the Layer-2
   real-git harness pattern from
   ``tests/integration/test_merge_lane_planning_data_loss.py``.
2. **Coordination worktree** (FR-004/US2 AC4, the coupled-triple variant) --
   exercised directly against the new
   ``specify_cli.merge.executor._pre_mutation_safety_preflight`` helper
   against a real coord-topology fixture (real git worktree + branch +
   ``meta.json``), because standing up a full coordination-topology CLI merge
   (placement-seam routing, coord status surface, etc.) is a separate,
   much heavier concern than the #4753 loss shape being pinned here. The
   preflight function itself is exactly the new WP03 code the full CLI path
   calls, so this is a faithful regression pin on the coupled-teardown
   invariant (INV-2), not a bypass of it.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from kernel.clock import now_utc_iso
from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_WORKTREE_DIRTY,
    DestructiveOpRefused,
)
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.executor import _pre_mutation_safety_preflight

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _write_meta(feature_dir: Path, slug: str, *, extra: dict[str, object] | None = None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "lane/coord worktree safety regression pin",
        "purpose_context": "real-merge #4753 preflight test",
    }
    if extra:
        meta.update(extra)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_lanes_manifest(feature_dir: Path, slug: str, *, mission_branch: str | None = None) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=None,
        mission_branch=mission_branch or f"kitty/mission-{slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/foo.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _commit_file(repo: Path, *, branch: str, relpath: str, content: str, message: str) -> None:
    _git(repo, "checkout", branch)
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", message)


def _bootstrap_mission(tmp_path: Path, slug: str) -> Path:
    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(feature_dir, slug)
    _write_lanes_manifest(feature_dir, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap mission fixture")

    mission_branch = f"kitty/mission-{slug}"
    _git(tmp_path, "branch", mission_branch, "main")

    lane_branch = lane_branch_name(slug, "lane-a")
    _git(tmp_path, "branch", lane_branch, "main")
    _commit_file(
        tmp_path,
        branch=lane_branch,
        relpath="src/foo.py",
        content="def foo():\n    return 1\n",
        message=f"feat({slug}): add foo function (WP01)",
    )
    _git(tmp_path, "checkout", "main")
    return feature_dir


def _add_lane_worktree(tmp_path: Path, slug: str, lane_branch: str) -> Path:
    wt_path = worktree_path(tmp_path, slug, mission_id=None, lane_id="lane-a")
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "worktree", "add", str(wt_path), lane_branch)
    return wt_path


@contextlib.contextmanager
def _real_merge_external_mocks(repo_root: Path):
    """Mirrors the Layer-2 harness in ``test_merge_lane_planning_data_loss.py``.

    The worktree-removal loop in ``_phase_cleanup_worktrees_and_branches`` is
    deliberately NOT mocked -- that (now guarded) chokepoint is exactly what
    T012/#4753 is pinning.
    """
    patches = [
        patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch(
            "specify_cli.merge.executor._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[7].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[8].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[3].return_value = stale_report
        ms[4].return_value = stale_report
        yield


def _invoke_merge(tmp_path: Path, slug: str, *, remove_worktree: bool, delete_branch: bool) -> None:
    with _real_merge_external_mocks(tmp_path):
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )


class TestLaneWorktreeSafety:
    """#4753 core: a dirty lane worktree must never be force-removed."""

    def test_dirty_lane_worktree_refuses_fail_closed_before_removal(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        slug = "test-lane-worktree-dirty"
        _bootstrap_mission(tmp_path, slug)
        lane_branch = lane_branch_name(slug, "lane-a")
        wt_path = _add_lane_worktree(tmp_path, slug, lane_branch)

        # Uncommitted TRACKED edit + an untracked file, never on the lane branch.
        (wt_path / "src" / "foo.py").write_text("def foo():\n    return 2  # uncommitted\n")
        (wt_path / "scratch.txt").write_text("implementer's in-progress notes\n")

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug, remove_worktree=True, delete_branch=False)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        assert MERGE_UNSAFE_WORKTREE_DIRTY in captured.out

        # NFR-001: the worktree survives, untouched, and the mission never
        # reached the target-ref advance.
        assert wt_path.exists()
        assert (wt_path / "src" / "foo.py").read_text() == ("def foo():\n    return 2  # uncommitted\n")
        assert (wt_path / "scratch.txt").read_text() == "implementer's in-progress notes\n"
        assert _git(tmp_path, "ls-tree", "--name-only", "-r", "main", "--", "src/foo.py").stdout.strip() == ""

    def test_clean_lane_worktree_removed_as_today(self, tmp_path: Path) -> None:
        """US2 AC3/NFR-002: a clean lane worktree is removed exactly as before."""
        slug = "test-lane-worktree-clean-parity"
        _bootstrap_mission(tmp_path, slug)
        lane_branch = lane_branch_name(slug, "lane-a")
        wt_path = _add_lane_worktree(tmp_path, slug, lane_branch)
        assert wt_path.exists()

        _invoke_merge(tmp_path, slug, remove_worktree=True, delete_branch=False)

        assert not wt_path.exists(), "Parity regression: a clean lane worktree must still be removed by the guarded chokepoint exactly as the raw force-remove did."
        assert (tmp_path / "src" / "foo.py").exists()


class TestCoordinationWorktreeSafety:
    """FR-004/US2 AC4: a dirty coord worktree holds back the coupled triple.

    Exercises ``_pre_mutation_safety_preflight`` directly against a real
    coord-topology fixture (see module docstring for why the full CLI path is
    not driven here).
    """

    def test_dirty_coord_worktree_holds_back_coupled_teardown(self, tmp_path: Path) -> None:
        slug = "test-coord-worktree-dirty"
        mid8 = "01COORD1X"[:8]
        _init_git_repo(tmp_path)

        coord_branch = CoordinationWorkspace.branch_name(slug, mid8)
        _git(tmp_path, "branch", coord_branch, "main")

        feature_dir = tmp_path / "kitty-specs" / slug
        _write_meta(
            feature_dir,
            slug,
            extra={"mid8": mid8, "coordination_branch": coord_branch},
        )
        lanes_manifest = _write_lanes_manifest(feature_dir, slug, mission_branch=coord_branch)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap coord mission fixture")

        coord_wt_path = CoordinationWorkspace.worktree_path(tmp_path, slug, mid8)
        coord_wt_path.parent.mkdir(parents=True, exist_ok=True)
        _git(tmp_path, "worktree", "add", str(coord_wt_path), coord_branch)

        # Uncommitted TRACKED edit + an untracked file in the coord worktree,
        # never on the coordination branch.
        (coord_wt_path / "README.md").write_text("coord worktree in-progress edit\n")
        (coord_wt_path / "coord-scratch.txt").write_text("coord scratch\n")

        _git(tmp_path, "checkout", "main")

        with pytest.raises(DestructiveOpRefused) as excinfo:
            _pre_mutation_safety_preflight(
                tmp_path,
                slug,
                "main",
                lanes_manifest,
                None,
                feature_dir,
                remove_worktree=True,
                teardown_coordination=True,
            )

        assert excinfo.value.error_code == MERGE_UNSAFE_WORKTREE_DIRTY

        # INV-2: the coupled coord triple (branch + worktree + marker) all
        # survive together -- nothing downstream of the raise ran.
        assert coord_wt_path.exists()
        assert (coord_wt_path / "README.md").read_text() == "coord worktree in-progress edit\n"
        assert (coord_wt_path / "coord-scratch.txt").read_text() == "coord scratch\n"
        assert _git(tmp_path, "rev-parse", "--verify", f"refs/heads/{coord_branch}").returncode == 0
        meta_after = json.loads((feature_dir / "meta.json").read_text())
        assert meta_after["coordination_branch"] == coord_branch

    def test_coord_teardown_not_requested_is_never_checked(self, tmp_path: Path) -> None:
        """Parity: a dirty coord worktree is not refused when the coupled
        teardown was never going to run (partial retention -- NFR-002).
        """
        slug = "test-coord-worktree-dirty-not-torn-down"
        mid8 = "01COORD2X"[:8]
        _init_git_repo(tmp_path)

        coord_branch = CoordinationWorkspace.branch_name(slug, mid8)
        _git(tmp_path, "branch", coord_branch, "main")

        feature_dir = tmp_path / "kitty-specs" / slug
        _write_meta(
            feature_dir,
            slug,
            extra={"mid8": mid8, "coordination_branch": coord_branch},
        )
        lanes_manifest = _write_lanes_manifest(feature_dir, slug, mission_branch=coord_branch)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap coord mission fixture")

        coord_wt_path = CoordinationWorkspace.worktree_path(tmp_path, slug, mid8)
        coord_wt_path.parent.mkdir(parents=True, exist_ok=True)
        _git(tmp_path, "worktree", "add", str(coord_wt_path), coord_branch)
        (coord_wt_path / "README.md").write_text("coord worktree in-progress edit\n")

        _git(tmp_path, "checkout", "main")

        # No lanes to remove either -- retention decision here mirrors a
        # ``--keep-branch`` / non-coupled request where the cleanup phase
        # would never touch the coord triple, so the preflight must not
        # refuse for a coord worktree it was never going to disturb.
        _pre_mutation_safety_preflight(
            tmp_path,
            slug,
            "main",
            lanes_manifest,
            None,
            feature_dir,
            remove_worktree=False,
            teardown_coordination=False,
        )
