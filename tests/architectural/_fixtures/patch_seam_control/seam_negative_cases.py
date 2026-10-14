"""Negatives the census must **not** flag, plus the ``in``-form n=0 case.

Control fixture for ``scripts/patch_seam_census.py`` (WP03 / SC-015). Not named
``test_*``, so pytest never collects it.

Three distinct negatives:

1. ``case_own_module_patch`` — patches a symbol **defined in** the module it
   names. This is the *correct* idiom and lands in the ``own_module`` bucket;
   flagging it is the 97.7% over-breadth FR-005's literal wording would cause.
2. ``case_monotonic_only`` — patches a reach-through seam that is **not** a
   sleep seam, so the function must not count as a sleep node.
3. ``case_membership_without_cardinality`` — reads the mock, but asserts
   **membership**, not cardinality. It must report ``n=0``. Deriving ``n`` from
   the length of the printed delay list would report ``n=1`` here and make
   SC-002 fakeable.

Every target resolves on this tree (``check_patch_targets.py`` requires it). The
patch *target* is incidental to the detected *form*: the own-module case patches
a class defined here, and the reach-through cases patch this fixture's own
module-level ``time`` (its leaf is still an imported module, so the seam stays
reach-through). The former ``specify_cli.tracker.saas_client`` targets were
removed with the frozen hosted surfaces (issue #6164).
"""

from __future__ import annotations

import time  # noqa: F401 — reach-through patch targets `<this module>.time.*` must resolve on disk
from unittest.mock import MagicMock, patch


class _LocalClient:
    """A class defined in THIS module, so patching it is the own-module idiom.

    Stands in for the former ``saas_client.SaaSTrackerClient`` target; its only
    job is to be a symbol the own-module negative can name.
    """


@patch("tests.architectural._fixtures.patch_seam_control.seam_negative_cases._LocalClient")
def case_own_module_patch(mock_client: MagicMock) -> None:
    """Own-module patch — the correct idiom. Must not be flagged."""
    assert mock_client.call_count == 0


@patch("tests.architectural._fixtures.patch_seam_control.seam_negative_cases.time.monotonic")
def case_monotonic_only(mock_monotonic: MagicMock) -> None:
    """A monotonic-only node. Reach-through, but not a *sleep* seam."""
    mock_monotonic.side_effect = [0.0, 301.0]
    assert mock_monotonic.call_count == 0


@patch("tests.architectural._fixtures.patch_seam_control.seam_negative_cases.time.sleep")
def case_membership_without_cardinality(mock_sleep: MagicMock) -> None:
    """Reads the mock but asserts no cardinality — must report ``n=0``."""
    mock_sleep(3.0)
    assert 3.0 in [c.args[0] for c in mock_sleep.call_args_list]
