"""T022 — End-to-end charter integration: triple coherence test.

Simulates a complete charter interview run and asserts that all three outputs
are coherent:
  - Decision Moment events in status.events.jsonl
  - Paper trail in decisions/ (index.json + DM-*.md files)
  - answers.yaml

The interview is driven by directly calling the interview function with
controlled mock inputs via typer.testing.CliRunner.  The Decision Moment
service is NOT mocked — real files are written under a tmp_path repo.

We exercise three scenarios on three distinct question IDs:
  - Q1: user provides a real answer    → resolve path
  - Q2: user defers (empty answer)     → defer path
  - Q3: N/A / cancels                  → cancel path (simulated via service.cancel)

Because the charter interview only has resolve and defer paths natively
(cancel has no in-interview UX trigger), the cancel scenario is exercised
by calling the service directly after the interview — the integration
test verifies that all three DM lifecycle states produce coherent triples.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.decisions import service as dm_service
from specify_cli.decisions import store as dm_store
from specify_cli.decisions.models import DecisionStatus, OriginFlow

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-charter-e2e-mission"
MISSION_ID = "01KCHARTERE2EMISSION0001"

runner = CliRunner()


def _setup_repo(tmp_path: Path) -> Path:
    """Set up a minimal spec-kitty project structure."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)

    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


def _invoke_interview(tmp_path: Path, inputs: str) -> object:
    """Invoke charter interview with the given stdin, returning the result."""
    with contextlib.chdir(tmp_path):
        return runner.invoke(
            charter_app,
            ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
            input=inputs,
            catch_exceptions=False,
        )


# ---------------------------------------------------------------------------
# T022 — Triple coherence after full charter run
# ---------------------------------------------------------------------------


