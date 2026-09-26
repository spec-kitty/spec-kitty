"""Tests for ``capture_branch_tip`` — the canonical target-branch tip-capture
authority consolidated in this mission (issue #4857).

The premise, verified empirically on git 2.43.0 (see plan.md's premise
correction): ``git rev-parse <name>`` and ``git rev-parse --verify <name>``
are IDENTICAL — both resolve a branch+tag name collision to the **tag**
SHA. The pre-consolidation classifier-tip callers resolved the bare branch
name, so a tag colliding with the target-branch name silently misresolved
the pin to the tag. ``capture_branch_tip`` closes that gap by resolving
``refs/heads/{branch}`` explicitly, forcing branch-tip resolution
regardless of a same-named tag.

Uses a real temp git repo (subprocess) — the defect this mission closes is
a git ref-resolution defect, so only real git ref resolution can prove it
is fixed.
"""

from __future__ import annotations

import subprocess

import pytest

from specify_cli.core.vcs.git import capture_branch_tip

pytestmark = pytest.mark.git_repo


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=True)


def _git_output(cmd, cwd) -> str:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(repo, filename, content, message):
    (repo / filename).write_text(content)
    _run(["git", "add", filename], repo)
    _run(["git", "commit", "-m", message], repo)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@test.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _commit(repo, "README.md", "init\n", "init")
    return repo


class TestCaptureBranchTipValidRef:
    def test_returns_same_sha_as_rev_parse_refs_heads(self, tmp_path) -> None:
        """NFR-001: no change for the common no-collision case."""
        repo = _make_repo(tmp_path)
        expected = _git_output(["git", "rev-parse", "refs/heads/main"], repo)

        assert capture_branch_tip(repo, "main") == expected


class TestCaptureBranchTipMissingRef:
    def test_returns_none_never_raises(self, tmp_path) -> None:
        repo = _make_repo(tmp_path)

        assert capture_branch_tip(repo, "no-such-branch") is None


class TestCaptureBranchTipTagCollision:
    """The RED-first correctness proof (#4857).

    Build a branch ``dup`` at C1 and a TAG ``dup`` at a later commit C2
    (C1 != C2). ``capture_branch_tip`` must return C1 (the branch tip, via
    ``refs/heads/dup``) — never C2 (the tag), which is what a bare-name
    ``git rev-parse dup`` / ``git rev-parse --verify dup`` resolves to.
    """

    @pytest.mark.regression
    def test_resolves_branch_tip_not_same_named_tag(self, tmp_path) -> None:
        repo = _make_repo(tmp_path)

        # Branch `dup` created off `main`, tipped at C1.
        _run(["git", "checkout", "-b", "dup"], repo)
        _commit(repo, "dup.txt", "branch commit\n", "branch tip C1")
        c1 = _git_output(["git", "rev-parse", "HEAD"], repo)

        # Advance `dup` (the branch) further, then tag the OLD position...
        # Actually: create the tag at a DIFFERENT commit than the branch tip.
        # Move back to main, advance main, and place a tag named `dup` there
        # (a tag `dup` is a distinct ref namespace from branch `dup`; git
        # permits the same short name in both `refs/heads/` and `refs/tags/`
        # simultaneously).
        _run(["git", "checkout", "main"], repo)
        _commit(repo, "tag-target.txt", "tag commit\n", "tag target C2")
        c2 = _git_output(["git", "rev-parse", "HEAD"], repo)
        assert c1 != c2, "branch tip and intended tag target must differ"
        _run(["git", "tag", "dup", "main"], repo)

        # Contrast: demonstrate the OLD (pre-fix) bare-name behaviour first.
        # Both bare `rev-parse` and bare `--verify` resolve the ambiguous
        # name `dup` to the TAG (C2), not the branch (C1) — confirming the
        # premise this helper's `refs/heads/` qualification fixes.
        bare_rev_parse = _git_output(["git", "rev-parse", "dup"], repo)
        bare_rev_parse_verify = _git_output(["git", "rev-parse", "--verify", "dup"], repo)
        assert bare_rev_parse == c2, "bare `git rev-parse dup` must resolve to the TAG (pre-fix defect)"
        assert bare_rev_parse_verify == c2, "bare `git rev-parse --verify dup` must resolve to the TAG (pre-fix defect)"

        # The fix: capture_branch_tip resolves refs/heads/dup -> the BRANCH tip (C1).
        result = capture_branch_tip(repo, "dup")

        assert result == c1, "capture_branch_tip must resolve the BRANCH tip, never the same-named tag"
        assert result != c2

    def test_former_call_paths_agree_with_the_consolidated_authority(self, tmp_path) -> None:
        """Equivalence: the consolidated helper agrees with an explicit refs/heads/ resolution."""
        repo = _make_repo(tmp_path)
        _run(["git", "checkout", "-b", "dup"], repo)
        _commit(repo, "dup.txt", "branch commit\n", "branch tip")
        expected = _git_output(["git", "rev-parse", "refs/heads/dup"], repo)

        assert capture_branch_tip(repo, "dup") == expected
