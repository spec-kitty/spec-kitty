"""#5443 / FR-010 / SC-006 (WP04): the mission-number bake commits only ``meta.json``.

Defect: ``bake.py`` committed with a bare ``git commit -m`` after ``git add``.
On the operator's primary checkout that swept everything the operator had
staged into the bookkeeping commit, landed on whatever branch (or detached
HEAD) happened to be checked out, and committed the operator's own unstaged
``meta.json`` edit. The temp-worktree commit on the mission branch had no
pathspec either.

These tests drive the real seam ``_bake_mission_number_into_mission_branch``
against real git. The primary checkout is on ``main`` (the merge target).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.git_repo, pytest.mark.non_sandbox]

SLUG = "bake-scope-5443"
COORD = f"kitty/mission-{SLUG}"
REL_META = f"kitty-specs/{SLUG}/meta.json"
REL_SPEC = f"kitty-specs/{SLUG}/spec.md"


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in list(os.environ):
        if (name.startswith("GIT_") or name.startswith("SPEC_KITTY_")) and name != "SPEC_KITTY_NO_UPGRADE_CHECK":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_STATE_HOME", "state"),
    ):
        monkeypatch.setenv(var, str(home / sub))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result.stdout


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line]


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--template=", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")


def _write_meta_file(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": "01HXBAKE5443MISSIONIDXXXX",
        "mission_number": None,
        "mission_slug": SLUG,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD,
        "created_at": "2026-10-07T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _coord_repo(tmp_path: Path) -> Path:
    """The #4474 coord shape: meta.json only on ``main``, the mission branch cut before it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    root_sha = _git(repo, "rev-list", "--max-parents=0", "HEAD").strip()
    feature_dir = repo / "kitty-specs" / SLUG
    _write_meta_file(feature_dir)
    (feature_dir / "spec.md").write_text("spec v1\n", encoding="utf-8")
    _git(repo, "add", REL_META, REL_SPEC)
    _git(repo, "commit", "-m", "add mission meta.json and spec")
    _git(repo, "branch", COORD, root_sha)
    return repo


def _state():  # noqa: ANN202 - imported lazily like the sibling modules
    from specify_cli.consolidation.state import ConsolidationState

    return ConsolidationState(
        mission_id="01HXBAKE5443MISSIONIDXXXX",
        mission_slug=SLUG,
        target_branch="main",
        wp_order=["WP01"],
        mission_number_baked=False,
    )


def _bake(repo: Path) -> tuple[int | None, list[str]]:
    from specify_cli.consolidation.mission_number import bake

    printed: list[str] = []
    with patch.object(bake.console, "print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
        result = bake._bake_mission_number_into_mission_branch(
            main_repo=repo,
            mission_slug=SLUG,
            mission_branch=COORD,
            target_branch="main",
            dry_run=False,
            merge_state=_state(),
        )
    return result, printed


def _assert_unbaked_warning(printed: list[str]) -> None:
    joined = "\n".join(printed)
    assert "could NOT be baked" in joined
    assert SLUG in joined


def test_primary_bake_commits_only_meta_and_keeps_operator_staging(tmp_path: Path) -> None:
    repo = _coord_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "staged.py").write_text("staged = 1\n", encoding="utf-8")
    _git(repo, "add", "src/staged.py")
    (repo / "README.md").write_text("test repo\noperator unstaged edit\n", encoding="utf-8")
    (repo / REL_SPEC).write_text("spec v2 unstaged\n", encoding="utf-8")
    (repo / "notes.txt").write_text("untracked\n", encoding="utf-8")
    # Preconditions: nothing passes vacuously.
    assert _lines(_git(repo, "diff", "--cached", "--name-only")) == ["src/staged.py"]
    before_count = int(_git(repo, "rev-list", "--count", "main"))

    result, _ = _bake(repo)

    assert result == 1
    assert int(_git(repo, "rev-list", "--count", "main")) == before_count + 1
    assert _lines(_git(repo, "show", "--name-only", "--format=", "HEAD")) == [REL_META]
    assert _lines(_git(repo, "diff", "--cached", "--name-only")) == ["src/staged.py"]
    assert sorted(_lines(_git(repo, "diff", "--name-only"))) == ["README.md", REL_SPEC]
    assert (repo / "README.md").read_text(encoding="utf-8") == "test repo\noperator unstaged edit\n"
    assert (repo / REL_SPEC).read_text(encoding="utf-8") == "spec v2 unstaged\n"
    assert "?? notes.txt" in _lines(_git(repo, "status", "--porcelain"))
    committed = json.loads(_git(repo, "show", f"HEAD:{REL_META}"))
    assert committed["mission_number"] == 1


