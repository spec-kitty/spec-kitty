"""Protected single_branch mission->target consolidate (WP08 / #5100 T037).

``contracts/single-branch-execution.md``'s consolidate table, protected row:
lands ``mission_branch`` onto ``target_branch``, switches the write checkout
back to ``target_branch``, then deletes ``mission_branch`` (honoring
retention) -- never removing the repository root checkout or the target
branch. Drives the REAL executor phase functions against a real git repo,
mirroring the established pattern in
``tests/specify_cli/consolidation/test_single_branch_bookkeeping_only.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import ConsolidationState

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01PROTECTEDMISSIONTOTARGET"
_SLUG = "single-branch-protected-to-target"
_MISSION_BRANCH = "kitty/mission-single-branch-protected-to-target-01protec"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _branch_exists(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"], capture_output=True, text=True).returncode == 0


def _current_branch(repo: Path) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


@pytest.fixture
def protected_repo(tmp_path: Path) -> Path:
    """A real git repo: `main` (protected target) plus a `mission_branch`
    that forked from it and carries one real code commit -- exactly the
    #5100 protected single_branch shape (WP08 mints & checks out the branch
    at create; every commit since lands there)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    # A real project ignores spec-kitty's runtime state (m_2_0_9_state_gitignore);
    # consolidation phases persist their state record there (#5318 / #5332).
    (repo / ".gitignore").write_text(".kittify/runtime/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-q", "-m", "seed")

    _git(repo, "checkout", "-q", "-b", _MISSION_BRANCH)
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_slug": _SLUG,
                "topology": "single_branch",
                "target_branch": "main",
                "mission_branch": _MISSION_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Code change\nexecution_mode: code_change\nowned_files:\n- src/**\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: WP01 implementation")
    # The write checkout stays on the mission branch throughout, exactly as
    # `mission create`'s mint left it and `implement`/status transitions kept
    # it -- consolidate must find it here, not on `main`.
    return repo


def _protected_lanes_manifest() -> SimpleNamespace:
    return SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="main",
        mission_branch=_MISSION_BRANCH,
        lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])],
    )


def _build_run(repo: Path, lanes_manifest: SimpleNamespace, *, delete_branch: bool = True) -> ex._MergeRunState:
    feature_dir = repo / "kitty-specs" / _SLUG
    state = ConsolidationState(
        mission_id=_MISSION_ID,
        mission_slug=_SLUG,
        target_branch="main",
        wp_order=["WP01"],
    )
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=delete_branch,
        remove_worktree=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )


# ---------------------------------------------------------------------------
# End-to-end: land, switch back, delete
# ---------------------------------------------------------------------------


def test_protected_mission_lands_switches_back_and_deletes_branch(protected_repo: Path) -> None:
    run = _build_run(protected_repo, _protected_lanes_manifest())

    ex._phase_mission_to_target(run)
    ex._switch_write_checkout_after_single_branch_landing(run)
    deleted = ex._delete_mission_branch(run)

    # Target contains the work.
    main_tree = _git(protected_repo, "show", "main:src/impl.py").stdout
    assert "VALUE = 1" in main_tree

    # The write checkout is switched back to the target branch.
    assert _current_branch(protected_repo) == "main"

    # The mission branch is gone.
    assert deleted is True
    assert not _branch_exists(protected_repo, _MISSION_BRANCH)

    # The repository root checkout is intact (a valid, non-detached repo).
    assert (protected_repo / ".git").exists()
    assert (protected_repo / "README.md").exists()


def test_unprotected_single_branch_control_no_landing(protected_repo: Path) -> None:
    """Control: when `mission_branch == target_branch` (unprotected), the
    mission->target phase is a no-op and the checkout-switch helper is also
    a no-op -- proving the new switch-back logic is scoped to the genuinely
    divergent (protected) case, per contracts/single-branch-execution.md."""
    _git(protected_repo, "checkout", "-q", "main")
    manifest = SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="main",
        mission_branch="main",
        lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])],
    )
    run = _build_run(protected_repo, manifest)

    from unittest.mock import patch

    with patch("specify_cli.lanes.consolidation.integrate_mission_into_target") as mock_integrate:
        ex._phase_mission_to_target(run)
    mock_integrate.assert_not_called()

    ex._switch_write_checkout_after_single_branch_landing(run)
    assert _current_branch(protected_repo) == "main", "the no-op control must never switch branches"


def test_switch_back_never_runs_for_non_single_branch_mission(protected_repo: Path) -> None:
    """Gate: a lanes mission's manifest also has ``mission_branch != target_branch``;
    the switch-back must key on the STORED single_branch topology, never on that."""
    meta = protected_repo / "kitty-specs" / _SLUG / "meta.json"
    meta.write_text(meta.read_text().replace("single_branch", "lanes"), encoding="utf-8")
    run = _build_run(protected_repo, _protected_lanes_manifest())

    ex._switch_write_checkout_after_single_branch_landing(run)

    assert _current_branch(protected_repo) == _MISSION_BRANCH, "a non-single_branch mission must never have its checkout switched"


# ---------------------------------------------------------------------------
# Authorship window for the reconciliation blob source (T037, R-9)
# ---------------------------------------------------------------------------


def test_authorship_window_is_fork_point_to_mission_branch(protected_repo: Path) -> None:
    from specify_cli.lanes.single_branch_landing import authorship_window

    fork = _git(protected_repo, "rev-parse", "main").stdout.strip()
    assert authorship_window(protected_repo, _SLUG, _MISSION_BRANCH, "main") == (fork, _MISSION_BRANCH)


def test_authorship_window_none_when_unprotected(protected_repo: Path) -> None:
    from specify_cli.lanes.single_branch_landing import authorship_window

    assert authorship_window(protected_repo, _SLUG, "main", "main") is None


def test_authorship_window_none_for_non_single_branch_topology(protected_repo: Path) -> None:
    """Control: a coord/lanes mission's mission_branch keeps the ordinary resolution."""
    from specify_cli.lanes.single_branch_landing import authorship_window

    meta = protected_repo / "kitty-specs" / _SLUG / "meta.json"
    meta.write_text(meta.read_text().replace("single_branch", "lanes"), encoding="utf-8")
    assert authorship_window(protected_repo, _SLUG, _MISSION_BRANCH, "main") is None


def test_collect_authored_uses_mission_branch_window(protected_repo: Path) -> None:
    """The squash blob source for the repo-root lane is base..mission_branch (non-empty)."""
    from specify_cli.consolidation.reconciliation import _collect_authored
    from specify_cli.lanes.single_branch_landing import authorship_window

    manifest = _protected_lanes_manifest()
    window = authorship_window(protected_repo, _SLUG, _MISSION_BRANCH, "main")
    wps = {"WP01": {"lane": "approved"}}
    with_window = _collect_authored(protected_repo, manifest, wps, "main", window, canceled_lane_commits=frozenset())
    without = _collect_authored(protected_repo, manifest, wps, "main", None, canceled_lane_commits=frozenset())
    assert ("src/impl.py", _git(protected_repo, "rev-parse", f"{_MISSION_BRANCH}:src/impl.py").stdout.strip()) in with_window[2]
    assert not without[2], "control: without the window the repo-root lane resolves to the target and has no authored blobs"


# ---------------------------------------------------------------------------
# Post-landing bookkeeping resolves to the target (#5100 B4)
# ---------------------------------------------------------------------------


def test_protected_landing_clears_mission_branch_and_keeps_tree_clean(protected_repo: Path) -> None:
    from mission_runtime.resolution import _resolve_single_branch_write_ref
    from specify_cli.mission_metadata import load_meta_or_empty

    run = _build_run(protected_repo, _protected_lanes_manifest())
    feature_dir = protected_repo / "kitty-specs" / _SLUG

    ex._phase_mission_to_target(run)
    ex._switch_write_checkout_after_single_branch_landing(run)
    ex._cleanup_mission_branch_and_coordination(run)

    meta = load_meta_or_empty(feature_dir)
    assert "mission_branch" not in meta, "the deleted mission branch must not stay recorded (mission reopen / write routing)"
    assert meta["topology"] == "single_branch"
    assert not _branch_exists(protected_repo, _MISSION_BRANCH)
    assert _current_branch(protected_repo) == "main"
    # The clear was committed ON the target: nothing left dirty.
    assert _git(protected_repo, "status", "--porcelain").stdout.strip() == ""
    assert '"mission_branch"' not in _git(protected_repo, "show", "main:kitty-specs/" + _SLUG + "/meta.json").stdout
    # A later post-landing write resolves to the target, not the deleted branch.
    ref = _resolve_single_branch_write_ref("single_branch", "main", protected_repo, _SLUG)
    assert ref == "main"


def test_retained_mission_branch_still_clears_meta_mission_branch(protected_repo: Path) -> None:
    """--keep-branch retains the landed branch but it stops being the write target (#5100)."""
    from mission_runtime.resolution import _resolve_single_branch_write_ref
    from specify_cli.mission_metadata import load_meta_or_empty

    run = _build_run(protected_repo, _protected_lanes_manifest(), delete_branch=False)

    ex._phase_mission_to_target(run)
    ex._switch_write_checkout_after_single_branch_landing(run)
    ex._cleanup_mission_branch_and_coordination(run)

    assert _branch_exists(protected_repo, _MISSION_BRANCH)
    assert "mission_branch" not in load_meta_or_empty(protected_repo / "kitty-specs" / _SLUG)
    assert _resolve_single_branch_write_ref("single_branch", "main", protected_repo, _SLUG) == "main"


# ---------------------------------------------------------------------------
# Truthful consolidate messaging for single_branch (#5100 B6)
# ---------------------------------------------------------------------------


def _unprotected_run(repo: Path) -> ex._MergeRunState:
    manifest = SimpleNamespace(
        mission_slug=_SLUG,
        target_branch="main",
        mission_branch="main",
        lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])],
    )
    run = _build_run(repo, manifest)
    run.planning_artifact_only = True
    return run


def test_single_branch_code_mission_is_not_called_planning_artifact_only(protected_repo: Path) -> None:
    run = _unprotected_run(protected_repo)

    notice = ex._planning_only_notice(run)

    assert notice is not None
    assert "Planning-artifact-only" not in notice
    assert "single_branch" in notice


def test_genuine_planning_artifact_only_notice_is_unchanged(protected_repo: Path) -> None:
    run = _unprotected_run(protected_repo)
    meta = protected_repo / "kitty-specs" / _SLUG / "meta.json"
    meta.write_text(meta.read_text().replace("single_branch", "lanes"), encoding="utf-8")

    notice = ex._planning_only_notice(run)

    assert notice is not None
    assert "Planning-artifact-only mission" in notice


def test_no_lane_branch_cleanup_line_when_none_were_deleted(protected_repo: Path) -> None:
    run = _unprotected_run(protected_repo)

    with ex.console.capture() as captured:
        ex._delete_lane_branches(run)

    assert "Cleaned up" not in captured.get()


def test_dry_run_reports_no_branch_deletion_for_target_equal_mission_branch() -> None:
    from specify_cli.consolidation.forecast import _effective_delete_branch

    unprotected = SimpleNamespace(target_branch="feat/sb", mission_branch="feat/sb", lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])])
    protected = SimpleNamespace(target_branch="main", mission_branch=_MISSION_BRANCH, lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])])

    assert _effective_delete_branch(True, unprotected) is False
    assert _effective_delete_branch(True, protected) is True
    assert _effective_delete_branch(False, protected) is False
