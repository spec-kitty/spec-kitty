"""Real-git coverage: policy, post-merge, preflight and creation sites read git paths losslessly.

Mission git-paths-are-data (#5392/#5400). Every test builds a temporary
repository and never mocks git. Paths with a space or a non-ASCII name are the
ones ``git`` prints quoted in its display formats, so a site that still reads
display text misses them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.bulk_edit.gate import _git_diff_files
from specify_cli.charter_runtime.preflight.runner import _detect_dirty_artifacts
from specify_cli.core.mission_creation import (
    MissionCreationError,
    _mint_protected_single_branch_mission_branch,
    _path_is_tracked_by_git,
)
from specify_cli.missions._substantive import _head_carries_path
from specify_cli.policy import commit_guard_hook
from specify_cli.post_merge.retrospective_terminus import _paths_with_uncommitted_changes
from specify_cli.post_merge.stale_assertions import _extract_changed_symbols, run_check

pytestmark = [pytest.mark.git_repo]

_LANE_BRANCH = "kitty/mission-057-feat-lane-a"
_QUOTED_SPEC = "kitty-specs/café notes.md"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8")
    return done.stdout


def _init(repo: Path, branch: str = "main") -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _write(repo: Path, rel: str, text: str = "x\n") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _commit(repo: Path, message: str = "c") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").strip()


# ---------------------------------------------------------------------------
# commit_guard_hook: a quoted protected staged path is seen
# ---------------------------------------------------------------------------


def _run_hook(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.chdir(repo)
    return commit_guard_hook.main()


def test_hook_blocks_quoted_protected_staged_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Was fail-open: ``diff --name-only`` printed ``"kitty-specs/caf\\303\\251 notes.md"`` (quoted), which never started with ``kitty-specs/``."""
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _write(repo, ".kittify/config.yaml", "policy:\n  commit_guard:\n    mode: block\n")
    _commit(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    _write(repo, _QUOTED_SPEC)
    _git(repo, "add", _QUOTED_SPEC)

    code = _run_hook(repo, monkeypatch)

    assert code == 1
    assert f"Protected path: {_QUOTED_SPEC}" in capsys.readouterr().err


def test_hook_lists_only_the_new_path_of_a_staged_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Default rename detection is kept: the old (deleted) path of a rename is not reported."""
    repo = _init(tmp_path / "repo")
    _write(repo, ".kittify/config.yaml", "policy:\n  commit_guard:\n    mode: block\n")
    _write(repo, "docs/old name.md", "same content\n" * 20)
    _commit(repo)
    _git(repo, "checkout", "-q", "-b", _LANE_BRANCH)
    (repo / "kitty-specs").mkdir()
    _git(repo, "mv", "docs/old name.md", "kitty-specs/new name.md")

    code = _run_hook(repo, monkeypatch)

    err = capsys.readouterr().err
    assert code == 1
    assert "Protected path: kitty-specs/new name.md" in err
    assert "old name.md" not in err.replace("kitty-specs/new name.md", "")


def test_hook_fails_closed_when_staged_listing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-013 guard: an unreadable index blocks instead of reading as "nothing staged"."""
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _commit(repo)
    (repo / ".git" / "index").write_bytes(b"not an index")

    code = _run_hook(repo, monkeypatch)

    assert code == 1
    assert "could not list staged files" in capsys.readouterr().err


def test_hook_with_guard_disabled_passes_even_when_staged_listing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A disabled guard returns before the fail-closed probe: an unreadable index is not its concern."""
    repo = _init(tmp_path / "repo")
    _write(repo, ".kittify/config.yaml", "policy:\n  commit_guard:\n    enabled: false\n")
    _commit(repo)
    (repo / ".git" / "index").write_bytes(b"not an index")

    assert _run_hook(repo, monkeypatch) == 0


# ---------------------------------------------------------------------------
# bulk_edit gate: quoted files are classified
# ---------------------------------------------------------------------------


def test_bulk_edit_diff_files_include_quoted_and_renamed_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "a.txt", "keep\n" * 30)
    _commit(repo)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _write(repo, "src/café module.py")
    _git(repo, "mv", "a.txt", "b b.txt")
    head = _commit(repo)

    result = _git_diff_files(repo, base, head)

    assert result.ok
    assert sorted(result.files) == ["b b.txt", "src/café module.py"]


def test_bulk_edit_diff_files_report_git_failure(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "a.txt")
    head = _commit(repo)
    # Both refs verify, then the diff itself fails: an unreadable index is not involved, so use a bad object.
    result = _git_diff_files(repo, head, "no-such-ref")

    assert not result.ok
    assert result.returncode is not None


# ---------------------------------------------------------------------------
# stale_assertions: quoted source files and test files
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore:stale-assertion analyzer")
def test_stale_assertions_sees_quoted_source_and_test_files(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "src/café mod.py", "def gone_function():\n    return 1\n")
    _write(repo, "tests/test café.py", "from x import gone_function\n\n\ndef test_it():\n    assert gone_function() == 1\n")
    base = _commit(repo, "base")
    _write(repo, "src/café mod.py", "def other_function():\n    return 1\n")
    head = _commit(repo, "head")

    symbols = _extract_changed_symbols(base, head, repo)
    report = run_check(base, head, repo)

    assert {s.source_file.name for s in symbols} == {"café mod.py"}
    assert report.files_scanned == 1
    assert [(f.test_file.name, f.changed_symbol) for f in report.findings] == [("test café.py", "gone_function")]


def test_stale_assertions_excludes_tests_dir_from_source_scan(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "tests/test_a.py", "def gone():\n    return 1\n")
    base = _commit(repo, "base")
    _write(repo, "tests/test_a.py", "def other():\n    return 1\n")
    head = _commit(repo, "head")

    assert _extract_changed_symbols(base, head, repo) == []


# ---------------------------------------------------------------------------
# retrospective_terminus: dirtiness of a quoted path; advisory on failure
# ---------------------------------------------------------------------------


def test_retrospective_dirty_probe_handles_quoted_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    clean = _write(repo, "kitty-specs/m/café retro.md")
    _commit(repo)
    dirty = _write(repo, "kitty-specs/m/status events.jsonl")

    assert _paths_with_uncommitted_changes(repo, [clean, dirty]) == (dirty,)
    clean.write_text("changed\n", encoding="utf-8")
    assert _paths_with_uncommitted_changes(repo, [clean]) == (clean,)


def test_retrospective_dirty_probe_is_fail_open_outside_a_repo(tmp_path: Path) -> None:
    target = _write(tmp_path / "plain", "f.md")

    assert _paths_with_uncommitted_changes(tmp_path / "plain", [target]) == ()


# ---------------------------------------------------------------------------
# charter preflight: exact dirty paths, advisory error reasons
# ---------------------------------------------------------------------------


def test_preflight_reports_quoted_dirty_path_exactly(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, ".kittify/charter/charter.md")
    _commit(repo)
    _write(repo, ".kittify/charter/café notes.md")

    is_dirty, paths, reason = _detect_dirty_artifacts(repo)

    assert (is_dirty, paths, reason) == (True, [".kittify/charter/café notes.md"], None)


def test_preflight_clean_scope_is_not_dirty(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, ".kittify/charter/charter.md")
    _commit(repo)
    _write(repo, "elsewhere/file.txt")

    assert _detect_dirty_artifacts(repo) == (False, [], None)


def test_preflight_git_failure_is_an_error_reason_not_an_exception(tmp_path: Path) -> None:
    is_dirty, paths, reason = _detect_dirty_artifacts(tmp_path / "not-a-repo")

    assert is_dirty is False
    assert paths == []
    assert reason is not None and "git" in reason


# ---------------------------------------------------------------------------
# core/mission_creation: tracked probe and protected-mint dirtiness
# ---------------------------------------------------------------------------


def test_path_is_tracked_by_git_with_quoted_path(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    tracked = _write(repo, "kitty-specs/café m/spec.md")
    _commit(repo)
    untracked = _write(repo, "kitty-specs/new m/spec.md")

    assert _path_is_tracked_by_git(repo, tracked) is True
    assert _path_is_tracked_by_git(repo, untracked) is False
    # A probe git cannot answer refuses deletion (fail closed).
    assert _path_is_tracked_by_git(tmp_path / "missing", tracked) is True


def _mint(repo: Path) -> dict[str, object]:
    meta: dict[str, object] = {}
    _mint_protected_single_branch_mission_branch(
        repo,
        "my-mission",
        mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        target_branch="main",
        meta=meta,
    )
    return meta


def test_protected_mint_refuses_unrelated_quoted_dirty_file(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _commit(repo)
    _write(repo, "my notes café.txt")

    with pytest.raises(MissionCreationError, match="my notes café.txt"):
        _mint(repo)


def test_protected_mint_ignores_own_scaffold_and_similar_prefixes(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "README.md")
    _commit(repo)
    _write(repo, "kitty-specs/my-mission/spec.md")
    _write(repo, ".kittify/cache/x.json")
    meta = _mint(repo)
    assert str(meta["mission_branch"]).startswith("kitty/mission-")

    sibling = _init(tmp_path / "sibling")
    _write(sibling, "kitty-specs/older/spec.md")
    _commit(sibling)
    # ``kitty-specs/my-mission-2`` is a different mission: component-wise, not a string prefix.
    _write(sibling, "kitty-specs/my-mission-2/spec.md")
    with pytest.raises(MissionCreationError, match="kitty-specs/my-mission-2"):
        _mint(sibling)


# ---------------------------------------------------------------------------
# missions/_substantive: tracked AND present at HEAD
# ---------------------------------------------------------------------------


def test_head_carries_quoted_path(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "kitty-specs/café/spec.md")
    _commit(repo)
    _write(repo, "kitty-specs/café/new.md")
    _git(repo, "add", "kitty-specs/café/new.md")

    assert _head_carries_path(repo, "kitty-specs/café/spec.md") is True
    # Tracked in the index but absent at HEAD.
    assert _head_carries_path(repo, "kitty-specs/café/new.md") is False
    assert _head_carries_path(repo, "kitty-specs/café/none.md") is False


@pytest.mark.filterwarnings("ignore:stale-assertion analyzer")
def test_stale_assertions_resolves_test_files_when_repo_root_is_a_subdirectory(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo, "pkg/src/mod.py", "def gone_function():\n    return 1\n")
    _write(repo, "pkg/tests/test_it.py", "from x import gone_function\n\n\ndef test_it():\n    assert gone_function() == 1\n")
    base = _commit(repo, "base")
    _write(repo, "pkg/src/mod.py", "def other_function():\n    return 1\n")
    head = _commit(repo, "head")

    report = run_check(base, head, repo / "pkg")

    assert report.files_scanned == 1
    assert [f.test_file.name for f in report.findings] == ["test_it.py"]
