"""Frozen lane membership for started work packages (#5573).

A work package that has *started* owns commits on its recorded lane's branch
(``refs/heads/<lane branch>`` plus the hidden lane work-tip ref). Changing its
lane id on a re-finalize strands that work, rebinds another work package onto a
branch carrying foreign commits, or poisons per-WP attribution. This module is
the one pure home for:

* which work packages are started (:func:`started_wp_ids`, history-based);
* which lane membership is therefore frozen (:func:`build_frozen_membership`);
* why a frozen membership cannot be honoured (:class:`MembershipConflict`,
  with a reason-specific, non-destructive remedy from :func:`remedy_for`);
* the writer's defence-in-depth re-check
  (:func:`assert_frozen_membership_honoured`).

Purity (C-002): no git, no ``meta.json``, no console. The caller gathers the
evidence (status events, recorded lane tips) and passes it in.

Import-cycle note: :mod:`specify_cli.lanes.compute` imports this module at
load time (it raises :class:`~specify_cli.lanes.compute.LaneMembershipFrozenError`
from conflicts built here), so this module reaches back into ``compute`` only
inside function bodies. The status facade is likewise imported lazily (and for
type checking only at module level) so that importing ``lanes.compute`` never
drags the status orchestration package into a cold import
(``tests/architectural/test_cold_import_status_boundary.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from mission_runtime import MissionTopology

from specify_cli.lanes.branch_naming import PLANNING_LANE_ID, code_lane_branch_name, parse_lane_id_from_branch

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.status import StatusEvent

__all__ = [
    "FrozenLaneMembership",
    "MembershipConflict",
    "assert_frozen_membership_honoured",
    "build_frozen_membership",
    "remedy_for",
    "started_wp_ids",
]

MembershipConflictReason = Literal[
    "started_lanes_collapsed",
    "started_wp_removed",
    "started_wp_kind_changed",
    "status_unreadable",
]

#: Precedence of conflict reasons: the error's top-level ``reason`` is the first
#: one present, and its ``next_step`` lists remedies in this order.
REASON_PRECEDENCE: tuple[MembershipConflictReason, ...] = (
    "started_lanes_collapsed",
    "started_wp_removed",
    "started_wp_kind_changed",
    "status_unreadable",
)

#: The lanes that mean "real work began". A positive set, so ``planned``,
#: ``blocked``, ``canceled`` and the ``genesis`` / ``uninitialized`` sentinels
#: are excluded by construction.
_STARTED_LANES = frozenset({"claimed", "in_progress", "for_review", "in_review", "approved", "done"})

_REMEDY_COLLAPSED = (
    "Remove the overlap that forces {wps} into one lane (for example, move the shared path into a new work package "
    "that depends on them, or drop it from one of them), then re-run finalize-tasks."
)
_REMEDY_REMOVED = (
    "Restore the task file of {wps}. To retire a started work package instead, cancel it with "
    "`spec-kitty agent tasks move-task {cmd_wp} --to canceled --mission <handle>` without clearing its owned files, "
    "then re-run finalize-tasks."
)
_REMEDY_KIND_CHANGED = "Restore the `execution_mode` of {wps}, put the new kind of work in a new work package, then re-run finalize-tasks."
_REMEDY_STATUS_UNREADABLE = (
    "Repair the status log (`spec-kitty agent status validate --mission <handle>` reports the problem; "
    "`spec-kitty agent status doctor` checks status hygiene), then re-run finalize-tasks."
)
_CLAUSES: dict[MembershipConflictReason, str] = {
    "started_lanes_collapsed": "{named} would be merged into one lane",
    "started_wp_removed": "{named} would be dropped from the plan",
    "started_wp_kind_changed": "{named} would cross the lane-planning boundary",
    "status_unreadable": "the status log is unreadable, so started work cannot be determined",
}
_REMEDIES: dict[MembershipConflictReason, str] = {
    "started_lanes_collapsed": _REMEDY_COLLAPSED,
    "started_wp_removed": _REMEDY_REMOVED,
    "started_wp_kind_changed": _REMEDY_KIND_CHANGED,
    "status_unreadable": _REMEDY_STATUS_UNREADABLE,
}


def _join_wp_ids(wp_ids: tuple[str, ...]) -> str:
    if len(wp_ids) <= 1:
        return "".join(wp_ids) or "the named work packages"
    return ", ".join(wp_ids[:-1]) + f" and {wp_ids[-1]}"


def remedy_for(reason: MembershipConflictReason, wp_ids: Iterable[str]) -> str:
    """Return the non-destructive remedy for *reason*, naming *wp_ids*.

    The texts follow ``contracts/lane-membership-frozen.md``. None of them
    suggests deleting ``lanes.json``, a force flag, ``git reset`` / ``restore``
    / ``checkout -- .``, or removing worktrees or branches.
    """
    ordered = tuple(sorted(wp_ids))
    cmd_wp = ordered[0] if len(ordered) == 1 else "<WP>"
    return _REMEDIES[reason].format(wps=_join_wp_ids(ordered), cmd_wp=cmd_wp)


@dataclass(frozen=True, slots=True)
class MembershipConflict:
    """One reason a frozen lane membership cannot be honoured.

    ``wp_ids`` and ``recorded_lanes`` are sorted (``recorded_lanes`` distinct)
    so the conflict, its JSON form and the error message are deterministic.
    """

    reason: MembershipConflictReason
    wp_ids: tuple[str, ...]
    recorded_lanes: tuple[str, ...]
    remedy: str
    #: ``(wp_id, recorded_lane)`` pairs, used only to word the error message
    #: precisely; not part of equality or of the JSON envelope.
    pairs: tuple[tuple[str, str], ...] = field(default=(), compare=False, repr=False)

    def describe(self) -> str:
        """Return the human clause naming each WP with its recorded lane."""
        pairs = self.pairs or tuple(zip(self.wp_ids, self.recorded_lanes, strict=False))
        named = _join_wp_ids(tuple(f"{wp} ({lane})" for wp, lane in pairs)) if pairs else _join_wp_ids(self.wp_ids)
        return _CLAUSES[self.reason].format(named=named)

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-envelope form of this conflict."""
        return {
            "reason": self.reason,
            "wp_ids": list(self.wp_ids),
            "recorded_lanes": list(self.recorded_lanes),
            "remedy": self.remedy,
        }


