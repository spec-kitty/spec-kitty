"""Fixture wiring for ``tests/specify_cli/``.

Re-exports the un-patched flat-topology mission fixture so tests in this
directory receive it by pytest fixture injection (parameter name) rather
than a module-level import that shadows the parameter (F811). No resolver is
patched by this fixture -- topology routing uses real git + filesystem
state. Mirrors ``tests/acceptance/conftest.py``'s rationale for the same
shared fixture.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests._support.charter_warning import rearmed_charter_warning

from tests.integration.coord_topology_fixture import (  # noqa: F401 — pytest fixture re-export
    flat_topology_mission,
)


@pytest.fixture(autouse=True)
def _rearm_charter_ambient_warning() -> Iterator[None]:
    """Re-arm the once-per-process charter warning around each test (#5714; see tests/_support/charter_warning.py)."""
    with rearmed_charter_warning():
        yield
