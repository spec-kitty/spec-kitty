"""Unit tests for the InnerStateChanged reducer fold (WP01 / FR-002, FR-004).

Proves the event-kind partition fold contract:
- lane transitions preserve untouched runtime slots (replace-dict hazard closed);
- the ``planned -> claimed`` transition folds its ``policy_metadata`` sidecar
  into the snapshot runtime slots;
- annotations apply a per-field merge (replace / per-subtask replace / append /
  union / wholesale-replace) in a dedicated post-transition pass;
- annotations never bump ``force_count``;
- same-``at`` ordering is a partition (annotation after transition), not a
  timestamp interleave;
- the annotation fold is O(annotations) and does NOT re-scan the transition
  list (NFR-005) — asserted structurally.
"""

from __future__ import annotations

import pytest

from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    ReviewOverride,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import reduce

pytestmark = pytest.mark.unit


def _ulid(suffix: str) -> str:
    """Build a syntactically valid 26-char ULID from a short suffix."""
    return ("01KX" + suffix).ljust(26, "0")[:26]


def _transition(
    event_id: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    at: str,
    *,
    force: bool = False,
    policy_metadata: dict | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="001-mission",
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=at,
        actor="alice",
        force=force,
        execution_mode="worktree",
        policy_metadata=policy_metadata,
    )


def _annotation(event_id: str, wp_id: str, at: str, delta: WPInnerStateDelta) -> InnerStateChanged:
    return InnerStateChanged(event_id=event_id, wp_id=wp_id, at=at, actor="alice", delta=delta)


def test_transition_preserves_runtime_slot_written_by_annotation() -> None:
    """A subtasks annotation followed by a transition keeps the subtasks slot
    (the reducer replace-dict hazard is closed)."""
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    ann = _annotation(
        _ulid("A01"), "WP01", "2026-01-01T00:01:00Z",
        WPInnerStateDelta(subtasks={"T001": Lane.DONE}),
    )
    # A later transition MUST NOT rebuild the WP dict dropping subtasks.
    t2 = _transition(_ulid("T02"), "WP01", "planned", "in_progress", "2026-01-01T00:05:00Z")

    wp = reduce([t1, t2], [ann]).work_packages["WP01"]

    assert wp["lane"] == "in_progress"
    assert wp["subtasks"] == {"T001": "done"}


def test_transition_preserves_every_untouched_runtime_slot() -> None:
    """Every runtime slot set by annotations survives a subsequent transition —
    not just the one the test happened to set first."""
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    ann = _annotation(
        _ulid("A01"), "WP01", "2026-01-01T00:01:00Z",
        WPInnerStateDelta(
            shell_pid=111,
            shell_pid_created_at="c1",
            subtasks={"T001": Lane.DONE},
            note="n1",
            tracker_refs=["JIRA-1"],
            agent="claude",
            assignee="pedro",
            review=ReviewOverride(at="t", actor="r", wp_id="WP01", reason="ok"),
        ),
    )
    t2 = _transition(_ulid("T02"), "WP01", "planned", "in_progress", "2026-01-01T00:05:00Z")

    wp = reduce([t1, t2], [ann]).work_packages["WP01"]

    assert wp["shell_pid"] == 111
    assert wp["shell_pid_created_at"] == "c1"
    assert wp["subtasks"] == {"T001": "done"}
    assert wp["notes"] == ["n1"]
    assert wp["tracker_refs"] == ["JIRA-1"]
    assert wp["agent"] == "claude"
    assert wp["assignee"] == "pedro"
    assert wp["review"] == {"at": "t", "actor": "r", "wp_id": "WP01", "reason": "ok"}


def test_claim_transition_folds_policy_metadata_into_slots() -> None:
    """``planned -> claimed`` extracts shell_pid/shell_pid_created_at/agent from
    its policy_metadata sidecar (FR-004 claim path)."""
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    claim = _transition(
        _ulid("T02"), "WP01", "planned", "claimed", "2026-01-01T00:01:00Z",
        policy_metadata=build_claim_policy_metadata(12345, "2026-01-01T00:01:00Z", "claude"),
    )

    wp = reduce([t1, claim]).work_packages["WP01"]

    assert wp["shell_pid"] == 12345
    assert wp["shell_pid_created_at"] == "2026-01-01T00:01:00Z"
    assert wp["agent"] == "claude"


