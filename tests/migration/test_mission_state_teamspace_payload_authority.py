"""The TeamSpace dry-run has ONE authority for its ``WPStatusChanged`` payload (#6449).

The dry-run synthesizes a TeamSpace replay envelope per ``status.events.jsonl``
row. Until this mission it hand-built the envelope ``payload`` as a plain dict,
so the shape could drift from ``spec_kitty_events.status.StatusTransitionPayload``
without anything noticing (the only backstop was a conformance report after the
fact). These tests pin the fix:

1. **Byte parity with a real transition** -- a transition emitted through the
   public status API writes a durable row; the dry-run's synthesized payload must
   be the projection of *that row* onto the contract model's field set, byte for
   byte. This is deliberately not a builder-vs-builder comparison.
2. **Construction authority** -- the dry-run reaches the payload through
   ``specify_cli.status.build_status_event_payload``; substituting it on the
   migration module must be observable.
3. **Non-raising rejection** -- a row the contract model cannot represent is
   reported as ``PAYLOAD_INVALID`` and the run still completes, while a valid row
   on the same fixture is still mapped (the positive control).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events.conformance import validate_event
from spec_kitty_events.status import StatusTransitionPayload

from specify_cli.migration import mission_state
from specify_cli.migration.mission_state import teamspace_dry_run
from specify_cli.status import store
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest
from specify_cli.status.reducer import materialize
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01M68JCJ9ACY7K2HH4TVY8G19V"
_MISSION_SLUG = "042-demo"

#: Contract fields whose values the dry-run overrides for historical rows. A
#: parity fixture must avoid them (see contracts/wp-status-changed-payload.md).
_HISTORICAL_OVERRIDE_FIELDS = frozenset({"from_lane", "evidence"})


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> Path:
    """A minimal committed mission repo, the shape the dry-run expects."""
    repo = tmp_path / "repo"
    mission = repo / "kitty-specs" / _MISSION_SLUG
    tasks = mission / "tasks"
    tasks.mkdir(parents=True)
    (repo / "README.md").write_text("# demo mission repo\n", encoding="utf-8")
    (mission / "spec.md").write_text("# Demo\n\nFixture mission.\n", encoding="utf-8")
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "friendly_name": "Demo",
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mission_type": "software-dev",
                "slug": _MISSION_SLUG,
                "status_phase": 1,
                "target_branch": "main",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (tasks / "WP01-task.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Task\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    _run_git(repo, "init", "-q", "-b", "main")
    _run_git(repo, "add", "-A")
    _run_git(repo, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "-q", "-m", "fixture")
    return repo


def _emit_real_transitions(repo: Path) -> Path:
    """Drive ``planned -> claimed -> in_progress`` through the public status API."""
    mission = repo / "kitty-specs" / _MISSION_SLUG
    seed_wp_to_planned(mission, "WP01", slug=_MISSION_SLUG)
    for lane in ("claimed", "in_progress"):
        emit_status_transition(
            TransitionRequest(
                feature_dir=mission,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane=lane,
                actor="claude",
                repo_root=repo,
            )
        )
    return mission


def _durable_rows(mission: Path) -> list[dict[str, Any]]:
    text = (mission / "status.events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


@contextmanager
def _captured_payloads() -> Iterator[list[dict[str, Any]]]:
    """Record the payload the dry-run hands to the envelope builder."""
    captured: list[dict[str, Any]] = []
    real_builder = mission_state._build_teamspace_envelope

    def _recording_builder(**kwargs: Any) -> Any:
        captured.append(kwargs["payload"])
        return real_builder(**kwargs)

    original = mission_state._build_teamspace_envelope
    mission_state._build_teamspace_envelope = _recording_builder  # type: ignore[assignment]
    try:
        yield captured
    finally:
        mission_state._build_teamspace_envelope = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# T006.1 -- byte parity with a real transition
# ---------------------------------------------------------------------------


def test_dry_run_payload_is_byte_identical_to_a_real_transition(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    mission = _emit_real_transitions(repo)

    with _captured_payloads() as captured:
        report = teamspace_dry_run(repo)

    assert report.valid, report.errors
    rows = _durable_rows(mission)
    assert report.envelope_count == len(captured) == len(rows)
    # The fixture really exercises both shapes: a legacy row the reader has to
    # backfill identity for, and rows that carry mission_id in the row itself.
    assert "mission_id" not in rows[0]
    assert all(row["mission_id"] == _MISSION_ID for row in rows[1:])
    for payload, row in zip(captured, rows, strict=True):
        # The oracle is the durable row itself: project it onto the contract
        # model's field set. No model construction, no builder call -- this is
        # what the row says the transition was.
        expected = {name: row[name] for name in StatusTransitionPayload.model_fields if name in row}
        if "mission_id" not in row:
            # ``status.store.read_events`` backfills mission_id from meta.json
            # for a legacy row; the payload carries the resolved identity.
            expected["mission_id"] = _MISSION_ID
        assert _canonical(payload) == _canonical(expected), row["event_id"]


def test_dry_run_payload_is_valid_conformance_and_carries_the_mission_id(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _emit_real_transitions(repo)

    with _captured_payloads() as captured:
        report = teamspace_dry_run(repo)

    assert report.valid, report.errors
    for payload in captured:
        assert payload["mission_id"] == _MISSION_ID
        assert validate_event(payload, "WPStatusChanged").valid
    # positive control on the same fixture: the fixture really does exercise the
    # lane chain, so a payload with no mission_id would be a real drop, not an
    # artifact of a fixture that never sets one.
    assert captured[-1]["from_lane"] == "claimed"
    assert captured[-1]["to_lane"] == "in_progress"


# ---------------------------------------------------------------------------
# T006.2 -- construction authority
# ---------------------------------------------------------------------------


def test_dry_run_builds_the_payload_through_the_facade_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _emit_real_transitions(repo)
    calls: list[dict[str, Any]] = []
    real_build = mission_state.build_status_event_payload

    def _spy(event: StatusEvent, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return real_build(event, **kwargs)

    monkeypatch.setattr(mission_state, "build_status_event_payload", _spy)

    report = teamspace_dry_run(repo)

    assert report.valid, report.errors
    assert len(calls) == report.envelope_count
    assert all("from_lane" in call["overrides"] for call in calls)


def test_historical_overrides_are_the_only_divergence_from_the_row(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    mission = _emit_real_transitions(repo)
    # A historical row that still records the pre-queue ``in_progress -> in_review``
    # edge, which the dry-run rewrites to ``for_review``.
    legacy = StatusEvent(
        event_id="01KQHRB8GCFJAX7HM4ZY52AQGT",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.IN_REVIEW,
        at="2026-01-02T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        reason="ready for review",
    )
    store.append_events_atomic(mission, [legacy])
    materialize(mission)

    with _captured_payloads() as captured:
        report = teamspace_dry_run(repo)

    assert report.valid, report.errors
    rewritten = next(payload for payload in captured if payload["from_lane"] == "for_review")
    assert rewritten["to_lane"] == "in_review"
    row = _durable_rows(mission)[-1]
    # every field outside the two documented overrides still equals the row
    for name in StatusTransitionPayload.model_fields:
        if name in _HISTORICAL_OVERRIDE_FIELDS or name not in row:
            continue
        assert rewritten[name] == row[name], name


# ---------------------------------------------------------------------------
# T006.3 -- a rejected row is reported, never raised
# ---------------------------------------------------------------------------


def test_model_rejected_row_is_reported_while_valid_rows_still_map(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    mission = _emit_real_transitions(repo)
    rejected_id = "01KQHRB8GCFJAX7HM4ZY52AQG5"
    # ``force=True`` without a reason: the local StatusEvent permits it, the
    # contract model rejects it. This is the row class the dry-run must report.
    store.append_events_atomic(
        mission,
        [
            StatusEvent(
                event_id=rejected_id,
                mission_slug=_MISSION_SLUG,
                mission_id=_MISSION_ID,
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.PLANNED,
                at="2026-01-03T00:00:00+00:00",
                actor="claude",
                force=True,
                execution_mode="worktree",
            )
        ],
    )
    materialize(mission)

    report = teamspace_dry_run(repo)

    assert not report.valid
    # a rejected row produces no envelope, so the count still matches the mappings
    assert report.envelope_count == len(report.row_mappings)
    payload_errors = [error for error in report.errors if error["error"] == "PAYLOAD_INVALID"]
    assert [error["event_id"] for error in payload_errors] == [rejected_id]
    assert payload_errors[0]["model_violations"]
    # positive control on the same fixture: the valid rows are still mapped, so
    # the rejection did not abort the run.
    assert {mapping.source_event_id for mapping in report.row_mappings} == {
        row["event_id"] for row in _durable_rows(mission) if row["event_id"] != rejected_id
    }
