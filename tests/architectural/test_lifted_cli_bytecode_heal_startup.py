"""Always-on gate: a corrupt migrations ``.pyc`` must not crash CLI startup.

Source: ``tests/specify_cli/cli/test_bytecode_heal_startup.py`` (#4124
regression), which lives under ``tests/specify_cli/cli`` — recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374,
decide-out-of-matrix-test-dirs ledger, lift-invariant disposition; PC1
nested-family bulk-lift).

Field symptom: an interrupted ``uv tool install`` left a truncated
``base.cpython-*.pyc``; every ``spec-kitty`` command died at app assembly
before any command ran. Runs against an isolated copy of ``src/`` (so the
shared checkout's ``__pycache__`` is never corrupted for parallel workers)
and invokes the real ``-m specify_cli --version`` entrypoint — the strongest
single invariant of the source suite's three tests: startup self-heals
(purge + recompile + retry) instead of crashing.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_bytecode_heal_startup import (
    test_corrupt_migrations_pyc_does_not_crash_startup as test_corrupt_migrations_pyc_does_not_crash_startup,
)

pytestmark = [pytest.mark.architectural]
