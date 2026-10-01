"""Tests for upgrade auto-commit path filtering and commit wiring."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

import specify_cli.cli.commands.upgrade as upgrade_cmd
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.runner import UpgradeResult


# ---------------------------------------------------------------------------
# _git_status_paths – parsing logic (real subprocess mock)
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_git_status_paths_parses_modified_files(tmp_path: Path, monkeypatch) -> None:
    """Porcelain output with modified files is parsed correctly."""
    # Simulate: " M src/foo.py\0 M src/bar.py\0"
    raw = b" M src/foo.py\0 M src/bar.py\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: fake_result,
    )
    paths = autocommit.git_status_paths(tmp_path)
    assert paths == {"src/foo.py", "src/bar.py"}


def test_git_status_paths_parses_added_and_untracked(tmp_path: Path, monkeypatch) -> None:
    """New files (A) and untracked files (??) are both captured."""
    raw = b"A  .kittify/metadata.yaml\0?? docs/new.md\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)
    paths = autocommit.git_status_paths(tmp_path)
    assert paths == {".kittify/metadata.yaml", "docs/new.md"}


def test_git_status_paths_handles_rename(tmp_path: Path, monkeypatch) -> None:
    """Rename entries use the destination (new) path.

    In ``--porcelain -z`` output the field order is *reversed* relative to
    the human format: ``R  <new>\0<old>\0`` (git-status(1), "Porcelain
    Format Version 1"). The previous fixture here encoded the order
    backwards, which let the parser silently keep the *old* name (#2492).
    """
    raw = b"R  new.py\0old.py\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)
    paths = autocommit.git_status_paths(tmp_path)
    assert "new.py" in paths
    assert "old.py" not in paths


def test_git_status_paths_handles_rename_followed_by_other_entry(tmp_path: Path, monkeypatch) -> None:
    """The source field of a rename is consumed, so the entry after it is
    still parsed as its own path (no off-by-one)."""
    raw = b"R  new.py\0old.py\0 M docs/x.md\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)
    assert autocommit.git_status_paths(tmp_path) == {"new.py", "docs/x.md"}


def test_git_status_paths_handles_real_git_rename(tmp_path: Path) -> None:
    """Against real git (not a fixture): a staged rename reports the new name
    and not the old one, so the commit-set never names a path that no longer
    exists (#2492)."""

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "old.py").write_text("print('hi')\n", encoding="utf-8")
    git("add", "old.py")
    git("commit", "-qm", "add old.py")
    git("mv", "old.py", "new.py")

    paths = autocommit.git_status_paths(tmp_path)

    assert paths is not None
    assert "new.py" in paths
    assert "old.py" not in paths


def test_prepare_copy_stages_only_destination_when_source_was_clean(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Copy identity protects ownership without staging the unchanged source."""
    raw = b"C  new.py\0old.py\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)

    files = autocommit.prepare_upgrade_commit_files(tmp_path, baseline_paths=set())

    assert files == [Path("new.py")]


def test_prepare_copy_excludes_destination_when_source_was_dirty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A copy of pre-run operator dirt remains operator-owned at its new path."""
    raw = b"C  new.py\0old.py\0"
    fake_result = MagicMock(returncode=0, stdout=raw)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)

    files = autocommit.prepare_upgrade_commit_files(tmp_path, baseline_paths={"old.py"})

    assert files == []


def test_git_status_paths_returns_none_on_failure(tmp_path: Path, monkeypatch) -> None:
    """Non-zero returncode → None (not empty set)."""
    fake_result = MagicMock(returncode=128, stdout=b"")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)
    result = autocommit.git_status_paths(tmp_path)
    assert result is None


def test_git_status_paths_empty_repo(tmp_path: Path, monkeypatch) -> None:
    """Clean working tree returns empty set (not None)."""
    fake_result = MagicMock(returncode=0, stdout=b"")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: fake_result)
    result = autocommit.git_status_paths(tmp_path)
    assert result == set()


def test_git_status_paths_strips_dot_slash(tmp_path: Path) -> None:
    """Leading ./ is normalised away (the normalizer, not a fabricated git line).

    git never prints ``./src/foo.py`` under ``-z`` and ``kernel.git`` rejects a
    non-normalised path, so the old fabricated-output fixture can no longer be
    fed through ``git_status_paths``; the normalisation rule is pinned directly.
    """
    assert autocommit._normalize_status_path("./src/foo.py") == "src/foo.py"


# ---------------------------------------------------------------------------
# _is_upgrade_commit_eligible – edge cases
# ---------------------------------------------------------------------------