def test_claim_transition_with_none_policy_metadata_does_not_crash() -> None:
    """A ``planned -> claimed`` with no sidecar leaves runtime slots empty."""
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    claim = _transition(_ulid("T02"), "WP01", "planned", "claimed", "2026-01-01T00:01:00Z")

    wp = reduce([t1, claim]).work_packages["WP01"]

    assert wp["lane"] == "claimed"
    assert "shell_pid" not in wp


def test_two_note_annotations_append_in_order() -> None:
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    a1 = _annotation(_ulid("A01"), "WP01", "2026-01-01T00:01:00Z", WPInnerStateDelta(note="n1"))
    a2 = _annotation(_ulid("A02"), "WP01", "2026-01-01T00:02:00Z", WPInnerStateDelta(note="n2"))

    wp = reduce([t1], [a1, a2]).work_packages["WP01"]

    assert wp["notes"] == ["n1", "n2"]


def test_subtasks_merge_per_id_and_tracker_refs_union_dedups() -> None:
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    a1 = _annotation(
        _ulid("A01"), "WP01", "2026-01-01T00:01:00Z",
        WPInnerStateDelta(subtasks={"T001": Lane.DONE, "T002": Lane.IN_PROGRESS},
                          tracker_refs=["JIRA-1", "JIRA-1", "JIRA-2"]),
    )
    a2 = _annotation(
        _ulid("A02"), "WP01", "2026-01-01T00:02:00Z",
        WPInnerStateDelta(subtasks={"T002": Lane.DONE}, tracker_refs=["JIRA-2", "JIRA-3"]),
    )

    wp = reduce([t1], [a1, a2]).work_packages["WP01"]

    # per-subtask replace: T001 kept, T002 upgraded to done.
    assert wp["subtasks"] == {"T001": "done", "T002": "done"}
    # union, dedup-preserving order.
    assert wp["tracker_refs"] == ["JIRA-1", "JIRA-2", "JIRA-3"]


def test_tracker_refs_replace_drops_stale_refs_and_wins_over_union() -> None:
    """The replace channel wholesale-replaces the slot (stale refs dropped) and
    takes precedence over a same-delta union."""
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    seed = _annotation(
        _ulid("A01"), "WP01", "2026-01-01T00:01:00Z",
        WPInnerStateDelta(tracker_refs=["STALE-1", "STALE-2"]),
    )
    replace = _annotation(
        _ulid("A02"), "WP01", "2026-01-01T00:02:00Z",
        WPInnerStateDelta(tracker_refs=["IGNORED-9"], tracker_refs_replace=["KEEP-1", "KEEP-1", "KEEP-2"]),
    )

    wp = reduce([t1], [seed, replace]).work_packages["WP01"]

    # Stale refs gone; the union channel in the same delta is ignored; dedup kept.
    assert wp["tracker_refs"] == ["KEEP-1", "KEEP-2"]


def test_annotation_never_bumps_force_count() -> None:
    forced = _transition(
        _ulid("T01"), "WP01", "in_review", "in_progress", "2026-01-01T00:00:00Z", force=True,
    )
    anns = [
        _annotation(_ulid(f"A{i:02d}"), "WP01", f"2026-01-01T01:0{i}:00Z", WPInnerStateDelta(note=f"n{i}"))
        for i in range(3)
    ]

    wp = reduce([forced], anns).work_packages["WP01"]

    assert wp["force_count"] == 1  # from the forced transition only


def test_same_at_partition_orders_annotation_after_transition() -> None:
    """At an equal ``at``, the annotation folds AFTER the transition (event-kind
    partition), so an annotation slot is never clobbered by a same-``at``
    transition."""
    at = "2026-01-01T00:00:00Z"
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", at)
    # Seed annotation shares the transition timestamp; partition (not timestamp
    # interleave) guarantees it applies after the transition.
    seed = _annotation(_ulid("A01"), "WP01", at, WPInnerStateDelta(shell_pid=777))

    wp = reduce([t1], [seed]).work_packages["WP01"]

    assert wp["shell_pid"] == 777


