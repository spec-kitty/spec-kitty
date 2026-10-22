"""The migration-registry restore keeps a collection-time class patchable (#6563)."""

from __future__ import annotations

import pytest

from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from tests._support.migration_registry import restored_migration_registry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PROBE_ID = "4.0.0rc8_command_skill_hyphen_names"


def test_a_clear_and_rediscover_inside_the_block_is_undone() -> None:
    auto_discover_migrations()
    mapping = MigrationRegistry._migrations
    collected = MigrationRegistry._migrations[_PROBE_ID]

    with restored_migration_registry():
        MigrationRegistry.clear()
        auto_discover_migrations()  # reloads the module: a NEW class object registers
        assert MigrationRegistry._migrations[_PROBE_ID] is not collected

    assert MigrationRegistry._migrations is mapping
    assert MigrationRegistry._migrations[_PROBE_ID] is collected


def test_every_migration_is_registered_before_the_first_snapshot() -> None:
    """A module first imported inside a cleared window must not be lost (the seed runs first)."""
    with restored_migration_registry():
        registered = set(MigrationRegistry._migrations)
    assert registered == set(load_order_manifest())


def test_a_replaced_mapping_is_put_back() -> None:
    mapping = MigrationRegistry._migrations
    before = dict(mapping)

    with restored_migration_registry():
        MigrationRegistry._migrations = {}

    assert MigrationRegistry._migrations is mapping
    assert MigrationRegistry._migrations == before
