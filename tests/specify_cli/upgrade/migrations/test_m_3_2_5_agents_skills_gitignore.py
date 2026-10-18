"""Regression tests for the ``.agents/skills/`` + skills-manifest gitignore backfill (#2412).

Covers the bug where the shared Agent-Skills projection root
(``.agents/skills/``, codex/vibe/pi/letta) and the per-machine install ledger
(``.kittify/skills-manifest.json``) were never gitignored by any init path or
migration — so absolute ``/Users/<name>/...`` skill symlinks and per-machine
manifest churn showed up as committable, and the upgrade auto-commit could
land them in the repo.

- apply() adds both entries and hides a projected skill symlink + the manifest
- apply() adds only the missing entry when the other is already present
- detect() is True when either entry is missing, False when both are present
- a wholesale ``.agents/`` (or no-trailing-slash) variant counts as present
- detect() ignores a commented-out entry
- apply() is idempotent; dry-run reports without mutating
- the backfill fires end-to-end via MigrationRunner on an already-current project
"""

from __future__ import annotations

import os
import subprocess
from kernel.clock import now_utc
from pathlib import Path

import pytest

from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_3_2_5_agents_skills_gitignore_backfill import (
    AgentsSkillsGitignoreBackfillMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _settle_all_except(project: Path, *keep_unsettled: str) -> None:
    """Seed the ledger so every declared migration except ``keep_unsettled`` is ``success``.

    Post-cutover ``get_applicable`` is a ledger-diff over the full declared set
    (version window retired, ADR 2026-10-17-1); seeding a fully-adopted ledger
    isolates the subject so an unrelated over-selected migration cannot write
    through this fixture's machine-local skill symlink. Fixture setup only.
    """
    for migration in MigrationRegistry.get_all():
        if migration.migration_id not in keep_unsettled:
            MigrationLedger(project).append(build_record(migration, "success"))

_SKILLS_ROOT_ENTRY = ".agents/skills/"
_MANIFEST_ENTRY = ".kittify/skills-manifest.json"
_SKILL_FILE_PATH = ".agents/skills/spec-kitty.implement/SKILL.md"


def _init_git_repo(project_root: Path) -> None:
    subprocess.run(["git", "-C", str(project_root), "init", "-q"], check=True)


def _write_gitignore(project_root: Path, *entries: str) -> None:
    project_root.joinpath(".gitignore").write_text(
        "# Added by Spec Kitty CLI (auto-managed)\n" + "\n".join(entries) + "\n",
        encoding="utf-8",
    )


def _write_metadata(project_root: Path, version: str) -> None:
    ProjectMetadata(version=version, initialized_at=now_utc()).save(
        project_root / ".kittify"
    )


def _is_ignored(project_root: Path, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(project_root), "check-ignore", "--quiet", path],
            check=False,
        ).returncode
        == 0
    )


def _project_machine_local_skill(project_root: Path) -> None:
    """Simulate the installer: an absolute symlink into a user-global root."""
    global_skill = project_root / "fake-home" / ".spec-kitty" / "SKILL.md"
    global_skill.parent.mkdir(parents=True)
    global_skill.write_text("# Skill\n", encoding="utf-8")
    dest = project_root / _SKILL_FILE_PATH
    dest.parent.mkdir(parents=True)
    dest.symlink_to(global_skill)
    (project_root / _MANIFEST_ENTRY).parent.mkdir(parents=True, exist_ok=True)
    (project_root / _MANIFEST_ENTRY).write_text('{"version": 1}\n', encoding="utf-8")


def test_apply_adds_both_entries_and_hides_projection(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _project_machine_local_skill(tmp_path)

    AgentsSkillsGitignoreBackfillMigration().apply(tmp_path)

    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _SKILLS_ROOT_ENTRY in gitignore_text
    assert _MANIFEST_ENTRY in gitignore_text
    assert _is_ignored(tmp_path, _SKILL_FILE_PATH)
    assert _is_ignored(tmp_path, _MANIFEST_ENTRY)


def test_apply_adds_only_missing_entry(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _MANIFEST_ENTRY)

    result = AgentsSkillsGitignoreBackfillMigration().apply(tmp_path)

    assert result.changes_made == [f"Added gitignore entry: {_SKILLS_ROOT_ENTRY}"]
    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(_MANIFEST_ENTRY) == 1


def test_detect_true_when_entries_missing(tmp_path: Path) -> None:
    """Already-initialised project: other entries present, ours missing."""
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/sync-state.json")

    assert AgentsSkillsGitignoreBackfillMigration().detect(tmp_path) is True


def test_detect_false_when_both_entries_present(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SKILLS_ROOT_ENTRY, _MANIFEST_ENTRY)

    assert AgentsSkillsGitignoreBackfillMigration().detect(tmp_path) is False


def test_detect_rejects_symlinked_gitignore(tmp_path: Path) -> None:
    """detect() must not follow a .gitignore that is a symlink (issue #626)."""
    _init_git_repo(tmp_path)
    outside_target = tmp_path.parent / f"outside-target-{os.getpid()}.txt"
    outside_target.write_text("do-not-touch\n")
    (tmp_path / ".gitignore").symlink_to(outside_target)

    try:
        with pytest.raises(GitignorePathError):
            AgentsSkillsGitignoreBackfillMigration().detect(tmp_path)
    finally:
        outside_target.unlink(missing_ok=True)


def test_detect_accepts_wholesale_agents_variant(tmp_path: Path) -> None:
    # A hand-added ``.agents/`` (this repo's own approach) already ignores the
    # skills root; the backfill must not add a duplicate beside it.
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".agents/", _MANIFEST_ENTRY)

    migration = AgentsSkillsGitignoreBackfillMigration()
    assert migration.detect(tmp_path) is False
    migration.apply(tmp_path)
    entries = [
        line.strip()
        for line in tmp_path.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert _SKILLS_ROOT_ENTRY not in entries


def test_detect_accepts_no_trailing_slash_variants(tmp_path: Path) -> None:
    # The no-trailing-slash forms (.agents and .agents/skills) must also count
    # as present so the backfill never appends a redundant entry beside them.
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".agents", _MANIFEST_ENTRY)

    migration = AgentsSkillsGitignoreBackfillMigration()
    assert migration.detect(tmp_path) is False

    _write_gitignore(tmp_path, ".agents/skills", _MANIFEST_ENTRY)
    assert migration.detect(tmp_path) is False


