"""#7555: ``spec-kitty init`` inside a git repository commits what it wrote.

Before the fix ``init`` wrote ``.kittify/``, the agent directory, ``.gitignore``
and ``.gitattributes`` and committed none of them, so the first gated command
saw them as dirt and the agent committed them by hand. Now the files ``init``
wrote land in one commit; anything that was already uncommitted before ``init``
ran is left alone (#5905), and ``--no-commit`` opts out.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import dirty, flat, git, isolated_env, run_sk

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(600)]

_INIT = ("init", "--ai", "claude", "--non-interactive")


def _repo(tmp_path: Path, *, with_commit: bool = True) -> tuple[Path, dict[str, str]]:
    env = isolated_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "QA")
    git(repo, "config", "user.email", "qa@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    if with_commit:
        (repo / "README.md").write_text("# demo\n", encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "-qm", "user commit")
    return repo, env


def _commit_count(repo: Path) -> int:
    proc = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=repo, capture_output=True, text=True)
    return int(proc.stdout.strip()) if proc.returncode == 0 else 0


def test_init_commits_everything_it_wrote_in_one_commit(tmp_path: Path) -> None:
    repo, env = _repo(tmp_path)

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(repo) == []
    assert _commit_count(repo) == 2
    head = git(repo, "show", "--name-only", "--format=%s", "HEAD").splitlines()
    assert head[0] == "chore: initialize spec-kitty project"
    for path in (".kittify/config.yaml", ".gitignore", ".gitattributes"):
        assert path in head, head


def test_init_leaves_files_that_were_dirty_before_it_ran(tmp_path: Path) -> None:
    repo, env = _repo(tmp_path)
    (repo / "notes.txt").write_text("operator scratch\n", encoding="utf-8")
    (repo / "README.md").write_text("# demo\n\nedited\n", encoding="utf-8")

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "notes.txt" not in committed
    assert "README.md" not in committed
    assert sorted(dirty(repo)) == ["README.md", "notes.txt"]


def test_no_commit_opts_out(tmp_path: Path) -> None:
    repo, env = _repo(tmp_path)

    proc = run_sk(repo, env, *_INIT, "--no-commit")

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert _commit_count(repo) == 1
    assert ".kittify/config.yaml" in dirty(repo)


def test_init_on_an_unborn_branch_says_to_make_the_first_commit(tmp_path: Path) -> None:
    """Residual: ``safe_commit`` lands only on an existing branch, so on a repository
    with no commit yet init leaves its files and says to make them the first commit."""
    repo, env = _repo(tmp_path, with_commit=False)

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert _commit_count(repo) == 0
    assert "no commits yet" in flat(proc)
    assert "commit them as your first commit" in flat(proc)
    # It never suggests a sweeping `git add -A`: that would also commit files the user already had.
    assert "add -A" not in flat(proc)


def test_init_outside_git_commits_nothing(tmp_path: Path) -> None:
    env = isolated_env(tmp_path)
    target = tmp_path / "plain"
    target.mkdir()

    proc = run_sk(target, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert not (target / ".git").exists()


def test_init_preserves_the_users_staged_changes(tmp_path: Path) -> None:
    """A staged new file and a staged edit stay staged and out of init's commit (#5905)."""
    repo, env = _repo(tmp_path)
    (repo / "staged.txt").write_text("mine\n", encoding="utf-8")
    (repo / "README.md").write_text("# demo\n\nstaged edit\n", encoding="utf-8")
    git(repo, "add", "staged.txt", "README.md")

    proc = run_sk(repo, env, *_INIT)

    assert proc.returncode == 0, flat(proc)[-2000:]
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "staged.txt" not in committed
    assert "README.md" not in committed
    staged = git(repo, "diff", "--cached", "--name-only").splitlines()
    assert sorted(staged) == ["README.md", "staged.txt"]
    assert "left out of that commit" in flat(proc)


def test_init_words_the_committers_reasons_for_init() -> None:
    from specify_cli.cli.commands.init import _init_commit_warning
    from specify_cli.upgrade import autocommit

    for reason in (
        autocommit.UPGRADE_COMMIT_SKIP_WARNING,
        autocommit.DETACHED_HEAD_WARNING,
        autocommit.BRANCH_DETECTION_FAILED_WARNING,
        autocommit.METADATA_DIRTY_AT_BASELINE_WARNING,
    ):
        worded = _init_commit_warning(reason)
        assert "upgrade" not in worded
        assert "init" in worded
    assert _init_commit_warning("something else") == "something else"


@pytest.mark.parametrize(
    ("sha", "stash", "expected"),
    [
        ("abc123", "stash@{0}", ["Commit abc123 did land.", "git stash pop --index stash@{0}"]),
        (None, None, ["No commit landed."]),
    ],
)
def test_init_renders_a_failed_staging_restore_honestly(sha: str | None, stash: str | None, expected: list[str]) -> None:
    from specify_cli.cli.commands.init import _render_init_recovery_failed
    from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed

    rendered = _render_init_recovery_failed(SafeCommitRecoveryFailed("restore failed", commit_sha=sha, orphan_stash_ref=stash))

    for fragment in expected:
        assert fragment in rendered
    assert "upgrade" not in rendered
