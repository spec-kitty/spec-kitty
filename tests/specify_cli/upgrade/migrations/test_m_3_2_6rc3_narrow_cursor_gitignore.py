"""Regression tests for the blanket .cursor/ gitignore narrowing migration (#2498).

Covers the bug where GitignoreManager.protect_all_agents() wrote a blanket
`.cursor/` line at init, which conflicts with teams that version-control their
own rules under `.cursor/rules/` (e.g. `.cursor/rules/contributing.mdc`):
once `.cursor/` is gitignored, those tracked files become unstageable.

- detect() is True when a blanket .cursor line exists, or a narrow entry is
  missing; False once both are resolved
- apply() removes the blanket line and backfills the narrow entries
- apply() preserves narrower, non-blocking .cursor/... patterns
- apply() is idempotent; dry-run reports without mutating
- the migration fires end-to-end via MigrationRunner on an already-current
  project and actually un-ignores a tracked .cursor/rules/*.mdc file
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kernel.clock import now_utc

import specify_cli.gitignore_manager as gitignore_manager_module
from specify_cli.gitignore_manager import GitignoreManager
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations import m_3_2_6rc3_narrow_cursor_gitignore as migration_module
from specify_cli.upgrade.migrations.m_3_2_6rc3_narrow_cursor_gitignore import (
    NarrowCursorGitignoreMigration,
    _NARROW_ENTRIES,
    _is_blanket_cursor_line,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _init_git_repo(project_root: Path) -> None:
    subprocess.run(["git", "-C", str(project_root), "init", "-q"], check=True)


def _write_gitignore(project_root: Path, *entries: str) -> None:
    project_root.joinpath(".gitignore").write_text(
        "# Added by Spec Kitty CLI (auto-managed)\n" + "\n".join(entries) + "\n",
        encoding="utf-8",
    )


def _write_metadata(project_root: Path, version: str) -> None:
    ProjectMetadata(version=version, initialized_at=now_utc()).save(project_root / ".kittify")


def _is_ignored(project_root: Path, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(project_root), "check-ignore", "--quiet", path],
            check=False,
        ).returncode
        == 0
    )


class TestIsBlanketCursorLine:
    @pytest.mark.parametrize(
        "line",
        [
            ".cursor",
            ".cursor/",
            "/.cursor",
            "/.cursor/",
            ".cursor/**",
            ".cursor/*",
            "/.cursor/**",
            "**/.cursor/",
            "**/.cursor",
            "**/.cursor/**",
            "  .cursor/  ",  # surrounding whitespace is stripped
        ],
    )
    def test_blanket_patterns_detected(self, line: str):
        assert _is_blanket_cursor_line(line) is True

    @pytest.mark.parametrize(
        "line",
        [
            ".cursor/rules/spec-kitty.mdc",
            ".cursor/rules/",
            ".cursor/commands/",
            ".cursor/skills/",
            ".cursor/plans",
            ".cursor/rules/**",
            "!.cursor/",  # negation re-includes; never a blanket block
            "!.cursor/rules/contributing.mdc",
            "# .cursor/",
            "#.cursor",
            "",
            "node_modules/",
            ".cursorignore",
            "my.cursor/",
        ],
    )
    def test_non_blanket_patterns_ignored(self, line: str):
        assert _is_blanket_cursor_line(line) is False


def test_detect_true_when_blanket_line_present(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/", *_NARROW_ENTRIES)

    assert NarrowCursorGitignoreMigration().detect(tmp_path) is True


def test_detect_true_when_narrow_entry_missing(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/sync-state.json")

    assert NarrowCursorGitignoreMigration().detect(tmp_path) is True


def test_detect_false_when_already_narrowed(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, *_NARROW_ENTRIES)

    assert NarrowCursorGitignoreMigration().detect(tmp_path) is False


def test_detect_true_when_no_gitignore_because_narrow_entries_missing(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    assert NarrowCursorGitignoreMigration().detect(tmp_path) is True


def test_apply_without_gitignore_creates_file_with_narrow_entries(tmp_path: Path) -> None:
    """detect()/can_apply() are True for a project with no .gitignore, so
    apply() must create the file with the narrow entries rather than raise
    FileNotFoundError (which would abort ``spec-kitty upgrade``)."""
    _init_git_repo(tmp_path)
    assert not tmp_path.joinpath(".gitignore").exists()

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success
    assert result.changes_made == [f"Added gitignore entry: {entry}" for entry in _NARROW_ENTRIES]
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    for entry in _NARROW_ENTRIES:
        assert content.count(entry) == 1
    assert not any(_is_blanket_cursor_line(line) for line in content.splitlines())


def test_apply_removes_blanket_and_backfills_narrow_entries(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    tmp_path.joinpath(".gitignore").write_text(
        "node_modules/\n\n# Added by Spec Kitty CLI (auto-managed)\n.gemini/\n.cursor/\n.qwen/\n.env\n",
        encoding="utf-8",
    )

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".cursor/\n" not in content
    assert "node_modules/" in content
    assert ".env" in content
    for entry in _NARROW_ENTRIES:
        assert entry in content


def test_apply_preserves_narrower_cursor_patterns(tmp_path: Path) -> None:
    """A team's own .cursor/rules/contributing.mdc-style commit must survive."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/", ".cursor/plans")

    NarrowCursorGitignoreMigration().apply(tmp_path)

    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".cursor/\n" not in content
    assert ".cursor/plans" in content


