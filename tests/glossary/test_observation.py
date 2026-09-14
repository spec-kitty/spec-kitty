"""Tests for the inline drift observation surface (WP01).

Covers all 8 required scenarios:
1. High severity -> notice returned
2. Medium severity -> filtered out
3. Multiple terms -> multiple notices
4. Same term twice -> deduplicated (last-seen wins)
5. Missing log file -> empty list, no exception
6. Malformed JSON line -> skip, no exception
7. invocation_id filter -> only matching invocation events
8. render_notices([]) -> no output
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

from rich.console import Console

from glossary.observation import InlineNotice, ObservationSurface

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_EVENT_LOG_RELPATH = Path(".kittify") / "events" / "glossary" / "mission-001.events.jsonl"


def _write_event_log(repo_root: Path, events: list[dict]) -> None:
    """Write a JSONL event log under repo_root."""
    log_path = repo_root / _EVENT_LOG_RELPATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def _make_event(
    term: str = "deployment-target",
    term_id: str = "glossary:deployment-target",
    severity: str = "high",
    conflict_type: str = "scope_mismatch",
    conflicting_senses: list[str] | None = None,
    invocation_id: str = "01JINVOCATION",
) -> dict:
    return {
        "event_type": "SemanticCheckEvaluated",
        "step_id": invocation_id,
        "run_id": f"run-{invocation_id}",
        "timestamp": "2026-04-23T05:00:00Z",
        "overall_severity": severity,
        "findings": [
            {
                "term": {"surface_text": term},
                "term_id": term_id,
                "severity": severity,
                "conflict_type": conflict_type,
                "candidate_senses": [
                    {
                        "surface": term,
                        "scope": "team_domain",
                        "definition": sense,
                        "confidence": 0.9,
                    }
                    for sense in (conflicting_senses or ["sense A", "sense B"])
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Scenario 1: high severity -> notice returned
# ---------------------------------------------------------------------------


def test_high_severity_returns_notice(tmp_path: Path) -> None:
    """A single high-severity event produces exactly one InlineNotice."""
    _write_event_log(tmp_path, [_make_event(severity="high")])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert {n.term_id for n in notices} == {"glossary:deployment-target"}
    notice = notices[0]
    assert notice.term == "deployment-target"
    assert notice.term_id == "glossary:deployment-target"
    assert notice.severity == "high"
    assert notice.conflict_type == "scope_mismatch"
    assert notice.conflicting_senses == ["sense A", "sense B"]
    assert notice.suggested_action == "run `spec-kitty glossary conflicts --unresolved`"


def test_critical_severity_returns_notice(tmp_path: Path) -> None:
    """A critical-severity event is also surfaced."""
    _write_event_log(tmp_path, [_make_event(severity="critical")])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert {n.severity for n in notices} == {"critical"}
    assert notices[0].severity == "critical"


# ---------------------------------------------------------------------------
# Scenario 2: medium severity -> filtered out
# ---------------------------------------------------------------------------


def test_medium_severity_filtered_out(tmp_path: Path) -> None:
    """Medium-severity events are not surfaced."""
    _write_event_log(tmp_path, [_make_event(severity="medium")])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert notices == []


def test_low_severity_filtered_out(tmp_path: Path) -> None:
    """Low-severity events are not surfaced."""
    _write_event_log(tmp_path, [_make_event(severity="low")])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert notices == []


# ---------------------------------------------------------------------------
# Scenario 3: multiple terms -> multiple notices
# ---------------------------------------------------------------------------


def test_multiple_terms_multiple_notices(tmp_path: Path) -> None:
    """Two distinct high-severity events produce two notices."""
    events = [
        _make_event(term="term-a", term_id="glossary:term-a", severity="high"),
        _make_event(term="term-b", term_id="glossary:term-b", severity="high"),
    ]
    _write_event_log(tmp_path, events)
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    term_ids = {n.term_id for n in notices}
    assert term_ids == {"glossary:term-a", "glossary:term-b"}


# ---------------------------------------------------------------------------
# Scenario 4: same term twice -> deduplicated (last-seen wins)
# ---------------------------------------------------------------------------


def test_same_term_deduplicated_last_seen_wins(tmp_path: Path) -> None:
    """Two events for the same term_id -> one notice, last event wins."""
    event_first = _make_event(
        term="my-term",
        term_id="glossary:my-term",
        conflict_type="scope_mismatch",
        severity="high",
    )
    event_last = _make_event(
        term="my-term",
        term_id="glossary:my-term",
        conflict_type="polysemy",
        severity="critical",
    )
    _write_event_log(tmp_path, [event_first, event_last])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    # cardinality-is-contract: same-term events must DEDUPLICATE to one notice; projecting conflict_type hides a failed dedup that leaves two notices
    assert len(notices) == 1
    assert {n.conflict_type for n in notices} == {"polysemy"}
    # Last-seen wins: should be the second event's data
    assert notices[0].conflict_type == "polysemy"
    assert notices[0].severity == "critical"


# ---------------------------------------------------------------------------
# Scenario 5: missing log file -> empty list, no exception
# ---------------------------------------------------------------------------


def test_missing_log_file_returns_empty(tmp_path: Path) -> None:
    """No event log at all -> returns [] without raising."""
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert notices == []


# ---------------------------------------------------------------------------
# Scenario 6: malformed JSON line -> skip, no exception
# ---------------------------------------------------------------------------


def test_malformed_json_line_skipped(tmp_path: Path) -> None:
    """Corrupt lines are skipped; valid events are still returned."""
    log_path = tmp_path / _EVENT_LOG_RELPATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write("THIS IS NOT JSON\n")
        f.write(json.dumps(_make_event(term="good-term", term_id="glossary:good-term")) + "\n")
        f.write("{broken json}\n")

    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert {n.term for n in notices} == {"good-term"}
    assert notices[0].term == "good-term"


# ---------------------------------------------------------------------------
# Scenario 7: invocation_id filter
# ---------------------------------------------------------------------------


def test_invocation_id_filter(tmp_path: Path) -> None:
    """Only events matching the given invocation_id are returned."""
    events = [
        _make_event(term="term-a", term_id="glossary:term-a", invocation_id="INV-001"),
        _make_event(term="term-b", term_id="glossary:term-b", invocation_id="INV-002"),
        _make_event(term="term-c", term_id="glossary:term-c", invocation_id="INV-001"),
    ]
    _write_event_log(tmp_path, events)
    surface = ObservationSurface()

    notices_001 = surface.collect_notices(tmp_path, invocation_id="INV-001")
    assert {n.term for n in notices_001} == {"term-a", "term-c"}

    notices_002 = surface.collect_notices(tmp_path, invocation_id="INV-002")
    assert {n.term for n in notices_002} == {"term-b"}
    assert notices_002[0].term == "term-b"


def test_invocation_id_filter_no_match_returns_empty(tmp_path: Path) -> None:
    """invocation_id with no matching events returns []."""
    _write_event_log(tmp_path, [_make_event(invocation_id="INV-A")])
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path, invocation_id="INV-UNKNOWN")
    assert notices == []


# ---------------------------------------------------------------------------
# Scenario 8: render_notices([]) -> no output
# ---------------------------------------------------------------------------


def test_render_notices_empty_no_output() -> None:
    """render_notices with an empty list must not call console.print()."""
    mock_console = MagicMock(spec=Console)
    surface = ObservationSurface()
    surface.render_notices([], mock_console)
    mock_console.print.assert_not_called()


def test_render_notices_empty_no_output_real_console() -> None:
    """render_notices([]) produces zero bytes even with a real Console."""
    buf = io.StringIO()
    console = Console(file=buf, highlight=False, markup=False)
    surface = ObservationSurface()
    surface.render_notices([], console)
    assert buf.getvalue() == ""


# ---------------------------------------------------------------------------
# Bonus: render_notices produces expected text for one notice
# ---------------------------------------------------------------------------


def test_render_notices_formats_notice() -> None:
    """Rendered output contains the term and severity."""
    buf = io.StringIO()
    console = Console(file=buf, highlight=False, markup=False, no_color=True)
    notice = InlineNotice(
        term="my-term",
        term_id="glossary:my-term",
        severity="high",
        conflict_type="scope_mismatch",
        conflicting_senses=["sense A", "sense B"],
        suggested_action="run `spec-kitty glossary conflicts --unresolved`",
    )
    surface = ObservationSurface()
    surface.render_notices([notice], console)
    output = buf.getvalue()
    assert "my-term" in output
    assert "high" in output
    assert "scope_mismatch" in output
    assert "spec-kitty glossary conflicts --unresolved" in output


# ---------------------------------------------------------------------------
# Resilience: collect_notices never raises even on bizarre inputs
# ---------------------------------------------------------------------------


def test_collect_notices_never_raises_on_read_error(tmp_path: Path) -> None:
    """Even if the log path exists but is a directory, returns [] silently."""
    log_path = tmp_path / _EVENT_LOG_RELPATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Make it a directory instead of a file to trigger a read error
    log_path.mkdir()
    surface = ObservationSurface()
    notices = surface.collect_notices(tmp_path)
    assert notices == []