def test_eligible_subdirectory_file(tmp_path: Path) -> None:
    assert autocommit.is_upgrade_commit_eligible("kitty-specs/001/WP01.md", tmp_path) is True


def test_eligible_rejects_empty(tmp_path: Path) -> None:
    assert autocommit.is_upgrade_commit_eligible("", tmp_path) is False


def test_eligible_preserves_whitespace_only_filename(tmp_path: Path) -> None:
    """Spaces are valid Git path bytes and must not alias another filename."""
    assert autocommit.is_upgrade_commit_eligible("   ", tmp_path) is True


# Root-level files written by the upgrade run (clean at baseline, dirty
# after) are committed like any other path: the gitignore-backfill
# migrations (.gitignore, #2385), the merge-driver / diff-attribute
# migrations (.gitattributes), m_3_2_8_provision_kitty_env (.claudeignore)
# and the session-presence surfaces AGENTS.md / GEMINI.md (surface repair,
# #2491) all write at the root. A depth-based "no '/' → skip" rule plus a
# hand-kept allowlist drifted four times and left them dirty (#2492
# follow-up); ownership is the pre-run baseline, not the path depth.
_ROOT_FILES_UPGRADE_WRITES = [".gitignore", ".gitattributes", ".claudeignore", "AGENTS.md", "GEMINI.md"]


@pytest.mark.parametrize("path", _ROOT_FILES_UPGRADE_WRITES)
def test_eligible_accepts_root_files_upgrade_writes(tmp_path: Path, path: str) -> None:
    assert autocommit.is_upgrade_commit_eligible(path, tmp_path) is True


@pytest.mark.parametrize("path", ["README.md", "CLAUDE.md", "pyproject.toml"])
def test_eligible_root_files_are_not_special_cased_by_depth(tmp_path: Path, path: str) -> None:
    """Eligibility does not depend on path depth. Pre-existing operator edits
    to these files are kept out of the commit by the baseline (see
    ``test_prepare_upgrade_commit_files_excludes_preexisting_changes`` and
    the real-git test below), not by a filename or depth rule."""
    assert autocommit.is_upgrade_commit_eligible(path, tmp_path) is True


@pytest.mark.parametrize("path", [".gitignore", ".zshrc", "AGENTS.md", "README.md"])
def test_eligible_rejects_root_files_when_checkout_is_home(path: str) -> None:
    """When the checkout *is* ``$HOME`` (#3652 hazard) root-level files are the
    operator's dotfiles and are never committed, whatever their name."""
    assert autocommit.is_upgrade_commit_eligible(path, Path.home().resolve()) is False


def test_eligible_accepts_nested_paths_when_checkout_is_home(tmp_path: Path) -> None:
    """Only root-level files and ``~/.kittify`` are excluded in ``$HOME``;
    a nested project's own files remain eligible (unchanged behaviour)."""
    home = Path.home().resolve()
    assert autocommit.is_upgrade_commit_eligible("Code/demo/.kittify/metadata.yaml", home) is True


def test_eligible_rejects_parent_traversal(tmp_path: Path) -> None:
    assert autocommit.is_upgrade_commit_eligible("../secret.txt", tmp_path) is False


def test_eligible_accepts_kittify_in_non_home(tmp_path: Path) -> None:
    assert autocommit.is_upgrade_commit_eligible(".kittify/metadata.yaml", tmp_path) is True


def test_eligible_rejects_home_kittify(monkeypatch) -> None:
    home = Path.home().resolve()
    assert autocommit.is_upgrade_commit_eligible(".kittify/metadata.yaml", home) is False


# ---------------------------------------------------------------------------
# _prepare_upgrade_commit_files
# ---------------------------------------------------------------------------


