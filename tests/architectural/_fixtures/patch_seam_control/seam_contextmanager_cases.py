"""The two patch-seam forms R1's census could not see.

Control fixture for ``scripts/patch_seam_census.py`` (WP03 / SC-015). Not named
``test_*``, so pytest never collects it.

Both cases below are **positives that a decorator-only matcher misses**:

1. ``with patch(...) as mock`` — a context-manager patch feeding a corruptible
   assertion.
2. ``side_effect=<list>.append`` — the sink form, where the corruptible
   assertion reads the *sink list*, not the mock.

Arm E of the control test narrows the analyzer to drop exactly these two forms
and requires this fixture to fail — that is what proves the census is measuring
rather than reciting. The patch *target* is incidental to the detected *form*:
this fixture patches its own module-level ``time`` so it depends on no
product module.
"""

from __future__ import annotations

import time
from unittest.mock import patch


def case_context_manager_call_count() -> None:
    """Context-manager patch read back through ``.call_count`` (n=4)."""
    with patch("tests.architectural._fixtures.patch_seam_control.seam_contextmanager_cases.time.sleep") as mock_sleep:
        for _ in range(4):
            time.sleep(0.25)
        assert mock_sleep.call_count == 4


def case_side_effect_sink_whole_list() -> None:
    """``side_effect=`` sink feeding a whole-list equality assertion (n=2)."""
    sleeps: list[float] = []
    with patch("tests.architectural._fixtures.patch_seam_control.seam_contextmanager_cases.time.sleep", side_effect=sleeps.append):
        time.sleep(0.5)
        time.sleep(1.0)
    assert sleeps == [0.5, 1.0]
