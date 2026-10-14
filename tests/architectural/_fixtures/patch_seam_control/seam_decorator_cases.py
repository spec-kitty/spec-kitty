"""Decorator-form patch seams with corruptible read-side assertions.

Control fixture for ``scripts/patch_seam_census.py`` (mission
``sync-sleep-count-3136-01KZ9B5A``, WP03 / SC-015).

This module is deliberately **not** named ``test_*``: pytest's default
``python_files`` is ``test_*.py``/``*_test.py``, so nothing here is ever
collected, executed, or counted by the arch-shard coverage baseline. It exists
only to be *read* by the census's AST walker.

Every ``patch()`` target below resolves on this tree — ``check_patch_targets.py``
rglobs every ``*.py`` under ``tests/`` with a **regex over raw source**, so an
unresolvable literal here (even one quoted in a docstring) would red an
``[ENFORCED]`` CI job. The patch *target* is incidental to the detected *form*:
this fixture patches its own module-level ``time`` so it depends on no product
module (the former ``specify_cli.tracker.saas_client`` target was removed with
the frozen hosted surfaces, issue #6164).
"""

from __future__ import annotations

import time  # noqa: F401 — patch target `<this module>.time.sleep` must resolve on disk
from unittest.mock import MagicMock, patch


@patch("tests.architectural._fixtures.patch_seam_control.seam_decorator_cases.time.sleep")
def case_assert_called_once(mock_sleep: MagicMock) -> None:
    """One sleep, read back through ``assert_called_once_with`` (n=1)."""
    mock_sleep(1.5)
    mock_sleep.assert_called_once_with(1.5)


@patch("tests.architectural._fixtures.patch_seam_control.seam_decorator_cases.time.sleep")
def case_call_count_comparison(mock_sleep: MagicMock) -> None:
    """Two sleeps, read back through a ``.call_count`` comparison (n=2)."""
    mock_sleep(0.1)
    mock_sleep(0.2)
    assert mock_sleep.call_count == 2


@patch("tests.architectural._fixtures.patch_seam_control.seam_decorator_cases.time.sleep")
def case_alias_whole_list_equality(mock_sleep: MagicMock) -> None:
    """The one-level-alias shape from ``test_saas_client.py:783-786``.

    ``call_args_list`` is bound to a local first, so a matcher without one
    level of alias resolution misses **both** assertions below entirely.
    """
    for delay in (0.9, 2.0, 4.4):
        mock_sleep(delay)
    sleep_calls = mock_sleep.call_args_list
    assert len(sleep_calls) == 3
    delays = [c.args[0] for c in sleep_calls]
    assert delays == [0.9, 2.0, 4.4]
