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

from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.decisions.models import DecisionOpenResponse
from specify_cli.retrospective.summary import classify_mission_record
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


def _git_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    (path / ".kittify").mkdir(exist_ok=True)


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