def test_charter_decision_triple_coherence(tmp_path: Path) -> None:
    """Full end-to-end: resolve + defer + cancel produce coherent triple.

    Part 1 (interview): Drive 'charter interview' with real service calls.
      - Q1..Q(n-1): provide a real non-empty answer → resolve
      - Q_last: provide an empty answer → defer

    Part 2 (manual cancel): Call dm_service.cancel directly on a fresh
      decision to simulate the cancel path.

    Assertions (step 4a..4k):
      a. decisions/index.json exists with at least 1 entry
      b. DM-*.md artifact files exist for all entries
      c. Resolved entry has status="resolved" and final_answer set
      d. Deferred entry has status="deferred"
      e. Canceled entry has status="canceled"
      f. status.events.jsonl contains at least 2 lines per decision (opened+resolved)
      g. All Opened events have origin_surface="planning_interview" + origin_flow="charter"
      h. Resolved event for Q1 has terminal_outcome="resolved"
      i. Resolved event for deferred Q has terminal_outcome="deferred"
      j. Resolved event for canceled DM has terminal_outcome="canceled"
      k. answers.yaml has at least one entry (only resolved answers written)
    """
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER, apply_answer_overrides, default_interview

    n_questions = len(MINIMAL_QUESTION_ORDER)
    assert n_questions >= 2, "need at least 2 questions for this test"

    # Build interview data where the LAST question has an empty default
    # so we can produce a defer by pressing Enter on it.
    real_data = default_interview(mission="software-dev", profile="minimal")
    last_q = MINIMAL_QUESTION_ORDER[-1]
    # Force empty default only for the last question
    override_answers = dict(real_data.answers)
    override_answers[last_q] = ""
    patched_data = apply_answer_overrides(real_data, answers=override_answers)

    # Build input string: non-empty answers for all but last Q, empty for last
    answer_lines: list[str] = []
    for i, qid in enumerate(MINIMAL_QUESTION_ORDER):
        if i < n_questions - 1:
            answer_lines.append(f"answer_for_{qid}")
        else:
            answer_lines.append("")  # empty → defer
    # Plus 3 more for paradigms / directives / tools
    answer_lines.extend([""] * 3)
    inputs = "\n".join(answer_lines) + "\n"

    import unittest.mock as mock

    with mock.patch(
        "specify_cli.cli.commands.charter.default_interview",
        return_value=patched_data,
    ):
        result = _invoke_interview(tmp_path, inputs)

    assert result.exit_code == 0, f"charter interview failed:\n{result.output}"

    # ---- Part 2: Open + cancel a third decision manually ----
    cancel_q_id = "charter_cancel_test_q"
    cancel_response = dm_service.open_decision(
        repo_root=tmp_path,
        mission_slug=MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=f"charter.{cancel_q_id}",
        input_key=cancel_q_id,
        question="Would you like to cancel this?",
        options=("yes", "no"),
        actor="test-actor",
    )
    canceled_decision_id = cancel_response.decision_id
    dm_service.cancel_decision(
        repo_root=tmp_path,
        mission_slug=MISSION_SLUG,
        decision_id=canceled_decision_id,
        rationale="owner canceled during charter interview",
        actor="test-actor",
    )

    # ---- Assertions ----
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG

    # (a) index.json exists with correct number of entries
    index_file = mission_dir / "decisions" / "index.json"
    assert index_file.exists(), "decisions/index.json was not created"

    index = dm_store.load_index(mission_dir)
    # n_questions entries from interview + 1 manual cancel
    assert len(index.entries) == n_questions + 1, f"Expected {n_questions + 1} index entries, got {len(index.entries)}"

    # (b) DM-*.md artifact files exist for all entries
    for entry in index.entries:
        artifact = mission_dir / "decisions" / f"DM-{entry.decision_id}.md"
        assert artifact.exists(), f"Missing artifact: DM-{entry.decision_id}.md"

    # Classify entries by question_id
    resolved_entries = [e for e in index.entries if e.status == DecisionStatus.RESOLVED]
    deferred_entries = [e for e in index.entries if e.status == DecisionStatus.DEFERRED]
    canceled_entries = [e for e in index.entries if e.status == DecisionStatus.CANCELED]

    # (c) Resolved entries have final_answer set
    assert resolved_entries, "no resolved entries found"
    for entry in resolved_entries:
        assert entry.final_answer is not None and entry.final_answer.strip(), f"Resolved entry {entry.decision_id} missing final_answer"

    # (d) Deferred entry exists
    assert deferred_entries, "no deferred entry found"
    assert all(e.status == DecisionStatus.DEFERRED for e in deferred_entries)

    # (e) Canceled entry exists
    assert canceled_entries, "no canceled entry found"
    assert canceled_entries[0].decision_id == canceled_decision_id

    # (f) status.events.jsonl has at least 2*(n_questions+1) event lines
    events_file = mission_dir / "status.events.jsonl"
    assert events_file.exists(), "status.events.jsonl was not created"
    event_lines = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Each decision produces opened + resolved = 2 events
    min_expected_events = 2 * (n_questions + 1)
    assert len(event_lines) >= min_expected_events, f"Expected >= {min_expected_events} events, got {len(event_lines)}"

    # (g) All Opened events have origin_surface and origin_flow
    from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_RESOLVED

    opened_events = [e for e in event_lines if e["event_type"] == DECISION_POINT_OPENED]
    for ev in opened_events:
        payload = ev["payload"]
        assert payload.get("origin_surface") == "planning_interview", f"Opened event has wrong origin_surface: {payload.get('origin_surface')}"
        assert payload.get("origin_flow") == "charter", f"Opened event has wrong origin_flow: {payload.get('origin_flow')}"

    # (h) Resolved event for Q1 (first question) has terminal_outcome="resolved"
    first_q_id = MINIMAL_QUESTION_ORDER[0]
    first_entry = next(e for e in index.entries if e.input_key == first_q_id)
    resolved_events = [e for e in event_lines if e["event_type"] == DECISION_POINT_RESOLVED and e["payload"].get("decision_point_id") == first_entry.decision_id]
    assert resolved_events, f"No resolved event found for Q1 ({first_q_id})"
    assert resolved_events[0]["payload"]["terminal_outcome"] == "resolved"

    # (i) Resolved event for the deferred entry has terminal_outcome="deferred"
    deferred_entry = deferred_entries[0]
    deferred_events = [e for e in event_lines if e["event_type"] == DECISION_POINT_RESOLVED and e["payload"].get("decision_point_id") == deferred_entry.decision_id]
    assert deferred_events, f"No resolved event found for deferred entry {deferred_entry.decision_id}"
    assert deferred_events[0]["payload"]["terminal_outcome"] == "deferred"

    # (j) Resolved event for canceled entry has terminal_outcome="canceled"
    canceled_events = [e for e in event_lines if e["event_type"] == DECISION_POINT_RESOLVED and e["payload"].get("decision_point_id") == canceled_decision_id]
    assert canceled_events, f"No resolved event found for canceled entry {canceled_decision_id}"
    assert canceled_events[0]["payload"]["terminal_outcome"] == "canceled"

    # (k) answers.yaml was written and is not empty
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    assert answers_path.exists(), "answers.yaml was not written"
    answers_content = answers_path.read_text(encoding="utf-8")
    assert answers_content.strip(), "answers.yaml is empty"
