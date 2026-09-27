"""#5113 (remedy-only): the CoordinationWorktreeUnmaterialized remedy text must
name a command that actually materializes the coordination worktree.

`spec-kitty doctor workspaces --fix` only removes stale registrations (husks) and
cannot CREATE a worktree, so the old remedy sent operators toward a no-op. The
corrected remedy names the concrete `git worktree add` command (mirroring the
#2240 `_coordination_doctor.py` hint). This mission fixes ONLY the remedy text;
the materialize-before-write change stays with #5108.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized


def _build(tmp_path: Path) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=tmp_path,
        mission_slug="demo-mission",
        mid8="01M3GN66",
        coordination_branch="kitty/mission-demo-mission-01M3GN66-lane-coord",
        primary_candidate=tmp_path / "kitty-specs" / "demo-mission",
    )


def test_remedy_names_git_worktree_add_command(tmp_path: Path) -> None:
    err = _build(tmp_path)
    assert "git" in err.next_step
    assert "worktree add" in err.next_step
    # Names the actual coordination branch to check out.
    assert "kitty/mission-demo-mission-01M3GN66-lane-coord" in err.next_step
    # Targets the coordination worktree ROOT under .worktrees/, not the husk-only
    # doctor command.
    assert ".worktrees" in err.next_step


def test_remedy_does_not_advertise_husk_only_doctor_as_materializer(tmp_path: Path) -> None:
    err = _build(tmp_path)
    # The old, misleading remedy promised self-materialization and pointed at a
    # husk-only command as the fix. That claim is gone.
    assert "self-materialize" not in err.next_step
    # If `doctor workspaces --fix` is mentioned at all, it must be qualified as
    # NOT the materializer (it only removes stale registrations), and the
    # actionable `git worktree add` command must precede it.
    if "doctor workspaces --fix" in err.next_step:
        assert "cannot create the worktree" in err.next_step
        assert err.next_step.index("worktree add") < err.next_step.index("doctor workspaces --fix")


def test_str_carries_the_actionable_remedy(tmp_path: Path) -> None:
    err = _build(tmp_path)
    assert "worktree add" in str(err)
