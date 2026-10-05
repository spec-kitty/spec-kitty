"""``spec-kitty upgrade`` writes project-global state once, never in an integrating worktree (#5457).

An *integrating worktree* is a linked worktree under ``.worktrees/`` whose
checked-out branch integrates back into the mission's target branch: a mission,
lane or coordination branch (``kitty/mission-...``), or a branch that cannot be
read (detached HEAD, fail safe). Upgrade used to run its worktree migrations,
stamp ``.kittify/metadata.yaml`` and auto-commit in every such worktree, so each
lane and coordination branch carried its own divergent upgrade commit and
``consolidate`` / ``agent action review`` refused afterwards.

Every test here drives the real CLI (``spec-kitty upgrade --yes``) on WP01's
older-version lanes fixture. The non-integrating worktree on
``feature/unrelated`` is the positive control on the same fixture: it still
gets upgraded and committed on its own branch (FR-003, #2385), which proves the
probe can see a worktree upgrade at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration.target_owned_fixtures import (
    METADATA_PATH,
    OLDER_VERSION,
    LanesProject,
    Topology,
    build_older_version_lanes_project,
    metadata_blob,
    observe_upgrade_divergence,
    upgrade_commits_on,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

NON_INTEGRATING_BRANCH = "feature/unrelated"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _head(cwd: Path) -> str:
    return _git(cwd, "rev-parse", "HEAD").strip()


def _porcelain(cwd: Path) -> str:
    return _git(cwd, "status", "--porcelain")


def _metadata_bytes(worktree: Path) -> bytes | None:
    path = worktree / METADATA_PATH
    return path.read_bytes() if path.is_file() else None


def _integrating_worktrees(project: LanesProject, detached: Path) -> list[Path]:
    out = list(project.lane_worktrees.values())
    if project.coord_worktree is not None:
        out.append(project.coord_worktree)
    out.append(detached)
    return out


@pytest.mark.parametrize("topology", ["lanes", "lanes_with_coord"])
def test_upgrade_leaves_integrating_worktrees_untouched(tmp_path: Path, topology: Topology) -> None:
    """FR-001/FR-002 with the FR-003 positive control on the same fixture."""
    project = build_older_version_lanes_project(tmp_path, topology=topology, lanes=2)
    control = project.extra_worktree(branch=NON_INTEGRATING_BRANCH)
    detached = project.extra_worktree(detached=True)
    integrating = _integrating_worktrees(project, detached)

    tips_before = {branch: _git(project.repo, "rev-parse", branch).strip() for branch in project.branches()}
    blobs_before = {branch: metadata_blob(project.repo, branch) for branch in project.branches()}
    heads_before = {wt: _head(wt) for wt in integrating}
    bytes_before = {wt: _metadata_bytes(wt) for wt in integrating}
    porcelain_before = {wt: _porcelain(wt) for wt in integrating}
    control_tip_before = _head(control)

    observed = observe_upgrade_divergence(project)
    assert observed.returncode == 0, observed.output

    # The defect, named: no lane / coordination branch carries the upgrade
    # auto-commit ("chore: apply spec-kitty upgrade changes ...").
    assert observed.branches_with_upgrade_commit == [], observed.upgrade_commits_by_branch
    # Every integrating branch keeps its pre-upgrade metadata (it receives the
    # root checkout's copy through integration, never its own divergent stamp).
    assert observed.metadata_by_branch == blobs_before
    assert {b: _git(project.repo, "rev-parse", b).strip() for b in project.branches()} == tips_before
    for worktree in integrating:
        assert _head(worktree) == heads_before[worktree], worktree
        assert _metadata_bytes(worktree) == bytes_before[worktree], worktree
        assert _porcelain(worktree) == porcelain_before[worktree], worktree

    # The repository root checkout is upgraded and committed once.
    assert observed.target_upgrade_commits, observed.output
    assert observed.root_metadata is not None and f"version: {OLDER_VERSION}" not in observed.root_metadata

    # Positive control: the non-integrating worktree is still upgraded and
    # committed on its own branch (#2385 kept for non-integrating branches).
    assert _head(control) != control_tip_before
    assert upgrade_commits_on(project.repo, NON_INTEGRATING_BRANCH), "non-integrating worktree must get its own upgrade commit"
    control_metadata = metadata_blob(project.repo, NON_INTEGRATING_BRANCH)
    assert control_metadata is not None and f"version: {OLDER_VERSION}" not in control_metadata
    assert _porcelain(control) == ""


def test_integrating_rule_on_one_fixture(tmp_path: Path) -> None:
    """The exact rule (squad fold): lane, coordination and detached are integrating;
    an unrelated branch and a plain directory without ``.git`` are not."""
    from specify_cli.upgrade.runner import _is_integrating_worktree

    project = build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=1)
    control = project.extra_worktree(branch=NON_INTEGRATING_BRANCH)
    detached = project.extra_worktree(detached=True)
    plain = project.repo / ".worktrees" / "plain-dir"
    (plain / ".kittify").mkdir(parents=True)

    assert project.coord_worktree is not None
    assert _is_integrating_worktree(project.lane_worktrees["lane-a"]) is True
    assert _is_integrating_worktree(project.coord_worktree) is True
    assert _is_integrating_worktree(detached) is True
    assert _is_integrating_worktree(control) is False
    assert _is_integrating_worktree(plain) is False


@pytest.mark.parametrize("flag", ["--dry-run", "--no-worktrees"])
def test_dry_run_and_no_worktrees_are_unchanged(tmp_path: Path, flag: str) -> None:
    """``--dry-run`` writes nothing anywhere; ``--no-worktrees`` upgrades the root
    checkout only. Neither touches a lane or the non-integrating control."""
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1)
    control = project.extra_worktree(branch=NON_INTEGRATING_BRANCH)
    checkouts = [*project.lane_worktrees.values(), control]
    before = {wt: (_head(wt), _metadata_bytes(wt), _porcelain(wt)) for wt in checkouts}
    root_head = _head(project.repo)

    result = project.run("upgrade", "--yes", flag)

    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    assert {wt: (_head(wt), _metadata_bytes(wt), _porcelain(wt)) for wt in checkouts} == before
    if flag == "--dry-run":
        assert _head(project.repo) == root_head
    else:
        assert upgrade_commits_on(project.repo, project.target_branch)
