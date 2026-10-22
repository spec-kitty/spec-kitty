"""Always-on gate: the shared terminal-control sanitization seam stays intact.

Source: ``tests/specify_cli/cli/test_terminal_control_sanitization.py``,
which lives under ``tests/specify_cli/cli`` — recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` (#4374, decide-out-of-matrix-test-dirs
ledger, lift-invariant disposition; PC1 nested-family bulk-lift).

Ledger assertion shape: "Feed a control-char payload through the shared
sanitization seam; assert stripped output + JSON round-trip." Lifts the two
seam-level tests that exercise ``CliConsole`` directly (render_str +
Rich-table segment rendering, and the machine-JSON round-trip) rather than
the source suite's per-call-site tests (routes/status/glossary/git_ops
rendering), which duplicate the same seam behavior through heavier imports.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_terminal_control_sanitization import (
    test_machine_json_output_remains_plain_and_round_trips as test_machine_json_output_remains_plain_and_round_trips,
)
from tests.architectural._lifted_cli_terminal_control_sanitization import (
    test_render_str_and_segment_rendering_share_the_policy as test_render_str_and_segment_rendering_share_the_policy,
)

pytestmark = [pytest.mark.architectural]