def _snapshot(repo: Path) -> dict[str, str]:
    return {
        "main": _git(repo, "rev-parse", "main").strip(),
        "head": _git(repo, "rev-parse", "HEAD").strip(),
        "meta": (repo / REL_META).read_text(encoding="utf-8"),
    }


def test_primary_bake_refuses_when_checkout_is_on_another_branch(tmp_path: Path) -> None:
    repo = _coord_repo(tmp_path)
    _git(repo, "switch", "-c", "operator-topic")
    before = _snapshot(repo)

    result, printed = _bake(repo)

    assert result == 1
    after = _snapshot(repo)
    assert after == before  # neither tip moved, meta.json bytes untouched
    assert _git(repo, "branch", "--show-current").strip() == "operator-topic"
    _assert_unbaked_warning(printed)
    assert "not the merge target" in "\n".join(printed)


def test_primary_bake_refuses_on_detached_head(tmp_path: Path) -> None:
    repo = _coord_repo(tmp_path)
    _git(repo, "checkout", "--detach")
    before = _snapshot(repo)

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before
    assert _git(repo, "branch", "--show-current").strip() == ""
    _assert_unbaked_warning(printed)
    assert "detached HEAD" in "\n".join(printed)


@pytest.mark.parametrize("staged", [False, True], ids=["unstaged_edit", "staged_edit"])
def test_primary_bake_refuses_when_meta_has_operator_edit(tmp_path: Path, staged: bool) -> None:
    repo = _coord_repo(tmp_path)
    meta_path = repo / REL_META
    edited = json.loads(meta_path.read_text(encoding="utf-8"))
    edited["note"] = "mine"
    meta_path.write_text(json.dumps(edited, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if staged:
        _git(repo, "add", REL_META)
    before = _snapshot(repo)
    cached_before = _lines(_git(repo, "diff", "--cached", "--name-only"))
    assert cached_before == ([REL_META] if staged else [])

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before  # no commit, operator bytes preserved
    assert _lines(_git(repo, "diff", "--cached", "--name-only")) == cached_before
    on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk["mission_number"] is None
    assert on_disk["note"] == "mine"
    _assert_unbaked_warning(printed)


@pytest.mark.parametrize(("flag", "tag"), [("--assume-unchanged", "h"), ("--skip-worktree", "S")], ids=["assume_unchanged", "skip_worktree"])
def test_primary_bake_refuses_a_hidden_operator_edit_to_meta(tmp_path: Path, flag: str, tag: str) -> None:
    """An index flag hides a dirty meta.json from ``git status``; the bake must still see the edit (#5443 WP04 fold)."""
    repo = _coord_repo(tmp_path)
    _git(repo, "update-index", flag, "--", REL_META)
    meta_path = repo / REL_META
    edited = json.loads(meta_path.read_text(encoding="utf-8"))
    edited["note"] = "hidden operator edit"
    meta_path.write_text(json.dumps(edited, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Preconditions: the edit is invisible to status, and the flag is set.
    assert _git(repo, "status", "--porcelain", "--", REL_META).strip() == ""
    assert _git(repo, "ls-files", "-v", "--", REL_META).split()[0] == tag
    before = _snapshot(repo)

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before  # no commit, operator bytes preserved
    assert _git(repo, "ls-files", "-v", "--", REL_META).split()[0] == tag, "the operator's index flag is kept"
    on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk["mission_number"] is None
    assert on_disk["note"] == "hidden operator edit"
    _assert_unbaked_warning(printed)
    assert "differs from HEAD" in "\n".join(printed)


def test_primary_bake_accepts_a_clean_crlf_meta_under_autocrlf(tmp_path: Path) -> None:
    """HEAD already holds CRLF and ``core.autocrlf`` applies: ``hash-object`` normalises, ``git status`` is clean (#5443 fold)."""
    repo = _coord_repo(tmp_path)
    meta_path = repo / REL_META
    crlf = meta_path.read_bytes().replace(b"\n", b"\r\n")
    meta_path.write_bytes(crlf)
    _git(repo, "add", REL_META)
    _git(repo, "commit", "-m", "meta.json with CRLF")
    _git(repo, "config", "core.autocrlf", "true")
    meta_path.touch()
    # Preconditions: HEAD's blob really is CRLF, and git considers the file clean.
    assert b"\r\n" in subprocess.run(["git", "cat-file", "blob", f"HEAD:{REL_META}"], cwd=str(repo), capture_output=True, check=True).stdout
    assert _git(repo, "status", "--porcelain", "--", REL_META).strip() == ""
    before_count = int(_git(repo, "rev-list", "--count", "main"))

    result, printed = _bake(repo)

    assert result == 1, printed
    assert int(_git(repo, "rev-list", "--count", "main")) == before_count + 1
    assert _lines(_git(repo, "show", "--name-only", "--format=", "HEAD")) == [REL_META]
    committed = json.loads(_git(repo, "show", f"HEAD:{REL_META}"))
    assert committed["mission_number"] == 1


def _untrack_meta_with_operator_content(repo: Path, *, ignored: bool) -> None:
    """meta.json exists on disk with operator-only content but is NOT tracked in HEAD."""
    if ignored:
        (repo / ".gitignore").write_text("kitty-specs/\n", encoding="utf-8")
        _git(repo, "add", ".gitignore")
    _git(repo, "rm", "--cached", "-q", REL_META)
    _git(repo, "commit", "-m", "stop tracking meta.json")
    meta_path = repo / REL_META
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    data["secret_note"] = "operator-only"
    meta_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.mark.parametrize("ignored", [False, True], ids=["untracked", "gitignored_untracked"])
def test_primary_bake_refuses_when_meta_is_not_tracked_in_head(tmp_path: Path, ignored: bool) -> None:
    repo = _coord_repo(tmp_path)
    _untrack_meta_with_operator_content(repo, ignored=ignored)
    before = _snapshot(repo)
    assert _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", REL_META).strip() == ""

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before  # no commit, operator bytes preserved
    assert _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", REL_META).strip() == ""
    assert _git(repo, "ls-files", "--", REL_META).strip() == ""
    on_disk = json.loads((repo / REL_META).read_text(encoding="utf-8"))
    assert on_disk["mission_number"] is None
    assert on_disk["secret_note"] == "operator-only"
    _assert_unbaked_warning(printed)
    assert "not tracked" in "\n".join(printed)


@pytest.mark.parametrize("probe", ["status_entries", "tree_entry", "run_git"])
def test_primary_bake_reports_unbaked_when_the_git_probe_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str) -> None:
    from specify_cli.consolidation.mission_number import bake

    repo = _coord_repo(tmp_path)
    before = _snapshot(repo)

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("git probe exploded")

    monkeypatch.setattr(bake, probe, _boom)

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before
    _assert_unbaked_warning(printed)
    assert "git probe exploded" in "\n".join(printed)


def test_primary_bake_restores_meta_when_a_hook_rejects_the_commit(tmp_path: Path) -> None:
    repo = _coord_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    before = _snapshot(repo)

    result, printed = _bake(repo)

    assert result == 1
    assert _snapshot(repo) == before
    assert _git(repo, "status", "--porcelain", "--", REL_META).strip() == ""
    _assert_unbaked_warning(printed)


def test_mission_branch_bake_commit_names_only_meta(tmp_path: Path) -> None:
    """Temp-worktree commit: content is a positive control, the argv is the regression."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_file(repo / "kitty-specs" / SLUG)
    _git(repo, "add", REL_META)
    _git(repo, "commit", "-m", "add mission meta.json")
    _git(repo, "branch", COORD)
    tip_before = _git(repo, "rev-parse", COORD).strip()

    recorded: list[list[str]] = []
    real_run = subprocess.run

    def _spy(args, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        if isinstance(args, list):
            recorded.append([str(x) for x in args])
        return real_run(args, *a, **k)

    with patch.object(subprocess, "run", _spy):
        result, _ = _bake(repo)

    assert result == 1
    tip_after = _git(repo, "rev-parse", COORD).strip()
    assert tip_after != tip_before
    assert _lines(_git(repo, "show", "--name-only", "--format=", COORD)) == [REL_META]
    assert json.loads(_git(repo, "show", f"{COORD}:{REL_META}"))["mission_number"] == 1

    commit_argvs = [argv for argv in recorded if "commit" in argv]
    assert len(commit_argvs) == 1
    assert "--only" in commit_argvs[0]
    assert commit_argvs[0][-2:] == ["--", REL_META]
    assert not [argv for argv in recorded if argv[:2] == ["git", "add"] and "--" not in argv]