def test_apply_adds_only_missing_narrow_entry(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".cursor/rules/spec-kitty.mdc", ".cursor/commands/")

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.changes_made == ["Added gitignore entry: .cursor/skills/"]
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert content.count(".cursor/rules/spec-kitty.mdc") == 1


def test_apply_removes_every_blanket_form(tmp_path: Path) -> None:
    """Only the exact legacy manager row is owned; variants are preserved."""
    _init_git_repo(tmp_path)
    _write_gitignore(
        tmp_path,
        ".gemini/",
        ".cursor/",
        ".qwen/",
        ".cursor/**",
        "**/.cursor/",
        "/.cursor/",
        "!.cursor/rules/contributing.mdc",
        ".cursor/plans",
        "# .cursor/ is tooling state",
    )

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success
    lines = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".cursor/" not in lines
    assert ".cursor/**" in lines
    assert "**/.cursor/" in lines
    assert "/.cursor/" in lines
    assert "!.cursor/rules/contributing.mdc" in lines
    assert ".cursor/plans" in lines
    assert "# .cursor/ is tooling state" in lines
    assert sum("managed blanket line" in c for c in result.changes_made) == 1
    assert len(result.warnings) == 3
    assert result.manual_review_required is True


def test_apply_preserves_unmarked_operator_blanket_and_secret_coverage(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    tmp_path.joinpath(".gitignore").write_text(".cursor/\n", encoding="utf-8")
    secret = tmp_path / ".cursor" / "local-secrets.json"
    secret.parent.mkdir()
    secret.write_text("secret\n", encoding="utf-8")

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success
    assert result.manual_review_required is True
    assert ".cursor/" in tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _is_ignored(tmp_path, ".cursor/local-secrets.json")
    assert any("Preserved operator-owned" in warning for warning in result.warnings)


def test_apply_preserves_operator_blanket_appended_after_generated_block(
    tmp_path: Path,
) -> None:
    """The marker has no end delimiter, so EOF rows are not manager-owned."""
    _init_git_repo(tmp_path)
    manager = GitignoreManager(tmp_path)
    assert manager.protect_all_agents().success
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + ".cursor/\n", encoding="utf-8")
    secret = tmp_path / ".cursor" / "local-secrets.json"
    secret.parent.mkdir()
    secret.write_text("secret\n", encoding="utf-8")

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success
    assert result.manual_review_required is True
    # The narrow backfill may append after it (protect_all_agents now ends with
    # the #6474 agent-files block, not the cursor rows); the operator's line stays.
    assert ".cursor/" in gitignore.read_text(encoding="utf-8").splitlines()
    assert _is_ignored(tmp_path, ".cursor/local-secrets.json")
    assert any("Preserved operator-owned" in warning for warning in result.warnings)


def test_apply_is_atomic_when_replacement_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/")
    gitignore = tmp_path / ".gitignore"
    original = gitignore.read_bytes()

    def fail_write(_gitignore_path: Path, _content: str) -> None:
        raise OSError("injected replacement failure")

    monkeypatch.setattr(migration_module, "write_gitignore_text", fail_write)
    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success is False
    assert result.errors == ["injected replacement failure"]
    assert gitignore.read_bytes() == original


def test_apply_uses_one_atomic_writer_for_removal_and_backfill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second manager write would reintroduce partial-migration failure."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/")
    primary_write = migration_module.write_gitignore_text
    primary_calls = 0
    secondary_calls = 0

    def count_primary(gitignore_path: Path, content: str) -> None:
        nonlocal primary_calls
        primary_calls += 1
        primary_write(gitignore_path, content)

    def reject_secondary(_gitignore_path: Path, _content: str) -> None:
        nonlocal secondary_calls
        secondary_calls += 1
        raise OSError("obsolete second writer called")

    monkeypatch.setattr(migration_module, "write_gitignore_text", count_primary)
    monkeypatch.setattr(gitignore_manager_module, "write_gitignore_text", reject_secondary)

    result = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert result.success is True
    assert primary_calls == 1
    assert secondary_calls == 0
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".cursor/\n" not in content
    assert all(entry in content for entry in _NARROW_ENTRIES)


