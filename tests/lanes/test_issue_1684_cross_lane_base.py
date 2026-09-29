"""Permanent guard for issue #1684.

**Landing note (2026-08, `tests/regression/` campsite clean).** #1684 is
fixed; this is a permanent regression guard, not a red-first reproduction, so
it carries no `regression` marker. Relocated to `tests/lanes/` (its direct
functional home — these are unit-level tests of
``specify_cli.lanes.worktree_allocator.allocate_lane_worktree`` against real
git repos, matching the style of the sibling
``tests/lanes/test_worktree_allocator.py`` /
``test_worktree_allocator_atomicity.py``, not the CLI/orchestrator-driven
tests in `tests/agent/`). The issue number is kept as history.

Bug: when a WP declares a dependency on a WP that lives on a *sibling*
lane, claiming the dependent WP creates the lane worktree from the bare
mission branch instead of from a base that contains the approved
dependency lane's tip. The dependent lane therefore cannot see the
upstream lane's committed code.

`lanes.json` carries the correct ``depends_on_lanes`` edge, but
``allocate_lane_worktree`` never read it — it always branched from
``mission_branch`` (or ``coordination_branch``). These tests reproduce
the cross-lane case and assert that lane-b's HEAD contains lane-a's
approved tip, plus the reuse-catch-up, two-deps-ordered,
missing-dep-fallback, and conflict-fail-closed cases.

The fix landed in stage 2 (commit ``fix(#1684)``); these tests guard it.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace as _dc_replace

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    allocate_lane_worktree,
)

pytestmark = pytest.mark.git_repo


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=check
    )


def _make_git_repo(path):
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    _git(path, "config", "user.email", "test@test.com")
    _git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("init\n")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "init")
    _git(path, "branch", "-M", "main")


def _lane(lane_id, wp_id, wp_num, *, depends_on=(), group):
    """Build an ExecutionLane with the test boilerplate filled in."""
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=(f"src/wp{wp_num}/**",),
        predicted_surfaces=(),
        depends_on_lanes=tuple(depends_on),
        parallel_group=group,
    )


def _manifest_with(mission_slug, lanes):
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-06-12T12:00:00+00:00",
        computed_from="test",
    )


def _make_manifest(mission_slug="010-feat"):
    """Two lanes; lane-b (WP02) depends on lane-a (WP01)."""
    return _manifest_with(
        mission_slug,
        [
            _lane("lane-a", "WP01", "01", group=0),
            # The dependency edge IS recorded here by compute_lanes.
            _lane("lane-b", "WP02", "02", depends_on=("lane-a",), group=1),
        ],
    )


def test_dependent_lane_base_contains_approved_dependency_tip(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)

    mission_slug = "010-feat"
    manifest = _make_manifest(mission_slug)

    # 1. Claim + implement WP01 on lane-a, commit work, "approve" it.
    wt_a, _branch_a = allocate_lane_worktree(repo, mission_slug, "WP01", manifest)
    (wt_a / "wp01_module.py").write_text("VALUE = 1\n")
    _git(wt_a, "add", ".")
    _git(wt_a, "commit", "-m", "WP01: add module")
    lane_a_tip = _git(wt_a, "rev-parse", "HEAD").stdout.strip()

    # 2. Now claim WP02 on lane-b. Per the implement/review skill docs, the
    #    workspace base should be "inferred automatically from the approved
    #    dependency graph" — lane-b must be able to see lane-a's tip.
    wt_b, _branch_b = allocate_lane_worktree(repo, mission_slug, "WP02", manifest)

    # 3. lane-a's approved module must be visible from lane-b.
    assert (wt_b / "wp01_module.py").exists(), (
        "WP01's module is not present on lane-b — the dependent lane was "
        "created from the bare mission branch and cannot import the "
        "approved sibling-lane dependency (issue #1684)."
    )

    # 4. lane-b's HEAD must contain lane-a's tip as an ancestor.
    lane_a_branch = code_lane_branch_name(mission_slug, "lane-a")
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", lane_a_branch, "HEAD"],
        cwd=str(wt_b),
        capture_output=True,
    )
    assert is_ancestor.returncode == 0, (
        f"lane-a tip ({lane_a_tip[:8]}) is not an ancestor of lane-b HEAD; "
        "depends_on_lanes was ignored when choosing the lane base (issue #1684)."
    )


def _make_three_lane_manifest(mission_slug="010-feat"):
    """Three lanes; lane-c (WP03) depends on BOTH lane-a and lane-b."""
    return _manifest_with(
        mission_slug,
        [
            _lane("lane-a", "WP01", "01", group=0),
            _lane("lane-b", "WP02", "02", group=0),
            _lane("lane-c", "WP03", "03", depends_on=("lane-a", "lane-b"), group=1),
        ],
    )


def test_reuse_path_catches_up_dependency_approved_after_creation(tmp_path):
    """#1684 reuse path: a dep approved AFTER lane creation must be merged in.

    Models the WP05/WP09 double-hit on mission 01KTYGTE: the dependent lane's
    worktree already exists, then its dependency lane is approved late. Re-entering
    the dependent lane (reuse path) must fast-forward the newly-approved dep tip.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    manifest = _make_manifest("010-feat")

    # Create lane-a worktree but do NOT commit work yet.
    wt_a, _ = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)
    # Create lane-b FIRST (dependency not yet present) — reuse path will catch up.
    wt_b, _ = allocate_lane_worktree(repo, "010-feat", "WP02", manifest)
    assert not (wt_b / "wp01_module.py").exists()

    # Now lane-a does its work and is "approved".
    (wt_a / "wp01_module.py").write_text("VALUE = 1\n")
    _git(wt_a, "add", ".")
    _git(wt_a, "commit", "-m", "WP01: add module (late)")

    # Re-enter lane-b (reuse path). The catch-up merge must pull lane-a's tip in.
    wt_b2, _ = allocate_lane_worktree(repo, "010-feat", "WP02", manifest)
    assert wt_b2 == wt_b
    assert (wt_b2 / "wp01_module.py").exists(), (
        "reuse path did not catch up the dependency lane tip approved after "
        "the dependent lane worktree was created (issue #1684)."
    )


