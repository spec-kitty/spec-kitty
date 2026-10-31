"""Core consumers of the optional ``Event.lamport_clock`` are clock-agnostic.

Issue #6414 (parent epic #6411). ``spec-kitty-events`` 11.0.0 made
``Event.lamport_clock`` optional and turned ``status_event_sort_key`` into a
4-tuple. Core imports none of that ordering surface, and the readers that *do*
see status rows fold them by wall clock. This module pins both claims, so the
audit recorded in ``docs/development/reference/optional-lamport-clock-consumers.md``
cannot quietly become false.

Each test name appears in that page's consumer table as its proof.
"""

from __future__ import annotations

import json
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events import Event
from spec_kitty_events.ordering import canonical_order_key
from spec_kitty_events.status import reduce_status_events

from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.decisions.models import DecisionOpenResponse
from specify_cli.migration.mission_state import _build_teamspace_envelope, teamspace_dry_run
from specify_cli.retrospective.summary import classify_mission_record
from specify_cli.state.contract import STATE_SURFACES
from specify_cli.status import EVENTS_FILENAME, materialize
from specify_cli.status.event_log_merge import merge_event_payloads
from specify_cli.status.lifecycle_events import persist_lifecycle_event_local, read_lifecycle_events

pytestmark = pytest.mark.fast

_REPLAY_ROOT = files("spec_kitty_events") / "conformance/fixtures/status_diary/replay"
_FIXTURE = "status_diary_every_lane"

#: Identifiers the audit page must account for. Kept here (not in the page) so the
#: guard is a test, not a prose promise.
_AUDITED_IDENTIFIERS = (
    "lamport_clock",
    "status_event_sort_key",
    "canonical_order_key",
    "node_order_key",
    "total_order_key",
    "work_replay",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUDIT_PAGE = _REPO_ROOT / "docs/development/reference/optional-lamport-clock-consumers.md"


def _diary_rows() -> list[dict[str, Any]]:
    text = (_REPLAY_ROOT / f"{_FIXTURE}.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _write_feature_dir(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    golden = json.loads((_REPLAY_ROOT / f"{_FIXTURE}_output.json").read_text(encoding="utf-8"))
    feature_dir = tmp_path / str(golden["mission_slug"])
    feature_dir.mkdir(parents=True)
    (feature_dir / EVENTS_FILENAME).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_number": int(golden["mission_number"]),
                "mission_slug": golden["mission_slug"],
                "mission_type": golden["mission_type"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return feature_dir


def test_mixed_stream_materializes_identically(tmp_path: Path) -> None:
    """A clock on a status row cannot change the CLI's materialized lane state."""
    rows = _diary_rows()

    plain_dir = _write_feature_dir(tmp_path / "plain", rows)
    materialize(plain_dir)
    plain = (plain_dir / "status.json").read_text(encoding="utf-8")

    # Alternating rows: a real clock, an explicit null, absent. All three shapes
    # must reduce to the same state, because the reader never reads the field.
    mixed: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index % 3 == 0:
            mixed.append({**row, "lamport_clock": index + 1})
        elif index % 3 == 1:
            mixed.append({**row, "lamport_clock": None})
        else:
            mixed.append(dict(row))

    mixed_dir = _write_feature_dir(tmp_path / "mixed", mixed)
    materialize(mixed_dir)
    with_clock = (mixed_dir / "status.json").read_text(encoding="utf-8")

    assert with_clock == plain


def test_dependency_lamport_reducer_handles_mixed_stream() -> None:
    """The 4-tuple key + unclocked-singleton grouping survives a mixed stream."""
    events = [
        Event.model_validate(
            {
                "event_id": event_id,
                "event_type": "WPStatusChanged",
                "aggregate_id": wp_id,
                "payload": {
                    "mission_slug": "041-lamport-audit",
                    "wp_id": wp_id,
                    "from_lane": from_lane,
                    "to_lane": to_lane,
                    "actor": "implementer",
                    "execution_mode": "worktree",
                },
                "timestamp": timestamp,
                "build_id": "b1",
                "node_id": "n1",
                "lamport_clock": clock,
                "project_uuid": "8a1f1b18-8a54-4e59-9b2f-4f4a1a7f5c11",
                "correlation_id": "01JAAAA0000000000000000005",
            }
        )
        for event_id, wp_id, from_lane, to_lane, timestamp, clock in (
            ("01JAAAA0000000000000000010", "WP01", None, "planned", "2026-01-01T00:00:00+00:00", None),
            ("01JAAAA0000000000000000011", "WP01", "planned", "claimed", "2026-01-01T00:01:00+00:00", 1),
            ("01JAAAA0000000000000000012", "WP02", None, "planned", "2026-01-01T00:02:00+00:00", None),
            ("01JAAAA0000000000000000013", "WP02", "planned", "blocked", "2026-01-01T00:03:00+00:00", 2),
        )
    ]

    forward = reduce_status_events(events)
    backward = reduce_status_events(list(reversed(events)))

    assert forward.wp_states["WP01"].current_lane.value == "claimed"
    assert forward.wp_states["WP02"].current_lane.value == "blocked"
    assert forward.model_dump() == backward.model_dump()
    assert {event.lamport_clock for event in events} == {None, 1, 2}


def _git_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    (path / ".kittify").mkdir(exist_ok=True)


def _mission_row(event_id: str, wp_id: str, at: str, clock: int | None) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "mission_slug": "041-lamport-audit",
        "wp_id": wp_id,
        "from_lane": "planned",
        "to_lane": "claimed",
        "at": at,
        "actor": "implementer",
        "force": False,
        "execution_mode": "worktree",
        "lamport_clock": clock,
    }


@pytest.mark.git_repo
def test_dry_run_discards_the_source_clock(tmp_path: Path) -> None:
    """Synthesized replay envelopes depend on ``(at, event_id)`` only, not on a source clock."""
    rows = [
        _mission_row("01JAAAA0000000000000000020", "WP01", "2026-01-01T00:00:00+00:00", None),
        _mission_row("01JAAAA0000000000000000021", "WP02", "2026-01-01T00:01:00+00:00", None),
    ]
    # The same two rows carrying clocks that AGREE with nothing: the later row
    # gets the lower clock, so any consumer reading the source clock would reorder.
    clocked = [
        {**rows[0], "lamport_clock": 99},
        {**rows[1], "lamport_clock": 1},
    ]

    # Same checkout name in both runs: the dry-run derives ``repo_slug`` from it,
    # so a differing directory name would change every envelope hash by itself.
    plain_repo = tmp_path / "plain" / "repo"
    clocked_repo = tmp_path / "clocked" / "repo"
    for repo, payload in ((plain_repo, rows), (clocked_repo, clocked)):
        _git_init(repo)
        mission_dir = repo / "kitty-specs" / "041-lamport-audit"
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(
            json.dumps({"mission_number": "041", "mission_slug": "041-lamport-audit", "mission_type": "software-dev"}) + "\n",
            encoding="utf-8",
        )
        (mission_dir / EVENTS_FILENAME).write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in payload),
            encoding="utf-8",
        )

    plain_report = teamspace_dry_run(plain_repo, scan_root=plain_repo / "kitty-specs")
    clocked_report = teamspace_dry_run(clocked_repo, scan_root=clocked_repo / "kitty-specs")

    assert plain_report.valid, plain_report.errors
    assert clocked_report.valid, clocked_report.errors
    assert plain_report.envelope_count == clocked_report.envelope_count == 2
    # Identical envelope hashes prove the source clock never reaches the output.
    assert [m.envelope_sha256 for m in plain_report.row_mappings] == [m.envelope_sha256 for m in clocked_report.row_mappings]
    # ... and the emission order is the source ``(at, event_id)`` order.
    assert [m.source_event_id for m in clocked_report.row_mappings] == [
        "01JAAAA0000000000000000020",
        "01JAAAA0000000000000000021",
    ]