def test_apply_only_collapses_blank_lines_at_removal_site(tmp_path: Path) -> None:
    """Removing the blanket line must not rewrite blank-line runs elsewhere in
    the operator's .gitignore -- an unrelated ``a\n\n\n\nb`` run is preserved
    byte-for-byte, while the hole left by the removed line is closed."""
    _init_git_repo(tmp_path)
    unrelated_run = "a\n\n\n\nb\n"
    tmp_path.joinpath(".gitignore").write_text(
        unrelated_run + "\n# Added by Spec Kitty CLI (auto-managed)\n.gemini/\n.cursor/\n.qwen/\n\nnode_modules/\n",
        encoding="utf-8",
    )

    NarrowCursorGitignoreMigration().apply(tmp_path)

    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert content.startswith(unrelated_run)
    assert "\n\n\n" not in content[len(unrelated_run) :]
    assert "node_modules/" in content
    assert ".cursor/\n" not in content


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/")

    first = NarrowCursorGitignoreMigration().apply(tmp_path)
    second = NarrowCursorGitignoreMigration().apply(tmp_path)

    assert first.success
    assert second.success
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    for entry in _NARROW_ENTRIES:
        assert content.count(entry) == 1


def test_dry_run_reports_without_mutating(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/")

    result = NarrowCursorGitignoreMigration().apply(tmp_path, dry_run=True)

    assert result.success
    assert any("Would remove managed blanket line" in c for c in result.changes_made)
    assert any("Would add gitignore entry" in c for c in result.changes_made)
    content = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".cursor/" in content  # unchanged


def test_can_apply_rejects_nonexistent_path() -> None:
    ok, reason = NarrowCursorGitignoreMigration().can_apply(Path("/nonexistent/path"))
    assert not ok
    assert "does not exist" in reason


@pytest.mark.parametrize("dangling", [False, True])
def test_symlinked_gitignore_is_rejected_without_external_write(tmp_path: Path, dangling: bool) -> None:
    _init_git_repo(tmp_path)
    external = tmp_path.parent / f"external-{tmp_path.name}.txt"
    external.unlink(missing_ok=True)
    if not dangling:
        external.write_text("outside\n", encoding="utf-8")
    tmp_path.joinpath(".gitignore").symlink_to(external)

    migration = NarrowCursorGitignoreMigration()
    assert migration.detect(tmp_path) is True
    ok, reason = migration.can_apply(tmp_path)
    result = migration.apply(tmp_path)

    assert ok is False
    assert "symlink" in reason.lower()
    assert result.success is False
    if not dangling:
        assert external.read_text(encoding="utf-8") == "outside\n"
    else:
        assert not external.exists()


def test_invalid_utf8_is_rejected_without_byte_loss(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    raw = b"node_modules/\n\xff.cursor/\n"
    tmp_path.joinpath(".gitignore").write_bytes(raw)

    migration = NarrowCursorGitignoreMigration()
    assert migration.detect(tmp_path) is True
    ok, reason = migration.can_apply(tmp_path)
    result = migration.apply(tmp_path)

    assert ok is False
    assert "UTF-8" in reason
    assert result.success is False
    assert tmp_path.joinpath(".gitignore").read_bytes() == raw


def test_migration_fires_and_unignores_tracked_rule_file(tmp_path: Path) -> None:
    """The #2498 case: a team-tracked .cursor/rules/contributing.mdc must
    become stageable again once the blanket entry is narrowed."""
    _init_git_repo(tmp_path)
    _write_metadata(tmp_path, "3.2.6rc2")
    _write_gitignore(tmp_path, ".gemini/", ".cursor/", ".qwen/")
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "contributing.mdc").write_text("# team rules\n", encoding="utf-8")

    assert _is_ignored(tmp_path, ".cursor/rules/contributing.mdc")

    MigrationRegistry.clear()
    auto_discover_migrations()
    result = MigrationRunner(tmp_path).upgrade("3.2.6rc3", include_worktrees=False)

    assert result.success
    assert NarrowCursorGitignoreMigration.migration_id in result.migrations_applied
    assert not _is_ignored(tmp_path, ".cursor/rules/contributing.mdc")


def test_runs_on_worktrees_is_true() -> None:
    assert NarrowCursorGitignoreMigration.runs_on_worktrees is True