def test_two_dependencies_merged_in_order(tmp_path):
    """#1684: a lane depending on two lanes sees BOTH approved tips."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    manifest = _make_three_lane_manifest("010-feat")

    wt_a, _ = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)
    (wt_a / "wp01_module.py").write_text("A = 1\n")
    _git(wt_a, "add", ".")
    _git(wt_a, "commit", "-m", "WP01")
    branch_a = code_lane_branch_name("010-feat", "lane-a")

    wt_b, _ = allocate_lane_worktree(repo, "010-feat", "WP02", manifest)
    (wt_b / "wp02_module.py").write_text("B = 2\n")
    _git(wt_b, "add", ".")
    _git(wt_b, "commit", "-m", "WP02")
    branch_b = code_lane_branch_name("010-feat", "lane-b")

    # lane-c depends on both — both tips must be visible.
    wt_c, _ = allocate_lane_worktree(repo, "010-feat", "WP03", manifest)
    assert (wt_c / "wp01_module.py").exists(), "lane-a tip missing on lane-c"
    assert (wt_c / "wp02_module.py").exists(), "lane-b tip missing on lane-c"
    for branch in (branch_a, branch_b):
        assert (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", branch, "HEAD"],
                cwd=str(wt_c),
                capture_output=True,
            ).returncode
            == 0
        ), f"{branch} is not an ancestor of lane-c HEAD"


def test_explicit_base_composes_with_dependency_merge(tmp_path):
    """#1684 / --base composition: an explicit base ref selects the lane ROOT,
    and approved ``depends_on_lanes`` tips are STILL merged on top.

    Mirrors ``implement.py``'s ``--base`` handling, which shallow-patches the
    manifest's ``mission_branch`` to the explicit ref (legacy/no-coordination
    topology) so ``allocate_lane_worktree`` roots the lane there. The fix's
    documented contract is that dependency tips compose with this root rather
    than replacing it — the dependent lane must see BOTH the chosen base's
    content and the approved sibling-lane code.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    mission_slug = "010-feat"
    manifest = _make_manifest(mission_slug)

    # 1. lane-a does its work and is "approved".
    wt_a, _ = allocate_lane_worktree(repo, mission_slug, "WP01", manifest)
    (wt_a / "wp01_module.py").write_text("VALUE = 1\n")
    _git(wt_a, "add", ".")
    _git(wt_a, "commit", "-m", "WP01: add module")

    # 2. Build an explicit base ref carrying a distinct file (non-conflicting
    #    with lane-a). This stands in for an operator-supplied --base.
    _git(repo, "branch", "explicit-base", "main")
    base_wt = repo / "base-wt"
    _git(repo, "worktree", "add", str(base_wt), "explicit-base")
    (base_wt / "base_marker.py").write_text("BASE = True\n")
    _git(base_wt, "add", ".")
    _git(base_wt, "commit", "-m", "base: marker")

    # 3. Patch the manifest exactly as implement.py does for --base, then claim
    #    WP02 on lane-b (legacy path: no coordination_branch in this fixture).
    patched = _dc_replace(manifest, mission_branch="explicit-base")
    wt_b, _ = allocate_lane_worktree(repo, mission_slug, "WP02", patched)

    # 4. The chosen ROOT's content is present...
    assert (wt_b / "base_marker.py").exists(), (
        "explicit --base ref content missing on lane-b — the chosen root was "
        "not honored (issue #1684 --base composition)."
    )
    # 5. ...AND the approved dependency tip was merged on top.
    assert (wt_b / "wp01_module.py").exists(), (
        "dependency lane tip was not merged on top of the explicit base — "
        "--base must compose with depends_on_lanes, not suppress it (issue #1684)."
    )
    lane_a_branch = code_lane_branch_name(mission_slug, "lane-a")
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", lane_a_branch, "HEAD"],
            cwd=str(wt_b),
            capture_output=True,
        ).returncode
        == 0
    ), "lane-a tip is not an ancestor of lane-b HEAD under --base composition"


