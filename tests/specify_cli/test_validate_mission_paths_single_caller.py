"""Single-production-caller invariant for ``validate_mission_paths`` (#3016, WP02, NFR-004b).

STRICTLY TEST-ONLY. The whole point of the #3016 fix is that the project path-convention override resolves
at *one* shared seam. That guarantee is only as strong as the number of production call sites: if a second
caller of ``validators.paths.validate_mission_paths`` appears in ``src/`` that does not route through
``acceptance.summary_core.evaluate_path_conventions``, the override could be silently bypassed on that path.

This guard walks the shipped ``specify_cli`` package with the AST and asserts the set of *production* call
sites is exactly ``{evaluate_path_conventions}``. It is deliberately placed OUTSIDE ``tests/architectural/``
so it does not trip that suite's shard-orphan cascade (and, before its retirement by #4315, the
golden-count cascade too) (WP02 guidance); it is a plain module-scoped guard. The assertions are
set/equality based (never ``len() == N``), so a violation names the offending caller instead of an
opaque count mismatch.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_root_validate_mission_paths_single_caller.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_root_validate_mission_paths_single_caller import (
    test_validate_mission_paths_has_single_production_caller as test_validate_mission_paths_has_single_production_caller,
)

pytestmark = [pytest.mark.unit, pytest.mark.non_sandbox]
