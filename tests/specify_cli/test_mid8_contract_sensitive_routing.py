"""Causal mid8 seam contracts.

Copied expressions for aggregate, doctor, implement, and allocator were
retired; their live consumers and the canonical branch-naming seam are covered
by dedicated suites. This module keeps the negative inline-slice invariant.
(The dashboard-scanner contract left with the bundled dashboard, #5530.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import resolve_mid8

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# --- Golden literals captured from HEAD before any edit (do NOT recompute) ---
FULL_ULID = "01KV7SFD9ABCDEFGHJKMNPQRST"  # 26-char ULID
FULL_MID8 = "01KV7SFD"  # first 8 chars of FULL_ULID — hard-coded, NOT FULL_ULID[:8]
SHORT_ID = "01KV"  # len 4, < 8
SLUG_WITH_TAIL = "naming-identity-routing-rider-01KV7SFD"
SLUG_NO_TAIL = "plain-mission"


class TestResolveMid8Contracts:
    """Pin the seam outputs the routed expressions rely on (declared literals)."""

    def test_full_ulid_with_matching_slug_tail_yields_mid8(self) -> None:
        assert resolve_mid8(SLUG_WITH_TAIL, mission_id=FULL_ULID) == "01KV7SFD"

    def test_full_ulid_with_no_slug_tail_yields_mid8(self) -> None:
        assert resolve_mid8(SLUG_NO_TAIL, mission_id=FULL_ULID) == "01KV7SFD"

    def test_none_mission_id_declines_to_empty_string(self) -> None:
        assert resolve_mid8(SLUG_WITH_TAIL, mission_id=None) == ""

    def test_short_mission_id_declines_to_empty_string(self) -> None:
        assert resolve_mid8(SLUG_WITH_TAIL, mission_id=SHORT_ID) == ""


def test_no_inline_mid8_slices_remain_after_routing() -> None:
    """Verification-by-deletion guard: the routed modules carry no inline
    ``mission_id[:8]`` derivation.

    This pins the *negative* invariant (no inline slice) across the routed
    modules — the load-bearing property. The former positive literal-presence
    check (``"resolve_mid8" in doctor.py``) was dropped: ``doctor.py`` was
    refactored into an orchestration shell and the mid8 logic delegated out, so
    that assertion measured module shape, not behaviour (convert-or-delete a
    stale positive-literal scan; never re-pin it). The negative reintroduction
    guards below cover ``doctor.py`` too.
    """
    src_root = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
    # aggregate, implement, allocator, doctor: no bare ``mission_id[:8]``.
    for rel in (
        "status/aggregate.py",
        "cli/commands/implement.py",
        "coordination/planning_commit.py",
        "lanes/worktree_allocator.py",
        "cli/commands/doctor.py",
    ):
        text = (src_root / rel).read_text(encoding="utf-8")
        assert "mission_id[:8]" not in text, f"inline mid8 slice still present in {rel}"

    # The dead ``try/except ValueError`` around _mid8 must not be reintroduced.
    doctor_text = (src_root / "cli/commands/doctor.py").read_text(encoding="utf-8")
    assert "import mid8 as _mid8" not in doctor_text


if __name__ == "__main__":  # pragma: no cover - manual invocation aid
    raise SystemExit(pytest.main([__file__, "-v"]))