def test_missing_dependency_branch_falls_back_with_warning(tmp_path, capfd):
    """#1684: a merged-and-deleted dep branch is skipped with a warning, no crash."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    manifest = _make_manifest("010-feat")

    # Claim WP02 (lane-b) WITHOUT ever creating lane-a's branch — it does not
    # resolve (simulates merged-and-deleted dependency lane).
    wt_b, _ = allocate_lane_worktree(repo, "010-feat", "WP02", manifest)
    assert wt_b.exists(), "lane-b worktree must still be created on missing dep"
    out = capfd.readouterr().out
    assert "lane-a" in out and "WARNING" in out, (
        "expected a warning that the missing dependency lane branch was skipped"
    )


def test_conflicting_dependency_merge_fails_closed(tmp_path):
    """#1684: a conflicting dep merge raises a structured error, worktree clean."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_git_repo(repo)
    manifest = _make_manifest("010-feat")

    # lane-a writes a file...
    wt_a, _ = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)
    (wt_a / "shared.py").write_text("VALUE = 'from-lane-a'\n")
    _git(wt_a, "add", ".")
    _git(wt_a, "commit", "-m", "WP01: shared file")

    # ...and the mission base independently writes the SAME file with different
    # content, so merging lane-a into a lane-b rooted on that base conflicts.
    # (The mission branch already exists — lane-a allocation created it.)
    mission_branch = manifest.mission_branch
    wt_base = repo / "base-wt"
    _git(repo, "worktree", "add", str(wt_base), mission_branch)
    (wt_base / "shared.py").write_text("VALUE = 'from-base'\n")
    _git(wt_base, "add", ".")
    _git(wt_base, "commit", "-m", "base: conflicting shared file")

    with pytest.raises(DependencyLaneMergeConflictError) as exc_info:
        allocate_lane_worktree(repo, "010-feat", "WP02", manifest)

    err = exc_info.value
    assert err.error_code == "DEPENDENCY_LANE_MERGE_CONFLICT"
    assert err.dep_lane_id == "lane-a"
    assert "next_step" in err.to_dict()

    # The worktree must NOT be left half-merged: the merge was aborted.
    wt_b = repo / ".worktrees" / "010-feat-lane-b"
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(wt_b),
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == "", (
        "worktree was left in a conflicted/half-merged state after fail-closed"
    )
