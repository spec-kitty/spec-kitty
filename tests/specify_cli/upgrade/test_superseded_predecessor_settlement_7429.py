"""A successor settles on its own ``success`` when its predecessor is superseded by it (#7429).

``4.0.0rc8_stamp_globalize_commands`` declares ``predecessor_id = "3.1.2_globalize_commands"``,
and ``SUPERSEDED_MIGRATIONS`` maps that predecessor to the successor itself, so the predecessor's
substitute only ever records ``skipped``. Under the bare #6688 rule the successor never settled
and was re-selected on every upgrade. These cases pin the narrowed rule and its limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry, migration_settled_in_view
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = [pytest.mark.unit]

STAMP = "4.0.0rc8_stamp_globalize_commands"
STAMP_PREDECESSOR = "3.1.2_globalize_commands"
RESIDUE_SUCCESSOR = "0.9.0_residue_safe_frontmatter_only_lanes"
RESIDUE_PREDECESSOR = "0.9.0_frontmatter_only_lanes"
FOREIGN_PREDECESSOR = "3.2.5_agents_skills_gitignore_backfill"


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir()
    return tmp_path


def _record(project: Path, migration: BaseMigration, result: str) -> None:
    MigrationLedger(project).append(build_record(migration, result))


def _get(migration_id: str) -> BaseMigration:
    migration = MigrationRegistry.get_by_id(migration_id)
    assert migration is not None, migration_id
    return migration


class _ForeignSuccessor(BaseMigration):
    """Declares a predecessor that ``SUPERSEDED_MIGRATIONS`` maps to a different migration."""

    migration_id = "9.9.9_foreign_successor"
    description = "test double"
    target_version = "9.9.9"
    predecessor_id: ClassVar[str] = FOREIGN_PREDECESSOR

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - test double
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 - test double
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002 - test double
        return MigrationResult(success=True)


def test_premises_hold() -> None:
    assert SUPERSEDED_MIGRATIONS[STAMP_PREDECESSOR] == STAMP
    assert _get(STAMP).predecessor_id == STAMP_PREDECESSOR
    assert SUPERSEDED_MIGRATIONS[FOREIGN_PREDECESSOR] != _ForeignSuccessor.migration_id


def test_own_success_settles_a_successor_its_predecessor_is_superseded_by(project: Path) -> None:
    stamp = _get(STAMP)
    _record(project, _get(STAMP_PREDECESSOR), "skipped")
    _record(project, stamp, "success")

    assert migration_settled_in_view(project, stamp) is True


def test_without_its_own_success_the_successor_stays_unsettled(project: Path) -> None:
    _record(project, _get(STAMP_PREDECESSOR), "skipped")

    assert migration_settled_in_view(project, _get(STAMP)) is False


def test_a_predecessor_superseded_by_a_different_migration_still_needs_success(project: Path) -> None:
    successor = _ForeignSuccessor()
    _record(project, _get(FOREIGN_PREDECESSOR), "skipped")
    _record(project, successor, "success")

    assert migration_settled_in_view(project, successor) is False

    _record(project, _get(FOREIGN_PREDECESSOR), "success")
    assert migration_settled_in_view(project, successor) is True


def test_an_adoption_eligible_residue_successor_keeps_the_6688_rule(project: Path) -> None:
    """Adoption can stamp a residue successor's ``success``, so it is not proof the repair ran."""
    successor = _get(RESIDUE_SUCCESSOR)
    assert SUPERSEDED_MIGRATIONS[RESIDUE_PREDECESSOR] == RESIDUE_SUCCESSOR
    _record(project, _get(RESIDUE_PREDECESSOR), "skipped")
    _record(project, successor, "success")

    assert migration_settled_in_view(project, successor) is False


def test_an_unparseable_successor_version_keeps_the_6688_rule(project: Path) -> None:
    class _Unversioned(_ForeignSuccessor):
        migration_id = STAMP
        target_version = "not-a-version"
        predecessor_id: ClassVar[str] = STAMP_PREDECESSOR

    successor = _Unversioned()
    _record(project, _get(STAMP_PREDECESSOR), "skipped")
    _record(project, successor, "success")

    assert migration_settled_in_view(project, successor) is False


def test_the_adoption_ceiling_is_the_backfill_bound() -> None:
    """The rule reads the ledger-adoption backfill's own bound, not a second copy of it."""
    from packaging.version import Version

    from specify_cli.upgrade.migrations.m_4_0_0rc8_backfill_migration_ledger import TARGET_VERSION
    from specify_cli.upgrade.registry import _adoption_ceiling

    assert _adoption_ceiling() == Version(TARGET_VERSION)


def test_with_no_adoption_migration_registered_the_6688_rule_holds(project: Path) -> None:
    """Fail closed: without a known adoption bound, a successor's own success settles nothing more."""
    from specify_cli.upgrade.registry import _own_run_settles_superseded_predecessor

    stamp = _get(STAMP)
    _record(project, stamp, "success")
    ledger = MigrationLedger(project)
    assert _own_run_settles_superseded_predecessor(ledger, stamp) is True  # control: the bound is known

    MigrationRegistry.clear()
    assert _own_run_settles_superseded_predecessor(ledger, stamp) is False
