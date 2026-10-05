"""Issue #610 regression: implement()'s WP-claim auto-commit must not
silently swallow a genuine branch-name mismatch.

Root cause (confirmed by a dialectic squad against thesis planning#854,
reproduced 7/7 outside pytest entirely): ``_commit_wp_claim_status``
(``implement.py``) caught every non-``SafeCommitPathPolicyError`` exception
from ``safe_commit`` -- including ``SafeCommitHeadMismatch`` -- as a soft
"Auto-commit skipped" warning. The WP status/lane files it was trying to
commit were already written to disk by the caller *before* ``safe_commit``
was ever invoked, so swallowing the mismatch left the worktree dirty with no
commit to cover it -- exactly what later trips ``ref_advance.py``'s
dirty-worktree safety gate at merge time.

This module drives the REAL ``safe_commit`` HEAD assertion against a real
git repository (mirrors the "no test infrastructure involved at all"
reproduction from the issue) rather than mocking ``safe_commit`` -- the
mismatch is genuine, not simulated.

The claim commit's destination is resolved through the canonical seam
(``placement_seam(repo_root, mission_slug).write_target(WORK_PACKAGE_TASK)``,
never a hand-built ``CommitTarget`` -- contracts/seam-api.md), which for a
PRIMARY-partition kind like ``WORK_PACKAGE_TASK`` projects the mission's
``target_branch`` as read from ``meta.json`` -- the same PRIMARY-partition
destination ``_ensure_planning_artifacts_committed_git`` uses for its own
primary group. These tests set ``meta.json``'s ``target_branch`` to a branch
that deliberately differs from the repo's actual checked-out branch, so the
seam resolves a genuinely different ref than HEAD and reproduces the
mismatch -- exactly as it would for a real mission whose worktree checkout
has drifted from its recorded target branch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specify_cli.cli.commands.implement_claim import _commit_wp_claim_status
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch

pytestmark = [pytest.mark.unit, pytest.mark.git_repo, pytest.mark.non_sandbox]

_MISSION_SLUG = "demo-mission"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_flat_repo(repo: Path, *, checked_out_branch: str) -> Path:
    """A real, on-disk flat-topology repo, checked out on *checked_out_branch*.

    Returns the WP file path. ``safe_commit``'s worktree-foreignness / HEAD
    checks need real git plumbing, so this is a genuine repo, not a fixture.
    """
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-qb", checked_out_branch, str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        '{"mission_id":"01KW1P0FZZ9QABCDEF01234567","mission_slug":"' + _MISSION_SLUG + '","mid8":"01KW1P0F","topology":"flat","target_branch":"main"}',
        encoding="utf-8",
    )
    wp_file = feature_dir / "tasks" / "WP01-demo.md"
    wp_file.write_text("---\nwork_package_id: WP01\n---\nbody\n", encoding="utf-8")
    # The status write itself -- landed on disk BEFORE any commit attempt,
    # matching the issue's "the status-file write itself still lands on
    # disk" observation.
    (feature_dir / "status.events.jsonl").write_text('{"event":"claimed"}\n', encoding="utf-8")
    (feature_dir / "status.json").write_text('{"WP01":"claimed"}\n', encoding="utf-8")
    return wp_file


def test_head_mismatch_propagates_instead_of_being_swallowed(tmp_path: Path) -> None:
    """The worktree is checked out on ``feat/checked-out``, but the resolved
    claim-commit target names a DIFFERENT branch (a genuine mismatch, exactly
    the scenario the issue describes). ``_commit_wp_claim_status`` must let
    ``SafeCommitHeadMismatch`` propagate, not fold it into a warning.
    """
    repo = tmp_path / "repo"
    wp_file = _init_flat_repo(repo, checked_out_branch="feat/checked-out")
    feature_dir = wp_file.parent.parent

    with pytest.raises(SafeCommitHeadMismatch):
        _commit_wp_claim_status(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            wp_file=wp_file,
            auto_commit=True,
            status_result=MagicMock(status_changed=True),
        )

    # Never swallowed into a commit either: safe_commit's HEAD assertion
    # runs before any staging, so the working tree still carries the
    # already-written (uncommitted) status/lane files -- the exact dirty
    # state the issue names, now surfaced via a raised exception instead of
    # a silent warning. The whole ``kitty-specs/`` tree is untracked (never
    # staged, let alone committed), so ``git status --porcelain`` reports it
    # as one untracked directory rather than per-file entries.
    porcelain = _git(repo, "status", "--porcelain").stdout
    assert "kitty-specs/" in porcelain
    assert (feature_dir / "status.events.jsonl").read_text(encoding="utf-8") != ""
    assert (feature_dir / "tasks" / "WP01-demo.md").exists()


def test_no_swallowed_warning_printed_on_head_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Regression pin for the specific symptom: no "Could not auto-commit
    lane change" warning should print on this path -- that print is exactly
    what silently downgraded this defect to a non-fatal warning before the
    fix, letting the caller move on with a dirty tree.
    """
    from specify_cli.cli.commands import implement_claim as impl_mod

    repo = tmp_path / "repo"
    wp_file = _init_flat_repo(repo, checked_out_branch="feat/checked-out")
    feature_dir = wp_file.parent.parent

    printed: list[str] = []
    original_print = impl_mod.console.print

    def _capturing_print(*args: object, **kwargs: object) -> None:
        printed.append(str(args[0]) if args else "")
        original_print(*args, **kwargs)

    import unittest.mock as mock

    with mock.patch.object(impl_mod.console, "print", side_effect=_capturing_print), pytest.raises(SafeCommitHeadMismatch):
        _commit_wp_claim_status(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            wp_file=wp_file,
            auto_commit=True,
            status_result=MagicMock(status_changed=True),
        )

    assert not any("Could not auto-commit lane change" in line for line in printed)
