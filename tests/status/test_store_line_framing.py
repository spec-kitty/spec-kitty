"""Row framing and JSON-limit errors of the status event-log readers (#7439).

Every text reader in :mod:`specify_cli.status.store` ends a row only at LF,
CRLF or a lone CR. ``str.splitlines()`` also breaks at VT, FF, FS, GS, RS,
U+0085, U+2028 and U+2029, which may appear raw inside a JSON string, so a
row holding one of them was cut into undecodable halves. A row that breaks a
CPython JSON limit (an integer over 4300 digits, very deep nesting) surfaces
as the reader's documented error type, never as a raw ``ValueError`` or
``RecursionError``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events.persistence import serialize_record

from specify_cli.events import sanitize_event_for_log
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import (
    EVENTS_FILENAME,
    StoreError,
    append_events_atomic,
    append_raw_rows_atomic,
    read_event_stream,
    read_event_stream_from_text,
    read_events,
    read_events_from_text,
    read_events_lenient,
    read_events_raw,
    seed_scratch_event_log,
    jsonl_lines,
    serialize_event_line,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_ID = "01KNXQS9ATWWFXS3K5ZJ9E5008"

#: Characters ``str.splitlines()`` treats as line boundaries that are legal raw
#: inside a JSON string: the reader cases below write them unescaped into a row.
_NON_BREAK_SEPARATORS = ["\x85", "\u2028", "\u2029"]

#: The C0 separators ``str.splitlines()`` also breaks at. ``json.dumps`` always
#: escapes them and a raw one inside a JSON string is invalid JSON, so a reader
#: case could not tell framing from decoding; they are pinned at the framing
#: seam (:func:`jsonl_lines`) instead.
_C0_SEPARATORS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]


def _row(event_id: str, reason: str | None = None) -> dict[str, Any]:
    event = StatusEvent(
        event_id=event_id,
        mission_slug="034-feature-name",
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-02-08T12:00:00Z",
        actor="claude-opus",
        force=False,
        execution_mode="worktree",
        reason=reason,
        mission_id=_MISSION_ID,
    )
    row: dict[str, Any] = event.to_dict()
    return row


def _line(row: dict[str, Any]) -> str:
    """One raw JSONL row with non-ASCII characters written unescaped."""
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


_FIRST_ID = "01HXYZ0123456789ABCDEFGHJK"
_SECOND_ID = "01HXYZ0123456789ABCDEFGHJM"


def _separator_log(separator: str) -> str:
    special = _line(_row(_FIRST_ID, reason=f"before{separator}after"))
    ordinary = _line(_row(_SECOND_ID))
    return f"{special}\n{ordinary}\n"


def _write_log(feature_dir: Path, text: str) -> None:
    (feature_dir / EVENTS_FILENAME).write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Separators inside a string field stay inside one row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("separator", _C0_SEPARATORS + _NON_BREAK_SEPARATORS, ids=lambda s: f"U+{ord(s):04X}")
def test_jsonl_lines_breaks_rows_only_at_lf_crlf_and_lone_cr(separator: str) -> None:
    """The raw separator stays inside its row; only real line breaks end one."""
    text = f"a{separator}b\nc\r\nd\re"
    assert list(jsonl_lines(text)) == [(1, f"a{separator}b"), (2, "c"), (3, "d"), (4, "e")]


@pytest.mark.parametrize("separator", _NON_BREAK_SEPARATORS, ids=lambda s: f"U+{ord(s):04X}")
class TestSeparatorInsideRow:
    def test_read_events(self, tmp_path: Path, separator: str) -> None:
        _write_log(tmp_path, _separator_log(separator))
        events = read_events(tmp_path)
        assert [e.event_id for e in events] == [_FIRST_ID, _SECOND_ID]
        assert events[0].reason == f"before{separator}after"

    def test_read_event_stream(self, tmp_path: Path, separator: str) -> None:
        _write_log(tmp_path, _separator_log(separator))
        assert len(read_event_stream(tmp_path).transitions) == 2

    def test_read_events_from_text(self, tmp_path: Path, separator: str) -> None:
        events = read_events_from_text(tmp_path, _separator_log(separator))
        assert [e.event_id for e in events] == [_FIRST_ID, _SECOND_ID]
        assert events[0].reason == f"before{separator}after"

    def test_read_event_stream_from_text(self, tmp_path: Path, separator: str) -> None:
        stream = read_event_stream_from_text(tmp_path, _separator_log(separator))
        assert len(stream.transitions) == 2

    def test_read_events_lenient(self, tmp_path: Path, separator: str) -> None:
        _write_log(tmp_path, _separator_log(separator))
        events = read_events_lenient(tmp_path)
        assert [e.event_id for e in events] == [_FIRST_ID, _SECOND_ID]

    def test_read_events_raw_positive_control(self, tmp_path: Path, separator: str) -> None:
        """Same fixture through the file-iterating reader, which already frames at LF."""
        _write_log(tmp_path, _separator_log(separator))
        rows = read_events_raw(tmp_path)
        assert [r["event_id"] for r in rows] == [_FIRST_ID, _SECOND_ID]

    def test_seed_scratch_event_log(self, tmp_path: Path, separator: str) -> None:
        scratch = tmp_path / "scratch"
        seed_scratch_event_log(scratch, _separator_log(separator).encode("utf-8"))
        rows = read_events_raw(scratch)
        assert [r["event_id"] for r in rows] == [_FIRST_ID, _SECOND_ID]
        assert rows[0]["reason"] == f"before{separator}after"


# ---------------------------------------------------------------------------
# Real line breaks (regression pins for the git-text path)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("line_break", ["\r\n", "\r"], ids=["crlf", "lone-cr"])
class TestLineBreaks:
    def _text(self, line_break: str) -> str:
        return f"{_line(_row(_FIRST_ID))}{line_break}{_line(_row(_SECOND_ID))}{line_break}"

    def test_read_events_from_text(self, tmp_path: Path, line_break: str) -> None:
        events = read_events_from_text(tmp_path, self._text(line_break))
        assert [e.event_id for e in events] == [_FIRST_ID, _SECOND_ID]

    def test_read_event_stream_from_text(self, tmp_path: Path, line_break: str) -> None:
        stream = read_event_stream_from_text(tmp_path, self._text(line_break))
        assert [e.event_id for e in stream.transitions] == [_FIRST_ID, _SECOND_ID]

    def test_read_events_on_disk(self, tmp_path: Path, line_break: str) -> None:
        _write_log(tmp_path, self._text(line_break))
        assert [e.event_id for e in read_events(tmp_path)] == [_FIRST_ID, _SECOND_ID]

    def test_read_event_stream_on_disk(self, tmp_path: Path, line_break: str) -> None:
        _write_log(tmp_path, self._text(line_break))
        assert [e.event_id for e in read_event_stream(tmp_path).transitions] == [_FIRST_ID, _SECOND_ID]

    def test_read_events_lenient_on_disk(self, tmp_path: Path, line_break: str) -> None:
        _write_log(tmp_path, self._text(line_break))
        assert [e.event_id for e in read_events_lenient(tmp_path)] == [_FIRST_ID, _SECOND_ID]


# ---------------------------------------------------------------------------
# JSON limits surface as the reader's documented error type
# ---------------------------------------------------------------------------


def _with_raw_field(row: dict[str, Any], raw_value: str) -> str:
    """The row as text with an extra field ``x`` whose JSON value is *raw_value* verbatim."""
    base = _line(row)
    return f'{base[:-1]}, "x": {raw_value}}}'


_LIMIT_ROWS = {
    "long-integer": "1" + "0" * 4300,
    "deep-nesting": "[" * 100_000 + "]" * 100_000,
}


@pytest.mark.parametrize("raw_value", list(_LIMIT_ROWS.values()), ids=list(_LIMIT_ROWS))
class TestJsonLimitRow:
    def _log(self, raw_value: str) -> str:
        return f"{_with_raw_field(_row(_FIRST_ID), raw_value)}\n{_line(_row(_SECOND_ID))}\n"

    def test_read_events(self, tmp_path: Path, raw_value: str) -> None:
        _write_log(tmp_path, self._log(raw_value))
        with pytest.raises(StoreError, match=r"^Invalid JSON on line 1"):
            read_events(tmp_path)

    def test_read_event_stream(self, tmp_path: Path, raw_value: str) -> None:
        _write_log(tmp_path, self._log(raw_value))
        with pytest.raises(StoreError, match=r"^Invalid JSON on line 1"):
            read_event_stream(tmp_path)

    def test_read_events_from_text(self, tmp_path: Path, raw_value: str) -> None:
        with pytest.raises(StoreError, match=r"^Invalid JSON on line 1"):
            read_events_from_text(tmp_path, self._log(raw_value))

    def test_read_events_raw(self, tmp_path: Path, raw_value: str) -> None:
        _write_log(tmp_path, self._log(raw_value))
        with pytest.raises(StoreError, match=r"^Invalid JSON on line 1"):
            read_events_raw(tmp_path)

    def test_read_events_lenient_skips_the_row(self, tmp_path: Path, raw_value: str) -> None:
        _write_log(tmp_path, self._log(raw_value))
        assert [e.event_id for e in read_events_lenient(tmp_path)] == [_SECOND_ID]

    def test_seed_scratch_event_log_raises_value_error(self, tmp_path: Path, raw_value: str) -> None:
        scratch = tmp_path / "scratch"
        with pytest.raises(ValueError, match="line 1") as excinfo:
            seed_scratch_event_log(scratch, self._log(raw_value).encode("utf-8"))
        assert not isinstance(excinfo.value, RecursionError)
        assert not (scratch / EVENTS_FILENAME).exists()


# ---------------------------------------------------------------------------
# Writer byte rule (#7441): non-finite numbers refuse, LF on every OS
# ---------------------------------------------------------------------------


_NON_FINITE = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}


def _evidence_row(value: object) -> dict[str, Any]:
    row = _row(_SECOND_ID)
    row["evidence"] = {"x": value}
    return row


class TestWriterByteRule:
    @pytest.mark.parametrize("value", list(_NON_FINITE.values()), ids=list(_NON_FINITE))
    def test_append_refuses_non_finite_and_writes_nothing(self, tmp_path: Path, value: float) -> None:
        path = tmp_path / EVENTS_FILENAME
        append_raw_rows_atomic(path, [_row(_FIRST_ID)])
        before = path.read_bytes()

        with pytest.raises(StoreError, match="non-finite") as excinfo:
            append_raw_rows_atomic(path, [_evidence_row(value)])

        assert _SECOND_ID in str(excinfo.value)
        assert path.read_bytes() == before
        assert sorted(p.name for p in tmp_path.iterdir()) == [EVENTS_FILENAME]

    @pytest.mark.parametrize("value", list(_NON_FINITE.values()), ids=list(_NON_FINITE))
    def test_serialize_event_line_refuses_non_finite(self, value: float) -> None:
        with pytest.raises(StoreError, match="non-finite"):
            serialize_event_line(_evidence_row(value))

    def test_finite_float_positive_control(self, tmp_path: Path) -> None:
        """Same fixture with a finite float appends and reads back."""
        path = tmp_path / EVENTS_FILENAME
        append_raw_rows_atomic(path, [_evidence_row(1.5)])
        assert read_events_raw(tmp_path)[0]["evidence"] == {"x": 1.5}

    def test_temp_file_is_written_with_lf_newlines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The write open pins ``newline="\\n"`` (CPython on Linux never writes CRLF, so the spy is the proof)."""
        real_fdopen = os.fdopen
        write_opens: list[dict[str, Any]] = []

        def spy(fd: int, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if "w" in mode:
                write_opens.append(dict(kwargs))
            return real_fdopen(fd, mode, *args, **kwargs)

        monkeypatch.setattr("specify_cli.status.store.os.fdopen", spy)
        append_raw_rows_atomic(tmp_path / EVENTS_FILENAME, [_row(_FIRST_ID)])

        assert len(write_opens) == 1
        assert write_opens[0].get("newline") == "\n"

    def test_written_log_has_no_crlf(self, tmp_path: Path) -> None:
        path = tmp_path / EVENTS_FILENAME
        append_raw_rows_atomic(path, [_row(_FIRST_ID), _row(_SECOND_ID)])
        assert b"\r\n" not in path.read_bytes()

    def test_row_bytes_match_the_events_contract(self) -> None:
        """Ratchet (passes on base): core's row equals spec-kitty-events' ``serialize_record``.

        ``spec_kitty_events.persistence.serialize_record`` is the contract byte rule
        ``json.dumps(record, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\\n"``.
        """
        row = _row(_FIRST_ID, reason="café   done")
        expected = serialize_record(sanitize_event_for_log(row)).decode("ascii")
        assert serialize_event_line(row) + "\n" == expected


def test_appending_to_a_crlf_and_lone_cr_log_keeps_every_event(tmp_path: Path) -> None:
    """A foreign-ended log loses no row on append, and the rewritten file is LF only."""
    ids = [_FIRST_ID, _SECOND_ID, "01HXYZ0123456789ABCDEFGHJN"]
    new_id = "01HXYZ0123456789ABCDEFGHJP"
    _write_log(tmp_path, _line(_row(ids[0])) + "\r\n" + _line(_row(ids[1])) + "\r" + _line(_row(ids[2])) + "\r\n")

    new_event = StatusEvent.from_dict(_row(new_id))
    append_events_atomic(tmp_path, [new_event])

    assert [e.event_id for e in read_events(tmp_path)] == [*ids, new_id]
    assert b"\r" not in (tmp_path / EVENTS_FILENAME).read_bytes()