def test_prepare_upgrade_commit_files_includes_root_files_written_by_the_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Root files dirty after the run but clean at baseline were written by
    the run and are part of the commit-set; root files already dirty at
    baseline are excluded — by the baseline, not by their depth."""
    project_path = tmp_path / "project"
    project_path.mkdir()

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".kittify/metadata.yaml",
            "kitty-specs/001-test/tasks/WP01.md",
            "README.md",
            "CLAUDE.md",
            ".gitattributes",
            "AGENTS.md",
            "docs/guides/upgrade.md",
        },
    )

    files = autocommit.prepare_upgrade_commit_files(
        project_path,
        baseline_paths={"README.md", "CLAUDE.md"},
    )

    assert {str(path) for path in files} == {
        ".kittify/metadata.yaml",
        "kitty-specs/001-test/tasks/WP01.md",
        "docs/guides/upgrade.md",
        ".gitattributes",
        "AGENTS.md",
    }


def test_prepare_upgrade_commit_files_excludes_preexisting_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".kittify/metadata.yaml",
            "kitty-specs/001-test/tasks/WP01.md",
        },
    )

    files = autocommit.prepare_upgrade_commit_files(
        project_path,
        baseline_paths={"kitty-specs/001-test/tasks/WP01.md"},
    )

    assert [str(path) for path in files] == [".kittify/metadata.yaml"]


def test_prepare_upgrade_commit_files_skips_home_level_kittify(monkeypatch) -> None:
    project_path = Path.home().resolve()

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".kittify/metadata.yaml",
            ".gitignore",
            ".zshrc",
            "Code/demo/.kittify/metadata.yaml",
            "Code/demo/kitty-specs/001-test/tasks/WP01.md",
        },
    )

    files = autocommit.prepare_upgrade_commit_files(project_path, baseline_paths=set())

    # ~/.kittify and root-level dotfiles never enter a commit when the
    # checkout is $HOME itself (#3652 hazard).
    assert {str(path) for path in files} == {
        "Code/demo/.kittify/metadata.yaml",
        "Code/demo/kitty-specs/001-test/tasks/WP01.md",
    }


def test_prepare_upgrade_commit_files_expands_untracked_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    skill_dir = project_path / ".agents" / "skills" / "new-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    refs_dir = skill_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "guide.md").write_text("guide\n", encoding="utf-8")

    backup_dir = project_path / ".kittify" / ".migration-backup"
    backup_dir.mkdir(parents=True)
    (backup_dir / "manifest.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".agents/skills/new-skill",
            ".kittify/.migration-backup",
        },
    )

    files = autocommit.prepare_upgrade_commit_files(project_path, baseline_paths=set())

    assert [str(path) for path in files] == [
        ".agents/skills/new-skill/SKILL.md",
        ".agents/skills/new-skill/references/guide.md",
        ".kittify/.migration-backup/manifest.json",
    ]


def test_prepare_upgrade_commit_files_skips_empty_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    empty_dir = project_path / ".agents" / "skills" / "empty-skill"
    empty_dir.mkdir(parents=True)

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".agents/skills/empty-skill",
        },
    )

    files = autocommit.prepare_upgrade_commit_files(project_path, baseline_paths=set())

    assert files == []


def test_prepare_skips_when_baseline_is_none(tmp_path: Path) -> None:
    """When baseline git status failed (None), skip auto-commit entirely."""
    files = autocommit.prepare_upgrade_commit_files(tmp_path, baseline_paths=None)
    assert files == []


def test_prepare_skips_when_current_status_fails(tmp_path: Path, monkeypatch) -> None:
    """When post-upgrade git status fails, skip auto-commit."""
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _repo: None)
    files = autocommit.prepare_upgrade_commit_files(tmp_path, baseline_paths=set())
    assert files == []


# ---------------------------------------------------------------------------
# _auto_commit_upgrade_changes
# ---------------------------------------------------------------------------


def test_auto_commit_upgrade_changes_calls_safe_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()

    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _project, baseline_paths: [
            Path(".kittify/metadata.yaml"),
            Path("kitty-specs/001-test/tasks/WP01.md"),
        ],
    )

    captured: dict[str, object] = {}

    def _fake_safe_commit(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(autocommit, "safe_commit", _fake_safe_commit)
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *_args, **_kwargs: "main\n",
    )

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=project_path,
        baseline_paths=set(),
        from_version="0.13.0",
        to_version="0.14.0",
    )

    assert committed is True
    assert warning is None
    assert committed_paths == [
        ".kittify/metadata.yaml",
        "kitty-specs/001-test/tasks/WP01.md",
    ]
    from specify_cli.core.commit_guard import GuardCapability

    assert captured["repo_root"] == project_path
    assert captured["worktree_root"] == project_path
    # T009: the upgrade flow constructs a ref-only CommitTarget (C-007) for the
    # current branch and asserts UPGRADE_BOOKKEEPING (no message-prefix channel).
    assert captured["target"].ref == "main"
    assert captured["capability"] is GuardCapability.UPGRADE_BOOKKEEPING
    assert captured["paths"] == (
        Path(".kittify/metadata.yaml"),
        Path("kitty-specs/001-test/tasks/WP01.md"),
    )
    assert "0.13.0 -> 0.14.0" in str(captured["message"])


def test_auto_commit_returns_warning_on_safe_commit_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """When safe_commit raises the caller gets a warning string."""
    project_path = tmp_path / "project"
    project_path.mkdir()

    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _project, baseline_paths: [Path("kitty-specs/001/WP01.md")],
    )
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=project_path,
        baseline_paths=set(),
        from_version="0.13.0",
        to_version="0.14.0",
    )

    assert committed is False
    assert warning is not None
    assert "review and commit manually" in warning
    assert committed_paths == ["kitty-specs/001/WP01.md"]


def test_auto_commit_noop_when_no_new_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """No files to commit → (False, [], None) with no safe_commit call."""
    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _project, baseline_paths: [],
    )

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=tmp_path,
        baseline_paths=set(),
        from_version="0.13.0",
        to_version="0.14.0",
    )

    assert committed is False
    assert committed_paths == []
    assert warning is None


def test_auto_commit_noop_when_baseline_is_none(
    tmp_path: Path,
) -> None:
    """None baseline propagates through to no-op (no accidental commits)."""
    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=tmp_path,
        baseline_paths=None,
        from_version="0.13.0",
        to_version="0.14.0",
    )

    assert committed is False
    assert committed_paths == []
    assert warning is None


def test_commit_set_is_porcelain_derived_not_hardcoded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """#2105 regression pin: the commit-set must include EVERYTHING the run
    changed (manifest updates, newly-installed skills), never just
    .kittify/metadata.yaml. Guards against regressing to a hardcoded list."""
    checkout = tmp_path / "project"
    skill_dir = checkout / ".agents" / "skills" / "new-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

    monkeypatch.setattr(
        autocommit,
        "git_status_paths",
        lambda _repo: {
            ".kittify/metadata.yaml",
            ".kittify/command-skills-manifest.json",
            ".agents/skills/new-skill",
        },
    )
    captured: dict[str, object] = {}

    def _fake_safe_commit(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(autocommit, "safe_commit", _fake_safe_commit)
    monkeypatch.setattr(subprocess, "check_output", lambda *_a, **_kw: "main\n")

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=checkout,
        baseline_paths=set(),
        from_version="3.2.3",
        to_version="3.2.4",
    )

    assert committed is True
    assert warning is None
    assert set(committed_paths) == {
        ".kittify/metadata.yaml",
        ".kittify/command-skills-manifest.json",
        ".agents/skills/new-skill/SKILL.md",
    }


def test_commit_skipped_on_detached_head(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A detached-HEAD checkout has no branch to land the bookkeeping commit
    on — never guess a ref; skip with a warning instead."""
    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _checkout, baseline_paths: [Path(".kittify/metadata.yaml")],
    )
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("safe_commit must not run on detached HEAD")),
    )
    # `git branch --show-current` prints an empty line on detached HEAD.
    monkeypatch.setattr(subprocess, "check_output", lambda *_a, **_kw: "\n")

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=tmp_path,
        baseline_paths=set(),
        from_version="3.2.3",
        to_version="3.2.4",
    )

    assert committed is False
    assert committed_paths == [".kittify/metadata.yaml"]
    assert warning == autocommit.DETACHED_HEAD_WARNING


