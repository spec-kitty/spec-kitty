"""Guardrail: the clone-local migration set carries the flag and re-applies safely (#6233).

``clone_local_effect = True`` routes a recorded migration's skip decision to
per-clone ``detect()`` instead of the shared ledger. That reselection is only
safe when ``apply()`` is idempotent (applying twice is a no-op: no error, no
duplicate line/config). This gate:

1. pins the known clone-local members as tagged, and the benign ones as NOT
   tagged (so neither set drifts), and
2. proves a representative apply-twice is an idempotent no-op on a real repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.git_ops import git_exclude_file, run_command
from specify_cli.upgrade.migrations._merge_driver_seeding import MergeDriverSeedingMigration
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations.m_0_13_1_exclude_worktrees import ExcludeWorktreesMigration
from specify_cli.upgrade.migrations.m_2_0_0_retire_git_hooks import RetireGitHooksMigration
from specify_cli.upgrade.migrations.m_3_0_3_globalize_skill_pack import GlobalizeSkillPackMigration
from specify_cli.upgrade.migrations.m_3_1_1_event_log_merge_driver import EventLogMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_1_2_globalize_commands import GlobalizeCommandsMigration
from specify_cli.upgrade.migrations.m_3_2_0a4_safe_globalize_commands import SafeGlobalizeCommandsMigration
from specify_cli.upgrade.migrations.m_3_2_6_decisions_event_log_merge_driver import (
    DecisionsEventLogMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers import GateArtifactMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint import IssueMatrixDriverRepointMigration
from specify_cli.upgrade.migrations.m_3_2_6_meta_traces_merge_drivers import MetaTracesMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_2_7_review_cycle_merge_driver import ReviewCycleMergeDriverMigration
from specify_cli.upgrade.migrations.m_4_0_0rc5_decision_index_merge_driver import DecisionIndexMergeDriverMigration
from specify_cli.upgrade.migrations.m_4_0_0rc5_install_lane_tip_recorder import InstallLaneTipRecorderMigration
from specify_cli.upgrade.migrations.m_4_0_0rc7_exclude_spec_kitty import ExcludeSpecKittyMigration

#: Every migration whose effect lives outside version control (per #6233).
CLONE_LOCAL_MIGRATIONS: tuple[type[BaseMigration], ...] = (
    ExcludeSpecKittyMigration,
    ExcludeWorktreesMigration,
    InstallLaneTipRecorderMigration,
    MergeDriverSeedingMigration,
    DecisionsEventLogMergeDriverMigration,
    GateArtifactMergeDriverMigration,
    MetaTracesMergeDriverMigration,
    IssueMatrixDriverRepointMigration,
    ReviewCycleMergeDriverMigration,
    DecisionIndexMergeDriverMigration,
    EventLogMergeDriverMigration,
)

#: Deliberately NOT clone-local (removals / per-machine, fail-safe-guarded).
TRACKED_OR_EXCLUDED_MIGRATIONS: tuple[type[BaseMigration], ...] = (
    RetireGitHooksMigration,
    GlobalizeSkillPackMigration,
    GlobalizeCommandsMigration,
    SafeGlobalizeCommandsMigration,
)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("migration_cls", CLONE_LOCAL_MIGRATIONS, ids=lambda c: c.__name__)
def test_clone_local_members_carry_the_flag(migration_cls: type[BaseMigration]) -> None:
    assert migration_cls.clone_local_effect is True


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("migration_cls", TRACKED_OR_EXCLUDED_MIGRATIONS, ids=lambda c: c.__name__)
def test_tracked_or_excluded_members_do_not_carry_the_flag(migration_cls: type[BaseMigration]) -> None:
    assert migration_cls.clone_local_effect is False


@pytest.mark.unit
@pytest.mark.fast
def test_base_default_is_false() -> None:
    assert BaseMigration.clone_local_effect is False


# --------------------------------------------------------------------------------------
# Idempotency: applying a clone-local migration twice is a safe no-op.
# --------------------------------------------------------------------------------------

pytestmark_git = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture
def git_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Spec Kitty")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "spec@example.com")
    repo = tmp_path / "project"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=repo)
    (repo / ".kittify").mkdir()
    return repo


def _exclude_text(repo: Path) -> str:
    exclude_file = git_exclude_file(repo)
    assert exclude_file is not None
    return exclude_file.read_text(encoding="utf-8")


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    ("migration", "entry"),
    [
        (ExcludeSpecKittyMigration(), ".spec-kitty/"),
        (ExcludeWorktreesMigration(), ".worktrees/"),
    ],
    ids=["exclude_spec_kitty", "exclude_worktrees"],
)
def test_exclude_apply_twice_is_idempotent(git_project: Path, migration: BaseMigration, entry: str) -> None:
    assert migration.apply(git_project, dry_run=False).success is True
    assert migration.apply(git_project, dry_run=False).success is True
    assert _exclude_text(git_project).count(entry) == 1
    assert migration.detect(git_project) is False


@pytest.mark.integration
@pytest.mark.git_repo
def test_merge_driver_apply_twice_is_idempotent(git_project: Path) -> None:
    migration = DecisionsEventLogMergeDriverMigration()
    assert migration.apply(git_project, dry_run=False).success is True
    assert migration.apply(git_project, dry_run=False).success is True

    attributes = (git_project / ".gitattributes").read_text(encoding="utf-8")
    assert attributes.count("kitty-specs/**/decisions.events.jsonl merge=spec-kitty-event-log") == 1
    driver = subprocess.run(
        ["git", "config", "--local", "--get-all", "merge.spec-kitty-event-log.driver"],
        cwd=git_project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert driver.stdout.strip().splitlines() == ["spec-kitty merge-driver-event-log %O %A %B"]
    assert migration.detect(git_project) is False
