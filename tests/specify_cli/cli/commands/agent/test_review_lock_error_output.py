"""``_prepare_review_workspace`` renders the review lock refusal (#4163).

The ``ReviewLockError`` leg was the last builtin ``print`` in ``src/`` carrying
Rich markup, so ``[red]…[/red]`` reached the terminal literally. It now goes
through the CLI console seam, with the message escaped: lock messages name
agents, work packages and paths, and a bracketed one would otherwise be eaten
as a tag (or raise ``MarkupError`` on a stray closing tag).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from specify_cli.cli.commands.agent import workflow


def test_review_lock_refusal_is_rendered_and_escaped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.review.lock import ReviewLock, ReviewLockError

    reason = "[locked] WP01 held by agent [claude] since 10:00 [/]"

    def _refuse(*args: object, **kwargs: object) -> None:
        raise ReviewLockError(reason)

    monkeypatch.setattr("specify_cli.review.lock._get_isolation_config", lambda root: None)
    monkeypatch.setattr(ReviewLock, "acquire", staticmethod(_refuse))

    workspace = SimpleNamespace(
        worktree_path=tmp_path,
        branch_name="kitty/wp01",
        is_husk=False,
        exists=True,
    )

    with pytest.raises(typer.Exit):
        workflow._prepare_review_workspace(workspace, tmp_path, "WP01", "claude")

    out = " ".join(capsys.readouterr().out.split())
    assert reason in out
    assert "[red]" not in out


# --- #6386: an unreadable lock gets a named, unwrapped refusal -------------


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    return root


def _corrupt_lock(worktree: Path) -> Path:
    from specify_cli.review.lock import LOCK_REL_PATH

    lock = worktree / LOCK_REL_PATH
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("{}")
    return lock


def test_unreadable_lock_at_acquire_is_a_named_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A lock that turns unreadable after the pre-claim check is still refused by name, not as a raw error."""
    repo = _repo(tmp_path)
    lock = _corrupt_lock(repo)
    monkeypatch.setattr("specify_cli.review.lock._get_isolation_config", lambda root: None)
    workspace = SimpleNamespace(worktree_path=repo, branch_name="main", is_husk=False, exists=True)

    with pytest.raises(typer.Exit):
        workflow._prepare_review_workspace(workspace, repo, "WP01", "claude")

    out = capsys.readouterr().out
    assert "REVIEW_LOCK_UNREADABLE" in out
    assert f"rm {lock}" in out, "the refusal is printed unwrapped, so the remedy copies intact"
    assert lock.read_text() == "{}"


def test_prepare_review_workspace_excludes_the_lock_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("specify_cli.review.lock._get_isolation_config", lambda root: None)
    workspace = SimpleNamespace(worktree_path=repo, branch_name="main", is_husk=False, exists=True)

    workflow._prepare_review_workspace(workspace, repo, "WP01", "claude")

    assert ".spec-kitty/" in (repo / ".git" / "info" / "exclude").read_text().splitlines()


def test_foreign_lock_check_names_an_unreadable_lock(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _corrupt_lock(repo)
    workspace = SimpleNamespace(worktree_path=repo, branch_name="main", is_husk=False, exists=True)

    message = workflow._foreign_review_lock_message(workspace, repo, "claude")

    assert message is not None and message.startswith("REVIEW_LOCK_UNREADABLE")


def test_review_checkout_ref_mirrors_worktree_creation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    def ref(*, exists: bool, branch: str | None, start: str | None = None) -> str | None:
        ws = SimpleNamespace(worktree_path=tmp_path / "w", branch_name=branch, is_husk=False, exists=exists)
        return workflow._review_checkout_ref(ws, repo, start)

    assert ref(exists=True, branch="main") is None
    assert ref(exists=False, branch=None) is None
    assert ref(exists=False, branch="main") == "main", "an existing local branch is checked out as is"
    assert ref(exists=False, branch="kitty/new", start="refs/remotes/origin/kitty/new") == "refs/remotes/origin/kitty/new"
    assert ref(exists=False, branch="kitty/new") == "HEAD"


def test_acquire_fallback_says_the_claim_was_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path)
    _corrupt_lock(repo)
    monkeypatch.setattr("specify_cli.review.lock._get_isolation_config", lambda root: None)
    workspace = SimpleNamespace(worktree_path=repo, branch_name="main", is_husk=False, exists=True)

    with pytest.raises(typer.Exit):
        workflow._prepare_review_workspace(workspace, repo, "WP01", "claude")

    assert "The review claim was already recorded" in capsys.readouterr().out


def test_husk_workspace_is_left_to_the_husk_refusal(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    workspace = SimpleNamespace(worktree_path=tmp_path / "husk", branch_name="main", is_husk=True, exists=False)
    assert workflow._unreadable_review_lock_message(workspace, repo, None) is None


def test_foreign_lock_check_fails_closed_when_the_lock_changes_mid_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lock that read as corrupt is never "free to move", even if a re-read succeeds."""
    from specify_cli.review.lock import ReviewLock, ReviewLockReadError

    repo = _repo(tmp_path)

    def _corrupt_once(worktree: Path) -> None:
        raise ReviewLockReadError(path=str(worktree / "lock"), reason="truncated")

    monkeypatch.setattr(ReviewLock, "load", staticmethod(_corrupt_once))
    monkeypatch.setattr(workflow, "_unreadable_review_lock_message", lambda *a, **k: None)
    workspace = SimpleNamespace(worktree_path=repo, branch_name="main", is_husk=False, exists=True)

    message = workflow._foreign_review_lock_message(workspace, repo, "claude")

    assert message is not None and message.startswith("REVIEW_LOCK_UNREADABLE")
    assert "changed while it was read" in message
