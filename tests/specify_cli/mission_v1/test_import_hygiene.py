"""Import-hygiene ratchet for :mod:`specify_cli.mission_v1` (FR-004 / SC-001).

Mission ``dead-port-disposition-01M1TZVN`` (WP01) retired the mission-DSL v1
runtime (``compat`` / ``runner`` / ``guards`` / ``schema``) and dropped the
``transitions`` dependency. ``mission_v1.events`` is the surviving module; it
sits on a hot path (``runtime/next/next_invocation_lifecycle.py`` emits the
``MissionNextInvoked`` observability event through it), so importing it must
never drag the retired state-machine stack -- or its transitive ``six`` --
back into the process.

These are permanent negative invariants, checked in an isolated subprocess so
the test cannot be satisfied by modules another test already imported. They
were RED on the base commit (the package ``__init__`` eagerly imported the
DSL modules, which imported ``transitions``) and GREEN after the retirement.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_mission_v1_import_hygiene.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_mission_v1_import_hygiene import test_events_import_does_not_load_transitions as test_events_import_does_not_load_transitions
from tests.architectural._lifted_mission_v1_import_hygiene import (
    test_events_import_loads_only_the_package_and_events as test_events_import_loads_only_the_package_and_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
