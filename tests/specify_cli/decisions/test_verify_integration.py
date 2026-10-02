"""Integration tests for specify_cli.decisions.verify — end-to-end drift detection.

Constructs realistic mission directories with mixed decision states and verifies
the full cross-check pipeline from file I/O through to structured findings.
"""

from __future__ import annotations

import contextlib
import json
from kernel.clock import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from specify_cli.decisions.models import (
    DecisionIndex,
    DecisionStatus,
    IndexEntry,
    OriginFlow,
)
from specify_cli.decisions.store import save_index, write_artifact
from specify_cli.decisions.verify import verify
from tests._factories.coord_mission import make_fork_fixture

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

ULID_A = "01AAAAAAAAAAAAAAAAAAAAAAAA"
ULID_B = "01BBBBBBBBBBBBBBBBBBBBBBBB"
ULID_C = "01CCCCCCCCCCCCCCCCCCCCCCCC"
ULID_UNKNOWN = "01ZZZZZZZZZZZZZZZZZZZZZZZZ"

MISSION_ID = "01KPWT8PNY8683QX3WBW6VXYM7"
MISSION_SLUG = "test-mission"

T0 = datetime(2026, 4, 23, 10, 0, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=60)
T2 = T0 + timedelta(seconds=120)


def _entry(
    decision_id: str,
    status: DecisionStatus,
    created_at: datetime = T0,
) -> IndexEntry:
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=OriginFlow.SPECIFY,
        step_id=f"step-{decision_id[:4]}",
        input_key="some_key",
        question="What should we do?",
        status=status,
        created_at=created_at,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
    )


def _sentinel(ulid: str, text: str = "some clarification needed") -> str:
    return f"[NEEDS CLARIFICATION: {text}] <!-- decision_id: {ulid} -->"


