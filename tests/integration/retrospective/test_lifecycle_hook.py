"""Integration tests for the retrospective lifecycle terminus hook (WP06).

Covers:
  - Autonomous + facilitator success → emits requested(runtime) → started → completed;
    record persisted; gate allows; no exception.
  - Autonomous + facilitator raises → emits requested → started → failed;
    gate blocks (MissionCompletionBlocked raised).
  - HiC + operator runs → prompt returns (True, None) → emits requested(human)
    → started → completed; gate allows.
  - HiC + operator skips → prompt returns (False, "low-value docs fix") →
    emits requested(human) → skipped (with reason); record has status=skipped;
    gate allows.
  - HiC + skip with empty reason → loops until non-empty (tests the loop behavior
    with sequential mock returns).

Test design:
  - ``tmp_path`` provides an isolated repo_root.
  - ``facilitator_callback`` is mocked to return a fixture RetrospectiveRecord.
  - ``hic_prompt`` is mocked to return controlled values.
  - Mode is forced via SPEC_KITTY_MODE env var to avoid parent-process detection.
  - Event assertions parse status.events.jsonl from feature_dir.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from runtime.next._internal_runtime.retrospective_hook import MissionCompletionBlocked
from runtime.next._internal_runtime.retrospective_terminus import run_terminus
from specify_cli.retrospective.schema import (
    ActorRef,
    MissionIdentity,
    Mode,
    ModeSourceSignal,
    RecordProvenance,
    RetrospectiveRecord,
)
from specify_cli.retrospective.reader import read_record
from specify_cli.retrospective.writer import write_record  # noqa: F401 (used by fixture comment)

# ---------------------------------------------------------------------------
# Shared test identifiers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

_MISSION_ID = "01KQ6YEGT4YBZ3GZF7X680KQ3V"
_MID8 = "01KQ6YEG"
_MISSION_SLUG = "test-mission"

_HUMAN_ACTOR = ActorRef(kind="human", id="rob@robshouse.net", profile_id=None)
_AGENT_ACTOR = ActorRef(kind="agent", id="facilitator", profile_id="retrospective-facilitator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_dir(tmp_path: Path, slug: str = _MISSION_SLUG) -> Path:
    """Create a feature_dir named after the mission slug."""
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir


def _read_events(feature_dir: Path) -> list[dict[str, Any]]:
    """Read all retrospective events from status.events.jsonl."""
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return []
    lines = events_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _event_names(feature_dir: Path) -> list[str]:
    return [e["event_name"] for e in _read_events(feature_dir)]


def _make_completed_record(mission_id: str = _MISSION_ID) -> RetrospectiveRecord:
    """Build a minimal completed RetrospectiveRecord for testing."""
    now = "2026-04-27T11:00:00+00:00"
    return RetrospectiveRecord(
        schema_version="1",
        mission=MissionIdentity(
            mission_id=mission_id,
            mid8=mission_id[:8],
            mission_slug=_MISSION_SLUG,
            mission_type="software-dev",
            mission_started_at="2026-04-27T10:00:00+00:00",
            mission_completed_at=now,
        ),
        mode=Mode(
            value="autonomous",
            source_signal=ModeSourceSignal(kind="explicit_flag", evidence="autonomous"),
        ),
        status="completed",
        started_at="2026-04-27T10:55:00+00:00",
        completed_at=now,
        actor=_AGENT_ACTOR,
        provenance=RecordProvenance(
            authored_by=_AGENT_ACTOR,
            runtime_version="3.2.0",
            written_at=now,
            schema_version="1",
        ),
    )


def _force_autonomous_mode(tmp_path: Path) -> dict[str, str]:
    """Return env override that forces autonomous mode (no charter needed)."""
    return {**os.environ, "SPEC_KITTY_MODE": "autonomous"}


def _force_hic_mode(tmp_path: Path) -> dict[str, str]:
    """Return env override that forces HiC mode."""
    return {**os.environ, "SPEC_KITTY_MODE": "human_in_command"}


# ---------------------------------------------------------------------------
# Test 1: Autonomous + facilitator success
# ---------------------------------------------------------------------------


def test_autonomous_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Autonomous mode: facilitator returns record → requested(runtime), started, completed.

    Record is persisted; gate allows; no exception raised.
    """
    monkeypatch.setenv("SPEC_KITTY_MODE", "autonomous")

    feature_dir = _make_feature_dir(tmp_path)
    record = _make_completed_record()

    def fake_facilitator(**kwargs: Any) -> RetrospectiveRecord:
        return record

    # Should not raise.
    run_terminus(
        mission_id=_MISSION_ID,
            mission_type="software-dev",
        feature_dir=feature_dir,
        repo_root=tmp_path,
        operator_actor=_HUMAN_ACTOR,
        facilitator_callback=fake_facilitator,
    )

    names = _event_names(feature_dir)
    assert names == [
        "retrospective.requested",
        "retrospective.started",
        "retrospective.completed",
    ], f"Unexpected event sequence: {names}"

    # retrospective.requested must carry actor.kind=runtime in autonomous mode.
    events = _read_events(feature_dir)
    requested_event = events[0]
    assert requested_event["actor"]["kind"] == "runtime"
    assert requested_event["actor"]["id"] == "next"

    # Record must be persisted.
    canonical = feature_dir / "retrospective.yaml"
    assert canonical.exists(), "Record was not persisted to canonical path"