def test_annotation_only_stream_materialises_runtime_only_wp() -> None:
    ann = _annotation(_ulid("A01"), "WP07", "2026-01-01T00:00:00Z", WPInnerStateDelta(note="orphan"))

    snapshot = reduce([], [ann])

    wp = snapshot.work_packages["WP07"]
    assert wp["notes"] == ["orphan"]
    # Runtime-only WP sits in the non-display UNINITIALIZED lane → not summarised.
    assert wp["lane"] == "uninitialized"
    assert snapshot.summary.get("uninitialized") is None


def test_empty_stream_yields_empty_snapshot() -> None:
    snapshot = reduce([], [])
    assert snapshot.work_packages == {}
    assert snapshot.event_count == 0


class _CountingList(list):
    """A list that counts how many times it is iterated."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.iter_count = 0

    def __iter__(self):  # type: ignore[override]
        self.iter_count += 1
        return super().__iter__()


def test_annotation_fold_does_not_rescan_transitions_ie_o_events() -> None:
    """Structural NFR-005 assertion: the number of times the transition list is
    scanned is INDEPENDENT of the annotation count M — so an accidental
    O(transitions x annotations) fold fails this test."""
    transitions = [
        _transition(_ulid(f"T{i:03d}"), "WP01", "genesis", "planned", f"2026-01-01T00:00:{i:02d}Z")
        for i in range(5)
    ]

    def scan_count(num_annotations: int) -> int:
        counting = _CountingList(transitions)
        anns = [
            _annotation(_ulid(f"A{i:03d}"), "WP01", f"2026-01-02T00:00:{i:02d}Z",
                        WPInnerStateDelta(note=f"n{i}"))
            for i in range(num_annotations)
        ]
        reduce(counting, anns)
        return counting.iter_count

    few = scan_count(1)
    many = scan_count(50)

    # The transition list is scanned a fixed number of times regardless of M.
    assert few == many
    # And it is a small constant (a single dedup walk plus one implementer-of-
    # record attribution pass, #4786), not per-annotation. The invariant this
    # test protects — scan count INDEPENDENT of annotation count M — is the
    # `few == many` assertion above; this bound is the constant-factor ceiling.
    assert few <= 3


@pytest.mark.parametrize("stream_order", ["file_order", "reversed"])
def test_same_field_annotations_resolve_by_timestamp_not_stream_order(
    stream_order: str,
) -> None:
    """Two annotations writing the SAME field resolve to the later-``at`` value
    regardless of their order in the stream.

    The fold sorts annotations by ``(at, event_id)`` (mirroring the transition
    pass) so a same-field conflict is broken by timestamp, not merge-order —
    otherwise a parallel-worktree merge that interleaves the two rows
    non-deterministically would flip the winner (the #2684 alphonso finding).
    """
    t1 = _transition(_ulid("T01"), "WP01", "genesis", "planned", "2026-01-01T00:00:00Z")
    # Earlier timestamp -> "early"; later timestamp -> "late". The later-``at``
    # value MUST win. The event_ids are chosen so ULID order does NOT rescue a
    # naive tie-break (A_late's id sorts BEFORE A_early's).
    ann_early = _annotation(
        _ulid("Z_EARLY"), "WP01", "2026-01-02T00:00:00Z",
        WPInnerStateDelta(assignee="early"),
    )
    ann_late = _annotation(
        _ulid("A_LATE"), "WP01", "2026-01-02T09:00:00Z",
        WPInnerStateDelta(assignee="late"),
    )

    annotations = [ann_early, ann_late]
    if stream_order == "reversed":
        annotations = list(reversed(annotations))

    snapshot = reduce([t1], annotations)

    assert snapshot.work_packages["WP01"]["assignee"] == "late", (
        "same-field annotation conflict must resolve to the later-`at` write, "
        f"not the stream/file-order last write (order={stream_order})"
    )
