"""Pin the Live Work emission vocabulary to the shared WorkObservation contract.

The literal list below is a *test pin*, not a second authority: it is the
25-kind closed set from the shared contract
(``spec-kitty/spec-kitty-events`` ``contracts/durable-work-observation.md``,
events#55/#56, 10.1.0). If either side drifts — this repo's capture layer
emitting a kind the contract does not define, or the contract renaming one
this layer emits — these tests fail loudly instead of silently forking the
wire.
"""

from __future__ import annotations

import pytest

from specify_cli.live_work.kinds import (
    EMISSION_FAMILIES,
    EMITTED_KINDS,
    FAMILY_BY_EMISSION_KIND,
    WORK_CONTRACT_VERSION,
    WorkEmissionKind,
    payload_id,
)

pytestmark = pytest.mark.fast


#: The shared contract's closed 25-kind set (``work.<kind>.v1`` values),
#: transcribed from contracts/durable-work-observation.md §3.
SHARED_CONTRACT_KINDS: frozenset[str] = frozenset(
    {
        # lifecycle (6)
        "lifecycle.mission_review_captured",
        "lifecycle.mission_review_failed",
        "lifecycle.mission_review_skipped",
        "lifecycle.retrospective_captured",
        "lifecycle.retrospective_failed",
        "lifecycle.retrospective_skipped",
        # session (5)
        "session.started",
        "session.ended",
        "session.delegation_started",
        "session.delegation_ended",
        # action (3)
        "action.tool_invoked",
        "action.file_edited",
        "action.test_executed",
        # narrative (9)
        "narrative.intent_declared",
        "narrative.progress_reported",
        "narrative.question_asked",
        "narrative.question_answered",
        "narrative.decision_recorded",
        "narrative.handoff_performed",
        "narrative.blocker_raised",
        "narrative.blocker_resolved",
        "narrative.next_proposed",
        # message (1)
        "message.peer_sent",
        # coverage (1)
        "coverage.gap_recorded",
    }
)


def test_every_emitted_kind_exists_in_the_shared_contract() -> None:
    emitted = {kind.value for kind in EMITTED_KINDS}
    unknown = emitted - SHARED_CONTRACT_KINDS
    assert not unknown, f"emission set invented kinds the contract does not define: {unknown}"


def test_emission_set_is_the_documented_subset() -> None:
    emitted = {kind.value for kind in EMITTED_KINDS}
    assert emitted == {
        "session.started",
        "session.ended",
        "session.delegation_started",
        "session.delegation_ended",
        "action.tool_invoked",
        "action.file_edited",
        "action.test_executed",
        "lifecycle.retrospective_captured",
        "lifecycle.retrospective_failed",
        "lifecycle.retrospective_skipped",
        "coverage.gap_recorded",
        # #4269's authored surface — the contract's closed narrative family
        # plus the peer reply kind, emitted by live_work.authored only.
        "narrative.intent_declared",
        "narrative.progress_reported",
        "narrative.question_asked",
        "narrative.question_answered",
        "narrative.decision_recorded",
        "narrative.handoff_performed",
        "narrative.blocker_raised",
        "narrative.blocker_resolved",
        "narrative.next_proposed",
        "message.peer_sent",
    }


def test_payload_id_shape_matches_the_contract_lineage() -> None:
    for kind in EMITTED_KINDS:
        assert payload_id(kind) == f"work.{kind.value}.v{WORK_CONTRACT_VERSION}"
    assert WORK_CONTRACT_VERSION == "1"


def test_payload_ids_fit_the_relay_kind_grammar() -> None:
    # The relay's EventArgs `kind`: <=64 chars, [A-Za-z0-9][A-Za-z0-9._@+-]*
    import re

    grammar = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}$")
    for kind in EMITTED_KINDS:
        assert grammar.match(payload_id(kind)), payload_id(kind)


def test_family_map_is_total_and_families_are_contract_subset() -> None:
    assert set(FAMILY_BY_EMISSION_KIND) == set(EMITTED_KINDS)
    assert {"lifecycle", "session", "action", "narrative", "message", "coverage"} >= EMISSION_FAMILIES
    # #4269: the narrative and message families joined the emission set —
    # all six of the contract's families are now represented.
    assert {"session", "action", "lifecycle", "coverage", "narrative", "message"} == EMISSION_FAMILIES


def test_deliberately_absent_kinds_are_named_in_the_module_docstring() -> None:
    from specify_cli.live_work import kinds as kinds_module

    docstring = kinds_module.__doc__ or ""
    for absent in ("mission_review", "#4269", "#4231", "finding"):
        assert absent in docstring, f"module docstring must name the absent surface {absent!r}"
    # The still-absent kinds really are absent.
    with pytest.raises(ValueError):
        WorkEmissionKind("lifecycle.mission_review_captured")
    with pytest.raises(ValueError):
        WorkEmissionKind("session.binding_changed")
    # And the authored kinds really are members now.
    assert WorkEmissionKind("narrative.intent_declared") is WorkEmissionKind.NARRATIVE_INTENT_DECLARED
    assert WorkEmissionKind("message.peer_sent") is WorkEmissionKind.MESSAGE_PEER_SENT
