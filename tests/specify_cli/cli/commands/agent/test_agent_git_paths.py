"""Real-git tests for the agent command path-listing sites (mission git-paths-are-data, WP05).

Every test runs against a temporary repository (no git mocks) holding paths git
would quote in display text: a space (``a b/``) and a non-ASCII name (``é/``).
Display text drops or mangles those; the typed ``kernel.git`` entries carry
them intact, so each migrated guard must see the real path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from kernel.git import GitCommandError, status_entries
from specify_cli.cli.commands.agent import (
    mission_repair,
    mission_setup_plan,
    tasks_mark_status,
    tasks_move_task,
    workflow,
    workflow_executor,
)
from specify_cli.cli.commands.agent.mission_finalize import (
    _read_refresh_worktree_status,
    _resolve_finalize_commit_candidates,
)
from specify_cli.cli.commands.agent.mission_record_analysis import _git_dirty_paths
from specify_cli.cli.commands.agent.tasks_move_task import _lane_deliverable_paths, _mt_enrol_gate_byproducts, _mt_pre_review_dirty_paths
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _check_uncommitted_worktree_changes,
    _validate_research_artifacts,
)
from specify_cli.cli.commands.agent.tasks_shared import _filter_runtime_state_paths
from specify_cli.review.dirty_classifier import classify_dirty_paths, owning_wp_for_path, status_entry_paths

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_SPACED = "a b/y.md"
_ACCENTED = "é/x.md"
_ARROW = "a -> b.txt"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "core.quotePath", "true")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _untracked_all(root: Path) -> tuple[str, ...]:
    return tuple(str(entry.path) for entry in status_entries(root, untracked="all"))


# ---------------------------------------------------------------------------
# tasks_move_task._lane_deliverable_paths / tasks_shared._filter_runtime_state_paths
# ---------------------------------------------------------------------------


def test_lane_deliverable_paths_keep_spaced_and_non_ascii_paths(repo: Path) -> None:
    _write(repo, _SPACED)
    _write(repo, _ACCENTED)
    _write(repo, _ARROW)
    entries = status_entries(repo, untracked="all")

    paths = _lane_deliverable_paths(repo, entries)

    assert {p.relative_to(repo).as_posix() for p in paths} == {_SPACED, _ACCENTED, _ARROW}
    assert all(p.exists() for p in paths)


def test_lane_deliverable_paths_stage_both_sides_of_a_rename(repo: Path) -> None:
    _write(repo, "src/a b.py")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")
    _git(repo, "mv", "src/a b.py", "src/c.py")

    paths = _lane_deliverable_paths(repo, status_entries(repo, untracked=None))

    assert sorted(p.relative_to(repo).as_posix() for p in paths) == ["src/a b.py", "src/c.py"]


def test_lane_deliverable_paths_skip_the_deny_listed_side_of_a_rename(repo: Path) -> None:
    _write(repo, ".kittify/keep.md")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-q", "-m", "state")
    _git(repo, "mv", ".kittify/keep.md", "é keep.md")

    paths = _lane_deliverable_paths(repo, status_entries(repo, untracked=None))

    assert [p.relative_to(repo).as_posix() for p in paths] == ["é keep.md"]


def test_filter_runtime_state_paths_drops_only_deny_listed_entries(repo: Path) -> None:
    _write(repo, ".spec-kitty/review lock.json")
    _write(repo, ".kittify/é/state.json")
    _write(repo, _SPACED)

    kept = _filter_runtime_state_paths(status_entries(repo, untracked="all"))

    assert [str(entry.path) for entry in kept] == [_SPACED]


def test_filter_runtime_state_paths_keeps_rename_leaving_deny_list(repo: Path) -> None:
    _write(repo, ".kittify/keep.md")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-q", "-m", "state")
    _git(repo, "mv", ".kittify/keep.md", "src keep.md")

    kept = _filter_runtime_state_paths(status_entries(repo, untracked=None))

    assert [str(entry.path) for entry in kept] == ["src keep.md"]


# ---------------------------------------------------------------------------
# tasks_parsing_validation guards
# ---------------------------------------------------------------------------


def test_uncommitted_worktree_guard_names_quoted_path(repo: Path) -> None:
    _write(repo, _SPACED)

    guidance = _check_uncommitted_worktree_changes(
        worktree_path=repo,
        wp_id="WP01",
        target_lane="for_review",
        filter_runtime_state_paths=_filter_runtime_state_paths,
    )

    assert guidance is not None
    assert "  ?? a b/" in guidance  # a new directory is one collapsed entry, named intact


def test_uncommitted_worktree_guard_passes_on_clean_and_runtime_state_only(repo: Path) -> None:
    _write(repo, ".spec-kitty/review-lock.json")
    assert (
        _check_uncommitted_worktree_changes(
            worktree_path=repo,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=_filter_runtime_state_paths,
        )
        is None
    )


def test_uncommitted_worktree_guard_fails_closed_when_git_fails(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(GitCommandError):
        _check_uncommitted_worktree_changes(
            worktree_path=not_a_repo,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=_filter_runtime_state_paths,
        )


class _Console:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *values: object) -> None:
        self.lines.extend(str(v) for v in values)


def _research_guard(repo: Path, mission: str = "001-demo") -> tuple[list[str] | None, _Console]:
    console = _Console()
    result = _validate_research_artifacts(
        main_repo_root=repo,
        feature_dir=repo / "kitty-specs" / mission,
        mission_slug=mission,
        wp_id="WP01",
        mission_type="software-dev",
        target_lane="for_review",
        console=console,
    )
    return result, console


def test_research_artifact_guard_blocks_on_quoted_own_wp_path(repo: Path) -> None:
    # A file with a space under the WP's own task directory is that WP's residue
    # (blocking). Display text would hand the classifier a quoted, unmatched string.
    _write(repo, "kitty-specs/001-demo/tasks/WP01-own/my notes.md")
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/é notes.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "tracked")
    _write(repo, "kitty-specs/001-demo/tasks/WP01-own/my notes.md", "edited\n")
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/é notes.md", "edited\n")

    guidance, _console = _research_guard(repo)

    assert guidance is not None
    text = "\n".join(guidance)
    assert "Blocking: 1 uncommitted file(s)" in text
    assert "my notes.md" in text
    assert "WP02-other" not in text


def test_research_artifact_guard_judges_both_sides_of_a_rename(repo: Path) -> None:
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/old name.py")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "other wp")
    (repo / "kitty-specs/001-demo/tasks/WP01-own").mkdir(parents=True)
    _git(repo, "mv", "kitty-specs/001-demo/tasks/WP02-other/old name.py", "kitty-specs/001-demo/tasks/WP01-own/é new.py")

    guidance, _console = _research_guard(repo)

    assert guidance is not None
    assert "Blocking: 1 uncommitted file(s)" in "\n".join(guidance)


def test_research_artifact_guard_passes_for_other_wps_residue(repo: Path) -> None:
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/é notes.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "tracked")
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/é notes.md", "edited\n")

    guidance, console = _research_guard(repo)

    assert guidance is None
    assert any("unrelated dirty file(s) ignored" in line for line in console.lines)


def test_research_artifact_guard_fails_closed_when_git_fails(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitCommandError):
        _research_guard(plain)


# ---------------------------------------------------------------------------
# dirty_classifier: a file literally named "a -> b" is one path
# ---------------------------------------------------------------------------


def test_status_entry_paths_keep_arrow_named_file_whole_and_rename_sides_apart(repo: Path) -> None:
    _write(repo, "kitty-specs/001-demo/tasks/WP02-other/a -> b.md")
    _write(repo, "old name.py")
    _git(repo, "add", "old name.py")
    _git(repo, "commit", "-q", "-m", "add")
    _git(repo, "mv", "old name.py", "new name.py")

    by_path = {str(entry.path): status_entry_paths(entry) for entry in status_entries(repo, untracked="all")}

    assert by_path["kitty-specs/001-demo/tasks/WP02-other/a -> b.md"] == ("kitty-specs/001-demo/tasks/WP02-other/a -> b.md",)
    assert by_path["new name.py"] == ("old name.py", "new name.py")


def test_file_named_with_arrow_is_attributed_to_its_wp() -> None:
    path = "kitty-specs/001-demo/tasks/WP02-other/a -> b.md"
    assert owning_wp_for_path(path, "001-demo") == "WP02"
    blocking, benign = classify_dirty_paths([path], wp_id="WP01", mission_slug="001-demo")
    assert (blocking, benign) == ([], [path])
    own = "kitty-specs/001-demo/tasks/WP01-own/a -> b.md"
    assert classify_dirty_paths([own], wp_id="WP01", mission_slug="001-demo") == ([own], [])


def test_arrow_named_file_is_one_blocking_path_through_the_guard(repo: Path) -> None:
    _write(repo, "kitty-specs/001-demo/tasks/WP01-own/a -> b.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "own")
    _write(repo, "kitty-specs/001-demo/tasks/WP01-own/a -> b.md", "changed\n")

    guidance, _console = _research_guard(repo)

    assert guidance is not None
    assert "Blocking: 1 uncommitted file(s)" in "\n".join(guidance)


# ---------------------------------------------------------------------------
# mission_* / workflow boolean dirtiness and listings
# ---------------------------------------------------------------------------


def test_git_dirty_paths_return_real_paths_and_both_rename_sides(repo: Path) -> None:
    _write(repo, "old é.py")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")
    _git(repo, "mv", "old é.py", "new name.py")
    _write(repo, _SPACED)

    paths = _git_dirty_paths(repo)

    assert "old é.py" in paths
    assert "new name.py" in paths
    assert "a b/" in paths  # a collapsed untracked directory keeps its marker


def test_git_dirty_paths_raises_runtime_error_when_git_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    from specify_cli.cli.commands.agent import mission_record_analysis

    monkeypatch.setattr(mission_record_analysis, "is_git_repo", lambda _root: True)
    with pytest.raises(RuntimeError):
        _git_dirty_paths(plain)


def test_setup_plan_artifact_change_detection_with_quoted_path(repo: Path) -> None:
    _write(repo, _ACCENTED)
    assert mission_setup_plan._artifact_has_no_git_changes(repo, repo / _ACCENTED) is False
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")
    assert mission_setup_plan._artifact_has_no_git_changes(repo, repo / _ACCENTED) is True


def test_setup_plan_artifact_probe_reports_changes_when_git_fails(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert mission_setup_plan._artifact_has_no_git_changes(plain, plain / "x.md") is False


def test_repair_worktree_dirtiness_with_quoted_path_and_failure(repo: Path, tmp_path: Path) -> None:
    assert mission_repair._is_worktree_dirty(repo) is False
    _write(repo, _SPACED)
    assert mission_repair._is_worktree_dirty(repo) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert mission_repair._is_worktree_dirty(plain) is True  # unreadable -> unsafe


def test_baseline_artifact_needs_commit_with_quoted_path(repo: Path) -> None:
    _write(repo, _ACCENTED)
    assert workflow_executor._baseline_artifact_needs_commit(repo, repo / _ACCENTED) is True
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")
    assert workflow_executor._baseline_artifact_needs_commit(repo, repo / _ACCENTED) is False


def test_baseline_artifact_needs_commit_degrades_to_true_when_git_fails(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert workflow_executor._baseline_artifact_needs_commit(plain, plain / "x.md") is True


def test_legacy_paths_already_committed_with_quoted_path(repo: Path, tmp_path: Path) -> None:
    target = repo / _SPACED
    _write(repo, _SPACED)
    assert workflow._legacy_paths_already_committed(repo, [target]) is False
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")
    assert workflow._legacy_paths_already_committed(repo, [target]) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert workflow._legacy_paths_already_committed(plain, [plain / "x"]) is False


def test_refresh_worktree_status_returns_typed_entries_or_a_diagnostic(repo: Path, tmp_path: Path) -> None:
    _write(repo, _ACCENTED)
    entries, error = _read_refresh_worktree_status(repo)
    assert error is None
    assert entries is not None
    assert [entry.display() for entry in entries] == ["?? é/x.md"]

    plain = tmp_path / "plain"
    plain.mkdir()
    entries, error = _read_refresh_worktree_status(plain)
    assert entries is None
    assert error is not None and "refresh could not inspect worktree" in error


# ---------------------------------------------------------------------------
# tasks_parsing_validation: a rename is dropped only when EVERY side is a dossier snapshot
# ---------------------------------------------------------------------------

_SNAPSHOT = "kitty-specs/001-demo/.kittify/dossiers/001-demo/snapshot-latest.json"


def test_dossier_snapshot_rename_from_a_real_file_is_not_dropped(repo: Path) -> None:
    _write(repo, "kitty-specs/001-demo/tasks/WP01-own/note.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "wp file")
    (repo / _SNAPSHOT).parent.mkdir(parents=True)
    _git(repo, "mv", "kitty-specs/001-demo/tasks/WP01-own/note.md", _SNAPSHOT)

    guidance, _console = _research_guard(repo)

    assert guidance is not None, "moving a WP file INTO a snapshot path is real drift, not a snapshot write"
    assert "Blocking: 1 uncommitted file(s)" in "\n".join(guidance)


def test_dossier_snapshot_rewrite_is_still_dropped(repo: Path) -> None:
    _write(repo, _SNAPSHOT)
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-q", "-m", "snap")
    _write(repo, _SNAPSHOT, "edited\n")

    guidance, _console = _research_guard(repo)

    assert guidance is None


# ---------------------------------------------------------------------------
# mission_finalize._resolve_finalize_commit_candidates
# ---------------------------------------------------------------------------


def _finalize_candidates(root: Path, mission: str = "001-demo") -> Any:
    planning_dir = root / "kitty-specs" / mission
    (planning_dir / "tasks").mkdir(parents=True, exist_ok=True)
    return _resolve_finalize_commit_candidates(planning_dir, planning_dir / "tasks", root, None)


@pytest.mark.parametrize("mission", ["001-demo", "002-é notes"])
def test_finalize_commit_candidates_see_dirty_then_committed_tasks(repo: Path, mission: str) -> None:
    _write(repo, f"kitty-specs/{mission}/tasks.md")

    dirty = _finalize_candidates(repo, mission)
    assert dirty.has_relevant_changes is True
    assert any(rel.endswith("tasks.md") for rel in dirty.files_to_commit_rel)

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "tasks")

    assert _finalize_candidates(repo, mission).has_relevant_changes is False


def test_finalize_commit_candidates_fail_closed_outside_a_repo(tmp_path: Path) -> None:
    _write(tmp_path, "kitty-specs/001-demo/tasks.md")
    with pytest.raises(GitCommandError):
        _finalize_candidates(tmp_path)


# ---------------------------------------------------------------------------
# tasks_mark_status._ms_report_owned_failure: an unreadable tree is "unknown", not clean
# ---------------------------------------------------------------------------


def test_owned_failure_envelope_reports_dirty_unknown_when_the_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    import typer

    owned: Any = SimpleNamespace(owned_root=tmp_path, mission_dir=tmp_path, write_branch="owned/x")
    st: Any = SimpleNamespace(status_dir=tmp_path, applied_event_ids=[], applied_wps=[], json_output=True)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise GitCommandError(argv=("status",), cwd=tmp_path, returncode=128, stderr="fatal: not a git repository")

    monkeypatch.setattr(tasks_mark_status, "status_entries", _boom)
    monkeypatch.setattr(tasks_mark_status, "_reconstruct_applied_events", lambda *_a, **_k: [])

    with pytest.raises(typer.Exit):
        tasks_mark_status._ms_report_owned_failure(st, owned, RuntimeError("boom"))

    assert json.loads(capsys.readouterr().out)["dirty"] is None


# ---------------------------------------------------------------------------
# tasks_move_task byproduct snapshots: an unknown snapshot enrols nothing (FR-013)
# ---------------------------------------------------------------------------


def _fail_status_once(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    real = tasks_move_task.status_entries
    calls = {"n": 0}

    def _flaky(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise GitCommandError(argv=("status",), cwd=root, returncode=128, stderr="fatal: transient")
        return real(*args, **kwargs)

    monkeypatch.setattr(tasks_move_task, "status_entries", _flaky)


def test_failed_before_probe_is_unknown_not_clean(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_status_once(monkeypatch, repo)
    assert _mt_pre_review_dirty_paths(repo) is None
    assert _mt_pre_review_dirty_paths(repo) == ()


def test_failed_before_probe_never_enrols_preexisting_user_files(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mine = repo / "my notes.txt"
    mine.write_text("precious\n", encoding="utf-8")
    _fail_status_once(monkeypatch, repo)

    dirty_before = _mt_pre_review_dirty_paths(repo)
    assert dirty_before is None
    # The after-probe succeeds and now lists the user's own pre-existing file.
    assert _mt_pre_review_dirty_paths(repo) == ("my notes.txt",)

    assert _mt_enrol_gate_byproducts(repo, dirty_before) == {}
    assert mine.read_text(encoding="utf-8") == "precious\n"


def test_failed_after_probe_enrols_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _mt_pre_review_dirty_paths(repo)
    assert before == ()
    (repo / "created by gate.txt").write_text("x\n", encoding="utf-8")
    _fail_status_once(monkeypatch, repo)

    assert _mt_enrol_gate_byproducts(repo, before) == {}


def test_known_snapshots_still_enrol_only_the_created_byproduct(repo: Path) -> None:
    (repo / "mine.txt").write_text("keep\n", encoding="utf-8")
    before = _mt_pre_review_dirty_paths(repo)
    (repo / "created by gate.txt").write_text("x\n", encoding="utf-8")

    assert _mt_enrol_gate_byproducts(repo, before) == {repo / "created by gate.txt": None}
