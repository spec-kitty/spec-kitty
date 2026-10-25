"""The 3.2.5 and 3.2.6rc3 gitignore backfills never undo the rc8 narrowing (#6589).

``4.0.0rc8_narrow_agent_gitignore`` removes the whole-folder agent rows Spec
Kitty wrote and writes a narrow agent-files block. A ``skipped`` ledger record
does not settle a migration, so the two older backfills were selected again on
the next upgrade; their ``detect()`` then saw their rows missing and wrote
``.agents/skills/`` and the ``.cursor/`` rows back. Both are now superseded by
the narrow migration through the registry's supersession table, with their
shipped modules left byte-identical (DIRECTIVE_044).

- a pre-ledger project and a ledger-era project, each with both backfills
  recorded ``skipped``, keep the narrow rows on every later upgrade
- the registered classes are ``SupersededMigration`` substitutes that keep the
  original identity, routing key and ``content_hash``
- every supersession entry names registered, manifest-listed migrations
- direct imports still get the shipped class, unchanged
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import AGENT_BLOCK_BEGIN, SPEC_KITTY_GITIGNORE_MARKER
from specify_cli.upgrade.ledger import MigrationLedger, build_record, compute_content_hash
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, SupersededMigration
from specify_cli.upgrade.migrations.m_3_2_5_agents_skills_gitignore_backfill import AgentsSkillsGitignoreBackfillMigration
from specify_cli.upgrade.migrations.m_3_2_6rc3_narrow_cursor_gitignore import NarrowCursorGitignoreMigration
from specify_cli.upgrade.migrations.m_4_0_0rc8_narrow_agent_gitignore import NarrowAgentGitignoreMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SKILLS_BACKFILL = AgentsSkillsGitignoreBackfillMigration.migration_id
CURSOR_BACKFILL = NarrowCursorGitignoreMigration.migration_id
NARROW = NarrowAgentGitignoreMigration.migration_id
TARGET = "4.0.0rc8"

#: Rows the two backfills write; the narrow block never contains them.
BACKFILL_ROWS = (".agents/skills/", ".cursor/commands/", ".cursor/skills/", ".cursor/rules/spec-kitty.mdc")

#: An rc7 gitignore on which both backfills' ``detect()`` is False, so a run records them ``skipped``.
RC7_GITIGNORE = (
    f"node_modules/\n\n{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.codex/\n.agents/skills/\n.kittify/skills-manifest.json\n"
    ".cursor/rules/spec-kitty.mdc\n.cursor/commands/\n.cursor/skills/\n"
)


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


def _project(tmp_path: Path) -> Path:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["claude"]))
    (tmp_path / ".gitignore").write_text(RC7_GITIGNORE, encoding="utf-8")
    return tmp_path


def _pre_ledger(tmp_path: Path) -> Path:
    """An rc7 project with no ledger whose ``metadata.yaml`` records both backfills ``skipped``.

    ``ProjectMetadata.save()`` no longer writes ``migrations.applied`` (the
    ledger owns it), so the pre-ledger shape is written by hand; the adoption
    backfill copies each ``skipped`` entry into the ledger as ``skipped``.
    """
    project = _project(tmp_path)
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(project / ".kittify")
    applied = "".join(f"  - id: {mid}\n    applied_at: '{now_utc().isoformat()}'\n    result: skipped\n" for mid in (SKILLS_BACKFILL, CURSOR_BACKFILL))
    metadata = project / ".kittify" / "metadata.yaml"
    metadata.write_text(metadata.read_text(encoding="utf-8") + f"migrations:\n  applied:\n{applied}", encoding="utf-8")
    return project


def _ledger_era(tmp_path: Path) -> Path:
    """A project whose ledger settles everything but the narrow migration and records both backfills ``skipped``."""
    project = _project(tmp_path)
    ProjectMetadata(version=TARGET, initialized_at=now_utc()).save(project / ".kittify")
    ledger = MigrationLedger(project)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id == NARROW:
            continue
        result = "skipped" if migration.migration_id in (SKILLS_BACKFILL, CURSOR_BACKFILL) else "success"
        ledger.append(build_record(migration, result))
    return project


def _lines(project: Path) -> list[str]:
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("make_project", [_pre_ledger, _ledger_era], ids=["pre-ledger", "ledger-era"])
def test_narrow_rows_survive_every_later_upgrade(tmp_path: Path, make_project: Callable[[Path], Path]) -> None:
    project = make_project(tmp_path)

    first = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert NARROW in first.migrations_applied, first.errors
    narrowed = _lines(project)
    assert AGENT_BLOCK_BEGIN in narrowed
    assert not set(BACKFILL_ROWS) & set(narrowed)

    for _ in range(2):
        later = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
        assert later.success, later.errors
        assert SKILLS_BACKFILL not in later.migrations_applied
        assert CURSOR_BACKFILL not in later.migrations_applied
        assert _lines(project) == narrowed


@pytest.mark.parametrize("original", [AgentsSkillsGitignoreBackfillMigration, NarrowCursorGitignoreMigration], ids=[SKILLS_BACKFILL, CURSOR_BACKFILL])
def test_registered_class_is_a_superseded_substitute(tmp_path: Path, original: type[BaseMigration]) -> None:
    registered = MigrationRegistry.get_by_id(original.migration_id)

    assert isinstance(registered, SupersededMigration)
    assert NARROW in registered.superseded_by
    for attr in ("migration_id", "target_version", "description", "clone_local_effect", "identity", "requires_git_repository", "runs_on_worktrees"):
        assert getattr(registered, attr) == getattr(original, attr), attr
    # The drift key stays on the shipped module's bytes, so recorded history never reads as drift.
    assert compute_content_hash(registered) == compute_content_hash(original())
    assert registered.detect(tmp_path) is False
    assert registered.can_apply(tmp_path) == (False, registered.superseded_by)


def test_direct_import_still_returns_the_shipped_class() -> None:
    assert not issubclass(AgentsSkillsGitignoreBackfillMigration, SupersededMigration)
    assert not issubclass(NarrowCursorGitignoreMigration, SupersededMigration)


def test_every_supersession_entry_names_registered_manifest_migrations() -> None:
    manifest = load_order_manifest()
    assert SUPERSEDED_MIGRATIONS
    for superseded, successor in SUPERSEDED_MIGRATIONS.items():
        assert MigrationRegistry.get_by_id(superseded) is not None, superseded
        assert MigrationRegistry.get_by_id(successor) is not None, successor
        assert manifest.index(superseded) < manifest.index(successor), (superseded, successor)
        assert successor not in SUPERSEDED_MIGRATIONS
