"""#7677: ``move-task`` help documents the canonical lane lifecycle.

The help text (docstring and ``--to`` option) is published verbatim on the
generated CLI reference page (``docs/api/agent-subcommands.md``). It used to
print the pre-9-lane flow ``planned → doing → for_review → approved → done``:
``doing`` is an input alias that is never recorded, and ``claimed`` and
``in_review`` were missing. These tests pin the documented lanes to the
``Lane`` enum so the help cannot drift from the lifecycle again.
"""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.agent.tasks import MOVE_TASK_TO_HELP, move_task
from specify_cli.status import NON_DISPLAY_LANES, Lane

pytestmark = pytest.mark.fast

_DISPLAY_LANES = [lane.value for lane in Lane if lane not in NON_DISPLAY_LANES]
_FORWARD_FLOW = ["planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done"]
_SIDE_LANES = ["blocked", "canceled"]


def _summary_line() -> str:
    doc = move_task.__doc__ or ""
    return doc.strip().splitlines()[0]


def test_documented_lanes_cover_the_lane_enum() -> None:
    """The forward flow plus the side lanes are exactly the displayed lanes."""
    assert sorted(_FORWARD_FLOW + _SIDE_LANES) == sorted(_DISPLAY_LANES)


def test_docstring_summary_lists_the_forward_flow_in_order() -> None:
    summary = _summary_line()
    flow = summary[summary.index("(") + 1 : summary.rindex(")")]
    assert [step.strip() for step in flow.split("→")] == _FORWARD_FLOW


def test_docstring_names_side_lanes_and_no_retired_wording() -> None:
    doc = move_task.__doc__ or ""
    for lane in _SIDE_LANES:
        assert f"``{lane}``" in doc
    assert "→ doing" not in doc
    assert "--to doing" not in doc
    assert "hosted sync" not in doc


def test_to_option_help_lists_every_display_lane() -> None:
    listed = MOVE_TASK_TO_HELP[MOVE_TASK_TO_HELP.index("(") + 1 : MOVE_TASK_TO_HELP.index(";")]
    assert listed.split("/") == _DISPLAY_LANES
    assert "doing is accepted as an alias of in_progress" in MOVE_TASK_TO_HELP
