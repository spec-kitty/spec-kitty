"""Always-on gate: the state doctor reports the authoritative runtime root.

Lifted from ``tests/state/test_doctor_spec_kitty_home.py`` (mission
spec-kitty-home-isolation, issue #2171, FR-009/FR-010/SC-004), a
``tests/state`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

The doctor's reported global-sync root must resolve to
``get_runtime_root().base`` under both env-configured and default HOME
configurations — never an independently recomputed ``~/.spec-kitty``
literal, which would silently diverge from the runtime the CLI itself uses.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_state import test_reported_root_matches_runtime_root_with_env as test_reported_root_matches_runtime_root_with_env
from tests.architectural._lifted_state import test_reported_root_matches_runtime_root_without_env as test_reported_root_matches_runtime_root_without_env

pytestmark = [pytest.mark.architectural]