def test_can_apply_rejects_nonexistent_path() -> None:
    ok, reason = AgentsSkillsGitignoreBackfillMigration().can_apply(Path("/nonexistent/path"))
    assert not ok
    assert "does not exist" in reason


def test_detect_ignores_commented_out_entry(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, f"# {_SKILLS_ROOT_ENTRY}", f"# {_MANIFEST_ENTRY}")

    assert AgentsSkillsGitignoreBackfillMigration().detect(tmp_path) is True


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, _SKILLS_ROOT_ENTRY, _MANIFEST_ENTRY)

    first = AgentsSkillsGitignoreBackfillMigration().apply(tmp_path)
    second = AgentsSkillsGitignoreBackfillMigration().apply(tmp_path)

    assert first.success
    assert second.success
    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(_SKILLS_ROOT_ENTRY) == 1
    assert gitignore_text.count(_MANIFEST_ENTRY) == 1


def test_dry_run_reports_without_mutating(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _write_gitignore(tmp_path, ".kittify/sync-state.json")

    result = AgentsSkillsGitignoreBackfillMigration().apply(tmp_path, dry_run=True)

    assert result.success
    assert result.changes_made == [
        f"Would add {_SKILLS_ROOT_ENTRY} to .gitignore",
        f"Would add {_MANIFEST_ENTRY} to .gitignore",
    ]
    gitignore_text = tmp_path.joinpath(".gitignore").read_text(encoding="utf-8")
    assert _SKILLS_ROOT_ENTRY not in gitignore_text
    assert _MANIFEST_ENTRY not in gitignore_text


def test_backfill_fires_on_already_current_project(tmp_path: Path) -> None:
    """The #2412 case: an initialised project with projected skills but no
    ignore coverage — the upgrade backfill must hide the machine-local surfaces."""
    _init_git_repo(tmp_path)
    _write_metadata(tmp_path, "3.2.5")
    _write_gitignore(tmp_path, ".kittify/sync-state.json")
    _project_machine_local_skill(tmp_path)

    MigrationRegistry.clear()
    auto_discover_migrations()
    _settle_all_except(tmp_path, AgentsSkillsGitignoreBackfillMigration.migration_id)
    result = MigrationRunner(tmp_path).upgrade("3.2.5", include_worktrees=False)

    assert result.success
    assert (
        AgentsSkillsGitignoreBackfillMigration.migration_id
        in result.migrations_applied
    )
    assert _is_ignored(tmp_path, _SKILL_FILE_PATH)
    assert _is_ignored(tmp_path, _MANIFEST_ENTRY)


def test_runs_on_worktrees_is_true() -> None:
    """Gitignore backfills must reach lane worktrees — projected skills land there too."""
    assert AgentsSkillsGitignoreBackfillMigration.runs_on_worktrees is True


def test_backfill_fires_on_worktree_checkout(tmp_path: Path) -> None:
    """Migration reaches lane worktrees when include_worktrees=True is passed to
    MigrationRunner.upgrade(), locking the runs_on_worktrees=True default together
    with the #2392 upgrade-runner worktree-dispatch seam.

    Both the main checkout and the worktree are missing the new entries; the
    migration must land on both.  (If the main checkout already had the entries,
    detect() would return False, migrations would be empty, and worktree_migrations
    would be empty too — so the worktree dispatch path would be a no-op.)
    """
    _init_git_repo(tmp_path)
    _write_metadata(tmp_path, "3.2.5")
    _write_gitignore(tmp_path, ".kittify/sync-state.json")  # missing both new entries

    # Simulate a lane worktree: a subdirectory under .worktrees/ with kitty-specs/
    # so the runner recognises it as an upgradeable checkout.
    worktree = tmp_path / ".worktrees" / "001-test-feature-lane-1"
    (worktree / "kitty-specs").mkdir(parents=True)
    _write_gitignore(worktree, ".kittify/sync-state.json")  # missing both new entries

    MigrationRegistry.clear()
    auto_discover_migrations()
    result = MigrationRunner(tmp_path).upgrade("3.2.5", include_worktrees=True)

    assert result.success
    assert AgentsSkillsGitignoreBackfillMigration.migration_id in result.migrations_applied
    wt_gitignore = (worktree / ".gitignore").read_text(encoding="utf-8")
    assert _SKILLS_ROOT_ENTRY in wt_gitignore
    assert _MANIFEST_ENTRY in wt_gitignore