def conflict_for(reason: MembershipConflictReason, bindings: Mapping[str, str]) -> MembershipConflict:
    """Build a :class:`MembershipConflict` for the started WPs in *bindings* (wp -> recorded lane)."""
    wp_ids = tuple(sorted(bindings))
    return MembershipConflict(
        reason=reason,
        wp_ids=wp_ids,
        recorded_lanes=tuple(sorted(set(bindings.values()))),
        remedy=remedy_for(reason, wp_ids),
        pairs=tuple((wp, bindings[wp]) for wp in wp_ids),
    )


class _FrozenBindings(Mapping[str, str]):
    """A read-only, hashable ``wp_id -> lane_id`` mapping."""

    __slots__ = ("_items",)

    def __init__(self, source: Mapping[str, str]) -> None:
        self._items: dict[str, str] = dict(source)

    def __getitem__(self, key: str) -> str:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        return f"{dict(sorted(self._items.items()))!r}"


@dataclass(frozen=True)
class FrozenLaneMembership:
    """The lane membership a re-finalize must honour.

    Attributes:
        bindings: Every started work package the previous manifest records in a
            lane, mapped to that recorded lane id (``lane-planning`` included).
            Stored as a read-only, hashable mapping.
        retired_wp_ids: Present work packages the cancellation projection
            excluded from lane inputs. A missing binding WP that is retired is
            leaving, not moving: no conflict, but its lane id stays reserved.
        reserved_ids: Lane ids reserved independently of the previous manifest
            still listing them: every lane id whose created branch carries a
            recorded work tip (:func:`_tipped_lane_ids`). A lane retired from the
            manifest keeps its branch and commits, so its id must never be
            re-minted on a later re-finalize either.
    """

    bindings: Mapping[str, str] = field(default_factory=dict)
    retired_wp_ids: frozenset[str] = frozenset()
    reserved_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", _FrozenBindings(self.bindings))
        object.__setattr__(self, "retired_wp_ids", frozenset(self.retired_wp_ids))
        object.__setattr__(self, "reserved_ids", frozenset(self.reserved_ids))

    @classmethod
    def empty(cls) -> FrozenLaneMembership:
        """Return the membership that constrains nothing (behaviour-identical to ``None``)."""
        return cls()

    @property
    def is_empty(self) -> bool:
        """True when there are no bindings, no retired work packages and no reserved lane ids."""
        return not self.bindings and not self.retired_wp_ids and not self.reserved_ids

    @property
    def reserved_lane_ids(self) -> frozenset[str]:
        """Lane ids that held started work: never minted for a new group (FR-004)."""
        return frozenset(self.bindings.values()) | self.reserved_ids


def started_wp_ids(events: Iterable[StatusEvent]) -> frozenset[str]:
    """Return the work packages whose status history shows real work began.

    A WP is started iff **some** event moved it into a started lane (claimed,
    in progress, for review, in review, approved, done). The rule reads the
    whole history, not the current lane (FR-008): a WP reset to ``planned`` or
    canceled after it worked still has commits on its lane branch, so it stays
    started. ``planned``, ``blocked``, ``canceled`` and the genesis /
    uninitialized sentinels never start a WP, so a WP blocked or canceled
    straight from planning is not started.
    """
    return frozenset(event.wp_id for event in events if str(event.to_lane) in _STARTED_LANES)


