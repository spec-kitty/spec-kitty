"""``safe_commit`` commits the link (not its target) and names a failing path (#5671, #4722)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget
from specify_cli.git.commit_helpers import SafeCommitError, safe_commit

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

BRANCH = "work"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "--template=", "-b", BRANCH)
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "real.md").write_text("base\n")
    (r / "tracked.txt").write_text("t\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    return r


def _commit(repo: Path, *paths: Path, **kwargs: object) -> object:
    return safe_commit(
        repo_root=repo,
        worktree_root=repo,
        target=CommitTarget(ref=BRANCH),
        message="msg",
        paths=tuple(paths),
        **kwargs,  # type: ignore[arg-type]
    )


def _symlink(link: Path, target: str) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("os.symlink unavailable (Windows without developer mode)")


def test_absolute_symlink_path_commits_the_link_not_the_target(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    (repo / "real.md").write_text("base\nWIP\n")
    _commit(repo, repo / "link.md")
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")
    assert _git(repo, "show", "HEAD:link.md") == "real.md"
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["link.md"]
    assert "+WIP" in _git(repo, "diff", "HEAD", "--", "real.md")


def test_tracked_link_repointed_commits_the_new_link_target(repo: Path) -> None:
    (repo / "other.md").write_text("o\n")
    _symlink(repo / "link.md", "real.md")
    _git(repo, "add", "link.md", "other.md")
    _git(repo, "commit", "-m", "link")
    (repo / "link.md").unlink()
    _symlink(repo / "link.md", "other.md")
    (repo / "real.md").write_text("base\nWIP\n")
    _commit(repo, repo / "link.md")
    assert _git(repo, "show", "HEAD:link.md") == "other.md"
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["link.md"]
    assert "+WIP" in _git(repo, "diff", "HEAD", "--", "real.md")


def test_relative_symlink_path_commits_the_link(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    _commit(repo, Path("link.md"))
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")


def test_looping_absolute_path_is_refused_as_a_runtime_error(repo: Path) -> None:
    _symlink(repo / "a", "b")
    _symlink(repo / "b", "a")
    head = _git(repo, "rev-parse", "HEAD")
    index = _git(repo, "ls-files", "-s")
    with pytest.raises(RuntimeError) as ei:
        _commit(repo, repo / "a")
    assert isinstance(ei.value, SafeCommitError)
    assert ei.value.error_code == "SAFE_COMMIT_PATH_LOOP"
    assert str(repo / "a") in str(ei.value)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "ls-files", "-s") == index


def test_expected_path_bytes_accepts_a_link_path(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    head = _git(repo, "rev-parse", "HEAD").strip()
    _commit(
        repo,
        repo / "link.md",
        expected_parent_sha=head,
        expected_path_bytes={repo / "link.md": b"real.md"},
    )
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")


def test_batch_stage_failure_names_the_path_and_gits_reason(repo: Path) -> None:
    (repo / "ok.md").write_text("ok\n")
    with pytest.raises(RuntimeError) as ei:
        _commit(repo, repo / "ok.md", Path("missing.md"))
    msg = str(ei.value)
    assert msg.startswith("safe_commit: failed to stage requested files in ")
    detail = msg.split(str(repo) + ": ", 1)[1]
    assert "missing.md" in detail
    assert "did not match any files" in detail
    assert "ok.md" not in detail
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""


# ---------------------------------------------------------------------------
# index_deletions (#5443 / FR-022): commit an index deletion, keep the file on disk
# ---------------------------------------------------------------------------


@pytest.fixture
def del_repo(repo: Path) -> Path:
    for name in ("a.md", "c.md", "p.txt"):
        (repo / name).write_text(f"{name}\nline2\nline3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "more")
    return repo


def _real_index_state(repo: Path, *pathspec: str) -> tuple[str, str, str]:
    tail = ["--", *pathspec] if pathspec else []
    return (_git(repo, "ls-files", "-s", *tail), _git(repo, "diff", "--cached", *tail), _git(repo, "diff", *tail))


def _no_temp_index(repo: Path) -> bool:
    return not list((repo / ".git").glob("spec-kitty-index-deletions*"))


def test_index_deletion_is_committed_while_the_file_stays_and_operator_staging_is_untouched(del_repo: Path) -> None:
    repo = del_repo
    (repo / "x.md").write_text("x\n")
    (repo / "b.md").write_text("b\n")
    _git(repo, "add", "b.md")  # operator-staged unrelated file
    _git(repo, "rm", "--cached", "-q", "c.md")  # operator-staged unrelated deletion
    _git(repo, "rm", "--cached", "-q", "a.md")  # the deletion under test
    _commit(repo, repo / "x.md", index_deletions=(Path("a.md"),))
    assert sorted(_git(repo, "show", "HEAD", "--name-status", "--format=").split("\n")[:-1]) == ["A\tx.md", "D\ta.md"]
    assert (repo / "a.md").read_text() == "a.md\nline2\nline3\n"
    assert _git(repo, "ls-files", "--", "a.md") == ""
    assert _git(repo, "diff", "--cached", "--name-status").split("\n")[:-1] == ["A\tb.md", "D\tc.md"]
    assert _git(repo, "diff", "--cached", "--name-only", "--", "a.md", "x.md") == ""
    assert _no_temp_index(repo)


def test_a_hook_sees_exactly_the_intended_diff(del_repo: Path) -> None:
    repo = del_repo
    seen = repo.parent / "hook-seen"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\ngit diff --cached --name-status > '{seen}'\n")
    hook.chmod(0o755)
    (repo / "b.md").write_text("b\n")
    _git(repo, "add", "b.md")
    _git(repo, "rm", "--cached", "-q", "c.md")
    _git(repo, "rm", "--cached", "-q", "a.md")
    _commit(repo, index_deletions=(Path("a.md"),))
    assert seen.read_text() == "D\ta.md\n"


def test_a_partially_staged_operator_file_is_not_disturbed(del_repo: Path) -> None:
    repo = del_repo
    (repo / "p.txt").write_text("p.txt\nSTAGED\nline3\n")
    _git(repo, "add", "p.txt")
    (repo / "p.txt").write_text("p.txt\nSTAGED\nline3\nUNSTAGED\n")
    _git(repo, "rm", "--cached", "-q", "a.md")
    before = _real_index_state(repo, "p.txt")
    on_disk = (repo / "p.txt").read_bytes()
    _commit(repo, index_deletions=(Path("a.md"),))
    assert (repo / "p.txt").read_bytes() == on_disk
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["a.md"]
    after = _real_index_state(repo, "p.txt")
    assert after[0] == before[0]  # the index entry (mode, blob, stage)
    assert after[1] == before[1]  # the staged half of p.txt, byte for byte
    assert after[2] == before[2]  # the unstaged half
    assert "+STAGED" in after[1] and "+UNSTAGED" in after[2]


def test_rejecting_hook_leaves_head_index_and_file_unchanged(del_repo: Path) -> None:
    repo = del_repo
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho no >&2\nexit 1\n")
    hook.chmod(0o755)
    (repo / "b.md").write_text("b\n")
    _git(repo, "add", "b.md")
    _git(repo, "rm", "--cached", "-q", "a.md")
    head = _git(repo, "rev-parse", "HEAD")
    before = _real_index_state(repo)
    with pytest.raises(RuntimeError, match="git commit failed"):
        _commit(repo, index_deletions=(Path("a.md"),))
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _real_index_state(repo) == before
    assert (repo / "a.md").exists()
    assert _no_temp_index(repo)


def test_an_untracked_index_deletion_is_a_no_op(del_repo: Path) -> None:
    repo = del_repo
    (repo / "x.md").write_text("x\n")
    _commit(repo, repo / "x.md", index_deletions=(Path("never-tracked.md"),))
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["x.md"]


def test_only_an_untracked_index_deletion_is_an_empty_changeset(del_repo: Path) -> None:
    from specify_cli.git.commit_helpers import SafeCommitStagedTreeUnchanged

    head = _git(del_repo, "rev-parse", "HEAD")
    with pytest.raises(SafeCommitStagedTreeUnchanged):
        _commit(del_repo, index_deletions=(Path("never-tracked.md"),))
    assert _git(del_repo, "rev-parse", "HEAD") == head
    assert _no_temp_index(del_repo)


def test_a_path_requested_and_listed_as_an_index_deletion_is_refused(del_repo: Path) -> None:
    repo = del_repo
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(SafeCommitError) as ei:
        _commit(repo, repo / "a.md", index_deletions=(Path("a.md"),))
    assert "a.md" in str(ei.value)
    assert _git(repo, "rev-parse", "HEAD") == head


def test_index_deletions_cannot_be_combined_with_an_expected_parent(del_repo: Path) -> None:
    head = _git(del_repo, "rev-parse", "HEAD").strip()
    with pytest.raises(ValueError, match="index_deletions"):
        _commit(del_repo, Path("c.md"), index_deletions=(Path("a.md"),), expected_parent_sha=head)


def test_an_inherited_git_index_file_is_the_operators_index_and_never_leaks(del_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = del_repo
    alt = repo.parent / "alt.idx"
    env = {**os.environ, "GIT_INDEX_FILE": str(alt)}
    subprocess.run(["git", "read-tree", "HEAD"], cwd=repo, env=env, check=True)
    (repo / "b.md").write_text("b\n")
    subprocess.run(["git", "add", "b.md"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "rm", "--cached", "-q", "a.md"], cwd=repo, env=env, check=True)
    default_index = (repo / ".git" / "index").read_bytes()
    monkeypatch.setenv("GIT_INDEX_FILE", str(alt))
    _commit(repo, index_deletions=(Path("a.md"),))
    assert os.environ["GIT_INDEX_FILE"] == str(alt)
    assert _git(repo, "show", "HEAD", "--name-status", "--format=") == "D\ta.md\n"
    staged_in_alt = subprocess.run(["git", "diff", "--cached", "--name-status"], cwd=repo, env=env, capture_output=True, text=True, check=True).stdout
    assert staged_in_alt == "A\tb.md\n"
    assert (repo / ".git" / "index").read_bytes() == default_index
    assert _no_temp_index(repo)


def test_an_inherited_git_index_file_inside_the_work_tree_never_hosts_the_temp_index(del_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = del_repo
    alt = repo / "alt.idx"
    env = {**os.environ, "GIT_INDEX_FILE": str(alt)}
    subprocess.run(["git", "read-tree", "HEAD"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "rm", "--cached", "-q", "a.md"], cwd=repo, env=env, check=True)
    seen = repo.parent / "hook-index"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\nprintf %s \"$GIT_INDEX_FILE\" > '{seen}'\n")
    hook.chmod(0o755)
    monkeypatch.setenv("GIT_INDEX_FILE", str(alt))
    _commit(repo, index_deletions=(Path("a.md"),))
    temp_index = Path(seen.read_text())
    assert (repo / ".git").resolve() in temp_index.resolve().parents
    assert _git(repo, "show", "HEAD", "--name-status", "--format=") == "D\ta.md\n"
    assert not list(repo.rglob("spec-kitty-index-deletions*"))