@pytest.mark.parametrize("clock", [1, 7])
def test_teamspace_envelope_builder_requires_a_clocked_index(clock: int) -> None:
    """The dry-run builder always supplies an int, so its local model may require one."""
    envelope = _build_teamspace_envelope(
        event_id="01JAAAA0000000000000000020",
        event_type="WPStatusChanged",
        aggregate_id="WP01",
        aggregate_type="WorkPackage",
        payload={"wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed"},
        timestamp="2026-01-01T00:00:00+00:00",
        build_id="mission-state-dry-run",
        node_id="mission-state-dry-run",
        lamport_clock=clock,
        project_uuid="8a1f1b18-8a54-4e9b-2f4f-4a1a7f5c11aa",
        project_slug="demo",
        repo_slug=None,
        correlation_id="01JAAAA0000000000000000005",
    ).model_dump()

    assert envelope["lamport_clock"] == clock
    assert canonical_order_key(Event.model_validate(envelope))[0] == 1  # clocked


@pytest.mark.git_repo
def test_live_lifecycle_envelope_carries_no_clock(tmp_path: Path) -> None:
    """The live lifecycle appender emits an unclocked row: the contract's "no clock"."""
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_dir = repo / "kitty-specs" / "041-lamport-audit"
    feature_dir.mkdir(parents=True)
    log_path = feature_dir / EVENTS_FILENAME

    persist_lifecycle_event_local(
        log_path,
        "WPCreated",
        {"wp_id": "WP01"},
        aggregate_id="WP01",
        aggregate_type="WorkPackage",
        project_uuid="8a1f1b18-8a54-4e9b-2f4f-4a1a7f5c11aa",
        project_slug="demo",
    )

    rows = read_lifecycle_events(log_path)
    assert len(rows) == 1
    assert "lamport_clock" not in rows[0]