def test_commit_skipped_when_branch_detection_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """When `git branch --show-current` raises, the commit is skipped with a
    warning — never fabricate "main" (FR-013/C7). A prior version of this
    behavior fell back to a hardcoded "main" ref and committed anyway; that
    risked landing upgrade churn on a branch the checkout was never on."""
    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _checkout, baseline_paths: [Path(".kittify/metadata.yaml")],
    )
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("safe_commit must not run when branch detection fails")),
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *_a, **_kw: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "git")),
    )

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=tmp_path,
        baseline_paths=set(),
        from_version="3.2.3",
        to_version="3.2.4",
    )

    assert committed is False
    assert committed_paths == [".kittify/metadata.yaml"]
    assert warning == autocommit.BRANCH_DETECTION_FAILED_WARNING


def test_collect_manual_review_paths_deduplicates() -> None:
    paths = upgrade_cmd._collect_manual_review_paths(
        {
            "a": MigrationResult(
                success=True,
                manual_review_required=True,
                preserved_paths=[".claude/commands/spec-kitty.implement.md", ".agents/skills/foo/SKILL.md"],
            ),
            "b": MigrationResult(
                success=True,
                manual_review_required=False,
                preserved_paths=["ignored"],
            ),
            "c": MigrationResult(
                success=True,
                manual_review_required=True,
                preserved_paths=[".agents/skills/foo/SKILL.md"],
            ),
        }
    )
    assert paths == [
        ".agents/skills/foo/SKILL.md",
        ".claude/commands/spec-kitty.implement.md",
    ]


# ---------------------------------------------------------------------------
# upgrade() function – auto-commit wiring (no-migrations path)
# ---------------------------------------------------------------------------


