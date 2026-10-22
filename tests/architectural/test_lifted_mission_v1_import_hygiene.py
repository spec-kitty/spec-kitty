"""Always-on gate: importing ``mission_v1.events`` never loads the retired DSL stack.

Lifted from ``tests/specify_cli/mission_v1/test_import_hygiene.py`` (FR-004 /
SC-001, mission ``dead-port-disposition-01M1TZVN`` WP01), a
``tests/specify_cli/mission_v1`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

``mission_v1.events`` sits on a hot path (``runtime/next/next_invocation_lifecycle.py``
emits the ``MissionNextInvoked`` observability event through it), so importing
it must never drag the retired mission-DSL v1 runtime (``compat`` / ``runner``
/ ``guards`` / ``schema``) — or its transitive ``transitions``/``six``
dependency — back into the process. Checked in an isolated subprocess so the
test cannot be satisfied by modules another test already imported.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_mission_v1_import_hygiene import test_events_import_does_not_load_transitions as test_events_import_does_not_load_transitions
from tests.architectural._lifted_mission_v1_import_hygiene import (
    test_events_import_loads_only_the_package_and_events as test_events_import_loads_only_the_package_and_events,
)

pytestmark = [pytest.mark.architectural]