def _lane_started_members(
    previous: LanesManifest,
    lane_id: str,
    wp_ids: tuple[str, ...],
    *,
    started: frozenset[str],
    tipped_branches: frozenset[str],
) -> tuple[str, ...]:
    """Return the members of one prior lane that count as started.

    History-started members win. A code lane with no history-started member
    whose created branch carries a recorded work tip counts as wholly started
    (the lane-work-tip fallback; over-freezing is the safe direction). The
    planning lane is never tip-frozen: it resolves to the target branch.
    """
    from specify_cli.lanes.compute import lane_created_branch  # cycle: compute imports this module

    history = tuple(wp for wp in wp_ids if wp in started)
    if history or lane_id == PLANNING_LANE_ID:
        return history
    if lane_created_branch(previous, lane_id) in tipped_branches:
        return wp_ids
    return ()


def _tipped_lane_ids(previous: LanesManifest, tipped_branches: frozenset[str]) -> frozenset[str]:
    """Return the code lane ids whose created branch for this mission has a recorded work tip.

    ``tipped_branches`` lists every mission's lane branches (one repository-wide
    listing), so each candidate id parsed from a branch is accepted only when
    :func:`~specify_cli.lanes.branch_naming.code_lane_branch_name` composes that
    exact branch back from this manifest's mission slug (compare candidates;
    never trust the parse alone).
    """
    candidates = (parse_lane_id_from_branch(branch) for branch in tipped_branches)
    return frozenset(
        lane_id
        for lane_id in candidates
        if lane_id is not None and lane_id != PLANNING_LANE_ID and code_lane_branch_name(previous.mission_slug, lane_id) in tipped_branches
    )


def build_frozen_membership(
    previous: LanesManifest | None,
    *,
    started: frozenset[str],
    tipped_branches: frozenset[str],
    present_wp_ids: frozenset[str],
    eligible_wp_ids: frozenset[str],
) -> FrozenLaneMembership:
    """Build the frozen membership from already-gathered evidence (pure).

    Args:
        previous: The lane manifest of the prior finalize; ``None`` on a first
            finalize (nothing is frozen).
        started: Work packages :func:`started_wp_ids` reports as started.
        tipped_branches: Lane branches with a recorded work tip
            (``lane_tip.recorded_tip_branches``): the fallback evidence for a
            lane without a history-started member, and the source of the lane
            ids reserved even once the manifest stops listing the lane.
        present_wp_ids: Every work package in the mission's task set.
        eligible_wp_ids: The work packages that are lane inputs (present minus
            the cancellation projection's exclusions).
    """
    if previous is None:
        return FrozenLaneMembership.empty()
    bindings: dict[str, str] = {}
    for lane in previous.lanes:
        members = _lane_started_members(previous, lane.lane_id, tuple(lane.wp_ids), started=started, tipped_branches=tipped_branches)
        bindings.update(dict.fromkeys(members, lane.lane_id))
    return FrozenLaneMembership(
        bindings=bindings,
        retired_wp_ids=present_wp_ids - eligible_wp_ids,
        reserved_ids=_tipped_lane_ids(previous, tipped_branches),
    )


def assert_frozen_membership_honoured(
    manifest: LanesManifest,
    frozen: FrozenLaneMembership | None,
    *,
    topology: MissionTopology = MissionTopology.LANES,
) -> None:
    """Defence in depth at the writer: every bound WP in *manifest* keeps its lane.

    ``compute_lanes(frozen=...)`` already guarantees this, so the check should
    be unreachable; it exists so a future regression in lane computation can
    never persist a manifest that moves started work. ``SINGLE_BRANCH``
    ignores *frozen* (one repository-root lane, nothing to move).

    Raises:
        LaneMembershipFrozenError: a bound WP appears in *manifest* on a lane
            other than its recorded one (reason ``started_lanes_collapsed``).
    """
    if frozen is None or topology is MissionTopology.SINGLE_BRANCH:
        return
    from specify_cli.lanes.compute import LaneMembershipFrozenError  # cycle: compute imports this module

    actual = {wp: lane.lane_id for lane in manifest.lanes for wp in lane.wp_ids}
    moved = {wp: lane_id for wp, lane_id in frozen.bindings.items() if wp in actual and actual[wp] != lane_id}
    if moved:
        raise LaneMembershipFrozenError(tuple(conflict_for("started_lanes_collapsed", {wp: lane_id}) for wp, lane_id in sorted(moved.items())))
