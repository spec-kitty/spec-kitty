"""Translation from generator-shape proposals to the typed proposals synthesize applies (#6385).

The rules under test are the ones in
``kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/plan.md`` ("Translation contract"):

===== ============================================== ==========================================
Rule  Input                                          Outcome
===== ============================================== ==========================================
T1    no ``payload``                                 untranslatable, remedy-bearing reason
T2    ``payload`` invalid under the nested union     untranslatable, named validation error
T3    ``payload.kind`` disagrees with the verb       untranslatable, names both
T4    valid payload                                  typed ``Proposal`` (id, state, provenance)
T5    two proposals derive the same id               second is refused, never merged
T6    no resolvable evidence event ids               empty evidence list, no invented id
===== ============================================== ==========================================
"""

from __future__ import annotations

import pytest

from specify_cli.retrospective.generator_proposals import (
    NO_PAYLOAD_REASON,
    TYPED_PROPOSAL_KINDS,
    _derive_proposal_id,
    translate_generator_proposals,
)
from specify_cli.retrospective.schema import (
    ActorRef,
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01M68ZKX1DCY9S7NM80G0YQFKY"  # the mission's own ULID
EVENT_ID = "01M68ZKX1DCY9S7NM80G0YQFKK"
ACTOR = ActorRef(kind="agent", id="pi")

GLOSSARY_PAYLOAD = {
    "kind": "add_glossary_term",
    "term_key": "generator-shape-record",
    "definition": "The dataclass record shape `retrospect create` writes.",
    "definition_hash": "sha256:aaaa",
    "related_terms": [],
}


def _record(proposals: list[GenProposal], evidence: list[GenEvidenceRef] | None = None) -> GenRetrospectiveRecord:
    return GenRetrospectiveRecord(
        schema_version=1,
        mission_id=MISSION_ID,
        mission_slug="retrospect-synthesize-generator-proposals-01M68ZKX",
        mission_type="software-dev",
        target_branch="issue-6385",
        created_at="2026-10-31T12:00:00+00:00",
        created_by=GenActor(kind="human", id="cli"),
        provenance=GenProvenance(kind="explicit_create", invoked_at="2026-10-31T12:00:00+00:00", policy_resolved_from={}),
        findings_status="has_findings",
        not_helpful=[GenFinding(id="n-001", category="process", summary="lane bounce", evidence_refs=["e-001"])],
        proposals=proposals,
        evidence_refs=evidence if evidence is not None else [GenEvidenceRef(id="e-001", kind="event_range", range=EVENT_ID)],
        generator_version="1.0",
    )


def _proposal(
    *,
    pid: str = "p-001",
    payload: dict[str, object] | None = GLOSSARY_PAYLOAD,
    verb: str = "add_glossary_term",
    auto_applicable: bool = False,
    evidence_refs: list[str] | None = None,
) -> GenProposal:
    return GenProposal(
        id=pid,
        category="glossary",
        risk_class="low" if auto_applicable else "structural",
        summary="  add a glossary term  " + "x" * 50,
        evidence_refs=["e-001"] if evidence_refs is None else evidence_refs,
        suggested_action=f"{verb}: generator-shape-record",
        auto_applicable=auto_applicable,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# T4 — a valid payload becomes a typed proposal
# ---------------------------------------------------------------------------


def test_valid_payload_becomes_typed_proposal() -> None:
    result = translate_generator_proposals(_record([_proposal()]), actor=ACTOR)

    assert result.untranslatable == []
    assert len(result.proposals) == 1
    typed = result.proposals[0]
    assert typed.kind == "add_glossary_term"
    assert typed.payload.term_key == "generator-shape-record"
    assert typed.state.status == "pending"
    assert typed.provenance.authored_by == ACTOR
    assert typed.provenance.source_mission_id == MISSION_ID
    assert result.translated_ids == {"p-001": typed.id}


def test_auto_applicable_becomes_accepted() -> None:
    """`auto_applicable` is the record's own statement that no further approval is needed."""
    result = translate_generator_proposals(_record([_proposal(auto_applicable=True)]), actor=ACTOR)

    assert result.proposals[0].state.status == "accepted"


def test_rationale_is_the_summary_capped_at_2000_chars() -> None:
    long_summary = "y" * 2500
    proposal = _proposal()
    proposal = GenProposal(**{**proposal.__dict__, "summary": long_summary})

    result = translate_generator_proposals(_record([proposal]), actor=ACTOR)

    assert len(result.proposals[0].rationale) == 2000


# ---------------------------------------------------------------------------
# T1 — no payload: the pre-#6385 shape, reported with the remedy
# ---------------------------------------------------------------------------


def test_missing_payload_is_untranslatable_with_remedy() -> None:
    result = translate_generator_proposals(_record([_proposal(payload=None)]), actor=ACTOR)

    assert result.proposals == []
    assert len(result.untranslatable) == 1
    entry = result.untranslatable[0]
    assert entry.proposal_id == "p-001"
    assert entry.reason == NO_PAYLOAD_REASON
    assert "#3947" in entry.reason


def test_untranslatable_and_translatable_coexist() -> None:
    """Positive control: the probe sees a translated proposal in the same record."""
    record = _record([_proposal(pid="p-001", payload=None), _proposal(pid="p-002")])

    result = translate_generator_proposals(record, actor=ACTOR)

    assert [p.kind for p in result.proposals] == ["add_glossary_term"]
    assert [u.proposal_id for u in result.untranslatable] == ["p-001"]


# ---------------------------------------------------------------------------
# T2 — invalid payloads
# ---------------------------------------------------------------------------


def test_invalid_payload_is_named() -> None:
    bad = {"kind": "synthesize_directive", "artifact_id": "DIRECTIVE_099", "body": "x"}
    result = translate_generator_proposals(_record([_proposal(payload=bad, verb="synthesize_directive")]), actor=ACTOR)

    assert result.proposals == []
    reason = result.untranslatable[0].reason
    assert "body_hash" in reason
    assert "synthesize_directive" in reason


# ---------------------------------------------------------------------------
# T3 — verb / payload disagreement
# ---------------------------------------------------------------------------


def test_payload_kind_disagreeing_with_verb_is_named() -> None:
    result = translate_generator_proposals(_record([_proposal(verb="synthesize_tactic")]), actor=ACTOR)

    assert result.proposals == []
    reason = result.untranslatable[0].reason
    assert "add_glossary_term" in reason and "synthesize_tactic" in reason


def test_free_text_verb_does_not_block_a_valid_payload() -> None:
    """A suggestion phrased in prose still translates: the payload is the authority."""
    result = translate_generator_proposals(_record([_proposal(verb="make_the_glossary_clearer")]), actor=ACTOR)

    assert len(result.proposals) == 1


# ---------------------------------------------------------------------------
# T5 — deterministic, collision-checked ids
# ---------------------------------------------------------------------------


def test_ids_are_stable_across_runs() -> None:
    record = _record([_proposal(pid="p-001"), _proposal(pid="p-002", payload=dict(GLOSSARY_PAYLOAD, term_key="second"))])

    first = translate_generator_proposals(record, actor=ACTOR)
    second = translate_generator_proposals(record, actor=ACTOR)

    assert [p.id for p in first.proposals] == [p.id for p in second.proposals]
    assert first.translated_ids == second.translated_ids
    assert len({p.id for p in first.proposals}) == 2


def test_derived_id_is_ulid_shaped_and_distinct() -> None:
    one = _derive_proposal_id(MISSION_ID, "p-001")
    two = _derive_proposal_id(MISSION_ID, "p-002")

    assert len(one) == 26
    assert one != two
    assert one[:23] == MISSION_ID[:23]


def test_derived_id_requires_a_ulid_mission_id() -> None:
    with pytest.raises(ValueError, match="not a ULID"):
        _derive_proposal_id("not-a-ulid", "p-001")


def test_non_ulid_mission_id_makes_proposals_untranslatable() -> None:
    record = _record([_proposal()])
    record = GenRetrospectiveRecord(**{**record.__dict__, "mission_id": "mission-1"})

    result = translate_generator_proposals(record, actor=ACTOR)

    assert result.proposals == []
    assert "not a ULID" in result.untranslatable[0].reason


def test_id_collision_is_refused_not_merged() -> None:
    """Two generator ids with the same derived id: the second is refused, never merged."""
    record = _record([_proposal(pid="p-001")])
    # Simulate a collision by making both proposals derive the same id: patch the second's
    # id to a value whose digest we force equal by reusing the first proposal object.
    collided = _record([_proposal(pid="p-001"), _proposal(pid="p-001")])

    result = translate_generator_proposals(collided, actor=ACTOR)

    assert len(result.proposals) == 1
    assert len(result.untranslatable) == 1
    assert "collides" in result.untranslatable[0].reason
    assert record.proposals[0].id == "p-001"


# ---------------------------------------------------------------------------
# T6 — evidence: real event ids only, never invented
# ---------------------------------------------------------------------------


def test_evidence_event_ids_are_mined_from_event_ranges() -> None:
    result = translate_generator_proposals(_record([_proposal()]), actor=ACTOR)

    assert result.proposals[0].provenance.source_evidence_event_ids == [EVENT_ID]


def test_event_range_with_two_ids_is_split() -> None:
    other = "01M68ZKX1DCY9S7NM80G0YQFKM"
    evidence = [GenEvidenceRef(id="e-001", kind="event_range", range=f"{EVENT_ID}..{other}")]

    result = translate_generator_proposals(_record([_proposal()], evidence=evidence), actor=ACTOR)

    assert result.proposals[0].provenance.source_evidence_event_ids == [EVENT_ID, other]


def test_finding_ids_are_never_turned_into_event_ids() -> None:
    """An evidence ref of kind `file` contributes nothing: no invented event id, no stale claim."""
    evidence = [GenEvidenceRef(id="e-001", kind="file", path="spec.md")]

    result = translate_generator_proposals(_record([_proposal()], evidence=evidence), actor=ACTOR)

    assert result.proposals[0].provenance.source_evidence_event_ids == []


def test_unknown_evidence_ref_is_ignored() -> None:
    result = translate_generator_proposals(_record([_proposal(evidence_refs=["e-999"])]), actor=ACTOR)

    assert result.proposals[0].provenance.source_evidence_event_ids == []


# ---------------------------------------------------------------------------
# Sanity — the typed kinds set matches the union's discriminators
# ---------------------------------------------------------------------------


def test_typed_kind_set_covers_the_union() -> None:
    from typing import get_args

    from specify_cli.retrospective.schema import ProposalPayload

    union = get_args(ProposalPayload)[0]
    discriminators = {get_args(member.model_fields["kind"].annotation)[0] for member in get_args(union)}

    assert discriminators == set(TYPED_PROPOSAL_KINDS)
