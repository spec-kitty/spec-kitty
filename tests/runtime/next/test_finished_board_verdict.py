"""The finished-board verdict and its acceptance/transition inputs (next-lifecycle-integrity WP01).

Covers T001 (the pure ``finished_board_verdict`` in the cores leaf, FR-007), FR-002 freshness
(``acceptance_is_fresh`` in the I/O seam, parsing through ``kernel.clock``) and T003 (the I/O
helpers ``mission_accepted_at`` and ``board_latest_transition_at`` that gather its inputs).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from runtime.next.board_status import BoardStatus
from runtime.next.runtime_bridge_cores import (
    FinishedBoardVerdict,
    finished_board_verdict,
)
from runtime.next.runtime_bridge_io import (
    acceptance_is_fresh,
    board_latest_transition_at,
    mission_accepted_at,
    parse_iso_timestamp,
)
from tests.runtime.next._board_path import board_status_from_dir

pytestmark = pytest.mark.fast

_EARLY = "2026-11-12T08:00:00+00:00"
_LATE = "2026-11-12T09:00:00+00:00"


# ---------------------------------------------------------------------------
# T001 -- the pure verdict (the cores leaf maps the board step + freshness fact)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("board_step", "accepted", "expected"),
    [
        # Not a finished board: NONE, whatever the acceptance says.
        ("implement", True, FinishedBoardVerdict.NONE),
        ("review", False, FinishedBoardVerdict.NONE),
        # Finished board.
        ("accept", True, FinishedBoardVerdict.ACCEPTED),
        ("done", True, FinishedBoardVerdict.ACCEPTED),
        ("accept", False, FinishedBoardVerdict.AWAITING_ACCEPTANCE),
        ("done", False, FinishedBoardVerdict.AWAITING_ACCEPTANCE),
    ],
)
def test_truth_table(board_step: str | None, accepted: bool, expected: FinishedBoardVerdict) -> None:
    assert finished_board_verdict(board_step, accepted=accepted) is expected


# ---------------------------------------------------------------------------
# FR-002 freshness -- acceptance_is_fresh (the I/O seam, parsing via kernel.clock)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("accepted_at", "latest", "expected"),
    [
        (_LATE, _EARLY, True),
        # A missing latest transition counts as fresh.
        (_LATE, None, True),
        # No acceptance recorded.
        (None, _EARLY, False),
        (None, None, False),
        ("", None, False),
        pytest.param(_LATE, _LATE, False, id="equal-timestamps-are-not-accepted"),
        pytest.param(_EARLY, _LATE, False, id="acceptance-older-than-latest-transition"),
        # 10:30+02:00 is 08:30Z: compared by instant, not by string.
        pytest.param("2026-11-12T10:30:00+02:00", _EARLY, True, id="offset-later-instant-with-earlier-string"),
        pytest.param("2026-11-12T10:30:00+02:00", _LATE, False, id="offset-earlier-instant-with-later-string"),
        pytest.param("2026-11-12T09:00:01Z", _LATE, True, id="zulu-suffix-read-as-utc"),
        pytest.param("2026-11-12T09:00:01", _LATE, True, id="naive-read-as-utc"),
    ],
)
def test_freshness_truth_table(accepted_at: str | None, latest: str | None, expected: bool) -> None:
    assert acceptance_is_fresh(accepted_at, latest) is expected


@pytest.mark.parametrize(("accepted_at", "latest"), [("not-a-date", _EARLY), ("not-a-date", None), (_LATE, "garbage")])
def test_garbage_fails_toward_blocked(accepted_at: str, latest: str | None) -> None:
    assert acceptance_is_fresh(accepted_at, latest) is False


def test_parse_iso_timestamp() -> None:
    assert parse_iso_timestamp(None) is None
    assert parse_iso_timestamp("") is None
    assert parse_iso_timestamp("garbage") is None
    parsed = parse_iso_timestamp("2026-11-12T09:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# T003 -- mission_accepted_at
# ---------------------------------------------------------------------------


def _write_meta(mission_dir: Path, meta: dict[str, Any]) -> Path:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def test_accepted_at_is_read_from_meta(tmp_path: Path) -> None:
    mission_dir = _write_meta(tmp_path / "m", {"mission_slug": "m", "accepted_at": _LATE})
    assert mission_accepted_at(mission_dir) == _LATE


def test_meta_without_accepted_at(tmp_path: Path) -> None:
    mission_dir = _write_meta(tmp_path / "m", {"mission_slug": "m"})
    assert mission_accepted_at(mission_dir) is None


def test_no_meta_file(tmp_path: Path) -> None:
    assert mission_accepted_at(tmp_path) is None


def test_malformed_meta_reads_as_not_accepted(tmp_path: Path) -> None:
    (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")
    assert mission_accepted_at(tmp_path) is None


@pytest.mark.parametrize("value", ["", 0, None, ["2026-11-12"]])
def test_non_string_or_empty_accepted_at_is_not_an_acceptance(tmp_path: Path, value: object) -> None:
    mission_dir = _write_meta(tmp_path / "m", {"accepted_at": value})
    assert mission_accepted_at(mission_dir) is None


# ---------------------------------------------------------------------------
# T003 -- board_latest_transition_at
# ---------------------------------------------------------------------------


def _event(wp_id: str, from_lane: str, to_lane: str, n: int, at: str) -> dict[str, Any]:
    return {
        "actor": "tester",
        "at": at,
        "event_id": f"01KVERDICT{n:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": "verdict-fixture",
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _board(states: dict[str, dict[str, Any]]) -> BoardStatus:
    return BoardStatus(
        lanes=MappingProxyType({}),
        wp_states=MappingProxyType({wp: MappingProxyType(state) for wp, state in states.items()}),
        has_log=True,
        weighted_percentage=None,
        source="path",
    )


def test_newest_transition_wins_on_a_reduced_board(tmp_path: Path) -> None:
    events = [
        _event("WP01", "planned", "claimed", 1, "2026-11-12T08:00:00+00:00"),
        _event("WP02", "planned", "claimed", 2, "2026-11-12T08:10:00+00:00"),
        _event("WP01", "claimed", "in_progress", 3, "2026-11-12T08:20:00+00:00"),
        _event("WP02", "claimed", "in_progress", 4, "2026-11-12T08:05:00+00:00"),
    ]
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "status.events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    board = board_status_from_dir(tmp_path)
    assert board_latest_transition_at(board) == "2026-11-12T08:20:00+00:00"


def test_empty_board_returns_none(tmp_path: Path) -> None:
    assert board_latest_transition_at(board_status_from_dir(tmp_path)) is None
    assert board_latest_transition_at(_board({})) is None


def test_no_board_returns_none() -> None:
    assert board_latest_transition_at(None) is None


def test_offsets_are_compared_by_instant() -> None:
    board = _board(
        {
            "WP01": {"last_transition_at": "2026-11-12T10:30:00+02:00"},  # 08:30Z
            "WP02": {"last_transition_at": "2026-11-12T09:00:00+00:00"},
        }
    )
    assert board_latest_transition_at(board) == "2026-11-12T09:00:00+00:00"


def test_states_without_a_timestamp_are_skipped() -> None:
    board = _board({"WP01": {"lane": "planned"}, "WP02": {"last_transition_at": None}, "WP03": {"last_transition_at": _EARLY}})
    assert board_latest_transition_at(board) == _EARLY


def test_an_unparsable_timestamp_is_returned_so_the_verdict_fails_closed() -> None:
    board = _board({"WP01": {"last_transition_at": _EARLY}, "WP02": {"last_transition_at": "garbage"}})
    latest = board_latest_transition_at(board)
    assert latest == "garbage"
    assert acceptance_is_fresh(_LATE, latest) is False
    assert finished_board_verdict("accept", accepted=acceptance_is_fresh(_LATE, latest)) is FinishedBoardVerdict.AWAITING_ACCEPTANCE
