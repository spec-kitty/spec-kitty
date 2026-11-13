"""Fixture wiring for ``tests/specify_cli/``.

Re-exports the un-patched flat-topology mission fixture so tests in this
directory receive it by pytest fixture injection (parameter name) rather
than a module-level import that shadows the parameter (F811). No resolver is
patched by this fixture -- topology routing uses real git + filesystem
state. Mirrors ``tests/acceptance/conftest.py``'s rationale for the same
shared fixture.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from tests._support.charter_warning import rearmed_charter_warning
from tests._support.migration_registry import restored_migration_registry

from tests.integration.coord_topology_fixture import (  # noqa: F401 — pytest fixture re-export
    flat_topology_mission,
)


@pytest.fixture(autouse=True)
def _rearm_charter_ambient_warning() -> Iterator[None]:
    """Re-arm the once-per-process charter warning around each test (#5714; see tests/_support/charter_warning.py)."""
    with rearmed_charter_warning():
        yield


@pytest.fixture(autouse=True)
def _restore_migration_registry() -> Iterator[None]:
    """Put back the registrations each test started with (#6563; see tests/_support/migration_registry.py)."""
    with restored_migration_registry():
        yield


@pytest.fixture
def settle_default_mission() -> Callable[..., Any]:
    """Build a default Mission and settle it ``lanes_with_coord`` through the real ``finalize-tasks``.

    ``settle(tmp_path, owned=THREE_LANES, standing_on="main", before_finalize=None)`` returns the
    ``DefaultMission``; *before_finalize* runs on it after creation and before the finalize (for
    example to commit a plan).
    """
    from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
        THREE_LANES,
        DefaultMission,
        make_default_mission,
        run_finalize,
    )

    def settle(
        tmp_path: Path,
        owned: Sequence[str] = THREE_LANES,
        *,
        standing_on: str = "main",
        before_finalize: Callable[[DefaultMission], None] | None = None,
    ) -> DefaultMission:
        mission = make_default_mission(tmp_path, owned, standing_on=standing_on)
        if before_finalize is not None:
            before_finalize(mission)
        code, payload = run_finalize(mission)
        assert code == 0, payload
        return mission

    return settle