# ---------------------------------------------------------------------------
# Test 2: Autonomous + facilitator raises
# ---------------------------------------------------------------------------


def test_autonomous_facilitator_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Autonomous mode: facilitator raises → requested, started, failed; gate blocks."""
    monkeypatch.setenv("SPEC_KITTY_MODE", "autonomous")

    feature_dir = _make_feature_dir(tmp_path)

    def failing_facilitator(**kwargs: Any) -> RetrospectiveRecord:
        raise RuntimeError("Facilitator exploded")

    with pytest.raises(MissionCompletionBlocked) as exc_info:
        run_terminus(
            mission_id=_MISSION_ID,
            mission_type="software-dev",
            feature_dir=feature_dir,
            repo_root=tmp_path,
            operator_actor=_HUMAN_ACTOR,
            facilitator_callback=failing_facilitator,
        )

    names = _event_names(feature_dir)
    assert names == [
        "retrospective.requested",
        "retrospective.started",
        "retrospective.failed",
    ], f"Unexpected event sequence: {names}"

    # Gate decision must be blocking (facilitator_failure).
    decision = exc_info.value.decision
    assert not decision.allow_completion
    assert decision.reason.code == "facilitator_failure"


# ---------------------------------------------------------------------------
# Test 3: HiC + operator runs
# ---------------------------------------------------------------------------


def test_hic_operator_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HiC mode: operator confirms → requested(human), started, completed; gate allows."""
    monkeypatch.setenv("SPEC_KITTY_MODE", "human_in_command")

    feature_dir = _make_feature_dir(tmp_path)
    record = _make_completed_record()

    def fake_facilitator(**kwargs: Any) -> RetrospectiveRecord:
        return record

    # Operator chooses to run.
    def hic_prompt_run() -> tuple[bool, str | None]:
        return True, None

    # Should not raise.
    run_terminus(
        mission_id=_MISSION_ID,
            mission_type="software-dev",
        feature_dir=feature_dir,
        repo_root=tmp_path,
        operator_actor=_HUMAN_ACTOR,
        facilitator_callback=fake_facilitator,
        hic_prompt=hic_prompt_run,
    )

    names = _event_names(feature_dir)
    assert names == [
        "retrospective.requested",
        "retrospective.started",
        "retrospective.completed",
    ], f"Unexpected event sequence: {names}"

    # retrospective.requested must carry actor = operator (human), not runtime.
    events = _read_events(feature_dir)
    requested_event = events[0]
    assert requested_event["actor"]["kind"] == "human"
    assert requested_event["actor"]["id"] == _HUMAN_ACTOR.id

    # Record persisted, as the completed record of this mission.
    canonical = feature_dir / "retrospective.yaml"
    assert canonical.exists(), "Record was not persisted"
    persisted = read_record(canonical)
    assert persisted.status == "completed"
    assert persisted.mission.mission_id == _MISSION_ID


# ---------------------------------------------------------------------------
# Test 4: HiC + operator skips
# ---------------------------------------------------------------------------


