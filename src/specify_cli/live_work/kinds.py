"""The closed Live Work emission vocabulary (spec-kitty#4268, #4269).

Single owner of the full 25-kind ``WorkObservation`` vocabulary is
``spec_kitty_events.work_observation`` (events#55/#56, package 10.1.0,
contract ``work.<kind>.v1`` lineage ``"1"``). This module is **not** a second
vocabulary: it names only the closed subset this capture layer is able to
*emit* as live relay frames, each carrying the exact payload ID the shared
contract defines, so the relay-side and events-side owners keep one spelling.
The remaining kinds of the shared contract are deliberately absent here:

* the ``lifecycle.mission_review_*`` kinds — no mission-review lifecycle
  seam exists yet (review outcomes are not recorded as lifecycle events);
  that gap is an explicit capability-matrix row, and the reachability work
  is #4231's lane;
* ``session.binding_changed`` — no producer exists in this capture layer
  yet (a repo-bound session binding to a mission later is the lifecycle
  seams' event, and they already publish their own moments);
* kinds whose producers are other seams (factory lineage planning#2270,
  ops invocations at the emitter seam #3929).

The narrative and message families are #4269's authored surface: the nine
``narrative.*`` kinds plus ``message.peer_sent`` are emitted by
:mod:`live_work.authored` (CLI ``spec-kitty zeitgeist send/reply`` and the
MCP ``zeitgeist_send``/``zeitgeist_reply`` tools) — never by a capture hook,
because model private reasoning is never narrative (content-safety rule,
``decisions/HIC-LIVE-WORK-DURABLE-ZEITGEIST-2026-09-13.md``). The glossary's
wider narrative list ("review finding, retrospective learning") exceeds the
shared contract's closed nine-kind narrative family: a "finding" role has no
contract kind, and :mod:`live_work.authored` refuses it as unsupported
vocabulary rather than inventing one the contract does not define.

The emission set is pinned by test against the shared contract's kind list
(``tests/specify_cli/live_work/test_kinds.py``) so a vocabulary drift in
either direction — this module inventing a kind the contract does not
define, or the contract renaming one this module emits — fails loudly
instead of silently forking the wire.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType

__all__ = [
    "EMISSION_FAMILIES",
    "EMITTED_KINDS",
    "FAMILY_BY_EMISSION_KIND",
    "WORK_CONTRACT_VERSION",
    "WorkEmissionKind",
    "payload_id",
]


WORK_CONTRACT_VERSION: str = "1"
"""The work-contract lineage embedded in every payload ID (``work.<kind>.v1``)."""


class WorkEmissionKind(StrEnum):
    """Closed set of Live Work kinds this capture layer can emit."""

    # session family
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    DELEGATION_STARTED = "session.delegation_started"
    DELEGATION_ENDED = "session.delegation_ended"
    # action family
    TOOL_INVOKED = "action.tool_invoked"
    FILE_EDITED = "action.file_edited"
    TEST_EXECUTED = "action.test_executed"
    # lifecycle family (folded in from #4267: retrospective continuity — the
    # retrospective outcome seam records locally but never published live)
    RETROSPECTIVE_CAPTURED = "lifecycle.retrospective_captured"
    RETROSPECTIVE_FAILED = "lifecycle.retrospective_failed"
    RETROSPECTIVE_SKIPPED = "lifecycle.retrospective_skipped"
    # coverage family (honest capture gaps — never a silent drop)
    COVERAGE_GAP = "coverage.gap_recorded"
    # narrative family (#4269's authored surface — the shared contract's
    # closed nine-kind narrative family, emitted only by live_work.authored)
    NARRATIVE_INTENT_DECLARED = "narrative.intent_declared"
    NARRATIVE_PROGRESS_REPORTED = "narrative.progress_reported"
    NARRATIVE_QUESTION_ASKED = "narrative.question_asked"
    NARRATIVE_QUESTION_ANSWERED = "narrative.question_answered"
    NARRATIVE_DECISION_RECORDED = "narrative.decision_recorded"
    NARRATIVE_HANDOFF_PERFORMED = "narrative.handoff_performed"
    NARRATIVE_BLOCKER_RAISED = "narrative.blocker_raised"
    NARRATIVE_BLOCKER_RESOLVED = "narrative.blocker_resolved"
    NARRATIVE_NEXT_PROPOSED = "narrative.next_proposed"
    # message family (#4269: the peer reply thread kind)
    MESSAGE_PEER_SENT = "message.peer_sent"


EMISSION_FAMILIES: frozenset[str] = frozenset({"session", "action", "lifecycle", "coverage", "narrative", "message"})
"""The kind families this capture layer emits — all six of the contract's
families are represented, though not every kind in each (the absent kinds
are named in the module docstring)."""


FAMILY_BY_EMISSION_KIND: MappingProxyType[WorkEmissionKind, str] = MappingProxyType(
    {
        WorkEmissionKind.SESSION_STARTED: "session",
        WorkEmissionKind.SESSION_ENDED: "session",
        WorkEmissionKind.DELEGATION_STARTED: "session",
        WorkEmissionKind.DELEGATION_ENDED: "session",
        WorkEmissionKind.TOOL_INVOKED: "action",
        WorkEmissionKind.FILE_EDITED: "action",
        WorkEmissionKind.TEST_EXECUTED: "action",
        WorkEmissionKind.RETROSPECTIVE_CAPTURED: "lifecycle",
        WorkEmissionKind.RETROSPECTIVE_FAILED: "lifecycle",
        WorkEmissionKind.RETROSPECTIVE_SKIPPED: "lifecycle",
        WorkEmissionKind.COVERAGE_GAP: "coverage",
        WorkEmissionKind.NARRATIVE_INTENT_DECLARED: "narrative",
        WorkEmissionKind.NARRATIVE_PROGRESS_REPORTED: "narrative",
        WorkEmissionKind.NARRATIVE_QUESTION_ASKED: "narrative",
        WorkEmissionKind.NARRATIVE_QUESTION_ANSWERED: "narrative",
        WorkEmissionKind.NARRATIVE_DECISION_RECORDED: "narrative",
        WorkEmissionKind.NARRATIVE_HANDOFF_PERFORMED: "narrative",
        WorkEmissionKind.NARRATIVE_BLOCKER_RAISED: "narrative",
        WorkEmissionKind.NARRATIVE_BLOCKER_RESOLVED: "narrative",
        WorkEmissionKind.NARRATIVE_NEXT_PROPOSED: "narrative",
        WorkEmissionKind.MESSAGE_PEER_SENT: "message",
    }
)
"""Total mapping: every emission kind to its family."""

EMITTED_KINDS: frozenset[WorkEmissionKind] = frozenset(WorkEmissionKind)
"""The closed emission set — every member of :class:`WorkEmissionKind`."""


def payload_id(kind: WorkEmissionKind) -> str:
    """The relay wire ``kind`` for one emission kind: ``work.<kind>.v<lineage>``."""
    return f"work.{kind.value}.v{WORK_CONTRACT_VERSION}"
