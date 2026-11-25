"""#5287: a remote-only coordination branch gets one complete, truthful remedy.

A fresh clone (or any checkout with no local head for the coordination branch)
used to be told the branch "has not fetched" (false: the clone has fetched it),
was always pointed at ``origin`` (the fixture's only remote is ``coord-remote``),
and was never told to create the local branch, the step that actually unblocks
reads. These tests drive the pre-existing entry point,
``CoordinationWorktreeUnmaterialized.for_mission``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from tests._factories.coord_mission import CoordMission, make_prefix_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_REMOTE = "coord-remote"


def _remote_only(tmp_path: Path) -> CoordMission:
    return make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="absent", remote_only=True)


def _refusal(coord: CoordMission) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=coord.repo_root,
        mission_slug=coord.mission_dir_name,
        mid8=coord.mid8,
        coordination_branch=coord.coordination_branch,
        primary_candidate=coord.root_mission_dir,
    )


def test_remote_only_refusal_names_the_resolved_remote_and_the_branch_step(tmp_path: Path) -> None:
    coord = _remote_only(tmp_path)
    branch = coord.coordination_branch

    next_step = _refusal(coord).next_step

    assert f"branch {branch} refs/remotes/{_REMOTE}/{branch}" in next_step
    assert f"spec-kitty doctor coordination --mission {coord.mission_dir_name} --fix" in next_step
    assert "has not fetched" not in next_step
    assert "not yet fetched" not in next_step
    assert " origin" not in next_step
    assert "origin/" not in next_step
    # The clone already holds refs/remotes/coord-remote/<b>: no fetch step is needed.
    assert " fetch " not in next_step


def test_remote_only_refusal_leads_with_a_targeted_fetch_when_no_tracking_ref_is_held(tmp_path: Path) -> None:
    coord = _remote_only(tmp_path)
    branch = coord.coordination_branch
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "update-ref", "-d", f"refs/remotes/{_REMOTE}/{branch}"],
        check=True,
        capture_output=True,
    )

    next_step = _refusal(coord).next_step

    # The fixture also carries an ``origin`` remote (the git template), so with
    # no tracking ref anywhere local config names ``origin`` (the default) and
    # cannot confirm it holds the branch: the text names the other candidate.
    fetch_step = f"fetch origin {branch}"
    branch_step = f"branch {branch} refs/remotes/origin/{branch}"
    assert fetch_step in next_step
    assert branch_step in next_step
    assert next_step.index(fetch_step) < next_step.index(branch_step)
    assert f"if origin does not hold the branch, use the remote that does: {_REMOTE}" in next_step
    assert "has not fetched" not in next_step


def test_doctor_refusal_and_write_refusal_carry_the_identical_remedy(tmp_path: Path) -> None:
    """FR-005 / SC-001: the three surfaces that print a remote-only remedy print one text.

    The expected text is the builder's own output, never a copied literal, so a
    surface that drifts from the single owner goes red here.
    """
    from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind
    from mission_runtime.coord_remedy import coordination_doctor_command, remote_only_branch, remote_only_steps
    from mission_runtime.write_target_degrade import assert_coord_write_materialized
    from specify_cli.cli.commands._coordination_doctor import _check_coordination_worktree_health
    from specify_cli.core.paths import load_meta_fail_closed

    coord = _remote_only(tmp_path)
    root, branch, slug = coord.repo_root, coord.coordination_branch, coord.mission_dir_name
    expected = remote_only_steps(remote_only_branch(root, branch), root, coordination_doctor_command(slug))

    refusal_text = _refusal(coord).next_step

    meta = load_meta_fail_closed(coord.root_mission_dir) or {}
    findings = _check_coordination_worktree_health(root, dict(meta))
    missing = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_MISSING"]
    assert len(missing) == 1, findings
    doctor_text = missing[0].next_step or ""

    with pytest.raises(ActionContextError) as excinfo:
        assert_coord_write_materialized(root, slug, MissionArtifactKind.ISSUE_MATRIX, CommitTarget(ref=branch))
    write_text = str(excinfo.value)

    assert f"{_REMOTE}/{branch}" in expected
    assert expected in refusal_text
    assert doctor_text == expected
    assert expected in write_text


def test_the_local_head_fallback_quotes_its_paths(tmp_path: Path) -> None:
    """Squad fold (LOW): the manual ``git worktree add`` fallback copy-pastes from a root with spaces."""
    import shlex

    root = tmp_path / "my repo"
    root.mkdir()
    for args in (("init", "-q", "-b", "main"), ("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "i")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    branch = "kitty/mission-demo-01ABCDEF"
    subprocess.run(["git", "-C", str(root), "branch", branch], check=True, capture_output=True)

    text = CoordinationWorktreeUnmaterialized._compose_next_step(root, branch, "demo-01ABCDEF", "01ABCDEF", root / "unused")

    assert f"git -C {shlex.quote(str(root))} worktree add '" in text


def test_the_flatten_skip_reason_on_a_remote_hit_carries_the_canonical_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Squad fold (MEDIUM): the doctor's flatten-skip hint no longer says a bare `git fetch` is enough."""
    import specify_cli.git.remote_probes as remote_probes
    from mission_runtime.coord_remedy import coordination_doctor_command, remote_only_branch, remote_only_steps
    from specify_cli.cli.commands._coordination_doctor import _coord_branch_remote_skip_reason

    monkeypatch.setattr(remote_probes, "remote_branch_lookup", lambda *_a, **_k: remote_probes.RemoteLookup.HIT)
    branch = "kitty/mission-demo-01ABCDEF"

    reason = _coord_branch_remote_skip_reason(tmp_path, branch, "demo-01ABCDEF")

    assert reason is not None
    assert reason.startswith("still exists on a remote -- not flattened.")
    assert remote_only_steps(remote_only_branch(tmp_path, branch), tmp_path, coordination_doctor_command("demo-01ABCDEF")) in reason
