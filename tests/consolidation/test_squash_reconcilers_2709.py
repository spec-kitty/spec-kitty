"""Unit coverage for the #2709 squash-merge reconcilers (FR-003 / FR-004).

Exercises the pure driver seams directly (``reconcile_meta_payloads``,
``union_trace_texts``, ``_union_acceptance_history``) so each merge branch has
focused coverage independent of a real ``git merge``, plus the ``write_meta``
idempotency pin the FR-004 field-merge relies on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation.drivers import (
    _union_acceptance_history,
    reconcile_meta_payloads,
    union_trace_texts,
)
from specify_cli.mission_metadata import load_meta, write_meta

pytestmark = pytest.mark.fast

# Delimiter used by the traces union contract (matches the #2709 repro fixtures).
_TARGET_MARKER = "<!-- section:target-newer -->"
_COORD_MARKER = "<!-- section:coord-older -->"


# ---------------------------------------------------------------------------
# FR-004: meta.json field merge
# ---------------------------------------------------------------------------


def test_reconcile_meta_takes_target_acceptance_and_vcs() -> None:
    ours = {  # target (accepted-newer)
        "accepted_at": "T2",
        "accepted_by": "reviewer-target",
        "accept_commit": "targetacc",
        "acceptance_mode": "automatic",
        "vcs": "git",
        "vcs_locked_at": "T2",
        "mission_slug": "m",
    }
    theirs = {  # mission (older)
        "accepted_at": "T1",
        "accepted_by": "reviewer-coord",
        "accept_commit": "coordacc",
        "acceptance_mode": "manual",
        "vcs": "svn",
        "vcs_locked_at": "T1",
        "mission_slug": "m",
    }
    merged = reconcile_meta_payloads(ours, theirs)
    assert merged["accepted_at"] == "T2"
    assert merged["accepted_by"] == "reviewer-target"
    assert merged["accept_commit"] == "targetacc"
    assert merged["acceptance_mode"] == "automatic"
    assert merged["vcs"] == "git"
    assert merged["vcs_locked_at"] == "T2"


def test_reconcile_meta_takes_target_lifecycle_canonical_fields() -> None:
    """mission_number / status are target-assigned lifecycle fields (target wins)."""
    ours = {"mission_number": 42, "status": "accepted", "mission_slug": "m"}
    theirs = {"mission_number": None, "status": "in_review", "mission_slug": "m"}
    merged = reconcile_meta_payloads(ours, theirs)
    assert merged["mission_number"] == 42
    assert merged["status"] == "accepted"


def test_reconcile_meta_keeps_planning_keys_mission_authoritative() -> None:
    """#1732 / C-002: non-provenance (planning) keys stay mission-authoritative."""
    ours = {"friendly_name": "Target Name", "purpose_tldr": "target purpose"}
    theirs = {"friendly_name": "Mission Name", "purpose_tldr": "mission purpose"}
    merged = reconcile_meta_payloads(ours, theirs)
    assert merged["friendly_name"] == "Mission Name"
    assert merged["purpose_tldr"] == "mission purpose"


def test_reconcile_meta_unions_acceptance_history() -> None:
    ours = {"acceptance_history": [{"accepted_at": "T2", "accepted_by": "target"}]}
    theirs = {"acceptance_history": [{"accepted_at": "T1", "accepted_by": "coord"}]}
    merged = reconcile_meta_payloads(ours, theirs)
    assert merged["acceptance_history"] == [
        {"accepted_at": "T1", "accepted_by": "coord"},
        {"accepted_at": "T2", "accepted_by": "target"},
    ]


def test_union_acceptance_history_dedupes_and_sorts() -> None:
    shared = {"accepted_at": "T1", "accepted_by": "a"}
    newer = {"accepted_at": "T2", "accepted_by": "b"}
    result = _union_acceptance_history([shared], [newer, shared])
    assert result == [shared, newer]  # deduped, chronological


def test_union_acceptance_history_handles_missing() -> None:
    assert _union_acceptance_history(None, None) == []


# ---------------------------------------------------------------------------
# FR-003: traces markdown union (bind the concrete contract, not "a section")
# ---------------------------------------------------------------------------


def _target_trace() -> str:
    return (
        "# Mission Trace\n\n"
        f"{_TARGET_MARKER}\n"
        "## Target section\n"
        "target body\n"
    )


def _coord_trace() -> str:
    return (
        "# Mission Trace\n\n"
        f"{_COORD_MARKER}\n"
        "## Coord section\n"
        "coord body\n"
    )


def test_union_traces_target_newer_section_survives() -> None:
    merged = union_trace_texts(_target_trace(), _coord_trace())
    assert _TARGET_MARKER in merged  # (a)
    assert _COORD_MARKER in merged


def test_union_traces_both_sides_section_not_duplicated() -> None:
    """(b) A line present on BOTH sides collapses to one (line-level dedup)."""
    merged = union_trace_texts(_target_trace(), _coord_trace())
    # ``# Mission Trace`` is on both sides -> exactly one copy.
    assert merged.count("# Mission Trace") == 1
    # A whole section identical on both sides is not duplicated.
    same = "# Trace\n\n<!-- section:s -->\n## S\nbody\n"
    merged_same = union_trace_texts(same, same)
    assert merged_same.count("<!-- section:s -->") == 1
    assert merged_same.count("## S") == 1


def test_union_traces_preserves_delimiter() -> None:
    """(c) The section delimiter comment survives verbatim for both sides."""
    merged = union_trace_texts(_target_trace(), _coord_trace())
    assert merged.count(_TARGET_MARKER) == 1
    assert merged.count(_COORD_MARKER) == 1


def test_union_traces_naive_cat_would_fail_the_contract() -> None:
    """A naive ``cat`` concat duplicates shared lines; the union must not."""
    naive = _target_trace() + _coord_trace()
    assert naive.count("# Mission Trace") == 2  # cat duplicates
    merged = union_trace_texts(_target_trace(), _coord_trace())
    assert merged.count("# Mission Trace") == 1  # union dedupes


# ---------------------------------------------------------------------------
# Idempotency: the field-merge survives the post-merge write_meta stamp.
# ---------------------------------------------------------------------------


def test_write_meta_validate_false_never_drops_unknown_key(tmp_path: Path) -> None:
    """The FR-004 edge: ``write_meta(validate=False)`` must round-trip unknown keys.

    The post-merge baseline stamp re-writes meta.json with ``validate=False``; if
    that dropped reconciled provenance keys, the field-merge would not survive.
    """
    meta = {"mission_slug": "m", "accepted_at": "T2", "some_future_key": {"nested": 1}}
    write_meta(tmp_path, meta, validate=False)
    reloaded = load_meta(tmp_path)
    assert reloaded is not None
    assert reloaded["some_future_key"] == {"nested": 1}
    assert reloaded["accepted_at"] == "T2"
