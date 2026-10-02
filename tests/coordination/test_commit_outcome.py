"""Tests for the per-surface commit-outcome contract (mission coord-artifact-single-home-01M3V4BE, WP05 T024).

Covers each status glyph, path listing, the JSON round-trip, exit codes, and
the empty-surfaces legacy case per ``contracts/commit-outcome.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from specify_cli.coordination.commit_outcome import (
    COORD_RECORD_IN_ROOT_CHECKOUT,
    COORDINATION_BRANCH_DELETED,
    COORDINATION_WORKTREE_UNMATERIALIZED,
    COORD_SEED_FORK_REFUSED,
    PATH_UNROUTABLE,
    PROTECTED_BRANCH_REFUSED,
    REASON_ALREADY_COMMITTED,
    REASON_NO_CHANGES,
    STATUS_LOCK_HELD,
    WRONG_SURFACE,
    PathFate,
    SurfaceOutcome,
    commit_outcome_exit_code,
    commit_outcome_payload,
    render_commit_outcome,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@dataclass(frozen=True)
class _FakeResult:
    """A minimal stand-in exposing only ``surfaces`` — proves the ``Protocol`` works."""

    surfaces: tuple[SurfaceOutcome, ...]


# ---------------------------------------------------------------------------
# render_commit_outcome
# ---------------------------------------------------------------------------


def test_render_committed_surface_matches_contract_example() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="topic",
                status="committed",
                commit_hash="abc1234567890",
                committed=("kitty-specs/m/spec.md", "kitty-specs/m/decisions/index.json"),
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == ["✓ primary (topic): committed abc1234 — 2 files"]


def test_render_refused_surface_matches_contract_example() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="status.events.jsonl", reason=STATUS_LOCK_HELD),),
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == ["✗ coordination (kitty/mission-m-01ABCDEF): refused — status.events.jsonl: STATUS_LOCK_HELD"]


def test_render_unchanged_surface_with_no_op_skips_renders_only_the_summary() -> None:
    """Benign no-op skips (already-committed / no-changes) are not rendered as separate lines."""
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="unchanged",
                commit_hash=None,
                skipped=(PathFate(path="status.events.jsonl", reason=REASON_ALREADY_COMMITTED),),
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == ["✓ coordination (kitty/mission-m-01ABCDEF): unchanged"]


def test_render_unchanged_surface_with_root_checkout_skip_is_actionable() -> None:
    """A ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip IS rendered — it names a root edit that never landed."""
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="unchanged",
                commit_hash=None,
                skipped=(
                    PathFate(
                        path="kitty-specs/m/traces/approach.md",
                        reason=COORD_RECORD_IN_ROOT_CHECKOUT,
                        owning_path="kitty-specs/m/traces/approach.md",
                    ),
                ),
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == [
        "✓ coordination (kitty/mission-m-01ABCDEF): unchanged",
        "✓ coordination (kitty/mission-m-01ABCDEF): skipped — kitty-specs/m/traces/approach.md: COORD_RECORD_IN_ROOT_CHECKOUT",
    ]


def test_render_error_surface_with_no_named_path_shows_diagnostic() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="main",
                status="error",
                commit_hash=None,
                diagnostic="safe_commit: git commit failed",
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == ["✗ primary (main): error — safe_commit: git commit failed"]


def test_render_bare_refusal_with_no_named_path_still_emits_a_summary() -> None:
    result = _FakeResult(surfaces=(SurfaceOutcome(surface="primary", branch="main", status="refused", commit_hash=None),))

    lines = render_commit_outcome(result)

    assert lines == ["✗ primary (main): refused"]


def test_render_multiple_surfaces_orders_primary_before_coordination() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234"),
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="status.events.jsonl", reason=STATUS_LOCK_HELD),),
            ),
        )
    )

    lines = render_commit_outcome(result)

    assert lines == [
        "✓ primary (topic): committed abc1234 — 0 files",
        "✗ coordination (kitty/mission-m-01ABCDEF): refused — status.events.jsonl: STATUS_LOCK_HELD",
    ]


def test_render_empty_surfaces_legacy_case_yields_no_lines() -> None:
    assert render_commit_outcome(_FakeResult(surfaces=())) == []


# ---------------------------------------------------------------------------
# commit_outcome_payload
# ---------------------------------------------------------------------------


def test_payload_round_trips_every_field() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="topic",
                status="committed",
                commit_hash="abc1234567890",
                committed=("kitty-specs/m/spec.md",),
                skipped=(PathFate(path="a", reason=REASON_NO_CHANGES),),
                refused=(PathFate(path="b", reason=PATH_UNROUTABLE, owning_path="c"),),
                diagnostic=None,
            ),
        )
    )

    payload = commit_outcome_payload(result)

    assert payload == {
        "surfaces": [
            {
                "surface": "primary",
                "branch": "topic",
                "status": "committed",
                "commit_hash": "abc1234567890",
                "committed": ["kitty-specs/m/spec.md"],
                "skipped": [{"path": "a", "reason": REASON_NO_CHANGES, "owning_path": None}],
                "refused": [{"path": "b", "reason": PATH_UNROUTABLE, "owning_path": "c"}],
                "diagnostic": None,
            }
        ]
    }


def test_payload_empty_surfaces_legacy_case() -> None:
    assert commit_outcome_payload(_FakeResult(surfaces=())) == {"surfaces": []}


# ---------------------------------------------------------------------------
# commit_outcome_exit_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected",
    [
        ("committed", 0),
        ("unchanged", 0),
        ("refused", 1),
        ("error", 1),
    ],
)
def test_exit_code_per_status(status: str, expected: int) -> None:
    result = _FakeResult(surfaces=(SurfaceOutcome(surface="primary", branch="main", status=status, commit_hash=None),))  # type: ignore[arg-type]

    assert commit_outcome_exit_code(result) == expected


def test_exit_code_any_refused_surface_among_several_is_nonzero() -> None:
    result = _FakeResult(
        surfaces=(
            SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234"),
            SurfaceOutcome(surface="coordination", branch="coord", status="refused", commit_hash=None),
        )
    )

    assert commit_outcome_exit_code(result) == 1


def test_exit_code_empty_surfaces_legacy_case_is_zero() -> None:
    assert commit_outcome_exit_code(_FakeResult(surfaces=())) == 0


# ---------------------------------------------------------------------------
# Reason-code constants are the canonical values the contract names.
# ---------------------------------------------------------------------------


def test_reason_code_constants_match_contract_values() -> None:
    assert REASON_ALREADY_COMMITTED == "no_op_already_committed"
    assert REASON_NO_CHANGES == "no_op_no_changes"
    assert COORD_RECORD_IN_ROOT_CHECKOUT == "COORD_RECORD_IN_ROOT_CHECKOUT"
    assert PROTECTED_BRANCH_REFUSED == "PROTECTED_BRANCH_REFUSED"
    assert STATUS_LOCK_HELD == "STATUS_LOCK_HELD"
    assert PATH_UNROUTABLE == "PATH_UNROUTABLE"
    assert WRONG_SURFACE == "WRONG_SURFACE"
    # The two existing class-attribute-backed codes resolve to a real value,
    # not a placeholder — proves this module imports them rather than
    # re-declaring a parallel literal.
    assert isinstance(COORDINATION_BRANCH_DELETED, str) and COORDINATION_BRANCH_DELETED
    assert isinstance(COORD_SEED_FORK_REFUSED, str) and COORD_SEED_FORK_REFUSED
    assert isinstance(COORDINATION_WORKTREE_UNMATERIALIZED, str) and COORDINATION_WORKTREE_UNMATERIALIZED