def test_merge_event_payloads_ignores_clock() -> None:
    """The event-log merge orders by ``(at, event_id)`` and keeps every row key."""
    early = {"event_id": "01JAAAA0000000000000000030", "at": "2026-01-01T00:00:00+00:00", "lamport_clock": 9}
    late = {"event_id": "01JAAAA0000000000000000031", "at": "2026-01-01T00:01:00+00:00", "lamport_clock": 1}

    merged = merge_event_payloads([late], [early])

    assert [row["event_id"] for row in merged] == [early["event_id"], late["event_id"]]
    assert [row["lamport_clock"] for row in merged] == [9, 1]


def test_state_contract_lamport_rows_are_retired_paths() -> None:
    """The contract's ``lamport_clock`` surfaces are retired files, not the envelope field."""
    latest = {surface.name: surface for surface in STATE_SURFACES}

    assert set(latest) >= {"lamport_clock", "legacy_lamport_clock"}
    for name in ("lamport_clock", "legacy_lamport_clock"):
        surface = latest[name]
        assert surface.deprecated is True
        assert surface.path_pattern.startswith("~/.spec-kitty/")
        assert surface.owner_module == "legacy"


def _write_retrospective_log(feature_dir: Path, rows: list[dict[str, Any]]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / EVENTS_FILENAME).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.mark.parametrize(("clock", "expected"), [(None, "missing"), ("not-an-int", "missing"), (3, "failed")])
def test_retrospective_clock_reads_tolerate_null(tmp_path: Path, clock: object, expected: str) -> None:
    """The retrospective log's own ``lamport`` may be null or junk: it falls back to 0."""
    feature_dir = tmp_path / "retro"
    _write_retrospective_log(
        feature_dir,
        [
            {"type": "RetrospectiveCaptured", "lamport": 1, "event_id": "01JAAAA0000000000000000040"},
            {"type": "RetrospectiveCaptureFailed", "lamport": clock, "event_id": "01JAAAA0000000000000000041"},
        ],
    )

    # No exception either way: null and junk fall back to 0 (never outranking the
    # real clock of 1), while a real 3 does outrank it.
    assert classify_mission_record(feature_dir) == expected


def test_decision_event_lamport_is_an_optional_passthrough() -> None:
    """``event_lamport`` is nullable on the wire and the contract gate accepts both."""
    response = DecisionOpenResponse(
        decision_id="DP01",
        idempotent=True,
        mission_id="01M68ZMFGV0P0XF1B4JFMH82M8",
        artifact_path="kitty-specs/041-lamport-audit/decisions/DP01.yaml",
        event_lamport=None,
    )
    assert response.event_lamport is None

    payload = {
        "mission_slug": "041-lamport-audit",
        "mission_id": response.mission_id,
        "decision_id": response.decision_id,
        "status": "open",
        "idempotent": response.idempotent,
        "artifact_path": response.artifact_path,
        "event_lamport": response.event_lamport,
    }
    validate_outbound_payload(dict(payload), "orchestrator_api")
    validate_outbound_payload(dict(payload, event_lamport=7), "orchestrator_api")


def test_test_probe_tolerates_missing_clock() -> None:
    """The coordination probe reads a row clock as ``int | None``, never a bare int."""
    from tests._factories.coord_mission import _row_lamport

    assert _row_lamport({"event_id": "A", "lamport_clock": 2}) == 2
    assert _row_lamport({"event_id": "B", "lamport_clock": None}) is None
    assert _row_lamport({"event_id": "C"}) is None
    assert _row_lamport({"event_id": "D", "payload": {"event_lamport": 5}}) == 5


def test_inventory_lists_every_core_consumer() -> None:
    """A new clock/ordering reference in ``src/`` fails until the audit page lists it."""
    src_root = _REPO_ROOT / "src"
    assert src_root.is_dir(), f"expected a source tree at {src_root}"

    hits: dict[str, set[str]] = {}
    for path in sorted(src_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        found = {identifier for identifier in _AUDITED_IDENTIFIERS if identifier in text}
        if found:
            hits[path.relative_to(_REPO_ROOT).as_posix()] = found

    assert hits, "expected at least one core reference to the audited identifiers"

    page = _AUDIT_PAGE.read_text(encoding="utf-8")
    unlisted = sorted(path for path in hits if path not in page)
    assert not unlisted, (
        "these core files reference the optional Lamport clock or the events ordering "
        "surface but are not in the audit page: "
        f"{unlisted}. Add a row with a verdict and a proof to {_AUDIT_PAGE.as_posix()}."
    )
