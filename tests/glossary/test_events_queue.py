"""Tests for how the clarification events reach the glossary event log (WP04 / T018, #6399).

Contract being verified:
- emit_sense_updated(), emit_clarification_resolved() and
  emit_clarification_requested() all write through the spec-kitty-events
  ledger write contract (``spec_kitty_events.persistence.append_event``).
  The "GlossarySenseUpdated stays off the SaaS queue" rule of #1549 is retired:
  the SaaS queue was removed in #6164 and the contract writer is a local-ledger
  writer, so every glossary event takes the same path.
- A record the contract refuses is not written; there is no local fallback.

These tests derive from the external observable behaviour described in the spec
(FR-018, FR-019, FR-020, FR-021, FR-022) — not from internal code structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import glossary.events as events_module
from glossary.events import (
    emit_clarification_requested,
    emit_clarification_resolved,
    emit_sense_updated,
    get_event_log_path,
)
from glossary.models import (
    ConflictType,
    SemanticConflict,
    SenseRef,
    Severity,
    TermSurface,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conflict(term: str = "workspace") -> SemanticConflict:
    """Build a minimal SemanticConflict for testing."""
    return SemanticConflict(
        term=TermSurface(surface_text=term),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.MEDIUM,
        confidence=0.8,
        candidate_senses=[
            SenseRef(surface=term, scope="team_domain", definition="A bounded area", confidence=0.9),
            SenseRef(surface=term, scope="spec_kitty_core", definition="Git worktree checkout", confidence=0.7),
        ],
    )


def _make_context(mission_id: str = "test-mission-001", actor_id: str = "user:alice") -> SimpleNamespace:
    """Build a minimal execution context for testing."""
    return SimpleNamespace(
        mission_id=mission_id,
        actor_id=actor_id,
        step_id="step-001",
        run_id="run-001",
        semantic_check_event_id="evt-001",
    )


def _make_selected_sense(term: str = "workspace") -> SenseRef:
    """Build a minimal SenseRef for testing clarification resolution."""
    return SenseRef(
        surface=term,
        scope="team_domain",
        definition="A bounded area of work",
        confidence=0.95,
    )


# ---------------------------------------------------------------------------
# T018-A..D: every clarification event goes through the write contract
# ---------------------------------------------------------------------------


def _read_log(repo_root: Path, mission_id: str) -> list[dict]:
    event_log = get_event_log_path(repo_root, mission_id)
    return [json.loads(line) for line in event_log.read_text().splitlines() if line.strip()]


def _emit_sense_updated(repo_root: Path | None, mission_id: str = "test-mission-001", term: str = "workspace") -> dict | None:
    return emit_sense_updated(
        conflict=_make_conflict(term),
        custom_definition="A bounded area of work for a team",
        scope_value="team_domain",
        context=_make_context(mission_id=mission_id),
        update_type="create",
        repo_root=repo_root,
    )


def _emit_resolved(repo_root: Path, mission_id: str = "test-mission-001", conflict_id: str = "conflict-uuid-001") -> dict | None:
    return emit_clarification_resolved(
        conflict_id=conflict_id,
        conflict=_make_conflict(),
        selected_sense=_make_selected_sense(),
        context=_make_context(mission_id=mission_id),
        resolution_mode="interactive",
        repo_root=repo_root,
    )


def _emit_requested(repo_root: Path, mission_id: str = "test-mission-001") -> dict | None:
    return emit_clarification_requested(
        conflict=_make_conflict(),
        context=_make_context(mission_id=mission_id),
        conflict_id="conflict-uuid-003",
        repo_root=repo_root,
    )


class TestClarificationEventsUseTheWriteContract:
    """Each clarification event is appended once through the contract writer."""

    @pytest.mark.parametrize(
        ("emit", "event_type"),
        [
            (_emit_sense_updated, "GlossarySenseUpdated"),
            (_emit_resolved, "GlossaryClarificationResolved"),
            (_emit_requested, "GlossaryClarificationRequested"),
        ],
    )
    def test_written_through_the_contract_writer(self, tmp_path: Path, emit, event_type: str) -> None:
        with patch("glossary.events._ledger_append", wraps=events_module._ledger_append) as ledger_append:
            result = emit(tmp_path)

        assert result is not None
        ledger_append.assert_called_once()
        assert [event["event_type"] for event in _read_log(tmp_path, "test-mission-001")] == [event_type]

    def test_sense_updated_log_contains_correct_term(self, tmp_path: Path) -> None:
        """The GlossarySenseUpdated line carries the expected term surface."""
        _emit_sense_updated(tmp_path, mission_id="test-term-mission", term="feature")
        assert _read_log(tmp_path, "test-term-mission")[0]["term_surface"] == "feature"

    def test_no_repo_root_writes_nothing(self) -> None:
        """Without repo_root, emit_sense_updated logs and returns the event dict."""
        with patch("glossary.events._ledger_append") as ledger_append:
            result = _emit_sense_updated(None)

        ledger_append.assert_not_called()
        assert result is not None

    def test_sense_updated_and_clarification_share_one_log(self, tmp_path: Path) -> None:
        """In one session both events land, in order, in the same mission log."""
        _emit_sense_updated(tmp_path, mission_id="test-isolation", term="lane")
        _emit_resolved(tmp_path, mission_id="test-isolation", conflict_id="conflict-uuid-005")

        assert [event["event_type"] for event in _read_log(tmp_path, "test-isolation")] == [
            "GlossarySenseUpdated",
            "GlossaryClarificationResolved",
        ]

    def test_a_refused_record_is_not_written(self, tmp_path: Path) -> None:
        """A record the contract refuses leaves no line behind; there is no fallback."""
        with patch("glossary.events.build_sense_updated", return_value={"event_type": "GlossarySenseUpdated"}):
            result = _emit_sense_updated(tmp_path, mission_id="test-refused")

        assert result is None
        assert not get_event_log_path(tmp_path, "test-refused").exists()


# ---------------------------------------------------------------------------
# T018-E: FR-021 — seed file write is deferred (Proposed, not Approved)
# ---------------------------------------------------------------------------


class TestFR021SeedWriteDeferred:
    """Document FR-021 current behavior: seed file is NOT written synchronously.

    FR-021 (Proposed — not Approved in delivery contract): "Immediately after a
    GlossaryClarificationResolved event is emitted, the glossary seed file
    (.kittify/glossaries/<scope>.yaml) is updated."

    Current behavior: emit_clarification_resolved() appends the event to the
    glossary event log. It does NOT synchronously write the seed file.
    Seed file updates happen separately in the glossary pipeline (clarification.py
    and downstream writers). This test pins that contract so a future FR-021
    implementation does not silently change the event-log write behavior.

    See: spec-kitty #1549, kitty-specs/event-architecture-cli-git-truth-01KT119Y/spec.md FR-021
    """

    def test_no_seed_file_written_by_emit(self, tmp_path: Path) -> None:
        """emit_clarification_resolved must NOT write a seed file as a side effect."""
        conflict = _make_conflict("workspace")
        context = _make_context()
        selected = _make_selected_sense()

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)

        emit_clarification_resolved(
            conflict_id="conflict-fr021-001",
            conflict=conflict,
            selected_sense=selected,
            context=context,
            resolution_mode="interactive",
            repo_root=tmp_path,
        )

        seed_files = list(seed_dir.glob("*.yaml"))
        assert seed_files == [], (
            "FR-021 seed write is deferred (Proposed, not Approved). "
            "emit_clarification_resolved must not write seed files synchronously."
        )

    def test_event_log_write_still_happens(self, tmp_path: Path) -> None:
        """The event-log write occurs even though the seed file is not written."""
        _emit_resolved(tmp_path, conflict_id="conflict-fr021-002")
        assert [event["event_type"] for event in _read_log(tmp_path, "test-mission-001")] == [
            "GlossaryClarificationResolved"
        ]