def _setup_upgrade_project(tmp_path: Path) -> Path:
    """Create a minimal .kittify project structure for upgrade() tests.

    Also a real (if minimal) git repo: ``commit_touched_checkout`` (FR-013/C7)
    genuinely runs ``git branch --show-current`` in this checkout and, since
    the fail-safe fix, no longer fabricates a "main" ref when that fails — a
    non-git tmp_path would now legitimately skip every auto-commit in these
    tests with a warning instead of the fixture's intended "committed" outcome.
    """
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()
    metadata_file = kittify_dir / "metadata.yaml"
    metadata_file.write_text(
        "spec_kitty:\n"
        "  version: '1.0.0a1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def _run_upgrade(**kwargs):
    kwargs.setdefault("plan_json", False)
    kwargs.setdefault("yes", False)
    kwargs.setdefault("no_nag", False)
    kwargs.setdefault("agent_check", False)
    kwargs.setdefault("agent_choice", None)
    kwargs.setdefault("agent_latest", None)
    return upgrade_cmd.upgrade(**kwargs)


def test_upgrade_no_migrations_json_includes_auto_commit_fields(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """The JSON output of a no-migrations upgrade includes auto_committed / auto_commit_paths."""
    project_path = _setup_upgrade_project(tmp_path)

    # Patch cwd to our project
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    # Baseline returns a set (git works), post-upgrade has one new file
    call_count = {"n": 0}

    def _fake_status(repo_path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return set()  # baseline: clean
        return {".kittify/metadata.yaml"}  # post-upgrade: metadata changed

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: object(),
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",  # same as metadata → no migrations
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["status"] == "up_to_date"
    assert data["auto_committed"] is True
    assert ".kittify/metadata.yaml" in data["auto_commit_paths"]
    assert data["warnings"] == []


def test_upgrade_no_migrations_stamps_missing_schema_version(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Regression for issue #1158: up-to-date semver must still repair schema metadata."""
    import yaml

    from specify_cli.migration.schema_version import (
        REQUIRED_SCHEMA_VERSION,
        check_compatibility,
        get_project_schema_version,
    )

    project_path = _setup_upgrade_project(tmp_path)
    metadata_path = project_path / ".kittify" / "metadata.yaml"
    metadata_path.write_text(
        "spec_kitty:\n"
        "  version: 3.2.0rc14\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.14'\n"
        "  platform: darwin\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied:\n"
        "  - id: 3.0.0_canonical_context\n"
        "    applied_at: '2026-01-01T00:00:00'\n"
        "    result: success\n"
        "    notes: canonical context already migrated\n"
        "  - id: 3.2.0a4_normalize_mission_lifecycle\n"
        "    applied_at: '2026-01-01T00:00:00'\n"
        "    result: success\n"
        "    notes: lifecycle already normalized\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    status_calls = {"count": 0}

    def _fake_status(_repo_path: Path) -> set[str]:
        status_calls["count"] += 1
        if status_calls["count"] == 1:
            return set()
        return {".kittify/metadata.yaml"}

    safe_commit_calls: list[list[str]] = []

    def _fake_safe_commit(**kwargs: object) -> object:
        safe_commit_calls.append([str(path) for path in kwargs["paths"]])
        return object()

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(autocommit, "safe_commit", _fake_safe_commit)

    assert get_project_schema_version(project_path) is None

    _run_upgrade(
        dry_run=False,
        force=True,
        target="3.2.0rc14",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["status"] == "up_to_date"
    assert data["auto_committed"] is True
    assert data["auto_commit_paths"] == [".kittify/metadata.yaml"]

    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert metadata["spec_kitty"]["schema_version"] == REQUIRED_SCHEMA_VERSION
    assert check_compatibility(
        get_project_schema_version(project_path),
        REQUIRED_SCHEMA_VERSION,
    ).is_compatible
    assert safe_commit_calls == [[".kittify/metadata.yaml"]]


def test_upgrade_no_migrations_stamps_existing_worktree_schema_version(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """CLI no-migrations path must repair existing worktree schema metadata."""
    import yaml

    from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION

    project_path = _setup_upgrade_project(tmp_path)
    worktree_kittify = project_path / ".worktrees" / "001-feature-lane-a" / ".kittify"
    worktree_kittify.mkdir(parents=True)
    (worktree_kittify / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  version: '1.0.0a1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    status_calls = {"count": 0}

    def _fake_status(_repo_path: Path) -> set[str]:
        status_calls["count"] += 1
        if status_calls["count"] == 1:
            return set()
        return {
            ".kittify/metadata.yaml",
            ".worktrees/001-feature-lane-a/.kittify/metadata.yaml",
        }

    safe_commit_calls: list[list[str]] = []

    def _fake_safe_commit(**kwargs: object) -> object:
        safe_commit_calls.append([str(path) for path in kwargs["paths"]])
        return object()

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(autocommit, "safe_commit", _fake_safe_commit)

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=True,
        verbose=False,
        no_worktrees=False,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["status"] == "up_to_date"
    assert data["auto_commit_paths"] == [
        ".kittify/metadata.yaml",
        ".worktrees/001-feature-lane-a/.kittify/metadata.yaml",
    ]
    worktree_metadata = yaml.safe_load((worktree_kittify / "metadata.yaml").read_text(encoding="utf-8"))
    assert worktree_metadata["spec_kitty"]["schema_version"] == REQUIRED_SCHEMA_VERSION
    assert safe_commit_calls == [
        [
            ".kittify/metadata.yaml",
            ".worktrees/001-feature-lane-a/.kittify/metadata.yaml",
        ]
    ]


def test_upgrade_no_migrations_keeps_current_worktree_metadata_clean(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A clean, already-current upgrade must not rewrite worktree timestamps."""
    from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
    from specify_cli.upgrade.metadata import ProjectMetadata
    from specify_cli.upgrade.runner import MigrationRunner

    project_path = _setup_upgrade_project(tmp_path)
    metadata_path = project_path / ".kittify" / "metadata.yaml"
    metadata = ProjectMetadata.load(project_path / ".kittify")
    assert metadata is not None
    metadata.save(project_path / ".kittify")
    MigrationRunner._stamp_schema_version(project_path / ".kittify", REQUIRED_SCHEMA_VERSION)
    root_before = metadata_path.read_text(encoding="utf-8")

    worktree_kittify = project_path / ".worktrees" / "001-feature-lane-a" / ".kittify"
    worktree_kittify.mkdir(parents=True)
    worktree_metadata_path = worktree_kittify / "metadata.yaml"
    worktree_metadata_path.write_text(root_before, encoding="utf-8")

    worktree_before = worktree_metadata_path.read_text(encoding="utf-8")

    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    status_calls = {"count": 0}

    def _fake_status(_repo_path: Path) -> set[str]:
        status_calls["count"] += 1
        return set()

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("safe_commit should not run")),
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=True,
        verbose=False,
        no_worktrees=False,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["status"] == "up_to_date"
    assert data["auto_committed"] is False
    assert data["auto_commit_paths"] == []
    assert status_calls["count"] >= 1
    assert metadata_path.read_text(encoding="utf-8") == root_before
    assert worktree_metadata_path.read_text(encoding="utf-8") == worktree_before


def test_upgrade_no_migrations_respects_no_worktrees_for_schema_stamp(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """--no-worktrees must keep the same-version repair scoped to the root project."""
    import yaml

    project_path = _setup_upgrade_project(tmp_path)
    worktree_kittify = project_path / ".worktrees" / "001-feature-lane-a" / ".kittify"
    worktree_kittify.mkdir(parents=True)
    (worktree_kittify / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  version: '1.0.0a1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _repo_path: {".kittify/metadata.yaml"})
    monkeypatch.setattr(autocommit, "safe_commit", lambda **_kw: object())

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    assert json.loads(capsys.readouterr().out.strip())["status"] == "up_to_date"
    worktree_metadata = yaml.safe_load((worktree_kittify / "metadata.yaml").read_text(encoding="utf-8"))
    assert "schema_version" not in worktree_metadata["spec_kitty"]


def test_upgrade_no_migrations_surfaces_teamspace_mission_state_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A normal upgrade run checks TeamSpace mission-state readiness even when up to date."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: set())
    monkeypatch.setattr(upgrade_cmd, "show_banner", lambda: None)

    calls: list[dict[str, object]] = []

    def _fake_offer(project_path: Path, **kwargs):
        kwargs["project_path"] = project_path
        calls.append(kwargs)
        return True, False

    monkeypatch.setattr(
        upgrade_cmd,
        "offer_teamspace_mission_state_migration",
        _fake_offer,
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=False,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    assert len(calls) == 1
    assert calls[0]["project_path"] == project_path
    assert calls[0]["dry_run"] is False
    assert calls[0]["assume_yes"] is True


def test_upgrade_dry_run_skips_auto_commit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """In dry-run mode the upgrade command must not auto-commit anything."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    # baseline_changed_paths will be called once; auto_commit should not be called
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: set())

    safe_commit_called = {"called": False}

    def _spy_safe_commit(**_kw):
        safe_commit_called["called"] = True
        return True

    monkeypatch.setattr(autocommit, "safe_commit", _spy_safe_commit)

    # T037 routes dry_run+json_output through the compat-planner path which
    # exits before reaching the auto-commit guard.  The test's goal is just to
    # confirm safe_commit is NOT called in dry-run mode, so skip json_output.
    _run_upgrade(
        dry_run=True,
        force=True,
        target="1.0.0a1",
        json_output=False,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    assert safe_commit_called["called"] is False


def test_upgrade_dry_run_json_output_exits_before_auto_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """json_output=True + dry_run=True routes through _run_planner_json before
    reaching the auto-commit guard — safe_commit must never be called."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    safe_commit_called = {"called": False}

    def _spy_safe_commit(**_kw):
        safe_commit_called["called"] = True
        return True

    monkeypatch.setattr(autocommit, "safe_commit", _spy_safe_commit)

    # Simulate _run_planner_json's normal behavior: raise typer.Exit(0)
    monkeypatch.setattr(upgrade_cmd, "_run_planner_json", lambda **_kw: (_ for _ in ()).throw(typer.Exit(0)))

    with pytest.raises(typer.Exit) as exc:
        _run_upgrade(
            dry_run=True,
            force=True,
            target="1.0.0a1",
            json_output=True,
            verbose=False,
            no_worktrees=True,
            cli=False,
            project=False,
        )

    assert exc.value.exit_code == 0
    assert safe_commit_called["called"] is False


def test_upgrade_baseline_failure_skips_auto_commit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """When the baseline git-status fails (None), auto-commit is skipped entirely."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    # Baseline fails → None
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: None)

    safe_commit_called = {"called": False}

    def _spy_safe_commit(**_kw):
        safe_commit_called["called"] = True
        return True

    monkeypatch.setattr(autocommit, "safe_commit", _spy_safe_commit)

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["auto_committed"] is False
    assert data["auto_commit_paths"] == []
    assert safe_commit_called["called"] is False


def test_upgrade_no_migrations_rich_output_shows_auto_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Rich (non-JSON) output shows the auto-commit summary line."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    call_count = {"n": 0}

    def _fake_status(repo_path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return set()
        return {"kitty-specs/001/tasks/WP01.md"}

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: object(),
    )

    captured_output: list[str] = []
    monkeypatch.setattr(
        upgrade_cmd.console,
        "print",
        lambda *args, **kw: captured_output.append(str(args[0])) if args else None,
    )
    monkeypatch.setattr(upgrade_cmd, "show_banner", lambda: None)

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=False,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    full = "\n".join(captured_output)
    assert "Auto-committed upgrade changes" in full
    assert "1 files" in full


def test_upgrade_no_migrations_safe_commit_failure_shows_warning(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """When safe_commit raises, the JSON output includes a warning."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    call_count = {"n": 0}

    def _fake_status(repo_path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return set()
        return {".kittify/metadata.yaml"}

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="1.0.0a1",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["auto_committed"] is False
    assert len(data["warnings"]) == 1
    assert "review and commit manually" in data["warnings"][0]


def test_upgrade_rejects_downgrade_target_in_json_mode(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Downgrade targets should fail before metadata is rewritten."""
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: set())

    with pytest.raises(typer.Exit) as exc:
        _run_upgrade(
            dry_run=False,
            force=True,
            target="0.9.0",
            json_output=True,
            verbose=False,
            no_worktrees=True,
            cli=False,
            project=False,
        )

    data = json.loads(capsys.readouterr().out.strip())
    assert exc.value.exit_code == 1
    assert data["status"] == "failed"
    assert data["success"] is False
    assert data["errors"] == ["Refusing to downgrade project metadata from 1.0.0a1 to 0.9.0"]


def test_upgrade_suppresses_auto_commit_when_manual_review_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: set())

    fake_migration = MagicMock(
        migration_id="3.2.0a4_safe_globalize_commands",
        description="Safely remove lingering per-project spec-kitty command files",
        target_version="3.2.0a4",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.registry.MigrationRegistry.get_applicable",
        lambda *_args, **_kwargs: [fake_migration],
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRunner.upgrade",
        lambda self, *args, **kwargs: UpgradeResult(
            success=True,
            from_version="1.0.0a1",
            to_version="3.2.0a4",
            migrations_applied=["3.2.0a4_safe_globalize_commands"],
            migration_results={
                "3.2.0a4_safe_globalize_commands": MigrationResult(
                    success=True,
                    manual_review_required=True,
                    preserved_paths=[".claude/commands/spec-kitty.implement.md"],
                )
            },
        ),
    )

    safe_commit_called = {"called": False}

    def _spy_safe_commit(**_kw):
        safe_commit_called["called"] = True
        return True

    monkeypatch.setattr(autocommit, "safe_commit", _spy_safe_commit)

    _run_upgrade(
        dry_run=False,
        force=True,
        target="3.2.0a4",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["success"] is True
    assert data["auto_committed"] is False
    assert data["manual_review_required"] is True
    assert data["manual_review_paths"] == [".claude/commands/spec-kitty.implement.md"]
    assert data["migrations"][0]["manual_review_required"] is True
    assert data["migrations"][0]["preserved_paths"] == [".claude/commands/spec-kitty.implement.md"]
    assert any("Skipped auto-commit" in warning for warning in data["warnings"])
    assert safe_commit_called["called"] is False


def test_upgrade_auto_commits_clean_run_when_no_manual_review(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "git_status_paths", lambda _rp: set())

    fake_migration = MagicMock(
        migration_id="3.2.0a4_safe_globalize_commands",
        description="Safely remove lingering per-project spec-kitty command files",
        target_version="3.2.0a4",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.registry.MigrationRegistry.get_applicable",
        lambda *_args, **_kwargs: [fake_migration],
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRunner.upgrade",
        lambda self, *args, **kwargs: UpgradeResult(
            success=True,
            from_version="1.0.0a1",
            to_version="3.2.0a4",
            migrations_applied=["3.2.0a4_safe_globalize_commands"],
            migration_results={"3.2.0a4_safe_globalize_commands": MigrationResult(success=True)},
        ),
    )
    monkeypatch.setattr(
        autocommit,
        "commit_touched_checkout",
        lambda *_a, **_kw: (True, [".kittify/metadata.yaml"], None),
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="3.2.0a4",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["success"] is True
    assert data["manual_review_required"] is False
    assert data["manual_review_paths"] == []
    assert data["auto_committed"] is True
    assert data["auto_commit_paths"] == [".kittify/metadata.yaml"]


# ---------------------------------------------------------------------------
# upgrade_worktrees_only — public entry point (tech-debt follow-up #2387)
# ---------------------------------------------------------------------------


def test_upgrade_worktrees_only_delegates_to_private_impl(tmp_path: Path, monkeypatch) -> None:
    """upgrade_worktrees_only() must call _upgrade_worktrees with an empty
    migrations list, forwarding target_version, dry_run, and auto_commit.

    This pins the public-method contract introduced as the #2387 follow-up:
    the no-migrations CLI path must no longer call the private ``_upgrade_worktrees``
    directly.
    """
    from specify_cli.upgrade.runner import MigrationRunner

    project_path = tmp_path / "project"
    project_path.mkdir()

    calls: list[dict] = []

    def _fake_upgrade_worktrees(
        target_version: str,
        migrations: list,
        dry_run: bool,
        auto_commit: bool = False,
    ) -> dict:
        calls.append(
            {
                "target_version": target_version,
                "migrations": migrations,
                "dry_run": dry_run,
                "auto_commit": auto_commit,
            }
        )
        return {"warnings": [], "errors": []}

    runner = MigrationRunner(project_path)
    monkeypatch.setattr(runner, "_upgrade_worktrees", _fake_upgrade_worktrees)

    result = runner.upgrade_worktrees_only("3.9.0", dry_run=True, auto_commit=False)

    assert result == {"warnings": [], "errors": []}
    assert len(calls) == 1
    assert calls[0]["target_version"] == "3.9.0"
    assert calls[0]["migrations"] == []
    assert calls[0]["dry_run"] is True
    assert calls[0]["auto_commit"] is False


def test_upgrade_worktrees_only_passes_auto_commit(tmp_path: Path, monkeypatch) -> None:
    """auto_commit=True is forwarded through the public entry point."""
    from specify_cli.upgrade.runner import MigrationRunner

    project_path = tmp_path / "project"
    project_path.mkdir()

    calls: list[dict] = []

    def _fake_upgrade_worktrees(
        target_version: str,
        migrations: list,
        dry_run: bool,
        auto_commit: bool = False,
    ) -> dict:
        calls.append({"auto_commit": auto_commit})
        return {"warnings": [], "errors": []}

    runner = MigrationRunner(project_path)
    monkeypatch.setattr(runner, "_upgrade_worktrees", _fake_upgrade_worktrees)

    runner.upgrade_worktrees_only("3.9.0", dry_run=False, auto_commit=True)

    assert calls[0]["auto_commit"] is True