def _build_mission(
    tmp_path: Path,
    entries: list[IndexEntry],
    spec_content: str = "",
    plan_content: str = "",
) -> None:
    """Write decisions/index.json, DM artifacts, spec.md, and plan.md."""
    idx = DecisionIndex(mission_id=MISSION_ID, entries=tuple(entries))
    save_index(tmp_path, idx)
    for entry in entries:
        write_artifact(tmp_path, entry)
    if spec_content:
        (tmp_path / "spec.md").write_text(spec_content, encoding="utf-8")
    if plan_content:
        (tmp_path / "plan.md").write_text(plan_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — Mixed state: drift with all three finding kinds
# ---------------------------------------------------------------------------


def test_mixed_state_drift(tmp_path: Path) -> None:
    """End-to-end: one clean match, one missing marker, one stale marker.

    Mission layout::

        decisions/
            index.json   (3 entries)
            DM-<A>.md    (DEFERRED — has matching marker in spec.md)
            DM-<B>.md    (DEFERRED — no marker anywhere → DEFERRED_WITHOUT_MARKER)
            DM-<C>.md    (CANCELED — has stale marker in plan.md → STALE_MARKER)
        spec.md          (sentinel for A)
        plan.md          (stale sentinel for C)
    """
    entry_a = _entry(ULID_A, DecisionStatus.DEFERRED, T0)
    entry_b = _entry(ULID_B, DecisionStatus.DEFERRED, T1)
    entry_c = _entry(ULID_C, DecisionStatus.CANCELED, T2)

    spec_content = f"# Mission spec\n\n{_sentinel(ULID_A)}\n"
    plan_content = f"# Plan\n\n{_sentinel(ULID_C)}\n"

    _build_mission(tmp_path, [entry_a, entry_b, entry_c], spec_content, plan_content)

    result = verify(tmp_path, MISSION_SLUG)

    # Overall status
    assert result.status == "drift"

    # Counts
    assert result.deferred_count == 2  # A and B are deferred
    assert result.marker_count == 2  # one in spec.md, one in plan.md

    # Exactly 2 findings: DEFERRED_WITHOUT_MARKER (B) + STALE_MARKER (C)
    assert len(result.findings) == 2

    kinds = {f.kind for f in result.findings}
    assert "DEFERRED_WITHOUT_MARKER" in kinds
    assert "STALE_MARKER" in kinds
    assert "MARKER_WITHOUT_DECISION" not in kinds

    # Check DEFERRED_WITHOUT_MARKER references B
    dwm = next(f for f in result.findings if f.kind == "DEFERRED_WITHOUT_MARKER")
    assert dwm.decision_id_or_ref == ULID_B

    # Check STALE_MARKER references C with plan.md location
    stale = next(f for f in result.findings if f.kind == "STALE_MARKER")
    assert stale.decision_id_or_ref == ULID_C
    assert stale.location is not None
    assert stale.location.startswith("plan.md:L")
    assert "canceled" in (stale.detail or "")


# ---------------------------------------------------------------------------
# Test 2 — All decisions resolved, no markers → clean
# ---------------------------------------------------------------------------


def test_all_resolved_no_markers(tmp_path: Path) -> None:
    """All decisions resolved and no markers → status=clean, counts=0."""
    entry_a = _entry(ULID_A, DecisionStatus.RESOLVED, T0)
    entry_b = _entry(ULID_B, DecisionStatus.RESOLVED, T1)

    _build_mission(tmp_path, [entry_a, entry_b])
    # No spec.md or plan.md created

    result = verify(tmp_path, MISSION_SLUG)

    assert result.status == "clean"
    assert result.findings == ()
    assert result.deferred_count == 0
    assert result.marker_count == 0


def test_resolved_decision_marker_is_not_drift(tmp_path: Path) -> None:
    """Resolved decision with a remaining marker is accepted as closed."""
    entry_a = _entry(ULID_A, DecisionStatus.RESOLVED, T0)
    spec_content = f"# Spec\n\n{_sentinel(ULID_A)}\n"

    _build_mission(tmp_path, [entry_a], spec_content)

    result = verify(tmp_path, MISSION_SLUG)

    assert result.status == "clean"
    assert result.findings == ()
    assert result.deferred_count == 0
    assert result.marker_count == 1


# ---------------------------------------------------------------------------
# Test 3 — MARKER_WITHOUT_DECISION
# ---------------------------------------------------------------------------


def test_marker_without_decision(tmp_path: Path) -> None:
    """spec.md contains a sentinel for a completely unknown decision_id."""
    entry_a = _entry(ULID_A, DecisionStatus.RESOLVED, T0)
    spec_content = f"# Spec\n\n{_sentinel(ULID_UNKNOWN)}\n"

    _build_mission(tmp_path, [entry_a], spec_content)

    result = verify(tmp_path, MISSION_SLUG)

    assert result.status == "drift"
    assert result.marker_count == 1

    mwd_findings = [f for f in result.findings if f.kind == "MARKER_WITHOUT_DECISION"]
    assert len(mwd_findings) == 1
    assert mwd_findings[0].decision_id_or_ref == ULID_UNKNOWN
    assert mwd_findings[0].location is not None
    assert mwd_findings[0].location.startswith("spec.md:L")


# ---------------------------------------------------------------------------
# WP17 (T090 R14, FR-010a, contract rule 5, #5023) -- a forked decision
# stream is a distinct, honest-verify failure, proven through the real CLI
# and parametrized over three of the NFR-002 fork fixtures (post-tasks squad
# R-m1): (a) root-uncommitted/coordination-untracked, (b) both committed,
# (c) a fresh clone.
# ---------------------------------------------------------------------------

_runner = CliRunner()


@pytest.mark.parametrize("shape", ["root_uncommitted_coord_untracked", "both_committed", "fresh_clone"])
def test_verify_not_clean_on_forked_log(tmp_path: Path, shape: str) -> None:
    """Red at base: ``decision verify`` only cross-checks markers against the
    ledger -- it has no concept of a forked decision-event stream, so it
    exits 0 (clean) on a Mission that is actively losing decisions to a
    fork. Fixed: it exits 1 with ``DECISION_LOG_FORKED`` in ``findings``,
    for every one of the three fixture shapes (a fresh clone included --
    the detector is read-only and reads the coordination ref)."""
    fixture = make_fork_fixture(tmp_path, shape, MissionTopology.COORD)  # type: ignore[arg-type]
    cwd = fixture.clone_root if fixture.clone_root is not None else fixture.repo_root

    with contextlib.chdir(cwd):
        result = _runner.invoke(
            root_app,
            ["agent", "decision", "verify", "--mission", fixture.mission_dir_name, "--json"],
            catch_exceptions=False,
        )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    kinds = {f["kind"] for f in payload["findings"]}
    assert "DECISION_LOG_FORKED" in kinds, payload
    assert payload["status"] == "drift"
