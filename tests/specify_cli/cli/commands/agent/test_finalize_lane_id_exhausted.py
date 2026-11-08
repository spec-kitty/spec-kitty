"""``finalize-tasks --json`` names ``LANE_ID_EXHAUSTED`` when lane ids run out (#5155)."""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.agent import mission_finalize_commit as finalize_commit
from specify_cli.lanes.compute import LaneIdExhaustedError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_json_envelope_carries_the_lane_id_exhausted_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    error = LaneIdExhaustedError()

    finalize_commit._emit_finalize_error_with_revert_note(error, None, json_output=True)

    assert emitted == [{"error": str(error), "error_code": "LANE_ID_EXHAUSTED"}]
