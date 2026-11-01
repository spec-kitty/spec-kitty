"""Translate generator-shape proposals into the typed proposals ``synthesize`` applies (#6385).

Why this module exists
----------------------
``spec-kitty retrospect create`` writes a *generator-shape* record
(:class:`~specify_cli.retrospective.schema.GenRetrospectiveRecord`), while
``spec-kitty agent retrospect synthesize`` applies the *nested* Pydantic
:class:`~specify_cli.retrospective.schema.Proposal`, whose payload is a discriminated union
(:data:`~specify_cli.retrospective.schema.ProposalPayload`). Before #6385 the two never met: the
command dropped every generator-shape proposal on the floor and reported an empty batch as a
successful dry-run.

This module is the missing translation step, and it is deliberately the *only* one:

* the payload is validated by the nested record's existing union — never a second schema;
* the output is the nested :class:`Proposal` itself, so ``apply_proposals`` needs no new path;
* nothing is guessed from free text: a proposal is translatable only when it carries a
  structurally valid ``payload`` whose ``kind`` agrees with the verb in ``suggested_action``;
* every proposal that cannot be translated comes back with a **named reason**, because a silently
  dropped proposal is the defect this module exists to remove.

Deciding *which* payload kind a finding maps to — i.e. generating payloads inside
``generator._build_findings`` — is #3947 and stays there. This module only consumes what a record
already declares.

Determinism
-----------
Running ``synthesize`` twice on the same record must not double-apply or rename anything, so every
translated proposal id is derived from ``(record.mission_id, generator proposal id)`` rather than
from a clock or a counter. The derived value is a legal ULID (``ProposalId`` is ULID-shaped while
a generator proposal id is ``p-001``) built from the mission's own ULID with its last three
Crockford characters replaced by a digest of the generator id. A collision is refused, never
merged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from specify_cli.retrospective.schema import (
    ActorRef,
    EventId,
    GenProposal,
    GenRetrospectiveRecord,
    Proposal,
    ProposalId,
    ProposalPayload,
    ProposalProvenance,
    ProposalState,
)

__all__ = [
    "GeneratorProposalTranslation",
    "translate_generator_proposals",
]

#: The verb of ``suggested_action`` that names a typed payload kind. A proposal whose verb is one
#: of these but whose ``payload.kind`` disagrees is a record bug worth naming, not a guess to make.
TYPED_PROPOSAL_KINDS: frozenset[str] = frozenset(
    {
        "synthesize_directive",
        "synthesize_tactic",
        "synthesize_procedure",
        "rewire_edge",
        "add_edge",
        "remove_edge",
        "add_glossary_term",
        "update_glossary_term",
        "flag_not_helpful",
    }
)

#: Crockford base32 — the ULID alphabet (no I, L, O, U).
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_PAYLOAD_ADAPTER: TypeAdapter[Any] = TypeAdapter(ProposalPayload)
_PROPOSAL_ID_ADAPTER: TypeAdapter[Any] = TypeAdapter(ProposalId)
_EVENT_ID_ADAPTER: TypeAdapter[Any] = TypeAdapter(EventId)

_MAX_RATIONALE_CHARS = 2000

# Reason text for the shape every pre-#6385 record has. It names the remedy and the owner of the
# generation half, so an operator is never left with an unexplained empty batch.
NO_PAYLOAD_REASON = (
    "no structured payload: a generator-shape proposal is plannable only when it carries a "
    "`payload` block validated by the nested proposal schema (see #6385); generating payloads "
    "from findings is #3947"
)


@dataclass(frozen=True)
class _UntranslatableProposal:
    """A generator-shape proposal that could not become a typed proposal, and why."""

    proposal_id: str
    reason: str


@dataclass(frozen=True)
class GeneratorProposalTranslation:
    """Result of translating one generator-shape record.

    Attributes:
        proposals: Typed proposals ready for ``apply_proposals``, in record order.
        untranslatable: Every proposal that could not be translated, with its reason. Never
            silently dropped: callers must surface these.
        translated_ids: Generator proposal id → derived typed proposal id, for diagnostics and
            for ``--proposal-id`` reporting.
    """

    proposals: list[Proposal]
    untranslatable: list[_UntranslatableProposal]
    translated_ids: dict[str, str]


def _derive_proposal_id(mission_id: str, generator_proposal_id: str) -> str:
    """Derive a stable, ULID-shaped proposal id for a generator-shape proposal.

    The generator shape numbers its proposals ``p-001``; :data:`ProposalId` is ULID-shaped, so an
    id has to be derived. It is derived deterministically from the source mission id and the
    generator proposal id — never from a clock or a counter — so re-running ``synthesize`` on the
    same record produces the same ids and cannot double-apply.

    Args:
        mission_id: The source mission's ULID (26 Crockford characters).
        generator_proposal_id: The generator-shape proposal id, e.g. ``p-001``.

    Returns:
        A 26-character ULID-shaped id: the mission id with its last three characters replaced by
        a digest of the generator proposal id.

    Raises:
        ValueError: when ``mission_id`` is not itself a ULID, i.e. the record cannot address a
            legal :data:`ProposalId`.
    """
    if not _is_adapter_value(_PROPOSAL_ID_ADAPTER, mission_id):
        raise ValueError(f"mission_id {mission_id!r} is not a ULID; cannot derive a proposal id")
    # An id-derivation digest, not a content hash of the charter layer: the purpose is a
    # deterministic 26-character ULID suffix, so routing it through charter.hasher's content
    # hasher would tie proposal ids to an unrelated hashing policy.
    digest = hashlib.sha256(  # noqa: TID251
        f"{mission_id}\x00{generator_proposal_id}".encode()
    ).digest()
    value = int.from_bytes(digest[:8], "big")
    suffix = "".join(_CROCKFORD_ALPHABET[(value >> (5 * shift)) & 31] for shift in (2, 1, 0))
    return f"{mission_id[:23]}{suffix}"


def translate_generator_proposals(record: GenRetrospectiveRecord, *, actor: ActorRef) -> GeneratorProposalTranslation:
    """Translate every proposal of a generator-shape record into the typed proposal shape.

    Pure: no filesystem, no repo root, no clock, no logging. The caller supplies ``actor`` for
    proposal provenance.

    Args:
        record: The generator-shape record read from ``retrospective.yaml``.
        actor: Who is running synthesis; recorded as the translated proposals' ``authored_by``.

    Returns:
        A :class:`GeneratorProposalTranslation` with the typed proposals, the untranslatable ones
        (each with a reason), and the id mapping.
    """
    translated: list[Proposal] = []
    untranslatable: list[_UntranslatableProposal] = []
    translated_ids: dict[str, str] = {}
    used_ids: set[str] = set()

    for proposal in record.proposals:
        reason = _untranslatable_reason(proposal)
        if reason is not None:
            untranslatable.append(_UntranslatableProposal(proposal.id, reason))
            continue

        assert proposal.payload is not None  # narrowed by _untranslatable_reason
        try:
            typed_payload = _PAYLOAD_ADAPTER.validate_python(proposal.payload)
        except ValidationError as exc:  # defensive: read_gen_record already validated
            untranslatable.append(_UntranslatableProposal(proposal.id, _first_validation_error(exc)))
            continue

        try:
            proposal_id = _derive_proposal_id(record.mission_id, proposal.id)
        except ValueError as exc:
            untranslatable.append(_UntranslatableProposal(proposal.id, str(exc)))
            continue

        if proposal_id in used_ids:
            owner = next(gen_id for gen_id, typed_id in translated_ids.items() if typed_id == proposal_id)
            untranslatable.append(
                _UntranslatableProposal(
                    proposal.id,
                    f"derived proposal id collides with the proposal derived from {owner!r}; refused rather than merged",
                )
            )
            continue

        try:
            typed = Proposal(
                id=proposal_id,
                kind=typed_payload.kind,
                payload=typed_payload,
                rationale=proposal.summary[:_MAX_RATIONALE_CHARS],
                # `auto_applicable` is a hand-editable YAML boolean (generation always writes
                # False), not a recorded accept decision, so a translated proposal is always
                # pending: it joins no default batch and is applied only when named with
                # `--proposal-id` together with `--apply`.
                state=ProposalState(status="pending"),
                provenance=ProposalProvenance(
                    source_mission_id=record.mission_id,
                    source_evidence_event_ids=_evidence_event_ids(record, proposal),
                    authored_by=actor,
                ),
            )
        except ValidationError as exc:
            untranslatable.append(_UntranslatableProposal(proposal.id, _first_validation_error(exc)))
            continue

        used_ids.add(proposal_id)
        translated_ids[proposal.id] = proposal_id
        translated.append(typed)

    return GeneratorProposalTranslation(
        proposals=translated,
        untranslatable=untranslatable,
        translated_ids=translated_ids,
    )


def _untranslatable_reason(proposal: GenProposal) -> str | None:
    """Return why ``proposal`` cannot be translated, or ``None`` when it can.

    Checked in report-priority order: a missing payload is the pre-#6385 shape and gets the
    remedy-bearing message; a verb/payload disagreement is a record bug that deserves its own
    wording.
    """
    if proposal.payload is None:
        return NO_PAYLOAD_REASON
    verb = proposal.suggested_action.split(":", 1)[0].strip().lower()
    payload_kind = proposal.payload.get("kind")
    if verb in TYPED_PROPOSAL_KINDS and payload_kind != verb:
        return f"payload.kind {payload_kind!r} disagrees with the typed verb {verb!r} in suggested_action; the record must declare one action"
    return None


def _evidence_event_ids(record: GenRetrospectiveRecord, proposal: GenProposal) -> list[str]:
    """Return the proposal's event-id evidence, limited to ids that are really event ids.

    The generator shape points at files and event ranges; only the ULIDs inside an
    ``event_range`` reference are event ids. Anything else contributes nothing: an empty list is a
    legal "no evidence to check" claim for ``apply_proposals``' staleness pass, while an invented
    id would make a proposal look stale (or, worse, resolve by accident).
    """
    by_id = {ref.id: ref for ref in record.evidence_refs}
    event_ids: list[str] = []
    for ref_id in proposal.evidence_refs:
        ref = by_id.get(ref_id)
        if ref is None or ref.kind != "event_range" or not ref.range:
            continue
        for candidate in ref.range.split(".."):
            if _is_adapter_value(_EVENT_ID_ADAPTER, candidate) and candidate not in event_ids:
                event_ids.append(candidate)
    return event_ids


def _is_adapter_value(adapter: TypeAdapter[Any], value: object) -> bool:
    try:
        adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def _first_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    first = errors[0] if errors else None
    if first is None:
        return "payload is invalid"
    location = ".".join(str(part) for part in first["loc"]) or "payload"
    return f"{location}: {first['msg']}"
