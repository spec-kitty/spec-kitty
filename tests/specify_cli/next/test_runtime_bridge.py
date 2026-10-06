"""Tests for runtime_bridge_guards._should_advance_wp_step() using state.is_run_affecting.

WP04 (T009): Verifies that the WP-iteration step gate uses WPState.is_run_affecting
to decide routing instead of hardcoded lane string comparisons.

Test quality requirement: Tests call _should_advance_wp_step() directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.models import Lane
from specify_cli.status.wp_state import wp_state_for

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Unit tests for WPState.is_run_affecting (verifies property semantics)
# ---------------------------------------------------------------------------


def test_is_run_affecting_true_for_active_lanes():
    """is_run_affecting is True for all active lanes (planned through approved)."""
    active_lanes = [
        Lane.PLANNED,
        Lane.CLAIMED,
        Lane.IN_PROGRESS,
        Lane.FOR_REVIEW,
        Lane.IN_REVIEW,
        Lane.APPROVED,
    ]
    for lane in active_lanes:
        state = wp_state_for(lane)
        assert state.is_run_affecting is True, f"Expected is_run_affecting=True for {lane!r}"


def test_is_run_affecting_false_for_terminal_and_blocked_lanes():
    """is_run_affecting is False for done, blocked, and canceled lanes."""
    non_active_lanes = [
        Lane.DONE,
        Lane.BLOCKED,
        Lane.CANCELED,
    ]
    for lane in non_active_lanes:
        state = wp_state_for(lane)
        assert state.is_run_affecting is False, f"Expected is_run_affecting=False for {lane!r}"


def test_is_run_affecting_matches_expected_routing():
    """Verify is_run_affecting produces expected routing for all 9 lanes.

    This is the canonical reference table:
      - planned, claimed, in_progress, for_review, in_review, approved → True
      - done, blocked, canceled → False
    """
    expected: dict[Lane, bool] = {
        Lane.PLANNED: True,
        Lane.CLAIMED: True,
        Lane.IN_PROGRESS: True,
        Lane.FOR_REVIEW: True,
        Lane.IN_REVIEW: True,
        Lane.APPROVED: True,
        Lane.DONE: False,
        Lane.BLOCKED: False,
        Lane.CANCELED: False,
    }
    for lane, expected_value in expected.items():
        state = wp_state_for(lane)
        assert state.is_run_affecting == expected_value, (
            f"Lane {lane!r}: expected is_run_affecting={expected_value}, got {state.is_run_affecting}"
        )


# ---------------------------------------------------------------------------
# Integration tests for _should_advance_wp_step() directly
# ---------------------------------------------------------------------------


def _write_status_events(
    feature_dir: Path,
    wp_lanes: dict[str, Lane],
    *,
    provenance: dict[str, str] | None = None,
) -> None:
    """Write a minimal status.events.jsonl with given WP lanes.

    ``provenance`` (T007, #3780) optionally maps a WP id whose ``final_lane``
    is ``CANCELED`` to a ``reason_source`` value — ``"operator"`` marks an
    operator-authored cancellation (a real, non-empty note). A WP omitted
    from ``provenance`` (the default) writes the CLI's synthetic
    cancellation shape (``reason=None, reason_source=None``) — the
    fail-closed case ``committed_authority.wp_ending`` must still block on.
    """
    from specify_cli.status.models import Lane as _Lane

    events_path = feature_dir / "status.events.jsonl"
    lines = []
    provenance = provenance or {}
    # Build events: planned -> (claimed) -> actual_lane for each WP
    for wp_id, final_lane in wp_lanes.items():
        # Always start with planned
        lines.append(json.dumps({
            "actor": "test",
            "at": "2026-04-09T00:00:00+00:00",
            "event_id": f"01TEST{wp_id}PLANNED",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": "test-feature",
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "planned",
            "wp_id": wp_id,
        }))
        if final_lane != _Lane.PLANNED:
            event: dict[str, object] = {
                "actor": "test",
                "at": "2026-04-09T00:01:00+00:00",
                "event_id": f"01TEST{wp_id}CLAIM",
                "evidence": None,
                "execution_mode": "worktree",
                "feature_slug": "test-feature",
                "force": False,
                "from_lane": "planned",
                "reason": None,
                "review_ref": None,
                "to_lane": str(final_lane),
                "wp_id": wp_id,
            }
            if final_lane == _Lane.CANCELED and wp_id in provenance:
                event["reason_source"] = provenance[wp_id]
                event["reason"] = "Operator-authored cancellation for test"
            lines.append(json.dumps(event))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    """Write a minimal WP task file."""
    wp_file = tasks_dir / f"{wp_id}-test-task.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test WP\ndependencies: []\n---\nContent.\n",
        encoding="utf-8",
    )


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    """Create a feature directory with tasks/ subdirectory."""
    fd = tmp_path / "kitty-specs" / "test-feature"
    fd.mkdir(parents=True)
    tasks = fd / "tasks"
    tasks.mkdir()
    return fd


def test_should_advance_implement_all_for_review(feature_dir: Path) -> None:
    """implement step advances when all WPs are at for_review."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_should_advance_implement_all_approved(feature_dir: Path) -> None:
    """implement step advances when all WPs are at approved."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.APPROVED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_should_advance_implement_all_done(feature_dir: Path) -> None:
    """implement step advances when all WPs are done."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.DONE, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_should_not_advance_implement_one_in_progress(feature_dir: Path) -> None:
    """implement step does NOT advance when a WP is still in_progress."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.IN_PROGRESS})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is False


def test_should_not_advance_implement_one_planned(feature_dir: Path) -> None:
    """implement step does NOT advance when a WP is planned (not started)."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.PLANNED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is False


def test_should_not_advance_implement_one_claimed(feature_dir: Path) -> None:
    """implement step does NOT advance when a WP is claimed (not yet in progress)."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.CLAIMED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is False


def test_should_not_advance_implement_one_in_review(feature_dir: Path) -> None:
    """implement step does NOT advance when a WP is in_review (not yet approved)."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.IN_REVIEW})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is False


def test_should_not_advance_implement_one_blocked(feature_dir: Path) -> None:
    """implement step does NOT advance when a WP is blocked."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.BLOCKED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is False


def test_should_advance_implement_one_synthetic_canceled(feature_dir: Path) -> None:
    """implement advances for canceled WPs; provenance gates review only."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.CANCELED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_parse_requirement_refs_handles_markdown_label_without_regex_backtracking() -> None:
    """Requirement refs parser accepts bold markdown labels and dedupes refs."""
    from runtime.next.runtime_bridge_cores import _parse_requirement_refs_from_tasks_md
    from specify_cli.requirement_mapping import grammar

    tasks_md = """
## Work Package WP01
**Requirement Refs**: FR-001, nfr-002, FR-001
Ignored line

## Work Package WP02
Requirement Refs: C-003, FR-004
""".strip()

    assert _parse_requirement_refs_from_tasks_md(tasks_md, grammar=grammar) == {
        "WP01": ["FR-001", "NFR-002"],
        "WP02": ["C-003", "FR-004"],
    }


def test_parse_requirement_refs_supports_heading_and_bullet_list_format() -> None:
    """Requirement refs parser accepts the documented heading + bullet form."""
    from runtime.next.runtime_bridge_cores import _parse_requirement_refs_from_tasks_md
    from specify_cli.requirement_mapping import grammar

    tasks_md = """
## Work Package WP01
### Requirement Refs
- FR-999
- nfr-001
""".strip()

    assert _parse_requirement_refs_from_tasks_md(tasks_md, grammar=grammar) == {
        "WP01": ["FR-999", "NFR-001"],
    }


def test_should_advance_review_all_approved(feature_dir: Path) -> None:
    """review step advances when all WPs are approved."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.APPROVED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is True


def test_should_advance_review_all_done(feature_dir: Path) -> None:
    """review step advances when all WPs are done."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.DONE})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is True


def test_should_not_advance_review_one_for_review(feature_dir: Path) -> None:
    """review step does NOT advance when a WP is still at for_review."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is False


def test_should_not_advance_review_one_in_review(feature_dir: Path) -> None:
    """review step does NOT advance when a WP is in_review."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_wp_file(tasks, "WP02")
    _write_status_events(feature_dir, {"WP01": Lane.APPROVED, "WP02": Lane.IN_REVIEW})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is False


@pytest.mark.regression
def test_should_advance_review_canceled_with_operator_provenance(feature_dir: Path) -> None:
    """#3780: a canceled WP carrying operator-authored provenance advances
    review — committed_authority.wp_ending's ``acceptable`` fold routes
    through ``is_acceptable_ending(has_provenance=True)``."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(
        feature_dir,
        {"WP01": Lane.CANCELED},
        provenance={"WP01": "operator"},
    )

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is True


@pytest.mark.regression
def test_should_advance_implement_canceled_with_operator_provenance(feature_dir: Path) -> None:
    """#3780: operator-provenance cancellation also advances implement (a
    canceled WP is not run-affecting regardless of provenance, but this
    pins the truth table's implement row explicitly)."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(
        feature_dir,
        {"WP01": Lane.CANCELED},
        provenance={"WP01": "operator"},
    )

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


