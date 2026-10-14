"""The three SC-015 decoys, alongside one live seam that must still be counted.

Control fixture for ``scripts/patch_seam_census.py`` (WP03 / SC-015). Not named
``test_*``, so pytest never collects it.

**Decoy 1 — this docstring.** The two constructs below are prose, not code. An
AST census (NFR-007) contributes nothing for either; a text-matching census
counts both::

    mock_sleep.assert_called_once_with(9.9)
    @patch("tests.architectural._fixtures.patch_seam_control.seam_decoy_cases.time.sleep")

That quoted target is a real, resolvable one on purpose: ``check_patch_targets.py``
extracts with a **regex over raw source**, so it sees this docstring. A dangling
target here would print ``::error::Broken patch() targets`` and exit 1 in an
``[ENFORCED]`` CI job. The target patches this fixture's own module-level
``time`` so it depends on no product module (the former
``specify_cli.tracker.saas_client`` target was removed with the frozen hosted
surfaces, issue #6164).

This is also the exact hazard that made three of the mission's artifacts
disagree: a pre-fix target carried inside a docstring means a grep-based arm
would demand a *prose edit* to satisfy a numeric gate.

Decoys 2 (a comment) and 3 (a bare string literal) live in the module body.
"""

from __future__ import annotations

import time  # noqa: F401 — patch target `<this module>.time.*` must resolve on disk
from unittest.mock import MagicMock, patch

# Decoy 3 — a bare string literal. It is a real dotted target, but it is not
# the first positional argument of a patch() call, so the AST census must
# contribute nothing for it.
_DECOY_BARE_LITERAL = "tests.architectural._fixtures.patch_seam_control.seam_decoy_cases.time.sleep"


@patch("tests.architectural._fixtures.patch_seam_control.seam_decoy_cases.time.sleep")
def case_live_seam_among_decoys(mock_sleep: MagicMock) -> None:
    """A genuine seam + assertion (n=1) that must survive the decoys around it."""
    # Decoy 2 — a comment. Also inert to the AST, also counted by a grep:
    # mock_sleep.call_count == 42
    # @patch("tests.architectural._fixtures.patch_seam_control.seam_decoy_cases.time.monotonic")
    mock_sleep(7.0)
    assert mock_sleep.call_count == 1
