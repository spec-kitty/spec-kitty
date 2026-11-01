# Contract: the generator-shape proposal payload seam (#6385)

**Status**: delivered by this mission.
**Machine authority**: `src/specify_cli/retrospective/schema.py`
(`GenProposal.payload`, `ProposalPayload`, `Proposal`) and
`src/specify_cli/retrospective/generator_proposals.py`
(`translate_generator_proposals`).
**On-disk record**: the generator shape's original contract,
`kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json`, is a
frozen archive artifact and is **not** edited (the `kitty-specs/` archive root is byte-preserved, and
`tests/architectural/test_archive_root_byte_identical.py` enforces it). The optional `payload` is an
additive field whose authority is the union above; it is documented in
`docs/api/retrospective-schema.md`.

## The two record shapes

| | Nested record (`schema.RetrospectiveRecord`) | Generator record (`schema.GenRetrospectiveRecord`) |
|---|---|---|
| Written by | runtime / hand-authored | `spec-kitty retrospect create`, `backfill` |
| `proposals[].id` | ULID (`ProposalId`) | `p-001`, `p-002`, … |
| Action | `kind` + discriminated `payload` | free-text `suggested_action` (+ optional `payload`) |
| Applied by | `apply_proposals` | `apply_proposals`, after translation |

## Translation contract

`translate_generator_proposals(record, *, actor)` is pure and returns
`GeneratorProposalTranslation(proposals, untranslatable, translated_ids)`.

| Rule | Input | Outcome |
|---|---|---|
| T1 | no `payload` | untranslatable; reason names the missing payload block and #3947 |
| T2 | `payload` fails `ProposalPayload` validation | untranslatable; reason is the first validation error |
| T3 | `payload.kind` disagrees with a typed verb in `suggested_action` | untranslatable; both named |
| T4 | valid payload | typed `Proposal`; `kind = payload.kind`; `rationale = summary[:2000]`; `state` = `accepted` iff `auto_applicable`, else `pending`; provenance = source mission ULID + event-id ULIDs mined from the cited `event_range` evidence + `authored_by = actor` |
| T5 | two proposals derive one id | the later one is untranslatable ("collides"); never merged |
| T6 | no resolvable event-id evidence | `source_evidence_event_ids = []` (no staleness claim); event ids are never invented |

**Id derivation**: `mission_id[:23]` + three Crockford characters of
`sha256(mission_id + NUL + generator_proposal_id)`. Deterministic across runs, legal as a
`ProposalId`, distinct per generator id.

## Reporting contract

A `synthesize` run on a generator-shape record adds a top-level `diagnostics`
object (sibling of `status`/`outcome`, never inside `result`) and a matching Rich warning:

```json
{"record_schema": "generator",
 "findings": {"helped": 0, "not_helpful": 19, "gaps": 2, "proposals": 0},
 "proposals_translated": 0, "proposals_planned": 0,
 "untranslatable": [{"proposal_id": "p-001", "reason": "..."}],
 "next_action": "..."}
```

Nested-schema envelopes are unchanged (no `diagnostics` key). Exit codes are unchanged: a valid
dry-run exits 0 even when the batch is empty; the diagnostic, not an error code, carries the
signal.

## Out of scope (owned elsewhere)

Deciding which payload kind a finding maps to, and emitting payloads from `_build_findings`, is
issue #3947. `generator.py` is untouched by this mission (constraint C-001).