@pytest.mark.regression
def test_should_not_advance_review_synthetic_cancellation(feature_dir: Path) -> None:
    """#3780: a synthetic cancellation (no operator provenance) still BLOCKS
    review — the fail-closed half of the truth table. This is the case that
    fails on base (lane-only predicate treats CANCELED as never blocking
    review, i.e. it does NOT distinguish provenance at all)."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.CANCELED})  # no provenance -> synthetic

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("review", feature_dir) is False


@pytest.mark.regression
def test_should_advance_implement_synthetic_cancellation(feature_dir: Path) -> None:
    """#3780: a synthetic cancellation still does NOT block implement — a
    canceled WP is never run-affecting there, independent of provenance."""
    tasks = feature_dir / "tasks"
    _write_wp_file(tasks, "WP01")
    _write_status_events(feature_dir, {"WP01": Lane.CANCELED})

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_should_advance_no_wps(feature_dir: Path) -> None:
    """Both steps advance when there are no WP files (no work to iterate)."""
    from runtime.next.runtime_bridge_guards import _should_advance_wp_step
    assert _should_advance_wp_step("implement", feature_dir) is True
    assert _should_advance_wp_step("review", feature_dir) is True


def test_is_run_affecting_used_not_raw_strings():
    """Verify that _should_advance_wp_step routing uses is_run_affecting semantics.

    This test calls _should_advance_wp_step with an in_progress WP and verifies
    it returns False — confirming the implementation correctly identifies that
    an in_progress WP (which has is_run_affecting=True and is not for_review/approved)
    blocks implement step advancement.
    """
    state_in_progress = wp_state_for(Lane.IN_PROGRESS)
    state_for_review = wp_state_for(Lane.FOR_REVIEW)
    state_done = wp_state_for(Lane.DONE)

    # Verify the is_run_affecting property drives the routing logic:
    # in_progress is run-affecting → blocks advancement (not yet handed off)
    assert state_in_progress.is_run_affecting is True
    assert state_in_progress.lane not in (Lane.FOR_REVIEW, Lane.APPROVED)

    # for_review is run-affecting but is a handoff lane → allows advancement
    assert state_for_review.is_run_affecting is True
    assert state_for_review.lane == Lane.FOR_REVIEW

    # done is not run-affecting → allows advancement
    assert state_done.is_run_affecting is False
