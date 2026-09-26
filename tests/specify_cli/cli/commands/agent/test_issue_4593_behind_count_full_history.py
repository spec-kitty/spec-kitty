"""Regression coverage for #4593 item1: accurate behind-count on merge-rich targets.

``_count_behind_commits_outside_planning_artifacts`` (``tasks_dependency_graph.py``)
composes a single ``git_rev_list_count`` call to report *source* divergence — the
number of behind-commits touching files outside the ``kitty-specs/``/``.kittify/``
ledger trees. Before #4593, that call used git's default history simplification,
which can silently PRUNE a source commit from the count when it arrives at the
target branch through a merge that is TREESAME to its followed (first) parent —
a classic ``git log -- <path>`` gotcha: when a merge resolves a conflicting path
by keeping the first parent's content, the diff between the merge and its first
parent is empty for that path, so default simplification treats the merge (and,
critically, the *entire second-parent line*) as uninteresting and drops it from
the walk, even though the second-parent commit genuinely touched a matching path.

``git_rev_list_count(..., full_history=True)`` disables that simplification, so
the pruned source commit is counted again — at the cost of also counting the
now-visible merge commit itself against the pathspec (a conservative upper
bound, acceptable for this message-only consumer; C-003: blocking decisions
still derive from the full merge-base diff, never this count).

These tests build a REAL git repo with the exact TREESAME-merge shape described
above (the defect is a git history-simplification defect, so only a real
git walk can prove it).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.agent.tasks_dependency_graph import (
    _count_behind_commits_outside_planning_artifacts,
)
from specify_cli.core.vcs.git import git_rev_list_count

pytestmark = pytest.mark.git_repo


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=True)


def _git_output(cmd, cwd) -> str:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _write_commit(repo, filename, content, message):
    path = repo / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _run(["git", "add", filename], repo)
    _run(["git", "commit", "-m", message], repo)


def _init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@test.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    return repo


def _build_treesame_merge_repo(tmp_path):
    """Build a repo where a source commit arrives via a TREESAME merge.

    Shape:
        C0 (init: src/thing.py = "base")
         |\\
         |  \\
      C_main1  C_topic1   (both rewrite src/thing.py, conflicting content)
         |    /
          \\  /
           M   (merge, resolved via -X ours -> tree == C_main1's tree for
                src/thing.py, i.e. TREESAME to the first/followed parent)

    Default (non-``--full-history``) path-limited history simplification
    collapses the merge ``M`` into a pass-through of its first parent
    (``C_main1``) because ``M`` is TREESAME to it for the pathspec, which
    also prunes the entire second-parent line (``C_topic1``) from the walk
    — even though ``C_topic1`` genuinely touched ``src/thing.py``.
    """
    repo = _init_repo(tmp_path)
    _write_commit(repo, "src/thing.py", "base\n", "init")
    old_ref = _git_output(["git", "rev-parse", "HEAD"], repo)

    _run(["git", "checkout", "-b", "topic"], repo)
    _write_commit(repo, "src/thing.py", "topic-content\n", "topic: source change (the pruned commit)")
    topic_sha = _git_output(["git", "rev-parse", "HEAD"], repo)

    _run(["git", "checkout", "main"], repo)
    _write_commit(repo, "src/thing.py", "main-content\n", "main: source change")
    main1_sha = _git_output(["git", "rev-parse", "HEAD"], repo)

    # Merge topic into main, resolving the whole-file conflict in main's
    # favour -> the merge tree for src/thing.py equals C_main1's tree
    # (TREESAME to the first/followed parent).
    _run(["git", "merge", "-X", "ours", "--no-edit", "topic"], repo)
    merge_sha = _git_output(["git", "rev-parse", "HEAD"], repo)

    assert topic_sha != main1_sha != merge_sha
    return repo, old_ref, merge_sha, topic_sha


class TestFullHistoryFlagClosesTheUndercount:
    @pytest.mark.regression
    def test_full_history_includes_the_treesame_pruned_source_commit(self, tmp_path) -> None:
        repo, old_ref, _merge_sha, _topic_sha = _build_treesame_merge_repo(tmp_path)
        rev_range = f"{old_ref}..main"
        pathspecs = (".",)

        without_full_history = git_rev_list_count(repo, rev_range, pathspecs=pathspecs, full_history=False)
        with_full_history = git_rev_list_count(repo, rev_range, pathspecs=pathspecs, full_history=True)

        assert without_full_history is not None
        assert with_full_history is not None
        # RED-first proof: default simplification prunes the topic commit
        # (and collapses the merge into a pass-through), undercounting.
        assert without_full_history == 1, "default simplification must undercount to just the main-line commit"
        # GREEN: --full-history recovers the pruned source commit (and also
        # counts the now-visible merge commit itself -- a conservative upper
        # bound, per the docstring's contract; assert inclusion, not a
        # naive exact equality the merge over-count would break).
        assert with_full_history > without_full_history
        assert with_full_history >= 2

    def test_production_wrapper_is_wired_to_full_history(self, tmp_path) -> None:
        """``_count_behind_commits_outside_planning_artifacts`` must pass
        ``full_history=True`` through to ``git_rev_list_count`` — confirms
        the production call site (not just the flag itself) is fixed."""
        repo, old_ref, merge_sha, _topic_sha = _build_treesame_merge_repo(tmp_path)
        # Point HEAD at old_ref so `HEAD..main` is the range the production
        # helper composes internally.
        _run(["git", "checkout", "-q", old_ref], repo)

        direct = git_rev_list_count(repo, "HEAD..main", pathspecs=(".", ":(exclude)kitty-specs", ":(exclude).kittify"), full_history=True)
        wrapped = _count_behind_commits_outside_planning_artifacts(repo, "main", behind_count=99)

        assert direct is not None
        assert wrapped == direct
        assert wrapped >= 2, "production wrapper must recover the TREESAME-pruned source commit"


class TestFailOpenFallbackPreserved:
    def test_undeterminable_count_falls_back_to_raw_behind_count(self, tmp_path) -> None:
        with patch("subprocess.run", return_value=MagicMock(returncode=128, stdout="")):
            result = _count_behind_commits_outside_planning_artifacts(tmp_path, "main", behind_count=42)
        assert result == 42


class TestLinearRangeUnchangedByFlag:
    def test_non_merge_range_same_count_with_or_without_full_history(self, tmp_path) -> None:
        repo = _init_repo(tmp_path)
        _write_commit(repo, "src/a.py", "1\n", "c1")
        old_ref = _git_output(["git", "rev-parse", "HEAD"], repo)
        _write_commit(repo, "src/a.py", "2\n", "c2")
        _write_commit(repo, "src/b.py", "1\n", "c3")

        rev_range = f"{old_ref}..main"
        pathspecs = (".",)

        without_full_history = git_rev_list_count(repo, rev_range, pathspecs=pathspecs, full_history=False)
        with_full_history = git_rev_list_count(repo, rev_range, pathspecs=pathspecs, full_history=True)

        assert without_full_history == with_full_history == 2
