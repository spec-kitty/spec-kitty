"""#7498 / #7540 item 5: the decisions runtime lock is never dirt and never committed.

``decisions/lock.py`` keeps ``kitty-specs/<mission>/decisions/index.json.lock`` on disk on
purpose (release truncates, never unlinks: kernel lock guarantee G3), so it must be:

* invisible to ``git status`` in every checkout role -- the repository root checkout, a
  coordination worktree and a lane worktree -- in a project with no ``*.lock`` ignore rule
  (FR-008);
* refused by the shared commit helper, so ``safe-commit`` / ``spec-commit`` / every Mission
  commit can never stage it (FR-009), while an ordinary file still commits (positive control);
* and a reset that would overwrite an obstructing file describes it in words, not a raw
  ``??``/``!!`` status code (FR-011).

The owned ``repair-runtime-lock`` index-only removal (FR-010) is pinned by
``tests/integration/test_owned_decision_runtime_lock.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.decisions.lock import decisions_lock, lock_path
from specify_cli.git.commit_helpers import SafeCommitPathPolicyError, safe_commit

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_BRANCH = "kitty/mission-lockhyg-01ABCDEF"
_MISSION = "lockhyg-01ABCDEF"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _init_repo(tmp_path: Path) -> Path:
    """A consumer-shaped repository: no ``*.lock`` rule anywhere in its ignore files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", f"--initial-branch={_BRANCH}")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n")
    mission = repo / "kitty-specs" / _MISSION
    mission.mkdir(parents=True)
    (mission / "spec.md").write_text("# spec\n")
    (repo / ".gitignore").write_text(".worktrees/\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _take_and_release_lock(mission_dir: Path) -> Path:
    held = lock_path(mission_dir)
    held.parent.mkdir(parents=True, exist_ok=True)
    with decisions_lock(held, timeout_s=5.0, mission_slug=_MISSION, decision_id=None):
        pass
    assert held.exists()  # G3: release truncates, never unlinks
    return held


def _status(checkout: Path) -> str:
    return _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")


# ---------------------------------------------------------------------------
# FR-008: excluded on every topology
# ---------------------------------------------------------------------------


def test_lock_is_not_dirt_in_the_repository_root_checkout(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    _take_and_release_lock(repo / "kitty-specs" / _MISSION)

    assert "index.json.lock" not in _status(repo)
    assert _status(repo) == ""


@pytest.mark.parametrize("role", ["coord", "lane-a"])
def test_lock_is_not_dirt_in_a_linked_worktree(tmp_path: Path, role: str) -> None:
    repo = _init_repo(tmp_path)
    worktree = repo / ".worktrees" / f"{_MISSION}-{role}"
    _git(repo, "worktree", "add", "-q", "-b", f"{_BRANCH}-{role}", str(worktree))

    _take_and_release_lock(worktree / "kitty-specs" / _MISSION)

    assert "index.json.lock" not in _status(worktree)
    assert _status(worktree) == ""


def test_an_ordinary_untracked_file_is_still_dirt(tmp_path: Path) -> None:
    """Positive control on the same fixture: only the runtime lock is excluded."""
    repo = _init_repo(tmp_path)
    _take_and_release_lock(repo / "kitty-specs" / _MISSION)
    decisions = repo / "kitty-specs" / _MISSION / "decisions"
    (decisions / "notes.lock").write_text("authored\n")

    assert f"?? kitty-specs/{_MISSION}/decisions/notes.lock" in _status(repo).splitlines()


# ---------------------------------------------------------------------------
# FR-009: the shared commit helper never stages it
# ---------------------------------------------------------------------------


def test_safe_commit_refuses_to_stage_the_lock(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission = repo / "kitty-specs" / _MISSION
    lock = _take_and_release_lock(mission)
    (mission / "spec.md").write_text("# spec v2\n")
    head = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(SafeCommitPathPolicyError) as refused:
        safe_commit(repo_root=repo, worktree_root=repo, destination_ref=_BRANCH, message="m", paths=(mission / "spec.md", lock))

    assert "runtime lock" in str(refused.value)
    assert refused.value.error_code == "SAFE_COMMIT_PATH_POLICY"
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "diff", "--cached", "--name-only") == ""


def test_safe_commit_without_the_lock_commits(tmp_path: Path) -> None:
    """Positive control: the same request minus the lock lands."""
    repo = _init_repo(tmp_path)
    mission = repo / "kitty-specs" / _MISSION
    _take_and_release_lock(mission)
    (mission / "spec.md").write_text("# spec v2\n")

    result = safe_commit(repo_root=repo, worktree_root=repo, destination_ref=_BRANCH, message="m", paths=(mission / "spec.md",))

    assert result.sha
    assert _git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines() == [".gitignore", ".kittify/config.json", f"kitty-specs/{_MISSION}/spec.md"]


def test_safe_commit_cli_refuses_the_lock_and_commits_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end through ``spec-kitty safe-commit`` (the pre-existing entry point)."""
    repo = _init_repo(tmp_path)
    mission = repo / "kitty-specs" / _MISSION
    lock = _take_and_release_lock(mission)
    (mission / "spec.md").write_text("# spec v2\n")
    head = _git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(
        cli_app,
        ["safe-commit", "--to-branch", _BRANCH, "--message", "m", "--json", str(mission / "spec.md"), str(lock)],
    )

    assert result.exit_code != 0, result.output
    assert "runtime lock" in result.output
    assert _git(repo, "rev-parse", "HEAD") == head
    assert "index.json.lock" not in _git(repo, "ls-tree", "-r", "--name-only", "HEAD")


# ---------------------------------------------------------------------------
# FR-011: obstruction lines also say what the file is, in words
# ---------------------------------------------------------------------------


def test_reset_obstruction_is_described_in_words(tmp_path: Path) -> None:
    from kernel.git import tree_paths
    from specify_cli.git.ref_advance import _dirty_entries

    repo = _init_repo(tmp_path)
    (repo / "incoming.txt").write_text("tracked on the other side\n")
    _git(repo, "add", "incoming.txt")
    _git(repo, "commit", "-q", "-m", "add incoming")
    target = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "rm", "-q", "--cached", "incoming.txt")
    _git(repo, "commit", "-q", "-m", "untrack incoming")
    # ``incoming.txt`` is now untracked here and tracked at ``target``: a reset overwrites it.

    lines = _dirty_entries(repo, None, new_sha=target, target_paths=tree_paths(repo, target))

    assert len(lines) == 1, lines
    assert lines[0].startswith("?? incoming.txt (would be overwritten"), lines  # the XY prefix stays
    assert lines[0].endswith("; untracked)"), lines


def test_lock_refusal_payload_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI refusal stays machine-readable (``--json``)."""
    repo = _init_repo(tmp_path)
    mission = repo / "kitty-specs" / _MISSION
    lock = _take_and_release_lock(mission)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(cli_app, ["safe-commit", "--to-branch", _BRANCH, "--message", "m", "--json", str(lock)])

    payload = json.loads(result.output[result.output.index("{") :])
    assert payload.get("success") is False, payload
    assert "runtime lock" in str(payload.get("error")), payload


def test_exclusion_is_written_when_info_exclude_is_missing(tmp_path: Path) -> None:
    """A clone made from an empty template has no ``info/exclude``: the lock is still excluded (review fold)."""
    repo = _init_repo(tmp_path)
    (repo / ".git" / "info" / "exclude").unlink()

    _take_and_release_lock(repo / "kitty-specs" / _MISSION)

    assert _status(repo) == ""


def test_exclusion_never_glues_onto_an_unterminated_last_rule(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("operator-rule.txt")  # no trailing newline

    _take_and_release_lock(repo / "kitty-specs" / _MISSION)

    lines = exclude.read_text().splitlines()
    assert lines[0] == "operator-rule.txt"
    assert "**/kitty-specs/*/decisions/index.json.lock" in lines
