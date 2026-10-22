"""Upgrade-suite isolation for the process-global migration registry."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests._support.migration_registry import restored_migration_registry


@pytest.fixture(autouse=True)
def _restore_migration_registry() -> Iterator[None]:
    """Restore collection-time registrations after every upgrade test.

    Upgrade tests intentionally exercise ``MigrationRegistry.clear()`` and
    temporary registrations.  Under loadfile scheduling, a later file runs in
    the same worker process; without restoration it observes whichever test
    last replaced the registry rather than the decorated production classes
    imported during collection.
    """
    with restored_migration_registry():
        yield
