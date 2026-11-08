"""Regression: safe_commit must distinguish a genuine empty changeset from a
real commit failure (e.g. a failing pre-commit hook).

Before this fix, ``_run_commit_capture_sha`` collapsed *every* non-zero
``git commit`` exit to ``None`` and ``safe_commit`` raised a single
``"safe_commit: git commit failed"`` RuntimeError for all of them. The commit
router's ``_is_empty_changeset_error`` matched that message by prefix, so a
commit that FAILED for a non-empty reason (a broken pre-commit hook, a rejected
commit, etc.) was silently reported as ``status="unchanged"`` / ``committed=False``
— masking the real failure. This surfaced live as ``spec-commit`` reporting
"Spec artifact(s) unchanged, no commit needed" for a fresh mission whose
pre-commit hook pointed at a since-deleted interpreter.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.commit_router import _is_empty_changeset_error
from specify_cli.git.commit_helpers import SafeCommitStagedTreeUnchanged, safe_commit

pytestmark = pytest.mark.git_repo

_UNPROTECTED_BRANCH = "kitty/mission-test-01ABCDEF"


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "README.md").write_text("# seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", _UNPROTECTED_BRANCH], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    return root


def _new_spec(root: Path) -> Path:
    spec = root / "kitty-specs" / "demo-mission" / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Spec\n\n| FR-001 | a real requirement | High | Open |\n")
    return spec


def test_hook_failure_is_not_classified_as_empty_changeset(repo: Path) -> None:
    """A failing pre-commit hook must surface as a real failure, never 'unchanged'."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'pre-commit boom' >&2\nexit 1\n")
    hook.chmod(0o755)

    spec = _new_spec(repo)

    with pytest.raises(RuntimeError) as excinfo:
        safe_commit(
            repo_root=repo,
            worktree_root=repo,
            destination_ref=_UNPROTECTED_BRANCH,
            message="Add spec",
            paths=(spec,),
        )

    # The load-bearing assertion: the router must NOT treat this as a benign
    # empty changeset (which it would render as status="unchanged").
    assert not _is_empty_changeset_error(excinfo.value), (
        "hook failure was misclassified as an empty changeset -> would surface "
        f"as 'unchanged, no commit needed'. message={excinfo.value!r}"
    )
    # And the failure must carry git's own output so the operator can diagnose it.
    assert "pre-commit boom" in str(excinfo.value)
    # The commit genuinely did not land.
    head_files = subprocess.run(
        ["git", "ls-files", "kitty-specs/demo-mission/spec.md"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head_files == "", "hook aborted the commit, so the spec must not be tracked"


def test_genuine_empty_changeset_is_still_classified_as_empty(repo: Path) -> None:
    """A true no-op (staged content identical to HEAD) stays 'unchanged'."""
    spec = _new_spec(repo)
    # First commit lands.
    safe_commit(
        repo_root=repo, worktree_root=repo, destination_ref=_UNPROTECTED_BRANCH,
        message="Add spec", paths=(spec,),
    )
    # Re-committing identical content is a genuine empty changeset.
    with pytest.raises(RuntimeError) as excinfo:
        safe_commit(
            repo_root=repo, worktree_root=repo, destination_ref=_UNPROTECTED_BRANCH,
            message="Add spec again", paths=(spec,),
        )
    assert _is_empty_changeset_error(excinfo.value), (
        "a genuine empty changeset must still classify as empty (-> 'unchanged'); "
        f"message={excinfo.value!r}"
    )


def test_hook_failure_that_prints_nothing_to_commit_is_not_classified_as_empty(repo: Path) -> None:
    """Adversarial case (audit BLOCK_MATERIAL): a pre-commit hook that FAILS
    while also printing a "nothing to commit" marker in its own stdout/stderr
    must still surface as a real failure, not as a benign empty changeset.

    Output-string matching alone cannot distinguish this from a genuine no-op,
    since git's own output and the hook's output are combined. The staged tree
    is the authority: a real (rejected) staged change differs from HEAD, so
    the classification must key off that, not off what strings appear in the
    combined output.
    """
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'nothing to commit, working tree clean'\nexit 1\n")
    hook.chmod(0o755)

    spec = _new_spec(repo)

    with pytest.raises(RuntimeError) as excinfo:
        safe_commit(
            repo_root=repo,
            worktree_root=repo,
            destination_ref=_UNPROTECTED_BRANCH,
            message="Add spec",
            paths=(spec,),
        )

    # The load-bearing assertion: a real staged change rejected by a failing
    # hook must NEVER classify as an empty changeset, even though the hook's
    # own output contains the "nothing to commit" marker.
    assert not _is_empty_changeset_error(excinfo.value), (
        "hook failure that prints a 'nothing to commit' marker was "
        "misclassified as an empty changeset -> would surface as "
        f"'unchanged, no commit needed'. message={excinfo.value!r}"
    )
    # The commit genuinely did not land.
    head_files = subprocess.run(
        ["git", "ls-files", "kitty-specs/demo-mission/spec.md"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head_files == "", "hook aborted the commit, so the spec must not be tracked"


def test_typed_staged_tree_unchanged_classifies_as_empty_even_with_drifted_message() -> None:
    """#4610: the typed signal is the primary classifier. A
    ``SafeCommitStagedTreeUnchanged`` whose message drifted (wording change,
    wrapping, a future rephrase) must still report as a benign empty
    changeset — the prose match is only a fallback for pre-type exceptions.
    """
    exc = SafeCommitStagedTreeUnchanged(destination_ref=_UNPROTECTED_BRANCH)
    # Simulate wording drift: the TYPE is the signal, not the prose.
    exc.args = ("safe_commit: a completely different message",)

    assert _is_empty_changeset_error(exc), (
        "a typed SafeCommitStagedTreeUnchanged must classify as an empty "
        "changeset regardless of its message text"
    )


def test_prose_fallback_still_matches_a_bare_runtime_error() -> None:
    """#4610: a plain ``RuntimeError`` carrying the historical prose keeps
    classifying as empty, so consumers that wrap or re-raise the message as a
    bare RuntimeError (the pre-#3861 shape) are not broken.
    """
    exc = RuntimeError(
        f"safe_commit: nothing to commit for destination_ref={_UNPROTECTED_BRANCH!r} (empty changeset)"
    )
    assert _is_empty_changeset_error(exc)


def test_fresh_untracked_file_commits_cleanly(repo: Path) -> None:
    """Control: with no broken hook, a brand-new untracked spec commits (guards the
    first-spec-of-a-fresh-mission path that originally looked broken)."""
    spec = _new_spec(repo)
    result = safe_commit(
        repo_root=repo, worktree_root=repo, destination_ref=_UNPROTECTED_BRANCH,
        message="Add spec", paths=(spec,),
    )
    assert result is not None and result.sha
    tracked = subprocess.run(
        ["git", "ls-files", "kitty-specs/demo-mission/spec.md"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tracked == "kitty-specs/demo-mission/spec.md"
