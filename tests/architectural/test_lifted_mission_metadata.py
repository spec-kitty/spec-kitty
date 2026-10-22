"""Always-on gate: mission identity (ULID ``mission_id``) resolution.

Lifted from ``tests/mission_metadata/test_mission_identity.py`` (T019 /
FR-203), a ``tests/mission_metadata`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

``resolve_mission_identity`` must round-trip a real ULID ``mission_id`` from
``meta.json`` (Mission Identity Model, 083+: ``mission_id`` is the only
runtime identity), and must tolerate a legacy mission with no ``mission_id``
by returning ``None`` rather than raising.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_mission_metadata import test_resolve_mission_identity_includes_mission_id as test_resolve_mission_identity_includes_mission_id
from tests.architectural._lifted_mission_metadata import (
    test_resolve_mission_identity_tolerates_legacy_mission as test_resolve_mission_identity_tolerates_legacy_mission,
)

pytestmark = [pytest.mark.architectural]