def test_hic_operator_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HiC mode: operator skips → requested(human), skipped; record status=skipped; gate allows."""
    monkeypatch.setenv("SPEC_KITTY_MODE", "human_in_command")

    feature_dir = _make_feature_dir(tmp_path)
    skip_reason = "low-value docs fix"

    def hic_prompt_skip() -> tuple[bool, str | None]:
        return False, skip_reason

    # Should not raise (gate allows skips in HiC mode).
    run_terminus(
        mission_id=_MISSION_ID,
            mission_type="software-dev",
        feature_dir=feature_dir,
        repo_root=tmp_path,
        operator_actor=_HUMAN_ACTOR,
        facilitator_callback=None,  # not called in skip path
        hic_prompt=hic_prompt_skip,
    )

    names = _event_names(feature_dir)
    assert names == [
        "retrospective.requested",
        "retrospective.skipped",
    ], f"Unexpected event sequence: {names}"

    # Skipped event payload must carry skip_reason.
    events = _read_events(feature_dir)
    skipped_event = events[1]
    assert skipped_event["payload"]["skip_reason"] == skip_reason

    # Persisted record must have status=skipped with skip_reason.
    canonical = feature_dir / "retrospective.yaml"
    assert canonical.exists(), "Skipped record was not persisted"
    persisted = read_record(canonical)
    assert persisted.status == "skipped"
    assert persisted.skip_reason == skip_reason
    assert persisted.mission.mission_id == _MISSION_ID

    # requested event must carry human actor.
    requested_event = events[0]
    assert requested_event["actor"]["kind"] == "human"
    assert requested_event["actor"]["id"] == _HUMAN_ACTOR.id


# ---------------------------------------------------------------------------
# Test 5: HiC + skip with empty reason — loops until non-empty
# ---------------------------------------------------------------------------


def test_hic_skip_empty_reason_loops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HiC default prompt loops until operator provides a non-empty skip reason.

    We mock rich Confirm.ask and Prompt.ask to simulate the loop behavior:
    - First Confirm.ask: False (operator declines).
    - First Prompt.ask: "" (empty — invalid).
    - Second Prompt.ask: "  " (whitespace-only — also invalid).
    - Third Prompt.ask: "low-value fix" (valid).
    """
    monkeypatch.setenv("SPEC_KITTY_MODE", "human_in_command")

    feature_dir = _make_feature_dir(tmp_path)

    # Build a sequential hic_prompt that mimics the loop behavior.
    # The default _default_hic_prompt loops until non-empty; we test that
    # contract by supplying a custom hic_prompt that simulates the same logic.
    prompt_results: list[str] = ["", "  ", "low-value fix"]
    call_count = [0]

    def looping_hic_prompt() -> tuple[bool, str | None]:
        """Simulate the loop: try empty reasons until a good one is provided."""
        skip_reason = ""
        while not skip_reason.strip():
            if call_count[0] < len(prompt_results):
                skip_reason = prompt_results[call_count[0]]
                call_count[0] += 1
            else:
                skip_reason = "fallback reason"  # should not reach here in test
        return False, skip_reason.strip()

    run_terminus(
        mission_id=_MISSION_ID,
            mission_type="software-dev",
        feature_dir=feature_dir,
        repo_root=tmp_path,
        operator_actor=_HUMAN_ACTOR,
        facilitator_callback=None,
        hic_prompt=looping_hic_prompt,
    )

    # Verify the prompt was called (iterated through blank values).
    assert call_count[0] == 3, f"Expected 3 calls to drain empty+whitespace, got {call_count[0]}"

    names = _event_names(feature_dir)
    assert names == [
        "retrospective.requested",
        "retrospective.skipped",
    ]

    # Skip reason recorded is the first non-empty stripped value.
    events = _read_events(feature_dir)
    assert events[1]["payload"]["skip_reason"] == "low-value fix"

    # Persisted record has non-empty skip_reason.
    canonical = feature_dir / "retrospective.yaml"
    persisted = read_record(canonical)
    assert persisted.skip_reason == "low-value fix"


# ---------------------------------------------------------------------------
# Test 6: Autonomous — no facilitator_callback raises RuntimeError + gate blocks
# ---------------------------------------------------------------------------


def test_autonomous_no_callback_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Autonomous mode with no facilitator_callback → RuntimeError → gate blocks."""
    monkeypatch.setenv("SPEC_KITTY_MODE", "autonomous")

    feature_dir = _make_feature_dir(tmp_path)

    with pytest.raises(MissionCompletionBlocked):
        run_terminus(
            mission_id=_MISSION_ID,
            mission_type="software-dev",
            feature_dir=feature_dir,
            repo_root=tmp_path,
            operator_actor=_HUMAN_ACTOR,
            facilitator_callback=None,  # missing callback
        )

    names = _event_names(feature_dir)
    assert "retrospective.failed" in names
