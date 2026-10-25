"""The encoding-provenance logs take the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation._io import CharterContent, _write_provenance

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def _content(source: Path) -> CharterContent:
    return CharterContent(text="x", source_encoding="utf-8", confidence=1.0, source_path=source, normalization_applied=False)


def test_mission_provenance_appends_one_row(tmp_path: Path) -> None:
    source = tmp_path / "kitty-specs" / "m" / "charter.md"
    _write_provenance(_content(source), bypass_used=False)
    rows = (tmp_path / "kitty-specs" / "m" / ".encoding-provenance.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["source_encoding"] == "utf-8"


def test_provenance_never_extends_a_torn_tail(tmp_path: Path) -> None:
    source = tmp_path / "kitty-specs" / "m" / "charter.md"
    log = tmp_path / "kitty-specs" / "m" / ".encoding-provenance.jsonl"
    log.parent.mkdir(parents=True)
    log.write_bytes(_TORN)
    _write_provenance(_content(source), bypass_used=False)  # non-fatal, as before
    assert log.read_bytes() == _TORN
