"""#6668: ``is_kitty_specs_residue`` decides residue git-aware, with a file-presence fallback.

Git-aware mode applies when git tracks at least one path under ``kitty-specs/``:
a folder is residue when ``is_mission_dir`` rejects it and neither ``spec.md`` nor
``meta.json`` exists on disk, whatever else it holds. Every other setting
(non-git, unusable git, an ignored ``kitty-specs/``, an untracked project nested
in a parent repository) keeps the file-presence rule.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context.mission_resolver import (
    RESIDUE_NOTICE,
    is_kitty_specs_residue,
    residue_notice,
    residue_notice_path,
    tracked_mission_paths,
)

pytestmark = [pytest.mark.git_repo]

_TASKS_ONLY = "050-tasks-only"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    return root


def _commit(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "snapshot")


def _committed_mission(repo: Path, slug: str = "001-real") -> Path:
    mission = repo / "kitty-specs" / slug
    mission.mkdir(parents=True)
    (mission / "spec.md").write_text("# Real\n", encoding="utf-8")
    _commit(repo)
    return mission


def _tasks_only(repo: Path, slug: str = _TASKS_ONLY) -> Path:
    folder = repo / "kitty-specs" / slug
    (folder / "tasks").mkdir(parents=True)
    (folder / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    return folder


@pytest.fixture()
def tracked_repo(tmp_path: Path) -> Path:
    repo = _init(tmp_path / "repo")
    _committed_mission(repo)
    return repo


def _folder(repo: Path, slug: str, files: dict[str, str]) -> Path:
    folder = repo / "kitty-specs" / slug
    for rel, text in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return folder


@pytest.mark.parametrize(
    "files",
    [
        {"tasks/WP01.md": "x"},
        {"status.events.jsonl": "{}\n"},
        {"status.json": "{}"},
        {"tasks/doing/WP01.md": "x"},
        {"decisions/index.json": "{}"},
    ],
    ids=["tasks-wp", "events", "status-json", "tasks-doing", "decisions"],
)
def test_git_aware_untracked_only_content_is_residue(tracked_repo: Path, files: dict[str, str]) -> None:
    assert is_kitty_specs_residue(_folder(tracked_repo, "060-leftover", files))


def test_git_aware_uncommitted_spec_is_a_mission(tracked_repo: Path) -> None:
    assert not is_kitty_specs_residue(_folder(tracked_repo, "061-new", {"spec.md": "# New\n"}))


def test_git_aware_untracked_identityless_meta_is_a_mission(tracked_repo: Path) -> None:
    assert not is_kitty_specs_residue(_folder(tracked_repo, "062-meta", {"meta.json": json.dumps({"mission_slug": "x"})}))


def test_git_aware_tracked_spec_deleted_on_disk_is_still_a_mission(tracked_repo: Path) -> None:
    mission = tracked_repo / "kitty-specs" / "001-real"
    (mission / "spec.md").unlink()
    assert not is_kitty_specs_residue(mission)


def test_folder_outside_kitty_specs_is_never_residue(tracked_repo: Path) -> None:
    outside = tracked_repo / "elsewhere" / "x"
    outside.mkdir(parents=True)
    assert not is_kitty_specs_residue(outside)


def test_git_aware_committed_tasks_only_folder_is_residue_accepted_cost(tracked_repo: Path) -> None:
    folder = _tasks_only(tracked_repo)
    _commit(tracked_repo)
    # Operator ruling (#6668): a committed, pre-identity, tasks-only folder becomes residue in git-aware mode.
    assert is_kitty_specs_residue(folder)


def _no_git_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "no-git-here"))


def test_fallback_non_git_project(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    folder = _tasks_only(project)
    assert not is_kitty_specs_residue(folder)


def test_fallback_when_git_cannot_run(tracked_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _tasks_only(tracked_repo)
    _no_git_path(monkeypatch, tmp_path)
    assert not is_kitty_specs_residue(folder)


def test_fallback_when_kitty_specs_is_gitignored(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    (repo / ".gitignore").write_text("kitty-specs/\n", encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _commit(repo)
    assert not is_kitty_specs_residue(_tasks_only(repo))


def test_fallback_for_an_untracked_project_nested_in_a_parent_repo(tmp_path: Path) -> None:
    parent = _init(tmp_path / "parent")
    (parent / "README.md").write_text("x\n", encoding="utf-8")
    _commit(parent)
    nested = parent / "sub" / "project"
    folder = _tasks_only(nested)
    assert not is_kitty_specs_residue(folder)


class _GitSpy:
    """Counts real ``git`` processes at the process boundary (``subprocess.Popen``).

    Patching one module's ``run_git`` misses calls made through ``kernel.git``
    helpers (``tracked_paths``, ``is_tracked``), so the count is taken where
    every runner ends up.
    """

    def __init__(self) -> None:
        self.calls = 0


@pytest.fixture()
def spy(tracked_repo: Path, monkeypatch: pytest.MonkeyPatch) -> _GitSpy:
    counting = _GitSpy()
    real_init = subprocess.Popen.__init__

    def counted_init(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name == "git":
            counting.calls += 1
        real_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", counted_init)
    return counting


def test_identity_bearing_folder_costs_no_git_call(tracked_repo: Path, spy: _GitSpy) -> None:
    folder = _folder(tracked_repo, "070-identified", {"meta.json": json.dumps({"mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"})})
    assert not is_kitty_specs_residue(folder)
    assert spy.calls == 0


def test_walk_with_precomputed_tracked_set_stays_within_the_git_budget(tracked_repo: Path, spy: _GitSpy) -> None:
    """NFR-003: the set plus 50 identity-less folders with ``tracked=`` cost exactly 2 git processes.

    Measured at the process boundary: ``rev-parse`` + ``ls-files`` = 2; each folder then costs 0.
    """
    folders = [_folder(tracked_repo, f"{i:03d}-bulk", {"decisions/index.json": "{}"}) for i in range(100, 150)]
    tracked = tracked_mission_paths(tracked_repo)
    assert all(is_kitty_specs_residue(f, repo_root=tracked_repo, tracked=tracked) for f in folders)
    assert spy.calls == 2


def test_explicit_none_is_not_probed_again(tracked_repo: Path, spy: _GitSpy) -> None:
    folders = [_folder(tracked_repo, f"{i:03d}-none", {"decisions/index.json": "{}"}) for i in range(200, 205)]
    # A walker that already probed and got ``None`` (no usable git) must not trigger a probe per folder.
    assert all(is_kitty_specs_residue(f, repo_root=tracked_repo, tracked=None) for f in folders)
    assert spy.calls == 0


def test_omitted_tracked_is_probed_when_needed(tracked_repo: Path, spy: _GitSpy) -> None:
    assert is_kitty_specs_residue(_folder(tracked_repo, "080-probe", {"decisions/index.json": "{}"}))
    assert spy.calls == 2  # rev-parse + ls-files, once


@pytest.mark.parametrize("prefix", ["", "001-slug: ", "Worktree wt1: "])
def test_notice_path_round_trip(prefix: str) -> None:
    rel = ".worktrees/wt1/kitty-specs/x"
    assert residue_notice_path(prefix + residue_notice(rel)) == rel


def test_notice_path_ignores_other_lines() -> None:
    assert residue_notice_path("Lifecycle preview unavailable: boom") is None


def test_notice_names_the_git_aware_reason_and_the_remedy() -> None:
    text = residue_notice("kitty-specs/x")
    assert "kitty-specs/x" in text
    assert "no mission_id" in text and "on disk or in git" in text
    assert "add a meta.json with a mission_id" in text and "`spec-kitty agent mission create`" in text
    assert "remove the folder" in text
    assert "Add a spec.md" not in text  # #5875: a spec.md alone no longer makes a Mission
    assert RESIDUE_NOTICE.count("{path}") == 1


@pytest.mark.parametrize(
    "rel",
    ["kitty-specs/x", ".worktrees/wt1/kitty-specs/a folder (copy)", "kitty-specs/odd: name; with `ticks`"],
)
def test_reworded_notice_round_trips_every_rendered_line(rel: str) -> None:
    """#5875 / D7: the regex derived from the reworded template still parses every rendered notice."""
    for prefix in ("", "001-slug: ", "Worktree wt1: ", "[yellow]skipped[/yellow] "):
        assert residue_notice_path(prefix + residue_notice(rel)) == rel


def test_corrupt_git_index_degrades_to_file_presence_instead_of_crashing(tracked_repo: Path) -> None:
    folder = _tasks_only(tracked_repo)
    (tracked_repo / ".git" / "index").write_bytes(b"not an index")
    # rev-parse still succeeds but ls-files fails: unusable git, so content-bearing folders stay repairable.
    assert not is_kitty_specs_residue(folder)
    empty = tracked_repo / "kitty-specs" / "090-empty"
    empty.mkdir()
    assert is_kitty_specs_residue(empty)
