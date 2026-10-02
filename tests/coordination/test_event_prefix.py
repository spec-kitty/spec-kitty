"""Pure prefix/fork classifier tests (mission coord-artifact-single-home-01M3V4BE, WP03 T013).

No git, no filesystem -- pure over event-id sequences, matching
``src/specify_cli/coordination/event_prefix.py``'s own contract.
"""

from __future__ import annotations

import json

import pytest

from specify_cli.coordination.event_prefix import (
    DuplicateEventIdError,
    MalformedEventLogLineError,
    PrefixVerdict,
    classify_prefix,
    event_ids_of,
    merged_log_bytes,
    non_blank_lines_of,
)


def _row(event_id: str) -> str:
    return f'{{"event_id": "{event_id}"}}\n'


class TestClassifyPrefixMatrix:
    """Table-driven matrix: every state row from D3 / I-SEED-4."""

    def test_both_empty(self) -> None:
        assert classify_prefix((), ()) == PrefixVerdict(kind="nothing")

    def test_coord_empty_root_nonempty(self) -> None:
        verdict = classify_prefix(("a", "b"), ())
        assert verdict == PrefixVerdict(kind="carry_tail", tail_start=0)

    def test_coord_proper_prefix_of_root(self) -> None:
        verdict = classify_prefix(("a", "b", "c"), ("a", "b"))
        assert verdict == PrefixVerdict(kind="carry_tail", tail_start=2)

    def test_root_proper_prefix_of_coord(self) -> None:
        verdict = classify_prefix(("a", "b"), ("a", "b", "c"))
        assert verdict == PrefixVerdict(kind="nothing")

    def test_equal_sequences(self) -> None:
        verdict = classify_prefix(("a", "b"), ("a", "b"))
        assert verdict == PrefixVerdict(kind="nothing")

    def test_diverge_at_index_zero(self) -> None:
        verdict = classify_prefix(("x",), ("y",))
        assert verdict.kind == "fork"
        assert verdict.first_divergence == ("x", "y")

    def test_diverge_mid_sequence(self) -> None:
        verdict = classify_prefix(("a", "b", "x"), ("a", "b", "y"))
        assert verdict.kind == "fork"
        assert verdict.first_divergence == ("x", "y")

    def test_diverge_at_last_with_unequal_lengths(self) -> None:
        verdict = classify_prefix(("a", "b"), ("a", "c", "d"))
        assert verdict.kind == "fork"
        assert verdict.first_divergence == ("b", "c")


class TestEventIdsOf:
    def test_skips_blank_lines(self) -> None:
        lines = [_row("a"), "\n", "   \n", _row("b")]
        assert event_ids_of(lines) == ("a", "b")

    def test_malformed_line_raises_not_skips(self) -> None:
        lines = [_row("a"), "not json\n"]
        with pytest.raises(MalformedEventLogLineError) as excinfo:
            event_ids_of(lines)
        assert excinfo.value.line_number == 2

    def test_missing_event_id_key_raises(self) -> None:
        with pytest.raises(MalformedEventLogLineError):
            event_ids_of(['{"no_event_id": true}\n'])

    def test_duplicate_event_id_raises(self) -> None:
        with pytest.raises(DuplicateEventIdError) as excinfo:
            event_ids_of([_row("a"), _row("a")])
        assert excinfo.value.event_id == "a"


class TestNonBlankLinesOf:
    def test_filters_blank_preserving_content(self) -> None:
        lines = [_row("a"), "\n", _row("b")]
        assert non_blank_lines_of(lines) == (_row("a"), _row("b"))


class TestMergedLogBytes:
    def test_carry_tail_appends_root_tail_byte_faithful(self) -> None:
        root_lines = (_row("a"), _row("b"), _row("c"))
        coord_lines = (_row("a"),)
        verdict = classify_prefix(("a", "b", "c"), ("a",))
        merged = merged_log_bytes(root_lines, coord_lines, verdict)
        assert merged == (_row("a") + _row("b") + _row("c")).encode("utf-8")

    def test_nothing_returns_coord_as_is(self) -> None:
        coord_lines = (_row("a"), _row("b"))
        verdict = PrefixVerdict(kind="nothing")
        assert merged_log_bytes((), coord_lines, verdict) == "".join(coord_lines).encode("utf-8")

    def test_fork_verdict_refuses_to_merge(self) -> None:
        verdict = PrefixVerdict(kind="fork", first_divergence=("a", "b"))
        with pytest.raises(ValueError, match="forked"):
            merged_log_bytes((_row("a"),), (_row("b"),), verdict)

    def test_coord_empty_carries_whole_root_verbatim(self) -> None:
        root_lines = (_row("a"), _row("b"))
        verdict = classify_prefix(("a", "b"), ())
        merged = merged_log_bytes(root_lines, (), verdict)
        assert merged == "".join(root_lines).encode("utf-8")

    def test_missing_trailing_newline_on_coord_last_line_does_not_glue_rows(self) -> None:
        """B9 (review cycle 2): a coordination log whose last kept line lacks a
        trailing newline must not glue the next carried row onto it."""
        coord_lines = (_row("a").rstrip("\n"),)  # no trailing newline
        root_lines = (_row("a"), _row("b"))
        verdict = classify_prefix(("a", "b"), ("a",))
        merged = merged_log_bytes(root_lines, coord_lines, verdict)
        assert merged == (_row("a") + _row("b")).encode("utf-8")
        # Exactly two well-formed JSONL rows, never one glued line.
        decoded = merged.decode("utf-8")
        lines = [line for line in decoded.splitlines() if line.strip()]
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # each line parses as its own JSON object

    def test_missing_trailing_newline_on_nothing_verdict_still_ends_in_newline(self) -> None:
        coord_lines = (_row("a").rstrip("\n"),)
        verdict = PrefixVerdict(kind="nothing")
        merged = merged_log_bytes((), coord_lines, verdict)
        assert merged == _row("a").encode("utf-8")
        assert merged.endswith(b"\n")


class TestDuplicateWithinOneSide:
    """A duplicate id within ONE side's own log is a parse-time refusal
    (never silently de-duplicated, never treated as a fork): NFR-002 forbids
    any id appearing twice."""

    def test_duplicate_within_root_refuses_before_classification(self) -> None:
        with pytest.raises(DuplicateEventIdError):
            event_ids_of([_row("a"), _row("b"), _row("a")])
