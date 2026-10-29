"""#6510 / #4226 -- re-synthesis after a directive activation.

Unit tests for the directive synthesis-input derivation in
``specify_cli.cli.commands.charter._synthesis``.
"""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.charter._synthesis import _directive_synthesis_inputs


# ---------------------------------------------------------------------------
# Directive synthesis-input derivation (pure helper)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_directive_inputs_empty() -> None:
    assert _directive_synthesis_inputs([]) == ([], [])


@pytest.mark.unit
def test_directive_inputs_preserve_order_and_shape() -> None:
    selected, nodes = _directive_synthesis_inputs(["DIRECTIVE_010", "DIRECTIVE_003", "TEAM_001"])

    assert selected == ["DIRECTIVE_010", "DIRECTIVE_003", "TEAM_001"]
    assert [node["urn"] for node in nodes] == ["directive:DIRECTIVE_010", "directive:DIRECTIVE_003", "directive:TEAM_001"]
    assert all(set(node) == {"urn", "kind"} and node["kind"] == "directive" for node in nodes)
