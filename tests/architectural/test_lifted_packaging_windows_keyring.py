"""Always-on gate: ``keyring`` must not be a declared project dependency.

Lifted from ``tests/packaging/test_windows_no_keyring.py``, a
``tests/packaging`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

#2979 marker-gap note: the source filename implies Windows-specific
behavior, but the assertion itself only reads ``pyproject.toml``'s static
dependency list — it never exercises any Windows-only runtime API, so it is
genuinely platform-independent and safe to lift as an always-on architectural
check rather than requiring a real ``windows_ci`` marker/runner. CLI auth
uses only the encrypted file store under ``~/.spec-kitty/auth/``, never the
OS keyring.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_packaging_windows_keyring import (
    test_keyring_not_declared_in_project_dependencies as test_keyring_not_declared_in_project_dependencies,
)

pytestmark = [pytest.mark.architectural]
