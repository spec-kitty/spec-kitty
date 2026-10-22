"""Always-on gate: ``validate_mission_paths`` has exactly one production caller.

Source: ``tests/specify_cli/test_validate_mission_paths_single_caller.py``
(#3016, WP02, NFR-004b), which lives directly under ``tests/specify_cli`` —
recorded ``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374,
decide-out-of-matrix-test-dirs ledger, lift-invariant disposition).

The #3016 fix guarantees the project path-convention override resolves at
one shared seam. That guarantee is only as strong as the number of
production call sites: if a second caller of
``validators.paths.validate_mission_paths`` appears in ``src/`` that does
not route through ``acceptance.summary_core.evaluate_path_conventions``, the
override could be silently bypassed on that path. AST-walks the shipped
package and asserts the set of production call sites is exactly
``{evaluate_path_conventions}`` (set-equality, so a violation names the
offending caller rather than an opaque count mismatch).
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_root_validate_mission_paths_single_caller import (
    test_validate_mission_paths_has_single_production_caller as test_validate_mission_paths_has_single_production_caller,
)

pytestmark = [pytest.mark.architectural]
