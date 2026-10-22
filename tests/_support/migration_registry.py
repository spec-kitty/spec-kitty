"""Restore the process-global migration registry around a test (#6563).

Upgrade tests call ``MigrationRegistry.clear()`` and then
``auto_discover_migrations()``, which reloads every already-imported migration
module and so registers NEW class objects. A later test in the same worker that
imported a migration class at collection time (to monkeypatch its ``apply``, say)
then patches a class the registry no longer holds: the upgrade it drives runs the
reloaded class, and the outcome depends on how ``--dist loadfile`` schedules files.

The suites that clear the registry (``tests/upgrade``, ``tests/specify_cli``) each
wire :func:`restored_migration_registry` into an autouse fixture in their own
``conftest.py``; the root ``tests/conftest.py`` is deliberately not used (see
:mod:`tests._support.charter_warning`).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache


@cache
def _discover_every_migration() -> None:
    """Import every migration module once, before the first snapshot.

    A module first imported inside a cleared window registers only into that window,
    so the restore would drop it; ``auto_discover_migrations`` then skips reloading it
    when it imports another, still-registered migration class, and the migration is
    lost for the rest of the process.
    """
    from specify_cli.upgrade.migrations import auto_discover_migrations

    auto_discover_migrations()


@contextmanager
def restored_migration_registry() -> Iterator[None]:
    """Put back the registrations (and the mapping object) the wrapped block started with."""
    from specify_cli.upgrade.registry import MigrationRegistry

    _discover_every_migration()
    original_mapping = MigrationRegistry._migrations
    original_entries = original_mapping.copy()
    try:
        yield
    finally:
        original_mapping.clear()
        original_mapping.update(original_entries)
        MigrationRegistry._migrations = original_mapping
